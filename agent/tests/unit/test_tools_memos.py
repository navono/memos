"""Unit tests for tools/memos module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.tools.memos import (
    create_memo,
    create_resource,
    delete_resource,
    get_memo,
    list_resources,
    list_tags,
    search_memos,
    set_memos_client,
    update_resource,
)
from agent.tools.memos_client import MemosClient


@pytest.fixture
def mock_client():
    """Create a mocked MemosClient."""
    client = MagicMock(spec=MemosClient)
    set_memos_client(client)
    return client


@pytest.fixture
def mock_config():
    """Mock langgraph get_config to return test context."""
    with patch("agent.tools.memos.get_config") as mock:
        mock.return_value = {
            "configurable": {
                "auth_token": "test-token",
                "user_id": 101,
                "username": "testuser",
            }
        }
        yield mock


@pytest.mark.asyncio
class TestSearchMemos:
    """Tests for search_memos tool."""

    async def test_search_by_content(self, mock_client, mock_config):
        """search_memos should search by content keyword."""
        mock_client.search_memos = AsyncMock(return_value=[
            {"name": "memos/1", "content": "Hello world"},
            {"name": "memos/2", "content": "Hello there"},
        ])
        result = await search_memos.ainvoke({"content": "Hello"})
        assert "Hello world" in result
        mock_client.search_memos.assert_called_once()

    async def test_search_by_tag(self, mock_client, mock_config):
        """search_memos should search by tag."""
        mock_client.search_memos = AsyncMock(return_value=[
            {"name": "memos/1", "content": "#todo Task 1"},
        ])
        result = await search_memos.ainvoke({"tag": "todo"})
        assert "todo" in result.lower() or "Task 1" in result

    async def test_search_no_criteria_returns_memos(self, mock_client, mock_config):
        """search_memos without criteria should return recent memos (no longer requires criteria)."""
        mock_client.search_memos = AsyncMock(return_value=[
            {"name": "memos/1", "content": "A memo"},
        ])
        result = await search_memos.ainvoke({})
        assert "A memo" in result

    async def test_search_no_results_returns_message(self, mock_client, mock_config):
        """search_memos with no results should return appropriate message."""
        mock_client.search_memos = AsyncMock(return_value=[])
        result = await search_memos.ainvoke({"content": "nonexistent"})
        assert "no memo" in result.lower() or "not found" in result.lower()

    async def test_search_passes_creator_name(self, mock_client, mock_config):
        """search_memos should filter by creator_name from config."""
        mock_client.search_memos = AsyncMock(return_value=[])
        await search_memos.ainvoke({"content": "test"})
        call_args = mock_client.search_memos.call_args
        assert call_args.kwargs["creator_name"] == "testuser"


@pytest.mark.asyncio
class TestGetMemo:
    """Tests for get_memo tool."""

    async def test_get_existing_memo(self, mock_client, mock_config):
        """get_memo should return full memo content."""
        mock_client.get_memo = AsyncMock(return_value={
            "name": "memos/abc",
            "content": "Full memo content here",
            "createTime": "2026-01-01T00:00:00Z",
            "tags": ["todo", "work"],
            "visibility": "PRIVATE",
        })
        result = await get_memo.ainvoke({"memo_name": "memos/abc"})
        assert "Full memo content here" in result
        assert "todo" in result

    async def test_get_nonexistent_memo(self, mock_client, mock_config):
        """get_memo should return not found message for invalid name."""
        mock_client.get_memo = AsyncMock(return_value=None)
        result = await get_memo.ainvoke({"memo_name": "memos/nonexistent"})
        assert "not found" in result.lower()

    async def test_get_memo_passes_auth_token(self, mock_client, mock_config):
        """get_memo should use auth_token from config."""
        mock_client.get_memo = AsyncMock(return_value={"name": "memos/1", "content": "test"})
        await get_memo.ainvoke({"memo_name": "memos/1"})
        call_args = mock_client.get_memo.call_args
        assert call_args.args[0] == "test-token"


@pytest.mark.asyncio
class TestCreateMemo:
    """Tests for create_memo tool."""

    async def test_create_memo_default_visibility(self, mock_client, mock_config):
        """create_memo should default to PRIVATE visibility."""
        mock_client.create_memo = AsyncMock(return_value={
            "name": "memos/new",
            "content": "New memo",
            "visibility": "PRIVATE",
        })
        result = await create_memo.ainvoke({"content": "New memo"})
        assert "New memo" in result
        call_args = mock_client.create_memo.call_args
        assert call_args.args[2] == "PRIVATE"

    async def test_create_memo_returns_name(self, mock_client, mock_config):
        """create_memo should return the new memo name."""
        mock_client.create_memo = AsyncMock(return_value={
            "name": "memos/xyz",
            "content": "Test",
            "visibility": "PRIVATE",
        })
        result = await create_memo.ainvoke({"content": "Test"})
        assert "memos/xyz" in result


@pytest.mark.asyncio
class TestListTags:
    """Tests for list_tags tool."""

    async def test_list_tags_returns_tags(self, mock_client, mock_config):
        """list_tags should return list of tags."""
        mock_client.list_tags = AsyncMock(return_value=["todo", "work", "personal"])
        result = await list_tags.ainvoke({})
        assert "todo" in result
        assert "work" in result

    async def test_list_tags_no_tags(self, mock_client, mock_config):
        """list_tags should return message when no tags exist."""
        mock_client.list_tags = AsyncMock(return_value=[])
        result = await list_tags.ainvoke({})
        assert "no tag" in result.lower()


@pytest.mark.asyncio
class TestToolContext:
    """Tests for tool context handling."""

    async def test_no_client_raises_error(self, mock_config):
        """Tools should raise error if client not initialized."""
        set_memos_client(None)
        with pytest.raises(RuntimeError, match="not initialized"):
            await search_memos.ainvoke({"content": "test"})

    async def test_missing_config_raises_error(self, mock_client):
        """Tools should handle missing config gracefully."""
        with patch("agent.tools.memos.get_config", return_value={}):
            with pytest.raises(KeyError):
                await search_memos.ainvoke({"content": "test"})


@pytest.mark.asyncio
class TestDeleteResource:
    """Tests for delete_resource tool."""

    async def test_delete_resource_success(self, mock_client, mock_config):
        """delete_resource should return success message."""
        mock_client.delete_resource = AsyncMock(return_value=True)
        result = await delete_resource.ainvoke({"resource_name": "attachments/7"})
        assert "attachments/7" in result
        assert "deleted" in result.lower()
