import asyncio

from fastapi import APIRouter, Request

from app import app_settings, requested as req_tracker
from app.favorites import get_favorites
from app.stats import get_weekly_requests
from app.templating import templates

router = APIRouter()


@router.get("/")
async def home_page(request: Request):
    ta = request.app.state.ta
    favorite_ids = get_favorites()

    if not favorite_ids:
        return templates.TemplateResponse(
            request,
            "pages/home.html",
            {
                "videos": [],
                "no_favorites": True,
                "active_page": "home",
                "weekly_requests": get_weekly_requests(),
            },
        )

    # Fetch pending videos from each favorite channel concurrently
    tasks = [ta.get_download_list(channel_id=cid, status="pending") for cid in favorite_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_videos = []
    for result in results:
        if isinstance(result, Exception):
            continue
        for v in result.get("data", []):
            if v.get("vid_type") not in ("shorts", "streams"):
                all_videos.append(v)

    # Sort by published date descending — YYYYMMDD strings compare correctly
    all_videos.sort(key=lambda v: v.get("published", "0"), reverse=True)

    page_size = app_settings.get("page_size") or 60
    return templates.TemplateResponse(
        request,
        "pages/home.html",
        {
            "videos": all_videos[:page_size],
            "no_favorites": False,
            "active_page": "home",
            "weekly_requests": get_weekly_requests(),
            "show_channel": True,
            "requested_ids": req_tracker.get_all(),
        },
    )
