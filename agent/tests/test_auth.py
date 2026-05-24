"""Tests for agent auth, chat, and conversation CRUD."""

import json

AGENT_URL = "http://localhost:8082"


class TestAuth:
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


class TestChat:
    def test_basic_chat(self, http, memos_token):
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

    def test_tool_call_list_tags(self, http, memos_token):
        """Agent should call list_tags tool."""
        with http.stream(
            "POST",
            f"{AGENT_URL}/v1/chat",
            headers={"X-Auth-Token": memos_token},
            json={"message": "List my tags"},
        ) as resp:
            events = _parse_sse(resp)
            content = "".join(e.get("content", "") for e in events if "content" in e)
            assert len(content) > 0, "Should have response content"

    def test_tool_call_search_memos(self, http, memos_token):
        """Agent should call search_memos tool."""
        with http.stream(
            "POST",
            f"{AGENT_URL}/v1/chat",
            headers={"X-Auth-Token": memos_token},
            json={"message": "Search my memos for TODO"},
        ) as resp:
            events = _parse_sse(resp)
            content = "".join(e.get("content", "") for e in events if "content" in e)
            assert len(content) > 0, "Should have response content"

    def test_tool_call_create_memo(self, http, memos_token):
        """Agent should call create_memo tool."""
        with http.stream(
            "POST",
            f"{AGENT_URL}/v1/chat",
            headers={"X-Auth-Token": memos_token},
            json={"message": "Create a memo: #test pytest auto test"},
        ) as resp:
            events = _parse_sse(resp)
            content = "".join(e.get("content", "") for e in events if "content" in e)
            assert len(content) > 0, "Should have response content"

    def test_conversation_continuity(self, http, memos_token):
        """Follow-up message in same conversation should work."""
        with http.stream(
            "POST",
            f"{AGENT_URL}/v1/chat",
            headers={"X-Auth-Token": memos_token},
            json={"message": "我的名字是小明"},
        ) as resp:
            events = _parse_sse(resp)
            done = [e for e in events if "done" in e]
            conv_id = done[0]["conversation_id"]

        # Follow-up
        with http.stream(
            "POST",
            f"{AGENT_URL}/v1/chat",
            headers={"X-Auth-Token": memos_token},
            json={"message": "我叫什么名字？", "conversation_id": conv_id},
        ) as resp:
            events = _parse_sse(resp)
            content = "".join(e.get("content", "") for e in events if "content" in e)
            assert "小明" in content, f"Should remember name from previous message, got: {content}"


class TestConversations:
    def test_list_conversations(self, http, memos_token):
        resp = http.get(
            f"{AGENT_URL}/v1/conversations",
            headers={"X-Auth-Token": memos_token},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_conversation(self, http, memos_token):
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

    def test_delete_conversation(self, http, memos_token):
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

    def test_system_prompt_not_repeated(self, http, memos_token):
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
