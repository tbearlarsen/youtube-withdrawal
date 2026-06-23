import asyncio
import json
import re

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app import auto_download as auto_dl
from app.favorites import toggle_favorite, is_favorite, get_favorites
from app.templating import templates


async def _resolve_channel_id(query: str) -> tuple[str | None, str | None]:
    """Return (channel_id, channel_name) by running yt-dlp locally."""
    query = query.strip()

    # Direct UC channel ID
    if re.match(r"^UC[\w-]{22}$", query):
        return query, None

    # Build a URL to pass to yt-dlp
    if re.match(r"^@", query):
        url = f"https://www.youtube.com/{query}/videos"
    elif "youtube.com" in query or "youtu.be" in query:
        url = query.rstrip("/")
        if not any(s in url for s in ("/videos", "/shorts", "/streams")):
            url += "/videos"
    else:
        url = f"https://www.youtube.com/@{query}/videos"

    try:
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--flat-playlist",
            "--playlist-items", "1",
            "-J",
            url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=25)
        data = json.loads(stdout.decode())
        cid = data.get("channel_id") or data.get("uploader_id", "")
        name = data.get("channel") or data.get("uploader", "")
        if cid and cid.startswith("UC"):
            return cid, name.strip()
    except Exception:
        pass

    return None, None

router = APIRouter()


async def _pending_count(ta, channel_id: str) -> int:
    try:
        data = await ta.get_download_list(channel_id=channel_id, status="pending")
        return data.get("paginate", {}).get("total_hits", 0)
    except Exception:
        return 0


SORT_OPTIONS = {
    "favorites": "Favorites first",
    "alpha":     "A → Z",
    "alpha-desc":"Z → A",
    "pending-desc": "Most pending",
    "pending-asc":  "Fewest pending",
}


@router.get("/channels")
async def channels_page(request: Request, sort: str = "pending-desc"):
    if sort not in SORT_OPTIONS:
        sort = "favorites"
    ta = request.app.state.ta
    favorites = set(get_favorites())

    # Fetch first page to learn total page count, then fetch remaining pages concurrently
    first = await ta.get_subscribed_channels(page=0)
    last_page = first.get("paginate", {}).get("last_page", 0)
    raw = list(first.get("data", []))

    if last_page > 0:
        rest = await asyncio.gather(*[ta.get_subscribed_channels(page=p) for p in range(1, last_page + 1)])
        for r in rest:
            raw.extend(r.get("data", []))

    # Deduplicate by channel_id — TA's pagination metadata can be inconsistent
    seen: set[str] = set()
    channels: list[dict] = []
    for c in raw:
        cid = c.get("channel_id")
        if cid and cid not in seen:
            seen.add(cid)
            channels.append(c)

    # Fetch pending counts for all channels concurrently
    counts = await asyncio.gather(*[_pending_count(ta, c["channel_id"]) for c in channels])
    pending_counts = {c["channel_id"]: count for c, count in zip(channels, counts)}

    # Apply sort
    name = lambda c: c.get("channel_name", "").lower()
    pending = lambda c: pending_counts.get(c["channel_id"], 0)
    fav_first = lambda c: c["channel_id"] not in favorites

    if sort == "alpha":
        channels.sort(key=name)
    elif sort == "alpha-desc":
        channels.sort(key=name, reverse=True)
    elif sort == "pending-desc":
        channels.sort(key=lambda c: (-pending(c), name(c)))
    elif sort == "pending-asc":
        channels.sort(key=lambda c: (pending(c), name(c)))
    else:  # favorites
        channels.sort(key=lambda c: (fav_first(c), name(c)))

    auto_download_ids = set(auto_dl.get_all())
    return templates.TemplateResponse(
        request,
        "pages/channels.html",
        {
            "channels": channels,
            "active_page": "channels",
            "active_section": "library",
            "favorites": favorites,
            "pending_counts": pending_counts,
            "auto_download_ids": auto_download_ids,
            "current_sort": sort,
            "sort_options": SORT_OPTIONS,
        },
    )


@router.post("/channels/search")
async def search_channel(request: Request, url: str = Form(...)):
    channel_id, channel_name = await _resolve_channel_id(url)

    if not channel_id:
        return HTMLResponse(
            '<p class="mt-3 text-sm text-red-400">'
            "Could not find that channel. Try the @handle (e.g. <code>@mkbhd</code>) or paste the full channel URL."
            "</p>"
        )

    ta = request.app.state.ta
    existing = await ta.get_channel(channel_id)
    if existing:
        channel_data = existing.get("data", existing)
    else:
        channel_data = {
            "channel_id": channel_id,
            "channel_name": channel_name or channel_id,
            "channel_subscribed": False,
            "channel_thumb_url": None,
            "channel_subs": None,
        }

    return templates.TemplateResponse(
        request,
        "partials/channel_subscribe_result.html",
        {"channel": channel_data},
    )


@router.post("/channels/{channel_id}/subscribe")
async def subscribe_channel(request: Request, channel_id: str):
    await request.app.state.ta.subscribe_channel(channel_id)
    return HTMLResponse(
        '<p class="text-sm text-green-400 font-medium">'
        "✓ Subscribed! The channel will appear after TubeArchivist's next scan."
        "</p>"
    )


@router.post("/channels/{channel_id}/favorite")
async def favorite_channel(request: Request, channel_id: str):
    now_favorite = toggle_favorite(channel_id)
    return templates.TemplateResponse(
        request,
        "partials/favorite_button.html",
        {"channel_id": channel_id, "is_favorite": now_favorite},
    )


@router.get("/channels/pending-total")
async def pending_total(request: Request):
    try:
        data = await request.app.state.ta.get_download_list(status="pending")
        total = data.get("paginate", {}).get("total_hits", 0)
    except Exception:
        total = 0
    if not total:
        return HTMLResponse("")
    return HTMLResponse(
        f'<span class="sidebar-label ml-auto text-fixed-white" style="font-size:0.6rem;font-weight:600;background:var(--c-accent);border-radius:999px;padding:0.1rem 0.45rem;line-height:1.6;font-family:system-ui,sans-serif">{total}</span>'
    )


@router.post("/channels/{channel_id}/card-star")
async def card_star(request: Request, channel_id: str):
    toggle_favorite(channel_id)
    favorites = set(get_favorites())
    return templates.TemplateResponse(
        request,
        "partials/channel_star.html",
        {"channel": {"channel_id": channel_id}, "favorites": favorites},
    )


@router.post("/channels/{channel_id}/auto-download")
async def toggle_auto_download(request: Request, channel_id: str, enable: str = Form(None)):
    if enable is None:
        enabled = auto_dl.toggle(channel_id)
    elif enable.lower() == "true":
        auto_dl.enable(channel_id)
        enabled = True
    else:
        auto_dl.disable(channel_id)
        enabled = False

    if enabled:
        ta = request.app.state.ta
        from app import requested as req_tracker
        already = req_tracker.get_all()
        try:
            pending_videos = await ta.get_all_download_items(channel_id=channel_id, status="pending")
            for video in pending_videos:
                vid_id = video.get("youtube_id")
                if vid_id and vid_id not in already:
                    await ta.request_video(vid_id)
                    req_tracker.add(vid_id)
        except Exception:
            pass

    from fastapi.responses import Response as FastAPIResponse
    return FastAPIResponse(headers={"HX-Refresh": "true"})


@router.post("/channels/{channel_id}/unsubscribe")
async def unsubscribe_channel(request: Request, channel_id: str):
    await request.app.state.ta.unsubscribe_channel(channel_id)
    if is_favorite(channel_id):
        toggle_favorite(channel_id)
    auto_dl.disable(channel_id)
    from fastapi.responses import Response as FastAPIResponse
    return FastAPIResponse(headers={"HX-Redirect": "/channels"})


@router.post("/channels/{channel_id}/request-all")
async def request_all_pending(request: Request, channel_id: str):
    ta = request.app.state.ta
    from app import requested as req_tracker
    already = req_tracker.get_all()
    try:
        pending_videos = await ta.get_all_download_items(channel_id=channel_id, status="pending")
        for video in pending_videos:
            vid_id = video.get("youtube_id")
            if vid_id and vid_id not in already:
                await ta.request_video(vid_id)
                req_tracker.add(vid_id)
    except Exception:
        pass
    from fastapi.responses import Response as FastAPIResponse
    return FastAPIResponse(headers={"HX-Refresh": "true"})


@router.post("/channels/{channel_id}/restore-all-ignored")
async def restore_all_ignored(request: Request, channel_id: str):
    ta = request.app.state.ta
    ignored = await ta.get_all_download_items(channel_id=channel_id, status="ignore")
    if not ignored:
        return HTMLResponse(
            '<span style="font-size:0.72rem;color:var(--c-text4)">Nothing to restore</span>'
        )
    await asyncio.gather(*[ta.restore_video(v["youtube_id"]) for v in ignored], return_exceptions=True)
    from fastapi.responses import Response as FastAPIResponse
    return FastAPIResponse(headers={"HX-Refresh": "true"})


@router.post("/channels/{channel_id}/ignore-all")
async def ignore_all_channel(request: Request, channel_id: str):
    ta = request.app.state.ta
    to_ignore: list[dict] = []
    page = 0
    while True:
        data = await ta.get_download_list(channel_id=channel_id, page=page, status="pending")
        batch = data.get("data", [])
        to_ignore.extend(batch)
        if page >= data.get("paginate", {}).get("last_page", 0) or not batch:
            break
        page += 1

    if not to_ignore:
        return HTMLResponse(
            '<span style="font-size:0.72rem;color:var(--c-text4)">Nothing to ignore</span>'
        )

    await asyncio.gather(*[ta.ignore_video(v["youtube_id"]) for v in to_ignore], return_exceptions=True)
    from fastapi.responses import Response as FastAPIResponse
    return FastAPIResponse(headers={"HX-Refresh": "true"})
