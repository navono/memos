import json

from langchain_core.tools import tool
from langgraph.config import get_config

from agent.tools.memos_client import MemosClient

_memos_client: MemosClient | None = None


def set_memos_client(client: MemosClient) -> None:
    global _memos_client
    _memos_client = client


def _get_request_context() -> tuple[MemosClient, str, int, str]:
    if _memos_client is None:
        raise RuntimeError("MemosClient not initialized")
    config = get_config()
    auth_token = config["configurable"]["auth_token"]
    user_id = config["configurable"]["user_id"]
    username = config["configurable"].get("username", "")
    return _memos_client, auth_token, user_id, username


@tool
async def search_memos(
    content: str | None = None,
    tag: str | None = None,
    limit: int = 10,
) -> str:
    """Search through user's memos. Can filter by content keyword or tag. If no filters provided, returns the most recent memos. Use this when the user asks about recent activity, what they've been doing, or to find specific memos."""
    client, auth_token, user_id, username = _get_request_context()
    memos = await client.search_memos(
        auth_token,
        creator_name=username or None,
        content=content,
        tag=tag,
        limit=limit,
    )
    if not memos:
        return "No memos found."
    lines = []
    for i, m in enumerate(memos, 1):
        text = m.get("content", "")
        snippet = text[:200] + "..." if len(text) > 200 else text
        created = m.get("createTime", "")
        tags = m.get("tags", [])
        tag_str = " ".join(f"#{t}" for t in tags) if tags else ""
        line = f"{i}. {created}"
        if tag_str:
            line += f" {tag_str}"
        line += f"\n   {snippet}"
        lines.append(line)
    return "\n".join(lines)


@tool
async def get_memo(memo_name: str) -> str:
    """Get the full content of a specific memo by its resource name (e.g. 'memos/abc123')."""
    client, auth_token, _, _ = _get_request_context()
    memo = await client.get_memo(auth_token, memo_name)
    if not memo:
        return f"Memo {memo_name} not found."
    tags = memo.get("tags", [])
    tag_str = " ".join(f"#{t}" for t in tags) if tags else ""
    lines = [f"Name: {memo.get('name', '')}"]
    lines.append(f"Created: {memo.get('createTime', '')}")
    if tag_str:
        lines.append(f"Tags: {tag_str}")
    lines.append(f"Visibility: {memo.get('visibility', '')}")
    lines.append(f"Content:\n{memo.get('content', '')}")
    return "\n".join(lines)


@tool
async def create_memo(content: str, visibility: str = "PRIVATE") -> str:
    """Create a new memo with the given content. The content supports Markdown formatting."""
    client, auth_token, _, _ = _get_request_context()
    memo = await client.create_memo(auth_token, content, visibility)
    return json.dumps({
        "name": memo.get("name", ""),
        "content": memo.get("content", ""),
        "visibility": memo.get("visibility", ""),
    }, ensure_ascii=False)


@tool
async def list_tags() -> str:
    """List all tags used by the user. Returns tag names."""
    client, auth_token, _, _ = _get_request_context()
    tags = await client.list_tags(auth_token)
    if not tags:
        return "No tags found."
    return json.dumps(tags, ensure_ascii=False)


@tool
async def list_resources(limit: int = 20) -> str:
    """List all resources/attachments owned by the user. Returns name, filename, type, and size."""
    client, auth_token, _, _ = _get_request_context()
    resources = await client.list_resources(auth_token, limit=limit)
    if not resources:
        return "No resources found."
    results = []
    for r in resources:
        entry = {
            "name": r.get("name", ""),
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
    client, auth_token, _, _ = _get_request_context()
    resource = await client.create_resource(auth_token, filename, external_link, resource_type)
    return json.dumps({
        "name": resource.get("name", ""),
        "filename": resource.get("filename", ""),
        "externalLink": resource.get("externalLink", ""),
        "type": resource.get("type", ""),
        "size": resource.get("size", 0),
    }, ensure_ascii=False)


@tool
async def update_resource(resource_name: str, filename: str) -> str:
    """Rename a resource's filename. Provide the resource name (e.g. 'attachments/abc123') and the new filename."""
    client, auth_token, _, _ = _get_request_context()
    resource = await client.update_resource(auth_token, resource_name, filename)
    return json.dumps({
        "name": resource.get("name", ""),
        "filename": resource.get("filename", ""),
    }, ensure_ascii=False)


@tool
async def delete_resource(resource_name: str) -> str:
    """Delete a resource/attachment by its resource name (e.g. 'attachments/abc123'). This action is irreversible."""
    client, auth_token, _, _ = _get_request_context()
    await client.delete_resource(auth_token, resource_name)
    return f"Resource {resource_name} deleted."
