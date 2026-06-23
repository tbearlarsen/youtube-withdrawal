import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from app import auto_download as auto_dl, requested as req_tracker
from app.ta_client import TAClient
from app.routers import channels, videos, queue, home, settings, downloads, pending


async def _reconcile_requested(ta: TAClient) -> None:
    """Remove stale entries from requested.json that are no longer in TA's pending queue."""
    requested = req_tracker.get_all()
    if not requested:
        return
    try:
        pending_items = await ta.get_all_pending()
        pending_ids = {v["youtube_id"] for v in pending_items}
        for vid_id in list(requested):
            if vid_id not in pending_ids:
                req_tracker.remove(vid_id)
    except Exception:
        pass


async def _auto_request_loop(app: FastAPI) -> None:
    """Every 5 minutes: reconcile requested tracker, then request pending videos from auto-download channels."""
    while True:
        await asyncio.sleep(5 * 60)
        await _reconcile_requested(app.state.ta)
        auto_channels = auto_dl.get_all()
        if not auto_channels:
            continue
        try:
            already = req_tracker.get_all()
            for channel_id in auto_channels:
                pending = await app.state.ta.get_all_download_items(
                    channel_id=channel_id, status="pending"
                )
                for video in pending:
                    vid_id = video.get("youtube_id")
                    if vid_id and vid_id not in already:
                        await app.state.ta.request_video(vid_id)
                        req_tracker.add(vid_id)
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.ta = TAClient()
    await _reconcile_requested(app.state.ta)
    auto_task = asyncio.create_task(_auto_request_loop(app))
    yield
    auto_task.cancel()
    try:
        await auto_task
    except asyncio.CancelledError:
        pass
    await app.state.ta.close()


app = FastAPI(title="YouTube Withdrawal", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(home.router)
app.include_router(channels.router)
app.include_router(videos.router)
app.include_router(queue.router)
app.include_router(downloads.router)
app.include_router(pending.router)
app.include_router(settings.router)


@app.get("/ta-cache/{path:path}")
async def proxy_cache(path: str, request: Request):
    content, content_type = await request.app.state.ta.proxy_cache(path)
    return Response(content=content, media_type=content_type)
