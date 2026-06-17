from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.favorites import is_favorite
from app import stats, requested as req_tracker
from app.templating import templates

router = APIRouter()


@router.get("/channels/{channel_id}")
async def channel_detail(
    request: Request,
    channel_id: str,
    page: int = 0,
    status: str = "pending",
):
    ta = request.app.state.ta
    channel_data = await ta.get_channel(channel_id)

    if status == "downloaded":
        videos_data = await ta.get_video_list(channel_id=channel_id, page=page)
    else:
        videos_data = await ta.get_download_list(
            channel_id=channel_id, page=page, status=status
        )

    return templates.TemplateResponse(
        request,
        "pages/channel_detail.html",
        {
            "channel": channel_data,
            "channel_id": channel_id,
            "videos": videos_data.get("data", []),
            "paginate": videos_data.get("paginate"),
            "active_page": "channels",
            "current_status": status,
            "is_favorite": is_favorite(channel_id),
            "requested_ids": req_tracker.get_all(),
        },
    )


@router.post("/videos/{video_id}/request")
async def request_video(request: Request, video_id: str):
    ta = request.app.state.ta
    await ta.request_video(video_id)
    stats.increment_requests()
    req_tracker.add(video_id)
    return HTMLResponse(
        f'<div id="vid-actions-{video_id}" class="mt-3 flex gap-2">'
        f'<div class="flex-1 text-center" style="padding:0.375rem 0;font-size:0.6rem;'
        f'letter-spacing:0.08em;text-transform:uppercase;font-weight:500;'
        f'font-family:system-ui,sans-serif;color:var(--c-queued);'
        f'border:1px solid color-mix(in srgb,var(--c-queued) 35%,transparent);'
        f'border-radius:0.25rem">Queued ✓</div>'
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
    await request.app.state.ta.delete_video(video_id)
    return HTMLResponse("")
