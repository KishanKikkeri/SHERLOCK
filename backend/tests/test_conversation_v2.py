import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.config import Base
from backend.database.models.enums import InvestigationV2Status
from backend.database.models.investigation_v2 import InvestigationV2
from backend.database.models.conversation_v2 import ConversationV2, MessageV2
from backend.tools.registry import ToolRegistry, ToolDefinition, ToolContext
from backend.conversation_v2.orchestrator import LLMOrchestrator
from backend.conversation_v2.prompts import build_system_prompt
from backend.conversation_v2.llm import DeterministicAdapter


@pytest.fixture(name="db_session")
def fixture_db_session():
    """Create a temporary in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_investigation_v2_crud(db_session):
    # Create
    inv = InvestigationV2(
        title="Test Case Workspace",
        description="Testing V2 workspace features",
        selected_fir_ids_json=json.dumps([12, 15]),
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)
    
    assert inv.id is not None
    assert inv.status == InvestigationV2Status.ACTIVE
    assert json.loads(inv.selected_fir_ids_json) == [12, 15]

    # Update
    inv.title = "Updated Workspace"
    db_session.commit()
    assert db_session.get(InvestigationV2, inv.id).title == "Updated Workspace"


def test_conversation_v2_crud(db_session):
    # Create
    conv = ConversationV2(
        nickname="Test Chat",
        language="kn",
    )
    db_session.add(conv)
    db_session.commit()
    db_session.refresh(conv)

    assert conv.id is not None
    assert conv.language == "kn"
    assert conv.pinned is False

    # Message posting
    msg = MessageV2(
        conversation_id=conv.id,
        role="user",
        content="Hello SHERLOCK",
    )
    db_session.add(msg)
    db_session.commit()

    assert len(conv.messages) == 1
    assert conv.messages[0].content == "Hello SHERLOCK"


@pytest.mark.anyio
async def test_tool_registry(db_session):
    registry = ToolRegistry()
    
    async def mock_handler(ctx: ToolContext, query: str) -> dict:
        return {"status": "ok", "results": [query]}

    tool_def = ToolDefinition(
        name="mock_tool",
        description="A mock tool for testing",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        handler=mock_handler,
    )
    registry.register(tool_def)
    
    assert "mock_tool" in registry
    assert len(registry) == 1

    ctx = ToolContext(db=db_session)
    res = await registry.execute("mock_tool", {"query": "test"}, ctx)
    assert res == {"status": "ok", "results": ["test"]}


@pytest.mark.anyio
async def test_llm_orchestrator(db_session):
    # Create mock tool registry
    registry = ToolRegistry()
    
    async def mock_search(ctx: ToolContext, name: str) -> dict:
        return {"status": "success", "findings": [{"source": "mock", "title": f"Profile of {name}"}]}

    registry.register(ToolDefinition(
        name="search_person",
        description="Search suspect",
        parameters={"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
        handler=mock_search,
    ))

    # Initialize orchestrator with DeterministicAdapter
    adapter = DeterministicAdapter()
    orchestrator = LLMOrchestrator(db_session, llm=adapter, tool_registry=registry)

    # Handle message
    res = await orchestrator.handle_message(
        conversation_id=None,
        message="Hello",
        language="en",
    )

    assert res.conversation_id is not None
    assert "hello" in res.reply.lower()

    # Query message history
    msgs = db_session.query(MessageV2).filter(MessageV2.conversation_id == res.conversation_id).all()
    assert len(msgs) == 2
    assert msgs[0].role == "user"
    assert msgs[1].role == "assistant"


def test_system_prompt_builder():
    prompt = build_system_prompt(
        language="kn",
        investigation_context={"title": "Mysuru Case", "selected_firs": [1, 2]},
    )
    assert "Mysuru Case" in prompt
    assert "ಕನ್ನಡ" in prompt  # Kannada directive present


@pytest.mark.anyio
async def test_generate_pdf_tool(db_session):
    from backend.tools.tool_definitions import build_default_registry
    
    # 1. Create a conversation in the DB
    conv = ConversationV2(
        nickname="Tool Test Chat",
        language="en",
    )
    db_session.add(conv)
    db_session.commit()
    db_session.refresh(conv)

    # 2. Add assistant message so findings list is populated
    msg = MessageV2(
        conversation_id=conv.id,
        role="assistant",
        content="This is a test tool finding message.",
    )
    db_session.add(msg)
    db_session.commit()

    registry = build_default_registry()
    ctx = ToolContext(db=db_session, conversation_id=conv.id)
    res = await registry.execute("generate_pdf", {"session_id": conv.id}, ctx)
    print("TOOL RESPONSE:", res)
    assert res["status"] == "success"
    assert res["pdf_length"] > 0
    assert "warnings" in res

