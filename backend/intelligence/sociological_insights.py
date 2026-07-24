"""
SHERLOCK — Sociological Crime Insights (Agent 2 workstream).

Builds on the Sprint B4 `SociologicalIntelligenceAgent` (which only
computed a single accused-demographics tabulation). This module is the
deterministic analytics engine behind both that agent and the new
platform-wide `/analytics/sociological` dashboard — computation lives
here, presentation (agent findings, API JSON, frontend charts) is built
on top of it, never the other way around.

Scope, honestly (same convention as backend/intelligence/board_intelligence.py):
  - demographics (accused + victims)      — real, direct tabulation of
                                             Person.gender/age/occupation
  - occupation-crime correlation          — real, the only socio-economic
                                             attribute the schema records
  - repeat_offender_communities           — real: count of distinct FIRs
                                             per accused person from the
                                             Accused table itself (not the
                                             `Accused.repeat_offender` flag,
                                             which the AER synthetic-data
                                             generator never populates —
                                             see generate_synthetic_data.py;
                                             only the legacy
                                             generate_demo_data.py script
                                             does, via mark_repeat_offenders().
                                             Computing directly from FIR
                                             counts is generator-independent)
  - family_crime_links                    — real: PersonAssociation rows
                                             with relation_type=family where
                                             both persons are also Accused
  - gang_indicators                       — real: OrganizationMembership
                                             joined to Organization where
                                             org_type=gang, restricted to
                                             accused persons. This reflects
                                             recorded membership, not an
                                             inferred/predicted affiliation
  - community_vulnerability               — real but a narrow proxy: crime
                                             count per district. NOT a
                                             validated socio-economic
                                             vulnerability index (that needs
                                             external census/poverty data —
                                             see economic_stress_analysis)
  - correlation_matrix                    — real cross-tabulations
                                             (gender x crime type, age
                                             bracket x crime type) from
                                             direct joins, not estimated
  - income_group / employment_status /
    housing_type / economic_category      — UNAVAILABLE: no such fields
                                             anywhere in the AER schema.
                                             Reported as gaps, not guessed
  - urbanization / migration /
    economic_stress / education           — UNAVAILABLE: no urban/rural
                                             classification on Location, no
                                             migration/origin or education
                                             field on Person, no external
                                             economic-indicator dataset.
                                             Each has a real extension-point
                                             method below (accepts an
                                             optional external lookup dict)
                                             so wiring in a real dataset
                                             later needs zero pipeline
                                             changes — but absent that
                                             input, nothing is fabricated;
                                             each returns `available: False`
                                             with the specific gap named
"""

from __future__ import annotations

import os
import logging
from collections import Counter, defaultdict

from sqlalchemy import func

from backend.database.models import (
    Person, Accused, Victim, FIR, Crime, Location,
    PersonAssociation, Organization, OrganizationMembership,
)
from backend.database.models.enums import RelationType, OrganizationType

logger = logging.getLogger(__name__)

AGE_BRACKETS = [(0, 18, "under 18"), (18, 25, "18-24"), (25, 35, "25-34"), (35, 50, "35-49"), (50, 200, "50+")]

UNAVAILABLE_DIMENSIONS = {
    "income_group": (
        "No income/income_group field on Person or anywhere in the schema. "
        "Extension point: pass an external {person_id: income_bracket} lookup into a future "
        "socioeconomic enrichment pass — no pipeline change needed beyond that input."
    ),
    "employment_status": (
        "Person.occupation is recorded, but employment STATUS (employed/unemployed/"
        "underemployed) is not a separate field and cannot be reliably derived from "
        "occupation text without fabricating a mapping."
    ),
    "housing_type": "No housing_type field on Person or Location anywhere in the schema.",
    "economic_category": "No economic_category classification exists in the schema.",
    "urbanization": (
        "Location has name/district/state/lat-lng only — no urban/rural/semi-urban "
        "classification field. urbanization_analysis() accepts an optional "
        "{district: 'urban'|'rural'|'semi_urban'} lookup (e.g. a Census town/village list); "
        "wiring that in produces real crime-by-urbanization-tier numbers with no other change."
    ),
    "migration": (
        "No migration/origin/native-district field on Person. migration_analysis() accepts "
        "an optional {person_id: origin_district} lookup."
    ),
    "economic_stress": (
        "No district-level economic-indicator table (unemployment rate, poverty rate, etc.) "
        "exists. economic_stress_analysis() accepts an optional {district: {indicator: value}} "
        "lookup and will correlate it against this service's own district crime-density numbers."
    ),
    "education": (
        "No education field on Person. education_analysis() accepts an optional "
        "{person_id: education_level} lookup."
    ),
}


def _bracket(age: int) -> str:
    for lo, hi, label in AGE_BRACKETS:
        if lo <= age < hi:
            return label
    return "unknown"


class SociologicalInsightsService:
    """Deterministic analytics. `accused_person_ids=None` means
    "everyone currently on record as accused" (the platform-wide
    dashboard); a list scopes every computation to one investigation."""

    def __init__(self, session):
        self.session = session

    # -- public entry points --------------------------------------------

    def build_dashboard(self, accused_person_ids: list[int] | None = None) -> dict:
        accused_persons = self._accused_persons(accused_person_ids)
        victim_persons = self._victim_persons(accused_person_ids)

        return {
            "scope": {
                "accused_sample_size": len(accused_persons),
                "victim_sample_size": len(victim_persons),
                "scoped_to_investigation": bool(accused_person_ids),
            },
            "demographics": {
                "accused": self._demographic_breakdown(accused_persons),
                "victims": self._demographic_breakdown(victim_persons),
            },
            "socioeconomic_analysis": self._socioeconomic(accused_persons),
            "social_risk_factors": self._social_risk_factors(accused_person_ids),
            "urbanization_analysis": self.urbanization_analysis(),
            "migration_analysis": self.migration_analysis(),
            "economic_stress_analysis": self.economic_stress_analysis(),
            "education_analysis": self.education_analysis(),
            "correlation_matrix": self._correlation_matrix(accused_person_ids),
            "data_availability": self._data_availability(),
        }

    def build_report(self, accused_person_ids: list[int] | None = None, query: str | None = None) -> dict:
        """The Sociological Report Generator: Executive Summary -> Key
        Findings -> Risk Factors -> Evidence -> Recommendations ->
        Confidence -> Supporting Data. Everything but the executive
        summary's prose is composed directly from `build_dashboard()`'s
        numbers; the LLM (when available) is only asked to phrase the
        summary, never to add facts. See _executive_summary()."""
        dashboard = self.build_dashboard(accused_person_ids)

        key_findings = self._key_findings(dashboard)
        risk_factors = self._risk_factor_summaries(dashboard)
        evidence = self._evidence_trail(dashboard)
        recommendations = self._recommendations(dashboard)
        confidence = self._confidence(dashboard)
        executive_summary = self._executive_summary(dashboard, key_findings, query)

        return {
            "executive_summary": executive_summary,
            "key_findings": key_findings,
            "risk_factors": risk_factors,
            "evidence": evidence,
            "recommendations": recommendations,
            "confidence": confidence,
            "supporting_data": dashboard,
        }

    # -- person scoping ----------------------------------------------------

    def _accused_persons(self, accused_person_ids: list[int] | None) -> list[Person]:
        q = self.session.query(Person).join(Accused, Accused.person_id == Person.id)
        if accused_person_ids:
            q = q.filter(Person.id.in_(accused_person_ids))
        return q.distinct().all()

    def _victim_persons(self, accused_person_ids: list[int] | None) -> list[Person]:
        q = self.session.query(Person).join(Victim, Victim.person_id == Person.id)
        if accused_person_ids:
            # Victims of the same FIRs the scoped accused persons appear
            # in — not the whole victims table, to match the
            # investigation's actual scope.
            fir_ids = [
                row[0] for row in
                self.session.query(Accused.fir_id).filter(Accused.person_id.in_(accused_person_ids)).distinct()
            ]
            if not fir_ids:
                return []
            q = q.filter(Victim.fir_id.in_(fir_ids))
        return q.distinct().all()

    def _all_accused_ids(self) -> set[int]:
        return {row[0] for row in self.session.query(Accused.person_id).distinct().all()}

    # -- demographics --------------------------------------------------

    def _demographic_breakdown(self, persons: list[Person]) -> dict:
        if not persons:
            return {
                "sample_size": 0,
                "gender_distribution": {},
                "age_bracket_distribution": {},
                "occupation_distribution": {},
            }
        gender_counts = Counter(p.gender.value for p in persons)
        occupation_counts = Counter(p.occupation or "unspecified" for p in persons)
        bracket_counts = Counter(_bracket(p.age) for p in persons)
        return {
            "sample_size": len(persons),
            "gender_distribution": dict(gender_counts),
            "age_bracket_distribution": dict(bracket_counts),
            "occupation_distribution": dict(occupation_counts.most_common(10)),
        }

    # -- socio-economic (occupation only — the rest are schema gaps) ----

    def _socioeconomic(self, accused_persons: list[Person]) -> dict:
        occ_crime: dict = {}
        if accused_persons:
            person_ids = [p.id for p in accused_persons]
            rows = (
                self.session.query(Person.occupation, Crime.type)
                .join(Accused, Accused.person_id == Person.id)
                .join(FIR, FIR.id == Accused.fir_id)
                .join(Crime, Crime.id == FIR.crime_id)
                .filter(Person.id.in_(person_ids))
                .all()
            )
            grouped = defaultdict(Counter)
            for occupation, ctype in rows:
                grouped[occupation or "unspecified"][ctype.value] += 1
            occ_crime = {occ: dict(counter) for occ, counter in grouped.items()}

        return {
            "occupation_crime_correlation": occ_crime,
            "note": (
                "Occupation is the only socio-economic attribute recorded on Person. Income "
                "group, employment status, housing type, and economic category are not in the "
                "current schema — see 'unavailable' below rather than an inferred estimate."
            ),
            "unavailable": {
                k: UNAVAILABLE_DIMENSIONS[k]
                for k in ("income_group", "employment_status", "housing_type", "economic_category")
            },
        }

    # -- social risk factors ---------------------------------------------

    def _social_risk_factors(self, accused_person_ids: list[int] | None) -> dict:
        # Repeat offenders: persons with >=2 distinct FIR accused-records.
        q = self.session.query(Accused.person_id, func.count(func.distinct(Accused.fir_id))) \
            .group_by(Accused.person_id)
        if accused_person_ids:
            q = q.filter(Accused.person_id.in_(accused_person_ids))
        repeat_offender_ids = sorted(pid for pid, fir_count in q.all() if fir_count >= 2)

        # Family crime links: relation_type=family where both ends are accused.
        accused_ids_all = self._all_accused_ids()
        scope_set = set(accused_person_ids) if accused_person_ids else None
        family_links = []
        for assoc in self.session.query(PersonAssociation).filter(PersonAssociation.relation_type == RelationType.FAMILY):
            if assoc.person_a_id not in accused_ids_all or assoc.person_b_id not in accused_ids_all:
                continue
            if scope_set and not ({assoc.person_a_id, assoc.person_b_id} & scope_set):
                continue
            family_links.append({
                "person_a": assoc.person_a_id, "person_b": assoc.person_b_id, "strength": assoc.strength,
            })

        # Gang indicators: recorded OrganizationMembership in a org_type=gang org.
        gang_rows = (
            self.session.query(Person.id, Organization.name)
            .join(OrganizationMembership, OrganizationMembership.person_id == Person.id)
            .join(Organization, Organization.id == OrganizationMembership.organization_id)
            .filter(Organization.org_type == OrganizationType.GANG)
            .filter(Person.id.in_(accused_ids_all))
            .all()
        )
        if scope_set:
            gang_rows = [r for r in gang_rows if r[0] in scope_set]
        gang_person_ids = sorted({pid for pid, _ in gang_rows})
        gang_orgs = Counter(name for _, name in gang_rows)

        # Community vulnerability proxy: recorded crime count per district.
        district_counts = (
            self.session.query(Location.district, func.count(Crime.id))
            .join(Crime, Crime.location_id == Location.id)
            .group_by(Location.district)
            .order_by(func.count(Crime.id).desc())
            .all()
        )

        return {
            "repeat_offender_communities": {
                "count": len(repeat_offender_ids),
                "person_ids": repeat_offender_ids[:50],
                "method": "Persons with >=2 distinct FIR accused-records, counted directly from the Accused table.",
            },
            "family_crime_links": {
                "count": len(family_links),
                "links": family_links[:50],
                "method": "PersonAssociation rows with relation_type=family where both persons also appear as Accused.",
            },
            "gang_indicators": {
                "count": len(gang_person_ids),
                "person_ids": gang_person_ids[:50],
                "organizations": dict(gang_orgs),
                "method": (
                    "OrganizationMembership joined to Organization where org_type=gang, restricted to "
                    "accused persons. Reflects recorded membership, not an inferred/predicted affiliation."
                ),
            },
            "community_vulnerability": {
                "by_district_crime_density": [{"district": d, "crime_count": c} for d, c in district_counts[:15]],
                "method": (
                    "Recorded crime count per district — a real but narrow proxy for vulnerability, not a "
                    "validated socio-economic index (that needs external census/poverty data; see "
                    "economic_stress_analysis's extension point)."
                ),
            },
        }

    # -- correlation matrix -----------------------------------------------

    def _correlation_matrix(self, accused_person_ids: list[int] | None) -> dict:
        q = (
            self.session.query(Person.gender, Person.age, Crime.type)
            .join(Accused, Accused.person_id == Person.id)
            .join(FIR, FIR.id == Accused.fir_id)
            .join(Crime, Crime.id == FIR.crime_id)
        )
        if accused_person_ids:
            q = q.filter(Person.id.in_(accused_person_ids))
        rows = q.all()

        gender_matrix = defaultdict(Counter)
        age_matrix = defaultdict(Counter)
        for gender, age, ctype in rows:
            gender_matrix[gender.value][ctype.value] += 1
            age_matrix[_bracket(age)][ctype.value] += 1

        return {
            "gender_by_crime_type": {g: dict(c) for g, c in gender_matrix.items()},
            "age_bracket_by_crime_type": {a: dict(c) for a, c in age_matrix.items()},
            "sample_size": len(rows),
            "method": "Direct cross-tabulation of accused-person attributes against the crime type of the FIR they're linked to.",
        }

    # -- extension-point placeholders (real when fed data, honest when not) --

    def urbanization_analysis(self, district_classification: dict[str, str] | None = None) -> dict:
        if not district_classification:
            return {"available": False, "reason": UNAVAILABLE_DIMENSIONS["urbanization"]}
        district_counts = dict(
            self.session.query(Location.district, func.count(Crime.id))
            .join(Crime, Crime.location_id == Location.id).group_by(Location.district).all()
        )
        tiers: Counter = Counter()
        for district, count in district_counts.items():
            tiers[district_classification.get(district, "unclassified")] += count
        return {"available": True, "crime_count_by_urbanization_tier": dict(tiers)}

    def migration_analysis(self, person_origin_district: dict[int, str] | None = None) -> dict:
        if not person_origin_district:
            return {"available": False, "reason": UNAVAILABLE_DIMENSIONS["migration"]}
        counts = Counter(person_origin_district.values())
        return {"available": True, "accused_count_by_origin_district": dict(counts)}

    def economic_stress_analysis(self, district_indicators: dict[str, dict] | None = None) -> dict:
        if not district_indicators:
            return {"available": False, "reason": UNAVAILABLE_DIMENSIONS["economic_stress"]}
        district_counts = dict(
            self.session.query(Location.district, func.count(Crime.id))
            .join(Crime, Crime.location_id == Location.id).group_by(Location.district).all()
        )
        correlated = {
            d: {"crime_count": district_counts.get(d, 0), "indicators": ind}
            for d, ind in district_indicators.items()
        }
        return {"available": True, "district_crime_vs_economic_indicators": correlated}

    def education_analysis(self, person_education_level: dict[int, str] | None = None) -> dict:
        if not person_education_level:
            return {"available": False, "reason": UNAVAILABLE_DIMENSIONS["education"]}
        counts = Counter(person_education_level.values())
        return {"available": True, "accused_count_by_education_level": dict(counts)}

    def _data_availability(self) -> dict:
        return {
            "age": "available", "gender": "available", "occupation": "available",
            "income_group": "unavailable", "employment_status": "unavailable",
            "housing_type": "unavailable", "economic_category": "unavailable",
            "repeat_offender_communities": "available", "family_crime_links": "available",
            "gang_indicators": "available", "community_vulnerability": "proxy_only",
            "urbanization": "unavailable_extension_point", "migration": "unavailable_extension_point",
            "economic_stress": "unavailable_extension_point", "education": "unavailable_extension_point",
        }

    # -- report composition ------------------------------------------------

    def _key_findings(self, dashboard: dict) -> list[str]:
        findings = []
        demo = dashboard["demographics"]["accused"]
        if demo["sample_size"]:
            gender = demo["gender_distribution"]
            brackets = demo["age_bracket_distribution"]
            occs = demo["occupation_distribution"]
            dominant_bracket = max(brackets, key=brackets.get) if brackets else "unknown"
            top_occ = max(occs, key=occs.get) if occs else "unspecified"
            findings.append(
                f"{demo['sample_size']} accused person(s) in scope: gender split {gender}, "
                f"dominant age bracket {dominant_bracket} ({brackets.get(dominant_bracket, 0)}), "
                f"top occupation '{top_occ}' ({occs.get(top_occ, 0)})."
            )
        else:
            findings.append("No accused persons in scope to build a demographic profile from.")

        risk = dashboard["social_risk_factors"]
        findings.append(
            f"{risk['repeat_offender_communities']['count']} repeat offender(s), "
            f"{risk['family_crime_links']['count']} family-linked accused pair(s), "
            f"{risk['gang_indicators']['count']} gang-affiliated accused person(s)."
        )
        district_density = risk["community_vulnerability"]["by_district_crime_density"]
        if district_density:
            top = district_density[0]
            findings.append(f"Highest recorded crime concentration: {top['district']} ({top['crime_count']} crimes).")

        gaps = [k for k, v in dashboard["data_availability"].items() if "unavailable" in v]
        if gaps:
            findings.append(f"Not available in current schema: {', '.join(gaps)}.")
        return findings

    def _risk_factor_summaries(self, dashboard: dict) -> list[dict]:
        risk = dashboard["social_risk_factors"]
        out = []
        for key in ("repeat_offender_communities", "family_crime_links", "gang_indicators"):
            entry = risk[key]
            out.append({"factor": key, "count": entry["count"], "method": entry["method"]})
        vuln = risk["community_vulnerability"]
        out.append({
            "factor": "community_vulnerability",
            "top_districts": vuln["by_district_crime_density"][:5],
            "method": vuln["method"],
        })
        return out

    def _evidence_trail(self, dashboard: dict) -> list[str]:
        risk = dashboard["social_risk_factors"]
        trail = [
            risk["repeat_offender_communities"]["method"],
            risk["family_crime_links"]["method"],
            risk["gang_indicators"]["method"],
            risk["community_vulnerability"]["method"],
            dashboard["correlation_matrix"]["method"],
        ]
        trail.append(
            f"Demographic tabulation direct from Person.gender/age/occupation "
            f"({dashboard['demographics']['accused']['sample_size']} accused, "
            f"{dashboard['demographics']['victims']['sample_size']} victims)."
        )
        return trail

    def _recommendations(self, dashboard: dict) -> list[str]:
        risk = dashboard["social_risk_factors"]
        recs = []
        ro = risk["repeat_offender_communities"]
        if ro["count"]:
            recs.append(f"{ro['count']} repeat offender(s) identified from FIR-tallies — prioritize case review for these individuals.")
        fam = risk["family_crime_links"]
        if fam["count"]:
            recs.append(f"{fam['count']} family-linked accused pair(s) found — worth checking for co-offending patterns during investigation.")
        gang = risk["gang_indicators"]
        if gang["count"]:
            org_list = ", ".join(gang["organizations"]) or "unnamed organization(s)"
            recs.append(f"{gang['count']} accused person(s) hold recorded membership in gang-type organizations ({org_list}) — cross-reference with Organization Intelligence findings.")
        vuln = risk["community_vulnerability"]["by_district_crime_density"]
        if vuln:
            recs.append(f"{vuln[0]['district']} shows the highest recorded crime count ({vuln[0]['crime_count']}) — a candidate for resource prioritization, pending a real vulnerability index (see economic_stress_analysis).")
        gaps = [k for k, v in dashboard["data_availability"].items() if "unavailable" in v]
        if gaps:
            recs.append(f"Add {', '.join(gaps)} data to the schema/dataset to unlock the remaining sociological analysis dimensions.")
        if not recs:
            recs.append("No risk-factor patterns found in the current scope.")
        return recs

    def _confidence(self, dashboard: dict) -> dict:
        availability = dashboard["data_availability"]
        available_count = sum(1 for v in availability.values() if v == "available")
        total = len(availability)
        coverage = available_count / total if total else 0.0

        sample_size = dashboard["demographics"]["accused"]["sample_size"]
        sample_weight = min(1.0, sample_size / 10) if sample_size else 0.0

        score = round(0.5 * coverage + 0.5 * sample_weight, 2)
        return {
            "score": score,
            "basis": (
                f"{available_count}/{total} dimensions have real data ({coverage:.0%} schema coverage); "
                f"accused sample size {sample_size} (weight {sample_weight:.0%} of full confidence at n>=10)."
            ),
        }

    def _executive_summary(self, dashboard: dict, key_findings: list[str], query: str | None) -> str:
        if not key_findings:
            return "No sociological findings were available for this scope."

        if os.getenv("ANTHROPIC_API_KEY"):
            try:
                return self._executive_summary_llm(dashboard, key_findings, query)
            except Exception:
                logger.warning("LLM executive summary failed, falling back to template", exc_info=True)
                return self._executive_summary_template(key_findings) + \
                    "\n\n(Note: AI-written summary was unavailable; the summary above is composed directly from computed findings.)"

        return self._executive_summary_template(key_findings)

    def _executive_summary_template(self, key_findings: list[str]) -> str:
        return " ".join(key_findings)

    def _executive_summary_llm(self, dashboard: dict, key_findings: list[str], query: str | None) -> str:
        from anthropic import Anthropic

        client = Anthropic()
        findings_text = "\n".join(f"- {f}" for f in key_findings)
        prompt = (
            "You are the Sociological Crime Insights component of SHERLOCK, an AI crime "
            "intelligence platform. Write a short (3-5 sentence), professional executive "
            "summary based ONLY on the computed findings below. Do not invent any fact, "
            "number, or dimension not present in the findings. Where a finding says a "
            "dimension is unavailable, state that plainly rather than speculating about it.\n\n"
            + (f"Context: {query}\n\n" if query else "")
            + f"Computed findings:\n{findings_text}"
        )
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in response.content if block.type == "text")
