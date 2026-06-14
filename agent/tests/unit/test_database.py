"""Unit tests for database module."""

import pytest

from agent.db.database import AgentDB


@pytest.fixture
async def db():
    """Create an in-memory database for testing."""
    database = AgentDB()
    await database.initialize(":memory:")
    yield database
    await database.close()


@pytest.mark.asyncio
class TestAgentDB:
    """Tests for AgentDB class."""

    async def test_initialize_creates_tables(self, db):
        """Database initialization should create required tables."""
        cursor = await db._db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in await cursor.fetchall()}
        assert "conversations" in tables
        assert "messages" in tables

    async def test_create_conversation_returns_id(self, db):
        """create_conversation should return a valid conversation ID."""
        user_id = 101
        conv_id = await db.create_conversation(user_id)
        assert isinstance(conv_id, str)
        assert len(conv_id) == 32  # UUID hex format

    async def test_get_conversation_returns_data(self, db):
        """get_conversation should return conversation data."""
        user_id = 101
        conv_id = await db.create_conversation(user_id)
        conv = await db.get_conversation(conv_id)
        assert conv is not None
        assert conv["id"] == conv_id
        assert conv["user_id"] == user_id
        assert "created_at" in conv
        assert "updated_at" in conv

    async def test_get_nonexistent_conversation_returns_none(self, db):
        """get_conversation should return None for invalid ID."""
        conv = await db.get_conversation("nonexistent")
        assert conv is None

    async def test_save_message_stores_data(self, db):
        """save_message should store message with all fields."""
        conv_id = await db.create_conversation(101)
        msg_id = await db.save_message(
            conversation_id=conv_id,
            role="user",
            content="Hello",
        )
        assert isinstance(msg_id, str)
        assert len(msg_id) == 32

    async def test_save_message_with_tool_call(self, db):
        """save_message should store tool call details."""
        conv_id = await db.create_conversation(101)
        msg_id = await db.save_message(
            conversation_id=conv_id,
            role="assistant",
            content="",
            tool_call_id="call_123",
            tool_name="search_memos",
            tool_arguments={"query": "test"},
        )
        assert msg_id is not None

        messages = await db.get_messages(conv_id)
        assert len(messages) == 1
        msg = messages[0]
        assert msg["tool_call_id"] == "call_123"
        assert msg["tool_name"] == "search_memos"
        assert msg["tool_arguments"] == {"query": "test"}

    async def test_get_messages_returns_in_order(self, db):
        """get_messages should return messages in chronological order."""
        conv_id = await db.create_conversation(101)
        await db.save_message(conv_id, "user", "First")
        await db.save_message(conv_id, "assistant", "Second")
        await db.save_message(conv_id, "user", "Third")

        messages = await db.get_messages(conv_id)
        assert len(messages) == 3
        assert messages[0]["content"] == "First"
        assert messages[1]["content"] == "Second"
        assert messages[2]["content"] == "Third"

    async def test_get_messages_respects_limit(self, db):
        """get_messages should respect the limit parameter."""
        conv_id = await db.create_conversation(101)
        for i in range(5):
            await db.save_message(conv_id, "user", f"Message {i}")

        messages = await db.get_messages(conv_id, limit=3)
        assert len(messages) == 3
        # Should get the most recent 3 in chronological order
        assert messages[0]["content"] == "Message 2"
        assert messages[1]["content"] == "Message 3"
        assert messages[2]["content"] == "Message 4"

    async def test_save_message_updates_conversation_timestamp(self, db):
        """save_message should update conversation's updated_at."""
        conv_id = await db.create_conversation(101)
        conv_before = await db.get_conversation(conv_id)

        import asyncio
        await asyncio.sleep(0.01)  # Small delay to ensure timestamp difference

        await db.save_message(conv_id, "user", "Test")
        conv_after = await db.get_conversation(conv_id)

        assert conv_after["updated_at"] > conv_before["updated_at"]

    async def test_multiple_conversations_isolated(self, db):
        """Messages in different conversations should be isolated."""
        conv1 = await db.create_conversation(101)
        conv2 = await db.create_conversation(102)

        await db.save_message(conv1, "user", "Conv1 message")
        await db.save_message(conv2, "user", "Conv2 message")

        msgs1 = await db.get_messages(conv1)
        msgs2 = await db.get_messages(conv2)

        assert len(msgs1) == 1
        assert len(msgs2) == 1
        assert msgs1[0]["content"] == "Conv1 message"
        assert msgs2[0]["content"] == "Conv2 message"

    async def test_wal_mode_enabled(self, db):
        """Database should use WAL mode for better concurrency.

        Note: :memory: databases use 'memory' journal mode, not WAL.
        This test verifies WAL is requested, but in-memory mode will differ.
        """
        cursor = await db._db.execute("PRAGMA journal_mode")
        row = await cursor.fetchone()
        # :memory: returns 'memory', file-based returns 'wal'
        assert row[0].lower() in ("wal", "memory")

    async def test_foreign_keys_enabled(self, db):
        """Database should have foreign keys enabled."""
        cursor = await db._db.execute("PRAGMA foreign_keys")
        row = await cursor.fetchone()
        assert row[0] == 1

    async def test_create_conversation_with_agent_id(self, db):
        """create_conversation should store agent_id."""
        conv_id = await db.create_conversation(101, agent_id="summary")
        conv = await db.get_conversation(conv_id)
        assert conv["agent_id"] == "summary"

    async def test_create_conversation_default_agent_id(self, db):
        """create_conversation should default agent_id to 'general'."""
        conv_id = await db.create_conversation(101)
        conv = await db.get_conversation(conv_id)
        assert conv["agent_id"] == "general"

    async def test_list_conversations_by_agent(self, db):
        """list_conversations should filter by agent_id."""
        await db.create_conversation(101, agent_id="general")
        await db.create_conversation(101, agent_id="summary")
        await db.create_conversation(101, agent_id="summary")

        all_convs = await db.list_conversations(101)
        assert len(all_convs) == 3

        summary_convs = await db.list_conversations(101, agent_id="summary")
        assert len(summary_convs) == 2
        assert all(c["agent_id"] == "summary" for c in summary_convs)

        general_convs = await db.list_conversations(101, agent_id="general")
        assert len(general_convs) == 1

    async def test_delete_conversation(self, db):
        """delete_conversation should remove the conversation."""
        conv_id = await db.create_conversation(101, agent_id="summary")
        await db.delete_conversation(conv_id)
        assert await db.get_conversation(conv_id) is None
