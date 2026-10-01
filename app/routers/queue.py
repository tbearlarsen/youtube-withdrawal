import html
import re
from urllib.parse import parse_qs, urlparse

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app import requested as req_tracker, deleted as del_tracker, stats
from app.templating import templates

router = APIRouter()


async def _get_queue_videos(ta) -> list[dict]:
    requested_ids = req_tracker.get_all()
    if not requested_ids:
        return []

    all_pending = await ta.get_all_pending()
    pending_by_id = {v["youtube_id"]: v for v in all_pending}

    # Remove from tracker any IDs that are no longer pending (already downloaded)
    req_tracker.prune(set(pending_by_id))

    # Return in tracker insertion order where possible
    return [pending_by_id[vid_id] for vid_id in requested_ids if vid_id in pending_by_id]


@router.get("/queue")
async def queue_page(request: Request):
    videos = await _get_queue_videos(request.app.state.ta)
    return templates.TemplateResponse(
        request,
        "pages/queue.html",
        {"videos": videos, "total": len(videos), "active_page": "queue", "active_section": "library"},
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


_VIDEO_ID = re.compile(r"^[\w-]{11}$")


def _parse_video_id(text: str) -> str | None:
    """Extract a single video's ID from a YouTube URL or bare ID. Channels and playlists aren't accepted."""
    text = text.strip()
    if _VIDEO_ID.match(text):
        return text
    if "://" not in text:
        text = "https://" + text
    url = urlparse(text)
    host = url.netloc.lower().removeprefix("www.").removeprefix("m.")
    parts = [p for p in url.path.split("/") if p]
    candidate = None
    if host == "youtu.be" and parts:
        candidate = parts[0]
    elif host in ("youtube.com", "music.youtube.com", "youtube-nocookie.com"):
        if parts == ["watch"]:
            candidate = parse_qs(url.query).get("v", [None])[0]
        elif len(parts) >= 2 and parts[0] in ("shorts", "live", "embed", "v"):
            candidate = parts[1]
    return candidate if candidate and _VIDEO_ID.match(candidate) else None


def _add_result(message: str, ok: bool) -> HTMLResponse:
    color = "var(--c-queued)" if ok else "var(--c-accent)"
    return HTMLResponse(
        f'<p style="font-size:0.7rem;color:{color};margin-top:0.6rem">{html.escape(message)}</p>'
    )


@router.post("/queue/add")
async def queue_add(request: Request, url: str = Form("")):
    """Request a single video by link — including from channels you don't subscribe to."""
    video_id = _parse_video_id(url)
    if not video_id:
        return _add_result("That doesn't look like a link to a single YouTube video.", ok=False)

    ta = request.app.state.ta
    if await ta.get_video(video_id):
        return _add_result("Already downloaded.", ok=False)

    await ta.add_videos([video_id], auto_start=True)
    req_tracker.add(video_id)
    del_tracker.remove_many({video_id})
    stats.increment_requests()
    return _add_result("Added — it will show up in the queue below within a minute.", ok=True)
