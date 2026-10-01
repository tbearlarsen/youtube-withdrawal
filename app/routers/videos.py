import asyncio

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from app import auto_download as auto_dl, categories
from app.favorites import is_favorite
from app import stats, requested as req_tracker, deleted as del_tracker
from app.templating import templates

router = APIRouter()


@router.get("/channels/{channel_id}")
async def channel_detail(request: Request, channel_id: str, status: str = "pending"):
    ta = request.app.state.ta
    channel_data, raw_videos = await asyncio.gather(
        ta.get_channel(channel_id),
        ta.get_all_videos(channel_id=channel_id) if status == "downloaded"
        else ta.get_all_download_items(channel_id=channel_id, status=status),
    )
    if status == "pending":
        deleted = del_tracker.get_all()
        videos = [v for v in raw_videos if v.get("youtube_id") not in deleted]
    else:
        videos = raw_videos
    if not channel_data:
        # Not indexed in TA yet (e.g. a channel you only requested a single video from)
        name = next((v.get("channel_name") for v in videos if v.get("channel_name")), channel_id)
        channel_data = {"channel_id": channel_id, "channel_name": name}
    return templates.TemplateResponse(
        request,
        "pages/channel_detail.html",
        {
            "channel": channel_data,
            "channel_id": channel_id,
            "videos": videos,
            "active_page": "channels",
            "active_section": "library",
            "current_status": status,
            "is_favorite": is_favorite(channel_id),
            "is_auto_download": auto_dl.is_auto(channel_id),
            "categories": categories.get_categories(),
            "sel_channel_id": channel_id,
            "sel_current": categories.category_of(channel_id),
            "requested_ids": req_tracker.get_all(),
        },
    )


@router.get("/videos/{video_id}")
async def video_detail_page(request: Request, video_id: str):
    ta = request.app.state.ta
    video, source = await ta.get_video_detail(video_id)
    if not video:
        return HTMLResponse("Video not found", status_code=404)
    channel = video.get("channel") or {}
    channel_name = video.get("channel_name") or channel.get("channel_name", "")
    channel_id = video.get("channel_id") or channel.get("channel_id", "")
    requested_ids = req_tracker.get_all()
    is_queued = video_id in requested_ids or video.get("status") in ("priority", "downloading")
    return templates.TemplateResponse(request, "pages/video_detail.html", {
        "video": video,
        "source": source,
        "channel_name": channel_name,
        "channel_id": channel_id,
        "is_queued": is_queued,
        "requested_ids": requested_ids,
        "active_section": "library",
        "active_page": "channels",
    })


def _detail_actions(request: Request, video: dict, is_queued: bool = False) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "partials/video_detail_actions.html",
        {"video": video, "source": "pending", "is_queued": is_queued},
    )


def _card(request: Request, video: dict) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "partials/video_card.html",
        {
            "video": video,
            "requested_ids": req_tracker.get_all(),
            "show_channel": request.query_params.get("show_channel") == "1",
        },
    )


@router.post("/videos/{video_id}/request")
async def request_video(request: Request, video_id: str, from_: str = Query("", alias="from")):
    ta = request.app.state.ta
    await ta.request_video(video_id)
    stats.increment_requests()
    req_tracker.add(video_id)
    video = await ta.get_download_item(video_id) or {"youtube_id": video_id}
    if from_ == "detail":
        return _detail_actions(request, video, is_queued=True)
    return _card(request, video)


@router.post("/videos/{video_id}/ignore")
async def ignore_video(request: Request, video_id: str, from_: str = Query("", alias="from")):
    """Ignore a pending video. Cards are removed from the list (empty response)."""
    ta = request.app.state.ta
    await ta.ignore_video(video_id)
    req_tracker.remove(video_id)
    if from_ == "detail":
        video = await ta.get_download_item(video_id) or {"youtube_id": video_id}
        return _detail_actions(request, {**video, "status": "ignore"})
    return HTMLResponse("")


@router.post("/videos/{video_id}/restore")
async def restore_video(request: Request, video_id: str, from_: str = Query("", alias="from")):
    """Un-ignore a video. Cards (only shown on a channel's Ignored tab) are removed."""
    ta = request.app.state.ta
    video = await ta.get_download_item(video_id) or {"youtube_id": video_id}
    await ta.restore_video(video_id, auto_start=bool(video.get("auto_start")))
    req_tracker.remove(video_id)
    if from_ == "detail":
        return _detail_actions(request, {**video, "status": "pending"})
    return HTMLResponse("")


@router.post("/videos/{video_id}/cancel")
async def cancel_request(request: Request, video_id: str, from_: str = Query("", alias="from")):
    """Undo a request: the video goes back to plain pending and keeps its card."""
    ta = request.app.state.ta
    video = await ta.get_download_item(video_id) or {"youtube_id": video_id}
    req_tracker.remove(video_id)
    if auto_dl.is_auto(video.get("channel_id", "")):
        # Back to pending, the auto-download loop would just request it again
        await ta.ignore_video(video_id)
        if from_ == "detail":
            return _detail_actions(request, {**video, "status": "ignore"})
        return HTMLResponse("")
    await ta.requeue_video(video_id)
    video = {**video, "status": "pending", "auto_start": False}
    if from_ == "detail":
        return _detail_actions(request, video)
    return _card(request, video)


@router.delete("/videos/{video_id}")
async def delete_video(request: Request, video_id: str):
    ta = request.app.state.ta
    await ta.delete_video(video_id)
    del_tracker.add(video_id)
    await ta.force_ignore_video(video_id)
    return HTMLResponse("")
