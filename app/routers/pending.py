from fastapi import APIRouter, Request

from app import categories, requested as req_tracker, deleted as del_tracker
from app.sorting import published_key
from app.templating import templates

router = APIRouter()

_SORT_OPTIONS = {
    "newest":  "Newest first",
    "oldest":  "Oldest first",
    "channel": "Channel A → Z",
}


@router.get("/pending")
async def pending_page(request: Request, sort: str = "newest", view: str = "grouped"):
    if sort not in _SORT_OPTIONS:
        sort = "newest"
    deleted = del_tracker.get_all()
    videos = [
        v for v in await request.app.state.ta.get_all_pending()
        if v.get("youtube_id") not in deleted
    ]

    if sort == "oldest":
        videos.sort(key=published_key)
    elif sort == "channel":
        videos.sort(key=lambda v: (v.get("channel_name", "").lower(), published_key(v)))
    else:
        videos.sort(key=published_key, reverse=True)

    return templates.TemplateResponse(
        request,
        "pages/pending.html",
        {
            **categories.build_view(videos, view),
            "total": len(videos),
            "base_path": "/pending",
            "base_qs": {"sort": sort},
            "active_page": "pending",
            "active_section": "library",
            "show_channel": True,
            "requested_ids": req_tracker.get_all(),
            "current_sort": sort,
            "sort_options": _SORT_OPTIONS,
        },
    )
