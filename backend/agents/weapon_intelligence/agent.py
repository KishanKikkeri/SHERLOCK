"""
SHERLOCK — Weapon Intelligence Agent (Sprint B3, Stage B Division 5).

Correction to an earlier note: Sprint B1's report (see
docs/STAGE_B_SPRINT_B1_REPORT.md) flagged weapon-reuse detection as
blocked because `Weapon.used_in_fir_id` is a 1:1 link (one weapon row,
one FIR). That's true for a single row, but it undersold what the
schema actually supports — nothing stops the SAME physical weapon
(same `serial_number`) from being logged as a separate `Weapon` row each
time it turns up at a different crime scene. Reuse is fully detectable by
grouping on `serial_number` across rows. This agent does exactly that.
Restated here rather than silently fixed, since the earlier note was
read by whoever's tracking this project.

Weapons without a serial number (very plausible for a real seizure —
filed-off or never-recorded serials) can't be matched to anything and
are reported as singletons, not silently dropped.
"""

from collections import defaultdict

from backend.agents.base.agent import BaseAgent
from backend.agents.base.finding import AgentFinding
from backend.database.models import Crime, Weapon


class WeaponIntelligenceAgent(BaseAgent):
    name = "WeaponIntelligence"

    def __init__(self, session):
        self.session = session

    def run(self, state: dict):
        gctx = state.get("graph_context", {})
        crime_ids = gctx.get("crime_ids")

        query = self.session.query(Crime)
        if crime_ids:
            query = query.filter(Crime.id.in_(crime_ids))
        crimes = query.all()

        fir_ids = {c.fir.id for c in crimes if c.fir}
        if not fir_ids:
            return [AgentFinding(
                agent_name=self.name,
                finding_type="weapon_history",
                summary="No FIRs in scope to check for weapons.",
                confidence=0.5,
            )]

        weapons_in_scope = self.session.query(Weapon).filter(Weapon.used_in_fir_id.in_(fir_ids)).all()
        if not weapons_in_scope:
            return [AgentFinding(
                agent_name=self.name,
                finding_type="weapon_history",
                summary="No weapons recorded for the case(s) in scope.",
                confidence=0.6,
            )]

        # Group by serial_number ACROSS THE WHOLE DATABASE (not just scope)
        # — reuse only shows up if we look beyond the current case set.
        serials = {w.serial_number for w in weapons_in_scope if w.serial_number}
        reuse_groups = defaultdict(list)
        if serials:
            all_matching = self.session.query(Weapon).filter(Weapon.serial_number.in_(serials)).all()
            for w in all_matching:
                reuse_groups[w.serial_number].append(w)

        reused = {sn: rows for sn, rows in reuse_groups.items() if len(rows) > 1}
        unmatched = [w for w in weapons_in_scope if not w.serial_number]

        if not reused:
            summary = (
                f"{len(weapons_in_scope)} weapon(s) in scope, no reuse across other cases detected "
                f"({len(unmatched)} without a serial number and therefore unmatchable)."
            )
            confidence = 0.7 if unmatched else 0.9
        else:
            total_reused_crimes = sum(len(rows) for rows in reused.values())
            summary = (
                f"Weapon reuse detected: {len(reused)} weapon(s) (by serial number) appear across "
                f"{total_reused_crimes} separate case record(s) — possible shared-weapon or gang signature."
            )
            confidence = 0.85

        evidence = []
        for sn, rows in reused.items():
            fir_numbers = [w.used_in_fir.fir_number for w in rows if w.used_in_fir]
            evidence.append(f"Serial {sn}: used in {', '.join(fir_numbers)}")
        for w in unmatched:
            evidence.append(f"{w.weapon_type.value} (no serial) in {w.used_in_fir.fir_number if w.used_in_fir else 'unknown FIR'}")

        return [AgentFinding(
            agent_name=self.name,
            finding_type="weapon_history",
            summary=summary,
            evidence=evidence[:8],
            confidence=confidence,
            source_entities=[f"weapon_{w.id}" for w in weapons_in_scope],
            metadata={
                "reused_serials": {sn: [w.id for w in rows] for sn, rows in reused.items()},
                "unmatched_count": len(unmatched),
            },
        )]
