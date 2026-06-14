from typing import Any

import httpx

from agent.observability.logger import log


class MemosClient:
    """Client for the Memos Connect/gRPC API."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._http = httpx.AsyncClient(timeout=30.0, proxy=None, trust_env=False)

    async def close(self) -> None:
        await self._http.aclose()

    def _headers(self, auth_token: str) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        return headers

    async def search_memos(
        self,
        auth_token: str,
        *,
        creator_name: str | None = None,
        content: str | None = None,
        tag: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search memos using the Connect ListMemos API with CEL filter."""
        conditions: list[str] = []
        if creator_name is not None:
            conditions.append(f'creator == "users/{creator_name}"')
        if content:
            conditions.append(f'content.contains("{content}")')
        if tag:
            conditions.append(f'tag in ["{tag}"]')

        body: dict[str, Any] = {"pageSize": limit}
        if conditions:
            body["filter"] = " && ".join(conditions)

        resp = await self._http.post(
            f"{self._base_url}/memos.api.v1.MemoService/ListMemos",
            json=body,
            headers=self._headers(auth_token),
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("memos", [])

    async def get_memo(self, auth_token: str, memo_name: str) -> dict[str, Any] | None:
        """Get a memo by its resource name (e.g. 'memos/abc123')."""
        resp = await self._http.post(
            f"{self._base_url}/memos.api.v1.MemoService/GetMemo",
            json={"name": memo_name},
            headers=self._headers(auth_token),
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    async def create_memo(
        self,
        auth_token: str,
        content: str,
        visibility: str = "PRIVATE",
    ) -> dict[str, Any]:
        resp = await self._http.post(
            f"{self._base_url}/memos.api.v1.MemoService/CreateMemo",
            json={"content": content, "visibility": visibility},
            headers=self._headers(auth_token),
        )
        resp.raise_for_status()
        return resp.json()

    async def list_tags(self, auth_token: str) -> list[str]:
        """List all tags by fetching memos and extracting unique tags."""
        memos = await self.search_memos(auth_token, limit=100)
        tags: set[str] = set()
        for m in memos:
            for t in m.get("tags", []):
                tags.add(t)
        return sorted(tags)

    async def list_resources(
        self,
        auth_token: str,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        resp = await self._http.post(
            f"{self._base_url}/memos.api.v1.AttachmentService/ListAttachments",
            json={"pageSize": limit},
            headers=self._headers(auth_token),
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("attachments", [])

    async def get_resource(self, auth_token: str, resource_name: str) -> dict[str, Any] | None:
        """Get a resource by its name (e.g. 'attachments/abc123')."""
        resp = await self._http.post(
            f"{self._base_url}/memos.api.v1.AttachmentService/GetAttachment",
            json={"name": resource_name},
            headers=self._headers(auth_token),
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    async def create_resource(
        self,
        auth_token: str,
        filename: str,
        external_link: str,
        resource_type: str = "",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"filename": filename, "externalLink": external_link}
        if resource_type:
            payload["type"] = resource_type
        resp = await self._http.post(
            f"{self._base_url}/memos.api.v1.AttachmentService/CreateAttachment",
            json=payload,
            headers=self._headers(auth_token),
        )
        resp.raise_for_status()
        return resp.json()

    async def update_resource(
        self,
        auth_token: str,
        resource_name: str,
        filename: str,
    ) -> dict[str, Any]:
        resp = await self._http.patch(
            f"{self._base_url}/memos.api.v1.AttachmentService/UpdateAttachment",
            json={"attachment": {"name": resource_name, "filename": filename}, "updateMask": "filename"},
            headers=self._headers(auth_token),
        )
        resp.raise_for_status()
        return resp.json()

    async def delete_resource(self, auth_token: str, resource_name: str) -> bool:
        resp = await self._http.post(
            f"{self._base_url}/memos.api.v1.AttachmentService/DeleteAttachment",
            json={"name": resource_name},
            headers=self._headers(auth_token),
        )
        resp.raise_for_status()
        return True
