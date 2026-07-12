"""
SHERLOCK — Phase 5 milestone demo: full investigation pipeline.

Runs the milestone query:
  "Show repeat burglary offenders operating in Mysuru during festival
   seasons and identify future hotspots."

…through the complete LangGraph agent orchestration:
  Chief (plan) → Crime Records → Network Analysis → Entity Resolution
  → Timeline Reconstruction → Financial → Similar Case → Pattern Analysis
  → Forecasting → Prevention → Evidence Validation → Chief (synthesis)

Then prints the investigation activity feed and final report.

Usage:
    python demo_investigation.py
    python demo_investigation.py --query "Show money trail linked to fraud"
"""

import argparse

from backend.database.config import SessionLocal
from backend.graph.service import get_graph_service
from backend.orchestrator.graph import run_investigation

MILESTONE_QUERY = (
    "Show repeat burglary offenders operating in Mysuru during festival "
    "seasons and identify future hotspots."
)


def divider(title=""):
    width = 70
    if title:
        pad = (width - len(title) - 2) // 2
        print("=" * pad + f" {title} " + "=" * (width - pad - len(title) - 2))
    else:
        print("=" * width)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", default=MILESTONE_QUERY)
    args = parser.parse_args()

    session = SessionLocal()
    graph_service = get_graph_service(backend="networkx", session=session)

    print("\n")
    divider("SHERLOCK — Investigation Initiated")
    print(f"\n  Query: {args.query}\n")

    final_state = run_investigation(
        query=args.query,
        session=session,
        graph_service=graph_service,
    )

    # --- Investigation Activity Feed ---
    divider("Investigation Activity Feed")
    for i, entry in enumerate(final_state.get("audit_trail", []), 1):
        status_icon = "✓" if entry["status"] == "done" else "—"
        print(f"\n  [{status_icon}] {entry['agent']} ({entry['status'].upper()})")
        print(f"      {entry['message']}")

    # --- Evidence Validation Summary ---
    divider("Evidence Validation")
    validated = final_state.get("validated_findings", [])
    for f in validated:
        icon = "✓" if f.get("validated") else "✗"
        conf = f.get("confidence", 0)
        print(f"\n  [{icon}] [{f.get('agent_name')}] {f.get('finding_type')}")
        print(f"      {f.get('summary', '')[:120]}")
        print(f"      Confidence: {conf:.0%}  |  Status: {f.get('validation_notes', '')}")
        evidence = f.get("evidence", [])
        for e in evidence[:2]:
            print(f"      Evidence: {e}")

    # --- Final Intelligence Report ---
    divider("Final Intelligence Report")
    report = final_state.get("final_report", {})
    print()
    print(report.get("narrative", "(no narrative generated)"))
    print(f"\n  Agents consulted:  {', '.join(report.get('agents_consulted', []))}")
    print(f"  Findings accepted: {len([f for f in validated if f.get('validated')])}")
    print(f"  Findings rejected: {len([f for f in validated if not f.get('validated')])}")
    divider()
    session.close()


if __name__ == "__main__":
    main()
