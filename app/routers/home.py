import asyncio

from fastapi import APIRouter, Request

from app import requested as req_tracker
from app.favorites import get_favorites
from app.stats import get_weekly_requests
from app.templating import templates

router = APIRouter()

_HOME_LIMIT = 200


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
                "active_section": "home",
                "weekly_requests": get_weekly_requests(),
            },
        )

    tasks = [ta.get_all_download_items(channel_id=cid, status="pending", vid_type="videos") for cid in favorite_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_videos = []
    for result in results:
        if not isinstance(result, Exception):
            all_videos.extend(result)

    all_videos.sort(key=lambda v: v.get("published", "0"), reverse=True)

    total = len(all_videos)
    capped = all_videos[:_HOME_LIMIT]

    return templates.TemplateResponse(
        request,
        "pages/home.html",
        {
            "videos": capped,
            "total": total,
            "capped": total > _HOME_LIMIT,
            "no_favorites": False,
            "active_page": "home",
            "active_section": "home",
            "weekly_requests": get_weekly_requests(),
            "show_channel": True,
            "requested_ids": req_tracker.get_all(),
        },
    )
