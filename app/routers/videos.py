import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app import auto_download as auto_dl
from app.favorites import is_favorite
from app import stats, requested as req_tracker
from app.templating import templates

router = APIRouter()


@router.get("/channels/{channel_id}")
async def channel_detail(request: Request, channel_id: str, status: str = "pending"):
    ta = request.app.state.ta
    channel_data, videos = await asyncio.gather(
        ta.get_channel(channel_id),
        ta.get_all_videos(channel_id=channel_id) if status == "downloaded"
        else ta.get_all_download_items(channel_id=channel_id, status=status),
    )
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


@router.post("/videos/{video_id}/request")
async def request_video(request: Request, video_id: str):
    ta = request.app.state.ta
    await ta.request_video(video_id)
    stats.increment_requests()
    req_tracker.add(video_id)
    return HTMLResponse(
        f'<div id="vid-actions-{video_id}" style="display:flex;align-items:center;gap:0.45rem;margin-top:0.65rem">'
        f'<span style="width:5px;height:5px;border-radius:50%;background:var(--c-queued);flex-shrink:0"></span>'
        f'<span style="font-size:0.55rem;letter-spacing:0.07em;text-transform:uppercase;font-weight:500;'
        f'font-family:system-ui,sans-serif;color:var(--c-queued)">Requested</span>'
        f'</div>'
    )


@router.post("/videos/{video_id}/ignore")
async def ignore_video(request: Request, video_id: str):
    ta = request.app.state.ta
    await ta.ignore_video(video_id)
    video = await ta.get_download_item(video_id)
    if video is None:
        video = {"youtube_id": video_id, "status": "ignore"}
    return templates.TemplateResponse(
        request, "partials/video_card.html", {"video": video, "requested_ids": req_tracker.get_all()}
    )


@router.post("/videos/{video_id}/restore")
async def restore_video(request: Request, video_id: str):
    ta = request.app.state.ta
    await ta.restore_video(video_id)
    req_tracker.remove(video_id)
    video = await ta.get_download_item(video_id)
    if video is None:
        video = {"youtube_id": video_id, "status": "pending"}
    return templates.TemplateResponse(
        request, "partials/video_card.html", {"video": video, "requested_ids": req_tracker.get_all()}
    )


@router.delete("/videos/{video_id}")
async def delete_video(request: Request, video_id: str):
    ta = request.app.state.ta
    await ta.delete_video(video_id)
    try:
        await ta.ignore_video(video_id)
    except Exception:
        pass
    return HTMLResponse("")
