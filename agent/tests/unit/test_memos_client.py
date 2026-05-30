"""Unit tests for memos_client module."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from agent.tools.memos_client import MemosClient


@pytest.fixture
def client():
    """Create a MemosClient with mocked HTTP client."""
    c = MemosClient("http://localhost:5230")
    c._http = MagicMock(spec=httpx.AsyncClient)
    return c


def _mock_response(status_code=200, json_data=None):
    """Create a mock httpx response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or []
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message="Error", request=MagicMock(), response=resp
        )
    return resp


@pytest.mark.asyncio
class TestMemosClient:
    """Tests for MemosClient class."""

    async def test_search_memos_returns_results(self, client):
        """search_memos should return list of memos."""
        client._http.get = AsyncMock(return_value=_mock_response(json_data=[
            {"id": 1, "content": "Hello world"},
            {"id": 2, "content": "Test memo"},
        ]))
        result = await client.search_memos("token", content="Hello")
        assert len(result) == 2
        assert result[0]["id"] == 1
        client._http.get.assert_called_once()
        call_args = client._http.get.call_args
        assert call_args.kwargs["params"]["content"] == "Hello"

    async def test_search_memos_with_tag(self, client):
        """search_memos should pass tag parameter."""
        client._http.get = AsyncMock(return_value=_mock_response(json_data=[]))
        await client.search_memos("token", tag="todo")
        call_args = client._http.get.call_args
        assert call_args.kwargs["params"]["tag"] == "todo"

    async def test_search_memos_with_creator_id(self, client):
        """search_memos should pass creator_id parameter."""
        client._http.get = AsyncMock(return_value=_mock_response(json_data=[]))
        await client.search_memos("token", creator_id=101)
        call_args = client._http.get.call_args
        assert call_args.kwargs["params"]["creatorId"] == 101

    async def test_search_memos_with_pagination(self, client):
        """search_memos should pass limit and offset."""
        client._http.get = AsyncMock(return_value=_mock_response(json_data=[]))
        await client.search_memos("token", limit=5, offset=10)
        call_args = client._http.get.call_args
        assert call_args.kwargs["params"]["limit"] == 5
        assert call_args.kwargs["params"]["offset"] == 10

    async def test_search_memos_sends_auth_header(self, client):
        """search_memos should send Authorization header."""
        client._http.get = AsyncMock(return_value=_mock_response(json_data=[]))
        await client.search_memos("my-token")
        call_args = client._http.get.call_args
        assert call_args.kwargs["headers"]["Authorization"] == "Bearer my-token"

    async def test_get_memo_returns_data(self, client):
        """get_memo should return memo data."""
        client._http.get = AsyncMock(return_value=_mock_response(json_data={
            "id": 42, "content": "Full memo content"
        }))
        result = await client.get_memo("token", 42)
        assert result is not None
        assert result["id"] == 42
        assert result["content"] == "Full memo content"

    async def test_get_memo_returns_none_on_404(self, client):
        """get_memo should return None for 404 response."""
        client._http.get = AsyncMock(return_value=_mock_response(status_code=404))
        result = await client.get_memo("token", 999)
        assert result is None

    async def test_get_memo_sends_auth_header(self, client):
        """get_memo should send Authorization header."""
        client._http.get = AsyncMock(return_value=_mock_response(json_data={"id": 1}))
        await client.get_memo("my-token", 1)
        call_args = client._http.get.call_args
        assert call_args.kwargs["headers"]["Authorization"] == "Bearer my-token"

    async def test_create_memo_returns_data(self, client):
        """create_memo should return created memo data."""
        client._http.post = AsyncMock(return_value=_mock_response(json_data={
            "id": 3, "content": "New memo", "visibility": "PRIVATE"
        }))
        result = await client.create_memo("token", "New memo")
        assert result["id"] == 3
        assert result["content"] == "New memo"
        call_args = client._http.post.call_args
        assert call_args.kwargs["json"]["content"] == "New memo"
        assert call_args.kwargs["json"]["visibility"] == "PRIVATE"

    async def test_create_memo_with_visibility(self, client):
        """create_memo should pass custom visibility."""
        client._http.post = AsyncMock(return_value=_mock_response(json_data={
            "id": 4, "content": "Public memo", "visibility": "PUBLIC"
        }))
        await client.create_memo("token", "Public memo", "PUBLIC")
        call_args = client._http.post.call_args
        assert call_args.kwargs["json"]["visibility"] == "PUBLIC"

    async def test_create_memo_sends_auth_header(self, client):
        """create_memo should send Authorization header."""
        client._http.post = AsyncMock(return_value=_mock_response(json_data={"id": 1}))
        await client.create_memo("my-token", "Test")
        call_args = client._http.post.call_args
        assert call_args.kwargs["headers"]["Authorization"] == "Bearer my-token"

    async def test_list_tags_returns_list(self, client):
        """list_tags should return list of tag strings."""
        client._http.get = AsyncMock(return_value=_mock_response(json_data=["todo", "work", "personal"]))
        result = await client.list_tags("token")
        assert result == ["todo", "work", "personal"]

    async def test_list_tags_sends_auth_header(self, client):
        """list_tags should send Authorization header."""
        client._http.get = AsyncMock(return_value=_mock_response(json_data=[]))
        await client.list_tags("my-token")
        call_args = client._http.get.call_args
        assert call_args.kwargs["headers"]["Authorization"] == "Bearer my-token"

    async def test_close_closes_http_client(self, client):
        """close should close the HTTP client."""
        client._http.aclose = AsyncMock()
        await client.close()
        client._http.aclose.assert_called_once()

    async def test_base_url_trailing_slash_stripped(self):
        """Constructor should strip trailing slash from base_url."""
        c = MemosClient("http://localhost:5230/")
        assert c._base_url == "http://localhost:5230"

    async def test_api_error_raises_exception(self, client):
        """HTTP error responses should raise HTTPStatusError."""
        client._http.get = AsyncMock(return_value=_mock_response(status_code=500))
        with pytest.raises(httpx.HTTPStatusError):
            await client.search_memos("token", content="test")
