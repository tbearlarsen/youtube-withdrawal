import asyncio

import httpx

from app.config import settings


class TAClient:
    def __init__(self):
        self._client = httpx.AsyncClient(
            base_url=settings.ta_url,
            headers={"Authorization": f"Token {settings.ta_api_key}"},
            timeout=15.0,
        )

    async def close(self):
        await self._client.aclose()

    async def get_subscribed_channels(self, page: int = 0) -> dict:
        r = await self._client.get(
            "/api/channel/", params={"filter": "subscribed", "page": page}
        )
        r.raise_for_status()
        return r.json()

    async def get_channel(self, channel_id: str) -> dict | None:
        r = await self._client.get(f"/api/channel/{channel_id}/")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    async def get_download_list(
        self,
        channel_id: str | None = None,
        page: int = 0,
        status: str = "pending",
        vid_type: str | None = None,
    ) -> dict:
        params: dict = {"filter": status, "page": page}
        if channel_id:
            params["channel"] = channel_id
        if vid_type:
            params["vid_type"] = vid_type
        r = await self._client.get("/api/download/", params=params)
        r.raise_for_status()
        return r.json()

    async def get_download_item(self, video_id: str) -> dict | None:
        r = await self._client.get(f"/api/download/{video_id}/")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        resp = r.json()
        # TA wraps single items: {"data": {...}, "message": "success"}
        return resp.get("data") if isinstance(resp.get("data"), dict) else resp

    async def get_task_status(self, task_name: str) -> dict | None:
        try:
            r = await self._client.get(f"/api/task/by-name/{task_name}/")
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
        except Exception:
            return None

    async def request_video(self, video_id: str) -> None:
        r = await self._client.post(
            f"/api/download/{video_id}/", json={"status": "priority"}
        )
        r.raise_for_status()

    async def ignore_video(self, video_id: str) -> None:
        r = await self._client.post(
            f"/api/download/{video_id}/", json={"status": "ignore"}
        )
        r.raise_for_status()

    async def restore_video(self, video_id: str) -> None:
        r = await self._client.post(
            f"/api/download/{video_id}/", json={"status": "pending"}
        )
        r.raise_for_status()

    async def search_channel_url(self, query: str) -> dict | None:
        r = await self._client.get("/api/channel/search/", params={"q": query})
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    async def subscribe_channel(self, channel_id: str) -> None:
        payload = {"data": [{"channel_id": channel_id, "channel_subscribed": True}]}
        r = await self._client.post("/api/channel/", json=payload)
        r.raise_for_status()

    async def search(self, query: str) -> dict:
        r = await self._client.get("/api/search/", params={"query": query})
        r.raise_for_status()
        return r.json()

    async def get_priority_downloads(self) -> list[dict]:
        """Fetch all user-requested (priority) downloads across all pending pages."""
        first = await self.get_download_list(status="pending", page=0)
        last_page = first.get("paginate", {}).get("last_page", 0)
        all_items = list(first.get("data", []))
        if last_page > 0:
            rest = await asyncio.gather(*[
                self.get_download_list(status="pending", page=p)
                for p in range(1, last_page + 1)
            ])
            for r in rest:
                all_items.extend(r.get("data", []))
        return [v for v in all_items if v.get("status") in ("priority", "downloading")]

    async def get_all_pending(self) -> list[dict]:
        """Fetch every pending download across all channels, all pages."""
        videos = []
        page = 0
        while True:
            data = await self.get_download_list(page=page, status="pending")
            batch = data.get("data", [])
            videos.extend(batch)
            paginate = data.get("paginate", {})
            if page >= paginate.get("last_page", 0) or not batch:
                break
            page += 1
        return videos

    async def get_video_list(
        self,
        channel_id: str | None = None,
        page: int = 0,
        watch: str | None = None,
        sort: str = "published",
        order: str = "desc",
    ) -> dict:
        params: dict = {"page": page, "sort": sort, "order": order}
        if channel_id:
            params["channel"] = channel_id
        if watch:
            params["watch"] = watch
        r = await self._client.get("/api/video/", params=params)
        r.raise_for_status()
        return r.json()

    async def get_video(self, video_id: str) -> dict | None:
        r = await self._client.get(f"/api/video/{video_id}/")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    async def delete_video(self, video_id: str) -> None:
        r = await self._client.delete(f"/api/video/{video_id}/")
        r.raise_for_status()

    async def trigger_rescan(self) -> dict:
        r = await self._client.post(
            "/api/appsettings/rescan-filesystem/",
            json={"ignore_error": False, "prefer_local": False},
        )
        r.raise_for_status()
        return r.json()

    async def get_ta_config(self) -> dict:
        r = await self._client.get("/api/appsettings/config/")
        r.raise_for_status()
        return r.json()

    async def update_ta_config(self, payload: dict) -> dict:
        r = await self._client.post("/api/appsettings/config/", json=payload)
        r.raise_for_status()
        return r.json()

    async def scan_subscriptions(self) -> dict:
        r = await self._client.post(
            "/api/task/by-name/update_subscribed/",
            json={"api_start": True},
        )
        r.raise_for_status()
        return r.json()

    async def proxy_cache(self, path: str) -> tuple[bytes, str]:
        r = await self._client.get(f"/{path}")
        r.raise_for_status()
        return r.content, r.headers.get("content-type", "image/jpeg")
