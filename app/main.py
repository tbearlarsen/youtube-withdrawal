import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from app import app_settings
from app.ta_client import TAClient
from app.routers import channels, videos, queue, search, home, settings, downloads


async def _scan_loop(app: FastAPI) -> None:
    """Periodically trigger a TA subscription scan. Interval is re-read each cycle."""
    last_scan: float = 0.0
    while True:
        await asyncio.sleep(60)
        interval_min = app_settings.get("scan_interval_minutes")
        if not interval_min:
            continue
        if time.monotonic() - last_scan >= interval_min * 60:
            try:
                await app.state.ta.scan_subscriptions()
                last_scan = time.monotonic()
            except Exception:
                pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.ta = TAClient()
    scan_task = asyncio.create_task(_scan_loop(app))
    yield
    scan_task.cancel()
    try:
        await scan_task
    except asyncio.CancelledError:
        pass
    await app.state.ta.close()


app = FastAPI(title="YouTube Withdrawal", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(home.router)
app.include_router(channels.router)
app.include_router(videos.router)
app.include_router(queue.router)
app.include_router(search.router)
app.include_router(downloads.router)
app.include_router(settings.router)


@app.get("/ta-cache/{path:path}")
async def proxy_cache(path: str, request: Request):
    content, content_type = await request.app.state.ta.proxy_cache(path)
    return Response(content=content, media_type=content_type)
