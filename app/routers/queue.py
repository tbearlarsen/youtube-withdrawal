from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app import requested as req_tracker
from app.templating import templates

router = APIRouter()


async def _get_queue_videos(ta) -> list[dict]:
    requested_ids = req_tracker.get_all()
    if not requested_ids:
        return []

    all_pending = await ta.get_all_pending()
    pending_by_id = {v["youtube_id"]: v for v in all_pending}

    # Remove from tracker any IDs that are no longer pending (already downloaded)
    for vid_id in list(requested_ids):
        if vid_id not in pending_by_id:
            req_tracker.remove(vid_id)

    # Return in tracker insertion order where possible
    return [pending_by_id[vid_id] for vid_id in requested_ids if vid_id in pending_by_id]


@router.get("/queue")
async def queue_page(request: Request):
    videos = await _get_queue_videos(request.app.state.ta)
    return templates.TemplateResponse(
        request,
        "pages/queue.html",
        {"videos": videos, "total": len(videos), "active_page": "queue"},
    )


@router.get("/queue/items")
async def queue_items(request: Request):
    videos = await _get_queue_videos(request.app.state.ta)
    return templates.TemplateResponse(
        request,
        "partials/queue_items.html",
        {"videos": videos},
    )


@router.post("/queue/{video_id}/remove")
async def queue_remove(request: Request, video_id: str):
    """Remove a video from the queue: restore to pending in TA and remove from tracker."""
    await request.app.state.ta.restore_video(video_id)
    req_tracker.remove(video_id)
    return HTMLResponse("")
