"""
SHERLOCK — Idempotent Conversation Trimming Script.

Keeps only the latest 10 conversations in conversations_v2 and their
associated messages in messages_v2. Deletes all older conversations
and dependent messages while preserving all entities, investigations,
FIRs, and crime data.
"""

import os
import sys
import sqlite3


def cleanup_conversations(db_path: str = "sherlock.db") -> dict:
    if not os.path.exists(db_path):
        print(f"Database file '{db_path}' does not exist.")
        return {"deleted_conversations": 0, "deleted_messages": 0, "remaining_conversations": 0}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("BEGIN TRANSACTION;")

        # Find IDs of the 10 most recently updated conversations
        cursor.execute("""
            SELECT id FROM conversations_v2
            ORDER BY updated_at DESC, id DESC
            LIMIT 10;
        """)
        keep_ids = [row[0] for row in cursor.fetchall()]

        if not keep_ids:
            print("No conversations found in database.")
            conn.commit()
            return {"deleted_conversations": 0, "deleted_messages": 0, "remaining_conversations": 0}

        placeholders = ",".join("?" for _ in keep_ids)

        # 1. Delete messages belonging to conversations outside top 10
        cursor.execute(f"""
            DELETE FROM messages_v2
            WHERE conversation_id NOT IN ({placeholders});
        """, keep_ids)
        deleted_messages = cursor.rowcount

        # 2. Delete conversations outside top 10
        cursor.execute(f"""
            DELETE FROM conversations_v2
            WHERE id NOT IN ({placeholders});
        """, keep_ids)
        deleted_conversations = cursor.rowcount

        cursor.execute("SELECT COUNT(*) FROM conversations_v2;")
        remaining_conversations = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM messages_v2;")
        remaining_messages = cursor.fetchone()[0]

        conn.commit()

        print(f"[Cleanup Summary]")
        print(f"  Deleted Conversations : {deleted_conversations}")
        print(f"  Deleted Messages      : {deleted_messages}")
        print(f"  Remaining Conversations: {remaining_conversations}")
        print(f"  Remaining Messages     : {remaining_messages}")

        return {
            "deleted_conversations": deleted_conversations,
            "deleted_messages": deleted_messages,
            "remaining_conversations": remaining_conversations,
            "remaining_messages": remaining_messages,
        }
    except Exception as e:
        conn.rollback()
        print(f"Error during conversation cleanup: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    db_file = sys.argv[1] if len(sys.argv) > 1 else "sherlock.db"
    cleanup_conversations(db_file)
