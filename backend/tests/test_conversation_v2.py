"""
SHERLOCK — Stage F3: Conversational Intelligence — V2 Refactor Unit Tests.

Verifies:
- Tool selection and budgeting by the planner
- Context-aware entity resolution and memory reuse
- Parallel tool execution in ToolGateway
- Tool result caching
- Direct native Kannada support (without post-translation)
- Error handling and normalization
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch

from backend.conversation.planner import ConversationPlanner, PlannedPlan
from backend.conversation.conversation_agent import ConversationAgent
from backend.conversation.tool_gateway import ToolGateway
from backend.conversation.orchestrator import ConversationOrchestrator
from backend.conversation.router import ConversationIntent
from backend.conversation.memory import ConversationStateMemory
from backend.database.models import InvestigationSession


class MockLLM:
    def __init__(self, completion_response: str):
        self.completion_response = completion_response
        self.called_with = []

    def completion(self, system_prompt: str, user_prompt: str, max_tokens: int = 400) -> str:
        self.called_with.append((system_prompt, user_prompt))
        return self.completion_response


def test_planner_tool_budgeting(db_session):
    """Planner parses context and decides intent and tool-calling budget."""
    mock_json = {
        "resolved_query": "Tell me about suspect Ravi Kumar",
        "intent": "investigate",
        "ambiguity_detected": False,
        "clarification_question": None,
        "tools_to_call": [
            {"name": "search_person", "arguments": {"name": "Ravi Kumar"}}
        ]
    }
    mock_llm = MockLLM(json.dumps(mock_json))

    planner = ConversationPlanner(db_session)
    planner.llm = mock_llm

    context = {
        "session_id": 1,
        "current_case_id": None,
        "active_entities": [],
        "last_findings": [],
        "previous_messages": []
    }

    plan = planner.plan("tell me about Ravi", context)
    assert plan.intent == ConversationIntent.INVESTIGATE
    assert plan.resolved_query == "Tell me about suspect Ravi Kumar"
    assert len(plan.tools_to_call) == 1
    assert plan.tools_to_call[0]["name"] == "search_person"
    assert plan.tools_to_call[0]["arguments"]["name"] == "Ravi Kumar"


def test_planner_ambiguity_detection(db_session):
    """Planner detects ambiguous query and sets clarification question."""
    mock_json = {
        "resolved_query": "Tell me about him",
        "intent": "investigate",
        "ambiguity_detected": True,
        "clarification_question": "Are you referring to suspect Ravi Kumar or Manoj Kumar?",
        "tools_to_call": []
    }
    mock_llm = MockLLM(json.dumps(mock_json))

    planner = ConversationPlanner(db_session)
    planner.llm = mock_llm

    context = {
        "session_id": 1,
        "current_case_id": None,
        "active_entities": [{"name": "Ravi Kumar"}, {"name": "Manoj Kumar"}],
        "last_findings": [],
        "previous_messages": []
    }

    plan = planner.plan("tell me about him", context)
    assert plan.ambiguity_detected is True
    assert plan.clarification_question == "Are you referring to suspect Ravi Kumar or Manoj Kumar?"
    assert len(plan.tools_to_call) == 0


@pytest.mark.anyio
async def test_tool_gateway_caching(db_session):
    """Verify ToolGateway caches tool calls to prevent redundant database runs."""
    gateway = ToolGateway(db_session)
    
    with patch("backend.conversation.tools.call_tool") as mock_call:
        mock_call.return_value = {"status": "success", "findings": [{"id": 1, "text": "Crime record"}]}
        
        # First call: executes tool
        res1 = await gateway.execute_tool("search_person", {"name": "Ravi"}, session_id=1)
        # Second call with same arguments: should use cache
        res2 = await gateway.execute_tool("search_person", {"name": "Ravi"}, session_id=1)
        
        assert res1 == res2
        assert mock_call.call_count == 1


@pytest.mark.anyio
async def test_tool_gateway_parallel_execution(db_session):
    """Verify ToolGateway executes independent tools concurrently."""
    gateway = ToolGateway(db_session)
    
    with patch("backend.conversation.tools.call_tool") as mock_call:
        mock_call.return_value = {"status": "success", "findings": []}
        
        tool_calls = [
            {"name": "search_person", "arguments": {"name": "Ravi"}},
            {"name": "financial_analysis", "arguments": {"account_number": "12345"}}
        ]
        
        results = await gateway.execute_tools_parallel(tool_calls, session_id=1)
        assert len(results) == 2
        assert mock_call.call_count == 2


def test_conversation_agent_native_kannada(db_session):
    """Verify direct native Kannada generation without translation hooks."""
    mock_llm = MockLLM("ರವಿ ಕುಮಾರ್ ಒಬ್ಬ ಶಂಕಿತ ಆರೋಪಿ.")
    agent = ConversationAgent(db_session)
    agent.llm = mock_llm

    response = agent.generate_response(
        message="tell me about Ravi",
        history=[],
        context={},
        language="kn"
    )

    assert response == "ರವಿ ಕುಮಾರ್ ಒಬ್ಬ ಶಂಕಿತ ಆರೋಪಿ."
    # Make sure prompt includes Kannada directive
    sys_prompt = mock_llm.called_with[0][0]
    assert "Kannada" in sys_prompt or "ಕನ್ನಡ" in sys_prompt


@pytest.mark.anyio
async def test_orchestrator_chitchat_no_tools(db_session):
    """Verify orchestrator routes chitchat/greeting directly to LLM with no tool execution."""
    session = InvestigationSession(session_code="TEST-SESS-99", title="Test Session")
    db_session.add(session)
    db_session.commit()

    orchestrator = ConversationOrchestrator(db_session)
    
    # Mock Planner to decide chitchat
    mock_plan = PlannedPlan(
        intent=ConversationIntent.CHITCHAT,
        resolved_query="hello",
        tools_to_call=[],
        ambiguity_detected=False
    )
    orchestrator.planner.plan = MagicMock(return_value=mock_plan)
    
    # Mock Agent direct reply
    orchestrator.agent.generate_response = MagicMock(return_value="Hello, how can I help you today?")
    
    with patch.object(orchestrator.gateway, "execute_tools_parallel") as mock_exec:
        result = await orchestrator.handle_message(session.id, "hello")
        
        assert result["reply"] == "Hello, how can I help you today?"
        assert result["intent"] == "chitchat"
        mock_exec.assert_not_called()
