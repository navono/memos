"""API tests for FastAPI routes using TestClient."""

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from agent.main import app
from agent.auth import AuthMiddleware


@pytest.fixture
def valid_token():
    """Create a valid JWT token for testing."""
    now = int(time.time())
    payload = {
        "iss": "memos",
        "sub": "101",
        "aud": "user.access-token",
        "name": "testuser",
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(payload, "usememos", algorithm="HS256")


@pytest.fixture
def another_user_token():
    """Create a token for a different user."""
    now = int(time.time())
    payload = {
        "iss": "memos",
        "sub": "202",
        "aud": "user.access-token",
        "name": "otheruser",
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(payload, "usememos", algorithm="HS256")


@pytest.fixture
def mock_db():
    """Create a mock database."""
    db = MagicMock()
    db.create_conversation = AsyncMock(return_value="conv-123")
    db.get_conversation = AsyncMock(return_value={
        "id": "conv-123",
        "user_id": 101,
        "created_at": time.time(),
        "updated_at": time.time(),
    })
    db._db = MagicMock()
    db._db.execute = AsyncMock()
    db._db.fetchall = AsyncMock(return_value=[])
    return db


@pytest.fixture
def mock_agent():
    """Create a mock agent that yields test messages."""
    agent = MagicMock()

    async def mock_astream(*args, **kwargs):
        from langchain_core.messages import AIMessage
        msg = AIMessage(content="Test response")
        yield msg, {"langgraph_node": "model"}

    agent.astream = mock_astream
    agent.aget_state = AsyncMock(return_value=MagicMock(values={"messages": []}))
    agent.checkpointer = None
    return agent


@pytest.fixture
def mock_memos_client():
    """Create a mock MemosClient."""
    client = MagicMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
async def client(mock_db, mock_agent, mock_memos_client):
    """Create an async test client with mocked dependencies."""
    app.state.db = mock_db
    app.state.agent = mock_agent
    app.state.memos_client = mock_memos_client

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac


class TestHealthEndpoint:
    """Tests for /v1/healthz endpoint."""

    @pytest.mark.asyncio
    async def test_healthz_no_auth_required(self, client):
        """healthz should be accessible without authentication."""
        resp = await client.get("/v1/healthz")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestAuthMiddleware:
    """Tests for authentication middleware."""

    @pytest.mark.asyncio
    async def test_missing_token_returns_401(self, client):
        """Request without token should return 401."""
        resp = await client.post("/v1/chat", json={"message": "hello"})
        assert resp.status_code == 401
        assert "missing" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self, client):
        """Invalid token should return 401."""
        resp = await client.post(
            "/v1/chat",
            headers={"X-Auth-Token": "invalid.token.here"},
            json={"message": "hello"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_token_in_header(self, client, valid_token):
        """Valid token in X-Auth-Token header should be accepted."""
        resp = await client.post(
            "/v1/chat",
            headers={"X-Auth-Token": valid_token},
            json={"message": "hello"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_valid_token_in_bearer(self, client, valid_token):
        """Valid token in Authorization Bearer header should be accepted."""
        resp = await client.post(
            "/v1/chat",
            headers={"Authorization": f"Bearer {valid_token}"},
            json={"message": "hello"},
        )
        assert resp.status_code == 200


class TestChatEndpoint:
    """Tests for /v1/chat endpoint."""

    @pytest.mark.asyncio
    async def test_chat_missing_message_returns_400(self, client, valid_token):
        """Chat request without message field should return 400."""
        resp = await client.post(
            "/v1/chat",
            headers={"X-Auth-Token": valid_token},
            json={},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_chat_creates_new_conversation(self, client, valid_token, mock_db):
        """Chat without conversation_id should create new conversation."""
        await client.post(
            "/v1/chat",
            headers={"X-Auth-Token": valid_token},
            json={"message": "hello"},
        )
        mock_db.create_conversation.assert_called_once_with(101)

    @pytest.mark.asyncio
    async def test_chat_uses_existing_conversation(self, client, valid_token, mock_db):
        """Chat with conversation_id should use existing conversation."""
        mock_db.get_conversation.return_value = {
            "id": "existing-conv",
            "user_id": 101,
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        await client.post(
            "/v1/chat",
            headers={"X-Auth-Token": valid_token},
            json={"message": "hello", "conversation_id": "existing-conv"},
        )
        mock_db.create_conversation.assert_not_called()

    @pytest.mark.asyncio
    async def test_chat_nonexistent_conversation_returns_404(self, client, valid_token, mock_db):
        """Chat with invalid conversation_id should return 404."""
        mock_db.get_conversation.return_value = None
        resp = await client.post(
            "/v1/chat",
            headers={"X-Auth-Token": valid_token},
            json={"message": "hello", "conversation_id": "nonexistent"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_chat_wrong_user_returns_403(self, client, valid_token, mock_db):
        """Chat with conversation belonging to another user should return 403."""
        mock_db.get_conversation.return_value = {
            "id": "conv-123",
            "user_id": 202,  # Different user
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        resp = await client.post(
            "/v1/chat",
            headers={"X-Auth-Token": valid_token},
            json={"message": "hello", "conversation_id": "conv-123"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_chat_returns_sse_stream(self, client, valid_token):
        """Chat should return SSE stream with content and done event."""
        async with client.stream(
            "POST",
            "/v1/chat",
            headers={"X-Auth-Token": valid_token},
            json={"message": "hello"},
        ) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")

            events = []
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))

            # Should have content and done event
            assert len(events) >= 1
            done_events = [e for e in events if "done" in e]
            assert len(done_events) == 1
            assert "conversation_id" in done_events[0]


class TestConversationsEndpoint:
    """Tests for /v1/conversations endpoints."""

    @pytest.mark.asyncio
    async def test_list_conversations(self, client, valid_token, mock_db):
        """List conversations should return user's conversations."""
        mock_db._db.fetchall.return_value = []
        resp = await client.get(
            "/v1/conversations",
            headers={"X-Auth-Token": valid_token},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_get_conversation(self, client, valid_token, mock_db, mock_agent):
        """Get conversation should return conversation with messages."""
        mock_agent.aget_state.return_value = MagicMock(values={
            "messages": [MagicMock(type="user", content="Hello")]
        })
        resp = await client.get(
            "/v1/conversations/conv-123",
            headers={"X-Auth-Token": valid_token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "conversation" in data
        assert "messages" in data

    @pytest.mark.asyncio
    async def test_get_nonexistent_conversation(self, client, valid_token, mock_db):
        """Get nonexistent conversation should return 404."""
        mock_db.get_conversation.return_value = None
        resp = await client.get(
            "/v1/conversations/nonexistent",
            headers={"X-Auth-Token": valid_token},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_other_user_conversation_forbidden(self, client, valid_token, mock_db):
        """Get conversation of another user should return 403."""
        mock_db.get_conversation.return_value = {
            "id": "conv-123",
            "user_id": 202,
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        resp = await client.get(
            "/v1/conversations/conv-123",
            headers={"X-Auth-Token": valid_token},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_conversation(self, client, valid_token, mock_db, mock_agent):
        """Delete conversation should succeed."""
        mock_db._db.execute = AsyncMock()
        mock_db._db.commit = AsyncMock()
        resp = await client.delete(
            "/v1/conversations/conv-123",
            headers={"X-Auth-Token": valid_token},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_delete_other_user_conversation_forbidden(self, client, valid_token, mock_db):
        """Delete conversation of another user should return 403."""
        mock_db.get_conversation.return_value = {
            "id": "conv-123",
            "user_id": 202,
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        resp = await client.delete(
            "/v1/conversations/conv-123",
            headers={"X-Auth-Token": valid_token},
        )
        assert resp.status_code == 403


class TestPermissionIsolation:
    """Tests for user permission isolation."""

    @pytest.mark.asyncio
    async def test_user_cannot_access_other_user_conversation(
        self, client, valid_token, another_user_token, mock_db
    ):
        """User A should not be able to access User B's conversation."""
        # User A creates a conversation
        mock_db.get_conversation.return_value = {
            "id": "conv-user-a",
            "user_id": 101,
            "created_at": time.time(),
            "updated_at": time.time(),
        }

        # User B tries to access it
        mock_db.get_conversation.return_value = {
            "id": "conv-user-a",
            "user_id": 101,  # Still belongs to user A
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        resp = await client.get(
            "/v1/conversations/conv-user-a",
            headers={"X-Auth-Token": another_user_token},
        )
        assert resp.status_code == 403
