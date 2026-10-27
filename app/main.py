import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from app import auto_download as auto_dl, requested as req_tracker, deleted as del_tracker, kept, yt_history
from app.ta_client import TAClient
from app.routers import categories, channels, videos, queue, home, settings, downloads, pending


async def _reconcile_requested(ta: TAClient) -> None:
    """Remove stale req_tracker entries; re-ignore any deleted videos that reappeared in pending."""
    try:
        pending_items = await ta.get_all_pending()
    except Exception:
        return

    pending_ids = {v["youtube_id"] for v in pending_items}

    req_tracker.prune(pending_ids)

    # If a deleted video reappeared in TA's pending queue (ES lag / scan race),
    # push the ignore again now that the queue entry exists
    deleted = del_tracker.get_all()
    for item in pending_items:
        vid_id = item.get("youtube_id")
        if vid_id and vid_id in deleted:
            try:
                await ta.ignore_video(vid_id)
            except Exception:
                pass


async def _unwatch_kept(ta: TAClient) -> None:
    """Kept videos are protected from TA's auto-delete by staying unwatched; un-watch any that got watched.
    Looks up only the kept IDs (not the library). The auto-delete threshold is at least a day, far longer
    than the 5-minute loop."""
    for vid_id in kept.get_all():
        try:
            # A missing video is skipped, not pruned: a transient 404 must not drop protection
            raw = await ta.get_video(vid_id) or {}
            if ((raw.get("data") or raw).get("player") or {}).get("watched"):
                await ta.set_watched(vid_id, False)
        except Exception:
            pass


async def _auto_request_loop(app: FastAPI) -> None:
    """Every 5 minutes: reconcile requested tracker, then request pending videos from auto-download channels."""
    while True:
        await asyncio.sleep(5 * 60)
        await _reconcile_requested(app.state.ta)
        await _unwatch_kept(app.state.ta)
        auto_channels = auto_dl.get_all()
        if not auto_channels:
            continue
        try:
            already = req_tracker.get_all()
            deleted = del_tracker.get_all()
            for channel_id in auto_channels:
                pending = await app.state.ta.get_all_download_items(
                    channel_id=channel_id, status="pending"
                )
                for video in pending:
                    vid_id = video.get("youtube_id")
                    if vid_id and vid_id not in already and vid_id not in deleted:
                        await app.state.ta.request_video(vid_id)
                        req_tracker.add(vid_id)
                        already.add(vid_id)
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.ta = TAClient()
    await _reconcile_requested(app.state.ta)
    auto_task = asyncio.create_task(_auto_request_loop(app))
    history_task = asyncio.create_task(yt_history.loop(app.state.ta))
    yield
    for task in (auto_task, history_task):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    await app.state.ta.close()


app = FastAPI(title="YouTube Withdrawal", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(home.router)
app.include_router(channels.router)
app.include_router(categories.router)
app.include_router(videos.router)
app.include_router(queue.router)
app.include_router(downloads.router)
app.include_router(pending.router)
app.include_router(settings.router)


@app.get("/ta-cache/{path:path}")
async def proxy_cache(path: str, request: Request):
    content, content_type = await request.app.state.ta.proxy_cache(path)
    return Response(content=content, media_type=content_type)
