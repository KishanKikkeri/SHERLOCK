"""
SHERLOCK — Summary Engine (Crime Pattern & Trend Analytics Agent).

This is the layer the redesigned analytics dashboard actually calls —
it aggregates trend_engine / hotspot_engine / cluster_engine /
seasonal_engine / modus_engine into one payload: KPI cards, an
evidence-citing executive summary, a flat insights list, MO
enrichment, and rule-based recommendations with confidence. No LLM
call anywhere in this module. Every number in the summary text is
read from an engine's output, not phrased freely — deterministic and
reproducible, which is the whole point of replacing raw agent output
with this. If a future version wants an LLM to phrase the summary
more naturally, that should read from this payload's numbers, not
replace them.

Recommendations are rule-based (a fixed threshold on an insight ->
a canned recommendation string + a confidence tier derived from the
same signal that triggered it), not model-generated, for the same
reason. They're deliberately plain and few — this is a starting rule
set, not a tuned policy engine.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from backend.analytics import trend_engine, hotspot_engine, cluster_engine, seasonal_engine, modus_engine
from backend.analytics.trend_engine import VictimFilter


def _kpi_cards(trend: dict, yoy: dict, top_districts: list[dict], spikes: list[dict],
               outbreaks: list[dict]) -> list[dict]:
    growth = trend["growth"]
    trend_label = "Trend (last complete period)" if growth["partial_excluded"] else "Trend (latest vs. previous period)"
    cards = [
        {"label": "Total crimes", "value": trend["total"]},
        {"label": trend_label, "value": f"{growth['direction']} {abs(growth['pct_change'])}%"},
        {"label": "Year-over-year", "value": f"{yoy['yoy_pct_change']}%" if yoy["current_year"] else "n/a"},
        {"label": "Top district", "value": top_districts[0]["district"] if top_districts else "n/a"},
        {"label": "Active spikes", "value": len(spikes)},
        {"label": "Active localized outbreaks", "value": len(outbreaks)},
    ]
    if trend["partial_period"]:
        cards.append({"label": "Current period (in progress)", "value": f"{trend['partial_period']}*"})
    return cards


def _executive_summary(trend: dict, type_distribution: dict, top_hotspots: list[dict],
                        outbreaks: list[dict], spikes: list[dict], repeat_sites: list[dict],
                        festival: list[dict]) -> str:
    """Briefing-style summary — every clause below cites the specific
    number(s) behind it (A -> B counts, z-scores, fractions), rather
    than asserting a conclusion with no evidence attached. Still plain
    string formatting, not an LLM — see module docstring.
    """
    growth = trend["growth"]
    period_phrase = "the last complete period" if growth["partial_excluded"] else f"the previous {trend['granularity']}"
    verb = "increased" if growth["direction"] == "up" else "decreased" if growth["direction"] == "down" else "held steady vs."
    parts = [
        f"Total reported crime {verb} {abs(growth['pct_change'])}% over {period_phrase} "
        f"({growth['previous']} \u2192 {growth['current']} cases, {growth['confidence']['tier']} confidence: "
        f"{growth['confidence']['reason']})."
    ]
    if trend["partial_period"]:
        parts.append(f"{trend['partial_period']} is still in progress and excluded from that comparison.")

    driving_types = [s["crime_type"] for s in spikes[:2]]
    if not driving_types:
        driving_types = [t["crime_type"] for t in type_distribution["type_growth"] if t["direction"] == "up"][:2]
    if driving_types:
        parts.append(f"This was driven primarily by {' and '.join(t.replace('_', ' ') for t in driving_types)}.")

    if top_hotspots:
        h = top_hotspots[0]
        parts.append(f"The strongest hotspot remains {h['location']} ({h['district']}), with {h['count']} recorded incidents.")

    if outbreaks:
        o = outbreaks[0]
        evidence = f"{o['z_score']}\u03c3 above baseline" if o["z_score"] is not None else f"{o['observed']} cases vs. an expected {o['expected']}"
        parts.append(f"{o['district']} shows a localized outbreak — incident density is {evidence}.")

    if repeat_sites:
        r = repeat_sites[0]
        parts.append(
            f"Repeat incidents at {r['location']} ({r['occurrences']} {r['crime_type'].replace('_', ' ')} cases "
            f"between {r['window_start']} and {r['window_end']}) suggest an emerging repeat-offence cluster."
        )

    flagged_festivals = [f for f in festival if f["flagged"]]
    if flagged_festivals:
        f = flagged_festivals[0]
        parts.append(
            f"Festival-related crime accounts for {f['festival_share']:.0%} of incidents in {f['district']} "
            f"({f['festival_count']} of {f['total']}) this period."
        )

    return " ".join(parts)


def _spike_confidence(flag: dict, z_threshold: float) -> dict:
    if flag["method"] == "zscore":
        z = flag["z_score"]
        if z >= z_threshold + 1:
            return {"tier": "high", "reason": f"z-score {z} (well past the {z_threshold} threshold)"}
        if z >= z_threshold + 0.5:
            return {"tier": "medium", "reason": f"z-score {z} (moderately past the {z_threshold} threshold)"}
        return {"tier": "low", "reason": f"z-score {z} (just past the {z_threshold} threshold)"}
    return {"tier": "medium", "reason": "flat historical baseline with an absolute-delta flag — no variance to z-test against"}


def _festival_confidence(f: dict) -> dict:
    if f["festival_share"] >= 0.6 and f["total"] >= 20:
        return {"tier": "high", "reason": f"{f['festival_share']:.0%} share over {f['total']} total cases"}
    if f["festival_share"] >= 0.5 and f["total"] >= 10:
        return {"tier": "medium", "reason": f"{f['festival_share']:.0%} share over {f['total']} total cases"}
    return {"tier": "low", "reason": f"small sample ({f['total']} total cases) despite a {f['festival_share']:.0%} share"}


def _repeat_confidence(r: dict) -> dict:
    if r["occurrences"] >= 5:
        return {"tier": "high", "reason": f"{r['occurrences']} occurrences in the window"}
    if r["occurrences"] >= 4:
        return {"tier": "medium", "reason": f"{r['occurrences']} occurrences in the window"}
    return {"tier": "low", "reason": f"at the minimum-threshold occurrence count ({r['occurrences']})"}


def _recommendations(spikes: list[dict], outbreaks: list[dict],
                      festival: list[dict], repeat_sites: list[dict],
                      z_threshold: float = 2.0) -> list[dict]:
    """-> [{"text": str, "confidence": {"tier": str, "reason": str}}, ...]"""
    recs = []
    for s in spikes:
        recs.append({
            "text": f"Investigate the spike in {s['crime_type'].replace('_', ' ')} cases ({s['period']}) — review resourcing for that category.",
            "confidence": _spike_confidence(s, z_threshold),
        })
    for o in outbreaks:
        recs.append({
            "text": f"Consider additional patrol presence in {o['district']} ({o['period']}) — localized outbreak flagged.",
            "confidence": _spike_confidence(o, z_threshold),
        })
    for f in festival:
        if f["flagged"]:
            recs.append({
                "text": f"Plan festival-season patrol increases in {f['district']} — {f['festival_share']:.0%} of cases historically fall in that window.",
                "confidence": _festival_confidence(f),
            })
    for r in repeat_sites[:5]:
        recs.append({
            "text": f"Flag {r['location']} ({r['district']}) for repeat-incident follow-up — {r['occurrences']} {r['crime_type'].replace('_', ' ')} incidents within a 30-day window.",
            "confidence": _repeat_confidence(r),
        })
    return recs


def generate_dashboard_summary(session: Session, crime_type: Optional[str] = None,
                                district: Optional[str] = None, granularity: str = "month",
                                victim_gender: Optional[str] = None,
                                victim_age_min: Optional[int] = None,
                                victim_age_max: Optional[int] = None) -> dict:
    """The single call the analytics dashboard route should make.

    Victim-demographic filters (`victim_gender`/`victim_age_min`/`victim_age_max`)
    apply everywhere EXCEPT `emerging_categories` and `repeat_incident_clusters`
    — those two already run unfiltered by district/crime_type in
    cluster_engine (a pre-existing scope limit, not introduced here) and
    weren't extended further in this pass.

    -> {
         "kpi_cards": [...],
         "executive_summary": str,
         "charts": {"trend": {...}, "type_distribution": {...}, "heatmap": [...], "seasonal": {...}},
         "tables": {"top_districts": [...], "top_hotspots": [...], "top_modus_operandi": [...]},
         "insights": {"spikes": [...], "outbreaks": [...], "emerging_categories": [...],
                       "repeat_incident_clusters": [...], "festival_concentration": [...]},
         "mo_enrichment": {...},   # see modus_engine.mo_enrichment_summary
         "recommendations": [{"text": str, "confidence": {...}}, ...],
       }
    """
    victim_filter = VictimFilter(gender=victim_gender, age_min=victim_age_min, age_max=victim_age_max)

    trend = trend_engine.crime_trend(session, granularity=granularity, crime_type=crime_type, district=district,
                                      victim_filter=victim_filter)
    yoy = trend_engine.year_over_year(session, crime_type=crime_type, district=district, victim_filter=victim_filter)
    type_distribution = trend_engine.crimes_by_type_distribution(session, district=district, victim_filter=victim_filter)
    top_districts = trend_engine.crimes_by_district(session, crime_type=crime_type, victim_filter=victim_filter)

    top_hotspots = hotspot_engine.top_hotspots(session, crime_type=crime_type, district=district, victim_filter=victim_filter)
    heatmap = hotspot_engine.heatmap_points(session, crime_type=crime_type, district=district, victim_filter=victim_filter)

    spikes = cluster_engine.spike_detection(session, granularity=granularity, district=district, victim_filter=victim_filter)
    outbreaks = cluster_engine.localized_outbreaks(session, granularity=granularity, crime_type=crime_type, victim_filter=victim_filter)
    emerging = cluster_engine.emerging_categories(session, granularity=granularity)
    repeat_sites = cluster_engine.repeat_incident_clusters(session, crime_type=crime_type)

    seasonal = seasonal_engine.seasonal_distribution(session, crime_type=crime_type, district=district, victim_filter=victim_filter)
    weekend_split = seasonal_engine.weekend_vs_weekday(session, crime_type=crime_type, district=district, victim_filter=victim_filter)
    festival = seasonal_engine.festival_season_concentration(session, crime_type=crime_type, victim_filter=victim_filter)

    top_mo = modus_engine.top_modus_operandi(session, crime_type=crime_type, district=district, victim_filter=victim_filter)
    mo_enrichment = modus_engine.mo_enrichment_summary(session, crime_type=crime_type, district=district)

    kpi_cards = _kpi_cards(trend, yoy, top_districts, spikes, outbreaks)
    executive_summary = _executive_summary(trend, type_distribution, top_hotspots, outbreaks, spikes, repeat_sites, festival)
    recommendations = _recommendations(spikes, outbreaks, festival, repeat_sites)

    return {
        "kpi_cards": kpi_cards,
        "executive_summary": executive_summary,
        "charts": {
            "trend": trend,
            "year_over_year": yoy,
            "type_distribution": type_distribution,
            "heatmap": heatmap,
            "seasonal": seasonal,
            "weekend_vs_weekday": weekend_split,
        },
        "tables": {
            "top_districts": top_districts,
            "top_hotspots": top_hotspots,
            "top_modus_operandi": top_mo,
        },
        "insights": {
            "spikes": spikes,
            "outbreaks": outbreaks,
            "emerging_categories": emerging,
            "repeat_incident_clusters": repeat_sites,
            "festival_concentration": festival,
        },
        "mo_enrichment": mo_enrichment,
        "recommendations": recommendations,
    }
