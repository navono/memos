"""Integration tests for agent service.

These tests require both Memos backend (port 5230) and Agent service (port 8082) to be running.
Run with: pytest -m integration tests/integration/
Or run all tests including integration: pytest -m "integration or not integration"
"""

import json

import pytest

AGENT_URL = "http://localhost:8082"


@pytest.mark.integration
class TestAuth:
    """Integration tests for authentication."""

    def test_healthz_no_auth(self, http):
        resp = http.get(f"{AGENT_URL}/v1/healthz")
        assert resp.status_code == 200

    def test_chat_no_token(self, http):
        resp = http.post(f"{AGENT_URL}/v1/chat", json={"message": "hi"})
        assert resp.status_code == 401

    def test_chat_invalid_token(self, http):
        resp = http.post(
            f"{AGENT_URL}/v1/chat",
            headers={"X-Auth-Token": "invalid.token.here"},
            json={"message": "hi"},
        )
        assert resp.status_code == 401

    def test_chat_valid_token(self, http, memos_token):
        resp = http.post(
            f"{AGENT_URL}/v1/chat",
            headers={"X-Auth-Token": memos_token},
            json={"message": "Hello"},
        )
        assert resp.status_code == 200

    def test_chat_bearer_token(self, http, memos_token):
        resp = http.post(
            f"{AGENT_URL}/v1/chat",
            headers={"Authorization": f"Bearer {memos_token}"},
            json={"message": "Hello"},
        )
        assert resp.status_code == 200


@pytest.mark.integration
class TestChat:
    """Integration tests for chat functionality."""

    def test_basic_chat(self, http, memos_token, seed_test_data):
        """Basic chat returns SSE stream with content and done."""
        with http.stream(
            "POST",
            f"{AGENT_URL}/v1/chat",
            headers={"X-Auth-Token": memos_token},
            json={"message": "你好"},
        ) as resp:
            assert resp.status_code == 200
            events = _parse_sse(resp)
            contents = [e["content"] for e in events if "content" in e]
            done = [e for e in events if "done" in e]
            assert len(contents) > 0, "Should return content chunks"
            assert len(done) == 1, "Should end with done event"
            assert "conversation_id" in done[0]

    def test_tool_call_list_tags(self, http, memos_token, seed_test_data):
        """Agent should call list_tags tool and return seeded tags."""
        with http.stream(
            "POST",
            f"{AGENT_URL}/v1/chat",
            headers={"X-Auth-Token": memos_token},
            json={"message": "List my tags"},
        ) as resp:
            events = _parse_sse(resp)
            content = "".join(e.get("content", "") for e in events if "content" in e)
            assert len(content) > 0, "Should have response content"
            assert "todo" in content.lower() or "work" in content.lower(), (
                f"Should list seeded tags, got: {content}"
            )

    def test_tool_call_search_memos(self, http, memos_token, seed_test_data):
        """Agent should call search_memos tool and find seeded data."""
        with http.stream(
            "POST",
            f"{AGENT_URL}/v1/chat",
            headers={"X-Auth-Token": memos_token},
            json={"message": "Search my memos for groceries"},
        ) as resp:
            events = _parse_sse(resp)
            content = "".join(e.get("content", "") for e in events if "content" in e)
            assert len(content) > 0, "Should have response content"
            assert "milk" in content.lower() or "groceries" in content.lower(), (
                f"Should find seeded memo about groceries, got: {content}"
            )

    def test_tool_call_get_memo(self, http, memos_token, seed_test_data):
        """Agent should call get_memo tool to retrieve a specific memo."""
        with http.stream(
            "POST",
            f"{AGENT_URL}/v1/chat",
            headers={"X-Auth-Token": memos_token},
            json={"message": "Show me the memo about birthday ideas"},
        ) as resp:
            events = _parse_sse(resp)
            content = "".join(e.get("content", "") for e in events if "content" in e)
            assert len(content) > 0, "Should have response content"
            assert "birthday" in content.lower() or "mom" in content.lower(), (
                f"Should find seeded memo about birthday, got: {content}"
            )

    def test_tool_call_create_memo(self, http, memos_token, seed_test_data):
        """Agent should call create_memo tool."""
        with http.stream(
            "POST",
            f"{AGENT_URL}/v1/chat",
            headers={"X-Auth-Token": memos_token},
            json={"message": "Create a memo: #test-integration pytest auto test"},
        ) as resp:
            events = _parse_sse(resp)
            content = "".join(e.get("content", "") for e in events if "content" in e)
            assert len(content) > 0, "Should have response content"

    def test_conversation_continuity(self, http, memos_token, seed_test_data):
        """Follow-up message in same conversation should work and return content."""
        with http.stream(
            "POST",
            f"{AGENT_URL}/v1/chat",
            headers={"X-Auth-Token": memos_token},
            json={"message": "我的名字是小明"},
        ) as resp:
            events = _parse_sse(resp)
            done = [e for e in events if "done" in e]
            assert len(done) == 1, "First message should complete"
            conv_id = done[0]["conversation_id"]
            assert conv_id, "Should have a conversation ID"

        # Follow-up in same conversation
        with http.stream(
            "POST",
            f"{AGENT_URL}/v1/chat",
            headers={"X-Auth-Token": memos_token},
            json={"message": "我叫什么名字？", "conversation_id": conv_id},
        ) as resp:
            events = _parse_sse(resp)
            done = [e for e in events if "done" in e]
            assert len(done) == 1, "Follow-up message should complete"
            # Same conversation ID means continuity is working
            assert done[0]["conversation_id"] == conv_id, (
                "Follow-up should use same conversation"
            )
            # Verify response has content (LLM may not literally repeat the name)
            content = "".join(e.get("content", "") for e in events if "content" in e)
            assert len(content) > 0, "Should have response content in follow-up"


@pytest.mark.integration
class TestConversations:
    """Integration tests for conversation CRUD."""

    def test_list_conversations(self, http, memos_token, seed_test_data):
        resp = http.get(
            f"{AGENT_URL}/v1/conversations",
            headers={"X-Auth-Token": memos_token},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_conversation(self, http, memos_token, seed_test_data):
        # Create a conversation first
        with http.stream(
            "POST",
            f"{AGENT_URL}/v1/chat",
            headers={"X-Auth-Token": memos_token},
            json={"message": "Test message"},
        ) as resp:
            events = _parse_sse(resp)
            done = [e for e in events if "done" in e]
            conv_id = done[0]["conversation_id"]

        resp = http.get(
            f"{AGENT_URL}/v1/conversations/{conv_id}",
            headers={"X-Auth-Token": memos_token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "conversation" in data
        assert "messages" in data
        assert len(data["messages"]) > 0

    def test_delete_conversation(self, http, memos_token, seed_test_data):
        # Create then delete
        with http.stream(
            "POST",
            f"{AGENT_URL}/v1/chat",
            headers={"X-Auth-Token": memos_token},
            json={"message": "To be deleted"},
        ) as resp:
            events = _parse_sse(resp)
            done = [e for e in events if "done" in e]
            conv_id = done[0]["conversation_id"]

        resp = http.delete(
            f"{AGENT_URL}/v1/conversations/{conv_id}",
            headers={"X-Auth-Token": memos_token},
        )
        assert resp.status_code == 200

        # Verify deleted
        resp = http.get(
            f"{AGENT_URL}/v1/conversations/{conv_id}",
            headers={"X-Auth-Token": memos_token},
        )
        assert resp.status_code == 404

    def test_get_nonexistent_conversation(self, http, memos_token):
        resp = http.get(
            f"{AGENT_URL}/v1/conversations/nonexistent",
            headers={"X-Auth-Token": memos_token},
        )
        assert resp.status_code == 404

    def test_system_prompt_not_repeated(self, http, memos_token, seed_test_data):
        """System prompt should only appear once in conversation history."""
        with http.stream(
            "POST",
            f"{AGENT_URL}/v1/chat",
            headers={"X-Auth-Token": memos_token},
            json={"message": "First message"},
        ) as resp:
            events = _parse_sse(resp)
            done = [e for e in events if "done" in e]
            conv_id = done[0]["conversation_id"]

        # Second message
        with http.stream(
            "POST",
            f"{AGENT_URL}/v1/chat",
            headers={"X-Auth-Token": memos_token},
            json={"message": "Second message", "conversation_id": conv_id},
        ) as resp:
            _parse_sse(resp)

        # Check messages
        resp = http.get(
            f"{AGENT_URL}/v1/conversations/{conv_id}",
            headers={"X-Auth-Token": memos_token},
        )
        data = resp.json()
        roles = [m["role"] for m in data["messages"]]
        system_count = roles.count("system")
        assert system_count == 1, f"Expected 1 system message, got {system_count}. Roles: {roles}"

        # Cleanup
        http.delete(
            f"{AGENT_URL}/v1/conversations/{conv_id}",
            headers={"X-Auth-Token": memos_token},
        )


def _parse_sse(resp):
    """Parse SSE stream into a list of event dicts."""
    events = []
    for line in resp.iter_lines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events
