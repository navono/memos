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
        """search_memos should return list of memos from Connect API."""
        client._http.post = AsyncMock(return_value=_mock_response(json_data={
            "memos": [
                {"name": "memos/abc", "content": "Hello world"},
                {"name": "memos/def", "content": "Test memo"},
            ]
        }))
        result = await client.search_memos("token", content="Hello")
        assert len(result) == 2
        assert result[0]["name"] == "memos/abc"
        call_args = client._http.post.call_args
        assert "MemoService/ListMemos" in call_args.args[0]
        assert "content.contains" in call_args.kwargs["json"]["filter"]

    async def test_search_memos_with_tag(self, client):
        """search_memos should include tag in filter."""
        client._http.post = AsyncMock(return_value=_mock_response(json_data={"memos": []}))
        await client.search_memos("token", tag="todo")
        call_args = client._http.post.call_args
        assert 'tag in ["todo"]' in call_args.kwargs["json"]["filter"]

    async def test_search_memos_with_creator_name(self, client):
        """search_memos should include creator in filter."""
        client._http.post = AsyncMock(return_value=_mock_response(json_data={"memos": []}))
        await client.search_memos("token", creator_name="pingeek")
        call_args = client._http.post.call_args
        assert 'creator == "users/pingeek"' in call_args.kwargs["json"]["filter"]

    async def test_search_memos_no_filter(self, client):
        """search_memos without criteria should not include filter."""
        client._http.post = AsyncMock(return_value=_mock_response(json_data={"memos": []}))
        await client.search_memos("token", limit=5)
        call_args = client._http.post.call_args
        assert "filter" not in call_args.kwargs["json"]
        assert call_args.kwargs["json"]["pageSize"] == 5

    async def test_search_memos_sends_auth_header(self, client):
        """search_memos should send Authorization header."""
        client._http.post = AsyncMock(return_value=_mock_response(json_data={"memos": []}))
        await client.search_memos("my-token")
        call_args = client._http.post.call_args
        assert call_args.kwargs["headers"]["Authorization"] == "Bearer my-token"

    async def test_get_memo_returns_data(self, client):
        """get_memo should return memo data."""
        client._http.post = AsyncMock(return_value=_mock_response(json_data={
            "name": "memos/abc", "content": "Full memo content"
        }))
        result = await client.get_memo("token", "memos/abc")
        assert result is not None
        assert result["name"] == "memos/abc"
        assert result["content"] == "Full memo content"

    async def test_get_memo_returns_none_on_404(self, client):
        """get_memo should return None for 404 response."""
        client._http.post = AsyncMock(return_value=_mock_response(status_code=404))
        result = await client.get_memo("token", "memos/nonexistent")
        assert result is None

    async def test_get_memo_sends_auth_header(self, client):
        """get_memo should send Authorization header."""
        client._http.post = AsyncMock(return_value=_mock_response(json_data={"name": "memos/1"}))
        await client.get_memo("my-token", "memos/1")
        call_args = client._http.post.call_args
        assert call_args.kwargs["headers"]["Authorization"] == "Bearer my-token"

    async def test_create_memo_returns_data(self, client):
        """create_memo should return created memo data."""
        client._http.post = AsyncMock(return_value=_mock_response(json_data={
            "name": "memos/xyz", "content": "New memo", "visibility": "PRIVATE"
        }))
        result = await client.create_memo("token", "New memo")
        assert result["name"] == "memos/xyz"
        assert result["content"] == "New memo"
        call_args = client._http.post.call_args
        assert "MemoService/CreateMemo" in call_args.args[0]
        assert call_args.kwargs["json"]["content"] == "New memo"

    async def test_create_memo_with_visibility(self, client):
        """create_memo should pass custom visibility."""
        client._http.post = AsyncMock(return_value=_mock_response(json_data={
            "name": "memos/pub", "content": "Public memo", "visibility": "PUBLIC"
        }))
        await client.create_memo("token", "Public memo", "PUBLIC")
        call_args = client._http.post.call_args
        assert call_args.kwargs["json"]["visibility"] == "PUBLIC"

    async def test_list_tags_extracts_from_memos(self, client):
        """list_tags should extract unique tags from memos."""
        client._http.post = AsyncMock(return_value=_mock_response(json_data={
            "memos": [
                {"content": "a", "tags": ["todo", "work"]},
                {"content": "b", "tags": ["work", "personal"]},
            ]
        }))
        result = await client.list_tags("token")
        assert result == ["personal", "todo", "work"]

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
        client._http.post = AsyncMock(return_value=_mock_response(status_code=500))
        with pytest.raises(httpx.HTTPStatusError):
            await client.search_memos("token", content="test")

    async def test_list_resources_returns_data(self, client):
        """list_resources should return list of attachments."""
        client._http.post = AsyncMock(return_value=_mock_response(json_data={
            "attachments": [
                {"name": "attachments/1", "filename": "photo.jpg", "type": "image/jpeg", "size": 1024},
                {"name": "attachments/2", "filename": "doc.pdf", "type": "application/pdf", "size": 2048},
            ]
        }))
        result = await client.list_resources("token")
        assert len(result) == 2
        assert result[0]["filename"] == "photo.jpg"
        call_args = client._http.post.call_args
        assert "AttachmentService/ListAttachments" in call_args.args[0]

    async def test_list_resources_empty(self, client):
        """list_resources should return empty list when no attachments."""
        client._http.post = AsyncMock(return_value=_mock_response(json_data={"attachments": []}))
        result = await client.list_resources("token")
        assert result == []

    async def test_create_resource_returns_data(self, client):
        """create_resource should POST and return created resource."""
        client._http.post = AsyncMock(return_value=_mock_response(json_data={
            "name": "attachments/3", "filename": "img.png", "externalLink": "https://x.com/img.png",
            "type": "image/png", "size": 0,
        }))
        result = await client.create_resource("token", "img.png", "https://x.com/img.png", "image/png")
        assert result["name"] == "attachments/3"
        call_args = client._http.post.call_args
        assert "AttachmentService/CreateAttachment" in call_args.args[0]
        assert call_args.kwargs["json"]["filename"] == "img.png"

    async def test_create_resource_without_type(self, client):
        """create_resource should omit type when empty."""
        client._http.post = AsyncMock(return_value=_mock_response(json_data={
            "name": "attachments/4", "filename": "f.txt", "externalLink": "http://x", "type": "", "size": 0,
        }))
        await client.create_resource("token", "f.txt", "http://x")
        call_args = client._http.post.call_args
        assert "type" not in call_args.kwargs["json"]

    async def test_delete_resource_sends_request(self, client):
        """delete_resource should call DeleteAttachment."""
        client._http.post = AsyncMock(return_value=_mock_response(json_data={}))
        result = await client.delete_resource("token", "attachments/7")
        assert result is True
        call_args = client._http.post.call_args
        assert "AttachmentService/DeleteAttachment" in call_args.args[0]
        assert call_args.kwargs["json"]["name"] == "attachments/7"
