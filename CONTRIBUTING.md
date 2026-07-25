# Contributing to SHERLOCK

Thank you for your interest in SHERLOCK. This document describes how to contribute effectively.

---

## Development Setup

```bash
git clone https://github.com/your-team/sherlock.git
cd sherlock
pip install -r backend/requirements.txt
python -m backend.datasets.generate_synthetic_data --persons 500 --crimes 1000 --reset
python -m backend.app.server
```

---

## Project Structure

```
backend/agents/     — Agent implementations (one package per agent)
backend/graph/      — Graph backends and intelligence service
backend/database/   — SQLAlchemy models and config
backend/orchestrator/ — LangGraph state and graph topology
backend/api/        — FastAPI endpoints and WebSocket stream
backend/reporting/  — PDF export
frontend/           — Single-file React Command Center
docs/               — Architecture, design, and demo documentation
```

---

## Adding a New Agent

1. Create `backend/agents/{agent_name}/agent.py`:
```python
from backend.agents.base.agent import BaseAgent
from backend.agents.base.finding import AgentFinding

class MyNewAgent(BaseAgent):
    name = "MyNewAgent"

    def __init__(self, session=None, graph_service=None):
        self.session = session
        self.graph_service = graph_service

    def run(self, state: dict) -> list[AgentFinding]:
        # Always return AgentFinding objects with evidence
        return [AgentFinding(
            agent_name=self.name,
            finding_type="my_finding_type",
            summary="...",
            evidence=["citation 1", "citation 2"],  # REQUIRED
            confidence=0.85,
            source_entities=[],
            metadata={},
        )]
```

2. Add to `backend/orchestrator/graph.py`:
```python
from backend.agents.my_new_agent.agent import MyNewAgent

my_agent = MyNewAgent(session=session, graph_service=graph_service)
builder.add_node("my_new_agent", my_agent.to_node())
builder.add_edge("pattern_analysis", "my_new_agent")
builder.add_edge("my_new_agent", "prevention_agent")
```

3. Add to `backend/agents/base/query_parser.py`:
```python
agents.append("MyNewAgent")  # in plan_agents(), when appropriate
```

4. Add to `backend/api/investigation_stream.py`:
```python
NODE_LABELS = {
    ...
    "my_new_agent": "My New Agent Display Name",
}
```

---

## Agent Rules

Every agent MUST follow these rules:

- **Return `AgentFinding` objects only.** No free-form text between agents.
- **Include `evidence`.** Every finding must have at least one evidence citation. Findings without evidence will be rejected by the Evidence Validation Agent.
- **Set realistic `confidence`.** Use 1.0 only for direct database facts. Use 0.7–0.9 for graph-derived insights. Use 0.6–0.7 for forecasts/predictions.
- **Scope to `active_agents`.** Your agent name must be in `active_agents` (controlled by `plan_agents()`). `BaseAgent.to_node()` handles skipping automatically.
- **No direct database access in graph agents.** Network Analysis, Pattern, and Financial agents use only `graph_service.*` methods.

---

## Graph Intelligence Service

When adding new graph queries, extend `GraphIntelligenceService` in `backend/graph/service.py` and implement in both `service_networkx.py` and `service_neo4j.py`. Keep the method signatures identical between backends.

---

## Code Style

- Python: PEP 8, type hints where practical
- Docstrings on all public classes and functions
- No bare `except:` clauses — always catch specific exceptions
- Agent files should be self-contained — avoid circular imports

---

## Testing

```bash
# Run a single demo
python demo_investigation.py --query "your test query here"

# Validate all three official demos
python -m pytest tests/ -v  # (test suite coming in Phase 2)
```

---

## Pull Request Process

1. Branch from `main`: `git checkout -b feature/my-agent`
2. Implement changes following the rules above
3. Run all three demo queries and confirm they still pass
4. Update `docs/AGENT_DESIGN.md` if adding a new agent
5. Update `docs/FEATURE_MAPPING.md` if addressing a new requirement
6. Open a PR with a description of what the agent does and why it belongs in SHERLOCK
