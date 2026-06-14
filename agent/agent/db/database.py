import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from agent.observability.logger import log

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    agent_id TEXT NOT NULL DEFAULT 'general',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    tool_call_id TEXT,
    tool_name TEXT,
    tool_arguments TEXT,
    token_count INTEGER,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at);
"""

_POST_MIGRATE_SCHEMA = """
CREATE INDEX IF NOT EXISTS idx_conversations_user_agent ON conversations(user_id, agent_id);
"""


def _now() -> float:
    return datetime.now(timezone.utc).timestamp()


class AgentDB:
    def __init__(self) -> None:
        self._db: aiosqlite.Connection | None = None

    async def initialize(self, data_dir: str) -> None:
        if data_dir == ":memory:":
            db_path = ":memory:"
        else:
            Path(data_dir).mkdir(parents=True, exist_ok=True)
            db_path = Path(data_dir) / "agent.db"
        self._db = await aiosqlite.connect(str(db_path))
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._db.executescript(_SCHEMA)
        await self._migrate()
        await self._db.executescript(_POST_MIGRATE_SCHEMA)
        await self._db.commit()
        log.info("database initialized", extra={"extra_data": {"path": str(db_path)}})

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    async def _migrate(self) -> None:
        """Add columns that may be missing from older schemas."""
        cols = await self._table_columns("conversations")
        if "agent_id" not in cols:
            await self._db.execute("ALTER TABLE conversations ADD COLUMN agent_id TEXT NOT NULL DEFAULT 'general'")
            log.info("migrated: added agent_id column to conversations")

    async def _table_columns(self, table: str) -> set[str]:
        cursor = await self._db.execute(f"PRAGMA table_info({table})")
        rows = await cursor.fetchall()
        return {row[1] for row in rows}

    async def create_conversation(self, user_id: int, agent_id: str = "general") -> str:
        conv_id = uuid.uuid4().hex
        now = _now()
        await self._db.execute(
            "INSERT INTO conversations (id, user_id, agent_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (conv_id, user_id, agent_id, now, now),
        )
        await self._db.commit()
        return conv_id

    async def get_conversation(self, conversation_id: str) -> dict | None:
        cursor = await self._db.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def list_conversations(self, user_id: int, agent_id: str | None = None, limit: int = 50) -> list[dict]:
        if agent_id:
            cursor = await self._db.execute(
                "SELECT * FROM conversations WHERE user_id = ? AND agent_id = ? ORDER BY updated_at DESC LIMIT ?",
                (user_id, agent_id, limit),
            )
        else:
            cursor = await self._db.execute(
                "SELECT * FROM conversations WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?",
                (user_id, limit),
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def delete_conversation(self, conversation_id: str) -> None:
        await self._db.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        await self._db.commit()

    async def save_message(
        self,
        conversation_id: str,
        role: str,
        content: str = "",
        tool_call_id: str | None = None,
        tool_name: str | None = None,
        tool_arguments: dict | None = None,
        token_count: int | None = None,
    ) -> str:
        msg_id = uuid.uuid4().hex
        now = _now()
        await self._db.execute(
            """INSERT INTO messages
               (id, conversation_id, role, content, tool_call_id, tool_name, tool_arguments, token_count, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                msg_id,
                conversation_id,
                role,
                content,
                tool_call_id,
                tool_name,
                json.dumps(tool_arguments) if tool_arguments else None,
                token_count,
                now,
            ),
        )
        await self._db.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conversation_id),
        )
        await self._db.commit()
        return msg_id

    async def get_messages(self, conversation_id: str, limit: int = 20) -> list[dict]:
        cursor = await self._db.execute(
            """SELECT * FROM messages
               WHERE conversation_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (conversation_id, limit),
        )
        rows = await cursor.fetchall()
        messages = []
        for row in reversed(rows):
            msg = dict(row)
            if msg["tool_arguments"]:
                msg["tool_arguments"] = json.loads(msg["tool_arguments"])
            messages.append(msg)
        return messages
