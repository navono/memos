import json

from langchain_core.tools import tool
from langgraph.config import get_config

from agent.tools.memos_client import MemosClient

_memos_client: MemosClient | None = None


def set_memos_client(client: MemosClient) -> None:
    global _memos_client
    _memos_client = client


def _get_request_context() -> tuple[MemosClient, str, int]:
    if _memos_client is None:
        raise RuntimeError("MemosClient not initialized")
    config = get_config()
    auth_token = config["configurable"]["auth_token"]
    user_id = config["configurable"]["user_id"]
    return _memos_client, auth_token, user_id


@tool
async def search_memos(
    content: str | None = None,
    tag: str | None = None,
    limit: int = 10,
) -> str:
    """Search through user's memos by content keyword or tag. Returns a list of matching memos with id, content snippet, and creation date."""
    client, auth_token, user_id = _get_request_context()
    if not content and not tag:
        return "Please provide at least one search criterion: content keyword or tag name."
    memos = await client.search_memos(
        auth_token,
        creator_id=user_id,
        content=content,
        tag=tag,
        limit=limit,
    )
    if not memos:
        return "No memos found matching your search."
    results = []
    for m in memos:
        text = m.get("content", "")
        snippet = text[:200] + "..." if len(text) > 200 else text
        results.append(f"[id:{m['id']}] {snippet}")
    return json.dumps(results, ensure_ascii=False)


@tool
async def get_memo(memo_id: int) -> str:
    """Get the full content of a specific memo by its ID."""
    client, auth_token, _ = _get_request_context()
    memo = await client.get_memo(auth_token, memo_id)
    if not memo:
        return f"Memo with id {memo_id} not found."
    return json.dumps({
        "id": memo["id"],
        "content": memo.get("content", ""),
        "created_at": memo.get("createdTs"),
        "tags": memo.get("tags", []),
        "visibility": memo.get("visibility", ""),
    }, ensure_ascii=False)


@tool
async def create_memo(content: str, visibility: str = "PRIVATE") -> str:
    """Create a new memo with the given content. The content supports Markdown formatting."""
    client, auth_token, _ = _get_request_context()
    memo = await client.create_memo(auth_token, content, visibility)
    return json.dumps({
        "id": memo["id"],
        "content": memo.get("content", ""),
        "visibility": memo.get("visibility", ""),
    }, ensure_ascii=False)


@tool
async def list_tags() -> str:
    """List all tags used by the user. Returns tag names."""
    client, auth_token, _ = _get_request_context()
    tags = await client.list_tags(auth_token)
    if not tags:
        return "No tags found."
    return json.dumps(tags, ensure_ascii=False)


@tool
async def list_resources(limit: int = 20) -> str:
    """List all resources/attachments owned by the user. Returns id, filename, type, size, and external link."""
    client, auth_token, _ = _get_request_context()
    resources = await client.list_resources(auth_token, limit=limit)
    if not resources:
        return "No resources found."
    results = []
    for r in resources:
        entry = {
            "id": r["id"],
            "filename": r.get("filename", ""),
            "type": r.get("type", ""),
            "size": r.get("size", 0),
        }
        if r.get("externalLink"):
            entry["externalLink"] = r["externalLink"]
        results.append(entry)
    return json.dumps(results, ensure_ascii=False)


@tool
async def create_resource(filename: str, external_link: str, resource_type: str = "") -> str:
    """Create a new resource with an external link. Use this to attach online files/images to memos. The filename should include the extension."""
    client, auth_token, _ = _get_request_context()
    resource = await client.create_resource(auth_token, filename, external_link, resource_type)
    return json.dumps({
        "id": resource["id"],
        "filename": resource.get("filename", ""),
        "externalLink": resource.get("externalLink", ""),
        "type": resource.get("type", ""),
        "size": resource.get("size", 0),
    }, ensure_ascii=False)


@tool
async def update_resource(resource_id: int, filename: str) -> str:
    """Rename a resource's filename. Provide the resource ID and the new filename."""
    client, auth_token, _ = _get_request_context()
    resource = await client.update_resource(auth_token, resource_id, filename)
    return json.dumps({
        "id": resource["id"],
        "filename": resource.get("filename", ""),
    }, ensure_ascii=False)


@tool
async def delete_resource(resource_id: int) -> str:
    """Delete a resource/attachment by its ID. This action is irreversible."""
    client, auth_token, _ = _get_request_context()
    await client.delete_resource(auth_token, resource_id)
    return f"Resource {resource_id} deleted."
