"""
SHERLOCK — Conversation V2: Migration Script.

Losslessly migrates all legacy ``InvestigationSession`` and
``ConversationTurn`` data into the new ``InvestigationV2``,
``ConversationV2``, and ``MessageV2`` models.

Conforms to Phase 6 requirements:
  - Sessions become user-curated workspaces (Investigations)
  - Turns are split into user/assistant message pairs under a migrated conversation
  - Original findings and metadata are preserved inside MessageV2.metadata_json
  - Original timestamps and status fields are preserved
"""

import os
import sys
import json
import logging
from datetime import datetime

# Add project root to sys.path so we can import backend packages
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.database.config import SessionLocal, engine
from backend.database.models.investigation_session import InvestigationSession
from backend.database.models.conversation import ConversationTurn
from backend.database.models.investigation_v2 import InvestigationV2
from backend.database.models.conversation_v2 import ConversationV2, MessageV2
from backend.database.models.enums import InvestigationSessionStatus, InvestigationV2Status

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migrate_to_v2")


def run_migration():
    db = SessionLocal()
    try:
        # Check if tables exist and create them if not
        from backend.database.config import Base
        Base.metadata.create_all(bind=engine, tables=[
            InvestigationV2.__table__,
            ConversationV2.__table__,
            MessageV2.__table__
        ])

        legacy_sessions = db.query(InvestigationSession).all()
        if not legacy_sessions:
            logger.info("No legacy investigation sessions found to migrate.")
            return

        logger.info(f"Beginning migration of {len(legacy_sessions)} legacy sessions...")

        migrated_inv_count = 0
        migrated_msg_count = 0

        for sess in legacy_sessions:
            # 1. Map status
            if sess.status == InvestigationSessionStatus.ARCHIVED:
                v2_status = InvestigationV2Status.ARCHIVED
            elif sess.status == InvestigationSessionStatus.CLOSED:
                v2_status = InvestigationV2Status.CLOSED
            else:
                v2_status = InvestigationV2Status.ACTIVE

            # 2. Select initial entities (scoped case)
            selected_firs = [sess.fir_id] if sess.fir_id is not None else []

            # 3. Create InvestigationV2
            inv_v2 = InvestigationV2(
                title=sess.title or f"Migrated Case {sess.session_code}",
                description=sess.notes,
                status=v2_status,
                created_by_officer_id=sess.opened_by_officer_id,
                selected_fir_ids_json=json.dumps(selected_firs),
                selected_person_ids_json=json.dumps([]),
                selected_account_ids_json=json.dumps([]),
                selected_location_ids_json=json.dumps([]),
                selected_org_ids_json=json.dumps([]),
                created_at=sess.opened_at,
                updated_at=sess.updated_at,
                archived_at=sess.archived_at,
            )
            db.add(inv_v2)
            db.flush()  # Obtain inv_v2.id

            # 4. Create ConversationV2
            conv_v2 = ConversationV2(
                investigation_id=inv_v2.id,
                nickname="Migrated Workspace Chat",
                language="en",
                pinned=False,
                is_deleted=False,
                context_summary=sess.context_summary,
                context_summary_through_msg=sess.context_summary_through_turn,
                created_at=sess.opened_at,
                updated_at=sess.updated_at,
            )
            db.add(conv_v2)
            db.flush()  # Obtain conv_v2.id

            # 5. Migrate ConversationTurns
            turns = (
                db.query(ConversationTurn)
                .filter(ConversationTurn.session_id == sess.id)
                .order_by(ConversationTurn.turn_index.asc())
                .all()
            )

            for turn in turns:
                # 5a. Create user message
                user_msg = MessageV2(
                    conversation_id=conv_v2.id,
                    role="user",
                    content=turn.raw_query,
                    created_at=turn.created_at,
                )
                db.add(user_msg)
                migrated_msg_count += 1

                # If the turn called a tool or had entity mentions, mock tool metadata
                tool_calls_json = None
                if turn.resolved_query and turn.resolved_query != turn.raw_query:
                    tool_calls_json = json.dumps([{
                        "name": "investigate",
                        "arguments": {"query": turn.resolved_query},
                        "call_id": f"mig_{turn.id}",
                    }])

                # Build metadata with findings/citations
                metadata = {}
                if turn.findings_json:
                    try:
                        findings = json.loads(turn.findings_json)
                        metadata["findings"] = findings
                        metadata["citations"] = [
                            {"source": f.get("source", "Record"), "text": f.get("title", "")}
                            for f in findings[:5]
                        ]
                    except Exception:
                        pass

                # 5b. Create assistant message
                assistant_msg = MessageV2(
                    conversation_id=conv_v2.id,
                    role="assistant",
                    content=turn.response_summary or "No summary recorded.",
                    tool_calls_json=tool_calls_json,
                    metadata_json=json.dumps(metadata) if metadata else None,
                    created_at=turn.created_at,
                )
                db.add(assistant_msg)
                migrated_msg_count += 1

            migrated_inv_count += 1

        db.commit()
        logger.info(
            f"Successfully migrated {migrated_inv_count} investigations/conversations "
            f"and {migrated_msg_count} messages."
        )

    except Exception:
        db.rollback()
        logger.exception("Migration failed")
    finally:
        db.close()


if __name__ == "__main__":
    run_migration()
