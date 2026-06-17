from fastapi import APIRouter, Request

from app import requested as req_tracker
from app.templating import templates

router = APIRouter()

_SORT_OPTIONS = {
    "newest":  "Newest first",
    "oldest":  "Oldest first",
    "channel": "Channel A → Z",
}


@router.get("/pending")
async def pending_page(request: Request, sort: str = "newest"):
    if sort not in _SORT_OPTIONS:
        sort = "newest"
    videos = await request.app.state.ta.get_all_pending()

    if sort == "oldest":
        videos.sort(key=lambda v: v.get("published", "0"))
    elif sort == "channel":
        videos.sort(key=lambda v: (v.get("channel_name", "").lower(), v.get("published", "0")))
    else:
        videos.sort(key=lambda v: v.get("published", "0"), reverse=True)

    return templates.TemplateResponse(
        request,
        "pages/pending.html",
        {
            "videos": videos,
            "active_page": "pending",
            "active_section": "library",
            "show_channel": True,
            "requested_ids": req_tracker.get_all(),
            "current_sort": sort,
            "sort_options": _SORT_OPTIONS,
        },
    )
