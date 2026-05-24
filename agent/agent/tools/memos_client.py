from typing import Any

import httpx

from agent.observability.logger import log


class MemosClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._http = httpx.AsyncClient(timeout=30.0, proxy=None)

    async def close(self) -> None:
        await self._http.aclose()

    def _headers(self, auth_token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {auth_token}"}

    async def search_memos(
        self,
        auth_token: str,
        *,
        creator_id: int | None = None,
        content: str | None = None,
        tag: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if creator_id is not None:
            params["creatorId"] = creator_id
        if content:
            params["content"] = content
        if tag:
            params["tag"] = tag
        resp = await self._http.get(
            f"{self._base_url}/api/v1/memo",
            params=params,
            headers=self._headers(auth_token),
        )
        resp.raise_for_status()
        return resp.json()

    async def get_memo(self, auth_token: str, memo_id: int) -> dict[str, Any] | None:
        resp = await self._http.get(
            f"{self._base_url}/api/v1/memo/{memo_id}",
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
            f"{self._base_url}/api/v1/memo",
            json={"content": content, "visibility": visibility},
            headers=self._headers(auth_token),
        )
        resp.raise_for_status()
        return resp.json()

    async def list_tags(self, auth_token: str) -> list[str]:
        resp = await self._http.get(
            f"{self._base_url}/api/v1/tag",
            headers=self._headers(auth_token),
        )
        resp.raise_for_status()
        return resp.json()
