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
            }
        }
        yield mock


@pytest.mark.asyncio
class TestSearchMemos:
    """Tests for search_memos tool."""

    async def test_search_by_content(self, mock_client, mock_config):
        """search_memos should search by content keyword."""
        mock_client.search_memos = AsyncMock(return_value=[
            {"id": 1, "content": "Hello world"},
            {"id": 2, "content": "Hello there"},
        ])
        result = await search_memos.ainvoke({"content": "Hello"})
        assert "Hello world" in result
        mock_client.search_memos.assert_called_once()

    async def test_search_by_tag(self, mock_client, mock_config):
        """search_memos should search by tag."""
        mock_client.search_memos = AsyncMock(return_value=[
            {"id": 1, "content": "#todo Task 1"},
        ])
        result = await search_memos.ainvoke({"tag": "todo"})
        assert "todo" in result.lower() or "Task 1" in result

    async def test_search_no_criteria_returns_message(self, mock_client, mock_config):
        """search_memos without criteria should return helpful message."""
        result = await search_memos.ainvoke({})
        assert "provide" in result.lower() or "criterion" in result.lower()

    async def test_search_no_results_returns_message(self, mock_client, mock_config):
        """search_memos with no results should return appropriate message."""
        mock_client.search_memos = AsyncMock(return_value=[])
        result = await search_memos.ainvoke({"content": "nonexistent"})
        assert "no memo" in result.lower() or "not found" in result.lower()

    async def test_search_truncates_long_content(self, mock_client, mock_config):
        """search_memos should truncate long content in results."""
        long_content = "x" * 500
        mock_client.search_memos = AsyncMock(return_value=[
            {"id": 1, "content": long_content},
        ])
        result = await search_memos.ainvoke({"content": "x"})
        assert "..." in result

    async def test_search_passes_user_id(self, mock_client, mock_config):
        """search_memos should filter by user_id from config."""
        mock_client.search_memos = AsyncMock(return_value=[])
        await search_memos.ainvoke({"content": "test"})
        call_args = mock_client.search_memos.call_args
        assert call_args.kwargs["creator_id"] == 101


@pytest.mark.asyncio
class TestGetMemo:
    """Tests for get_memo tool."""

    async def test_get_existing_memo(self, mock_client, mock_config):
        """get_memo should return full memo content."""
        mock_client.get_memo = AsyncMock(return_value={
            "id": 42,
            "content": "Full memo content here",
            "createdTs": 1234567890,
            "tags": ["todo", "work"],
            "visibility": "PRIVATE",
        })
        result = await get_memo.ainvoke({"memo_id": 42})
        assert "Full memo content here" in result
        assert "todo" in result

    async def test_get_nonexistent_memo(self, mock_client, mock_config):
        """get_memo should return not found message for invalid ID."""
        mock_client.get_memo = AsyncMock(return_value=None)
        result = await get_memo.ainvoke({"memo_id": 999})
        assert "not found" in result.lower()

    async def test_get_memo_passes_auth_token(self, mock_client, mock_config):
        """get_memo should use auth_token from config."""
        mock_client.get_memo = AsyncMock(return_value={"id": 1, "content": "test"})
        await get_memo.ainvoke({"memo_id": 1})
        call_args = mock_client.get_memo.call_args
        assert call_args.args[0] == "test-token"


@pytest.mark.asyncio
class TestCreateMemo:
    """Tests for create_memo tool."""

    async def test_create_memo_default_visibility(self, mock_client, mock_config):
        """create_memo should default to PRIVATE visibility."""
        mock_client.create_memo = AsyncMock(return_value={
            "id": 3,
            "content": "New memo",
            "visibility": "PRIVATE",
        })
        result = await create_memo.ainvoke({"content": "New memo"})
        assert "New memo" in result
        call_args = mock_client.create_memo.call_args
        assert call_args.args[2] == "PRIVATE"

    async def test_create_memo_custom_visibility(self, mock_client, mock_config):
        """create_memo should accept custom visibility."""
        mock_client.create_memo = AsyncMock(return_value={
            "id": 4,
            "content": "Public memo",
            "visibility": "PUBLIC",
        })
        result = await create_memo.ainvoke({"content": "Public memo", "visibility": "PUBLIC"})
        call_args = mock_client.create_memo.call_args
        assert call_args.args[2] == "PUBLIC"

    async def test_create_memo_returns_id(self, mock_client, mock_config):
        """create_memo should return the new memo ID."""
        mock_client.create_memo = AsyncMock(return_value={
            "id": 123,
            "content": "Test",
            "visibility": "PRIVATE",
        })
        result = await create_memo.ainvoke({"content": "Test"})
        assert "123" in result


@pytest.mark.asyncio
class TestListTags:
    """Tests for list_tags tool."""

    async def test_list_tags_returns_tags(self, mock_client, mock_config):
        """list_tags should return list of tags."""
        mock_client.list_tags = AsyncMock(return_value=["todo", "work", "personal"])
        result = await list_tags.ainvoke({})
        assert "todo" in result
        assert "work" in result
        assert "personal" in result

    async def test_list_tags_no_tags(self, mock_client, mock_config):
        """list_tags should return message when no tags exist."""
        mock_client.list_tags = AsyncMock(return_value=[])
        result = await list_tags.ainvoke({})
        assert "no tag" in result.lower()

    async def test_list_tags_passes_auth_token(self, mock_client, mock_config):
        """list_tags should use auth_token from config."""
        mock_client.list_tags = AsyncMock(return_value=[])
        await list_tags.ainvoke({})
        call_args = mock_client.list_tags.call_args
        assert call_args.args[0] == "test-token"


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
class TestListResources:
    """Tests for list_resources tool."""

    async def test_list_resources_returns_data(self, mock_client, mock_config):
        """list_resources should return resource list."""
        mock_client.list_resources = AsyncMock(return_value=[
            {"id": 1, "filename": "photo.jpg", "type": "image/jpeg", "size": 1024, "externalLink": "https://example.com/photo.jpg"},
            {"id": 2, "filename": "doc.pdf", "type": "application/pdf", "size": 2048},
        ])
        result = await list_resources.ainvoke({})
        assert "photo.jpg" in result
        assert "doc.pdf" in result
        mock_client.list_resources.assert_called_once()

    async def test_list_resources_empty(self, mock_client, mock_config):
        """list_resources should return message when no resources."""
        mock_client.list_resources = AsyncMock(return_value=[])
        result = await list_resources.ainvoke({})
        assert "no resource" in result.lower()

    async def test_list_resources_passes_limit(self, mock_client, mock_config):
        """list_resources should pass limit parameter."""
        mock_client.list_resources = AsyncMock(return_value=[])
        await list_resources.ainvoke({"limit": 5})
        call_args = mock_client.list_resources.call_args
        assert call_args.kwargs["limit"] == 5

    async def test_list_resources_passes_auth_token(self, mock_client, mock_config):
        """list_resources should use auth_token from config."""
        mock_client.list_resources = AsyncMock(return_value=[])
        await list_resources.ainvoke({})
        call_args = mock_client.list_resources.call_args
        assert call_args.args[0] == "test-token"


@pytest.mark.asyncio
class TestCreateResource:
    """Tests for create_resource tool."""

    async def test_create_resource_returns_data(self, mock_client, mock_config):
        """create_resource should return created resource data."""
        mock_client.create_resource = AsyncMock(return_value={
            "id": 10, "filename": "image.png", "externalLink": "https://example.com/img.png",
            "type": "image/png", "size": 0,
        })
        result = await create_resource.ainvoke({
            "filename": "image.png", "external_link": "https://example.com/img.png",
        })
        assert "10" in result
        assert "image.png" in result
        mock_client.create_resource.assert_called_once()

    async def test_create_resource_with_type(self, mock_client, mock_config):
        """create_resource should pass resource_type."""
        mock_client.create_resource = AsyncMock(return_value={
            "id": 11, "filename": "data.json", "externalLink": "https://example.com/data.json",
            "type": "application/json", "size": 0,
        })
        await create_resource.ainvoke({
            "filename": "data.json",
            "external_link": "https://example.com/data.json",
            "resource_type": "application/json",
        })
        call_args = mock_client.create_resource.call_args
        assert call_args.args[3] == "application/json"

    async def test_create_resource_passes_auth_token(self, mock_client, mock_config):
        """create_resource should use auth_token from config."""
        mock_client.create_resource = AsyncMock(return_value={
            "id": 1, "filename": "f.txt", "externalLink": "http://x", "type": "", "size": 0,
        })
        await create_resource.ainvoke({"filename": "f.txt", "external_link": "http://x"})
        call_args = mock_client.create_resource.call_args
        assert call_args.args[0] == "test-token"


@pytest.mark.asyncio
class TestUpdateResource:
    """Tests for update_resource tool."""

    async def test_update_resource_returns_data(self, mock_client, mock_config):
        """update_resource should return updated resource data."""
        mock_client.update_resource = AsyncMock(return_value={
            "id": 5, "filename": "renamed.jpg",
        })
        result = await update_resource.ainvoke({"resource_id": 5, "filename": "renamed.jpg"})
        assert "renamed.jpg" in result
        assert "5" in result

    async def test_update_resource_passes_args(self, mock_client, mock_config):
        """update_resource should pass resource_id and filename."""
        mock_client.update_resource = AsyncMock(return_value={"id": 5, "filename": "new.png"})
        await update_resource.ainvoke({"resource_id": 5, "filename": "new.png"})
        call_args = mock_client.update_resource.call_args
        assert call_args.args[1] == 5
        assert call_args.args[2] == "new.png"


@pytest.mark.asyncio
class TestDeleteResource:
    """Tests for delete_resource tool."""

    async def test_delete_resource_success(self, mock_client, mock_config):
        """delete_resource should return success message."""
        mock_client.delete_resource = AsyncMock(return_value=True)
        result = await delete_resource.ainvoke({"resource_id": 7})
        assert "7" in result
        assert "deleted" in result.lower()

    async def test_delete_resource_passes_args(self, mock_client, mock_config):
        """delete_resource should pass resource_id and auth_token."""
        mock_client.delete_resource = AsyncMock(return_value=True)
        await delete_resource.ainvoke({"resource_id": 7})
        call_args = mock_client.delete_resource.call_args
        assert call_args.args[0] == "test-token"
        assert call_args.args[1] == 7
