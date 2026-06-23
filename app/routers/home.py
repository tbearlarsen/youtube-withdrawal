import asyncio

from fastapi import APIRouter, Request

from app import requested as req_tracker, deleted as del_tracker
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
                "downloaded_videos": [],
                "no_favorites": True,
                "active_page": "home",
                "active_section": "home",
                "weekly_requests": get_weekly_requests(),
            },
        )

    # Fetch pending and first page of downloaded concurrently for all favorited channels
    pending_tasks = [
        ta.get_all_download_items(channel_id=cid, status="pending", vid_type="videos")
        for cid in favorite_ids
    ]
    downloaded_tasks = [
        ta.get_video_list(channel_id=cid, page=0, sort="published", order="desc")
        for cid in favorite_ids
    ]

    all_results = await asyncio.gather(*pending_tasks, *downloaded_tasks, return_exceptions=True)
    pending_results = all_results[:len(favorite_ids)]
    downloaded_results = all_results[len(favorite_ids):]

    deleted = del_tracker.get_all()
    pending_videos = []
    for result in pending_results:
        if not isinstance(result, Exception):
            for v in result:
                if v.get("youtube_id") not in deleted:
                    pending_videos.append(v)

    raw_downloaded = []
    for result in downloaded_results:
        if not isinstance(result, Exception):
            raw_downloaded.extend(result.get("data", []))

    # Deduplicate downloaded videos
    seen: set[str] = set()
    downloaded_videos = []
    for v in raw_downloaded:
        vid_id = v.get("youtube_id")
        if vid_id and vid_id not in seen:
            seen.add(vid_id)
            downloaded_videos.append(v)

    pending_videos.sort(key=lambda v: v.get("published", "0"), reverse=True)
    downloaded_videos.sort(key=lambda v: v.get("published", "0"), reverse=True)

    total_pending = len(pending_videos)
    total_downloaded = len(downloaded_videos)

    return templates.TemplateResponse(
        request,
        "pages/home.html",
        {
            "videos": pending_videos[:_HOME_LIMIT],
            "total": total_pending,
            "capped": total_pending > _HOME_LIMIT,
            "downloaded_videos": downloaded_videos[:_HOME_LIMIT],
            "total_downloaded": total_downloaded,
            "no_favorites": False,
            "active_page": "home",
            "active_section": "home",
            "weekly_requests": get_weekly_requests(),
            "show_channel": True,
            "requested_ids": req_tracker.get_all(),
        },
    )
