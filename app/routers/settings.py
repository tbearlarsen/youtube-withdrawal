import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app import app_settings
from app.templating import templates

router = APIRouter(prefix="/settings")


@router.get("")
async def settings_page(request: Request):
    current = app_settings.get_all()
    ta = request.app.state.ta
    try:
        ta_config = await ta.get_ta_config()
        subs = ta_config.get("subscriptions", {})
        dl = ta_config.get("downloads", {})
        shorts_enabled = (subs.get("shorts_channel_size") or 0) > 0
        streams_enabled = (subs.get("live_channel_size") or 0) > 0
    except Exception:
        dl = {}
        shorts_enabled = None
        streams_enabled = None

    try:
        task_results = await ta.get_task_status("update_subscribed")
        results_list = task_results if isinstance(task_results, list) else []
        last_scan = next((t for t in results_list if t.get("status") == "SUCCESS"), None)
    except Exception:
        last_scan = None

    return templates.TemplateResponse(
        request,
        "pages/settings.html",
        {
            "active_page": "settings",
            "page_size": current.get("page_size", 60),
            "scan_interval_minutes": current.get("scan_interval_minutes", 30),
            "last_scan": last_scan,
            "shorts_enabled": shorts_enabled,
            "streams_enabled": streams_enabled,
            "dl": dl,
        },
    )


@router.post("/ignore-before")
async def ignore_before(request: Request, days: int = Form(...)):
    ta = request.app.state.ta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_str = cutoff.strftime("%Y%m%d")

    videos = await ta.get_all_pending()
    to_ignore = [v for v in videos if (v.get("published") or "99999999") < cutoff_str]

    if not to_ignore:
        return HTMLResponse(
            f'<p class="text-sm" style="color:var(--c-text3)">Nothing older than {days} days to ignore.</p>'
        )

    ignored = 0
    errors = 0
    tasks = [ta.ignore_video(v["youtube_id"]) for v in to_ignore]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, Exception):
            errors += 1
        else:
            ignored += 1

    msg = f"Ignored {ignored} video{'s' if ignored != 1 else ''} older than {days} days."
    if errors:
        msg += f" ({errors} failed)"
    return HTMLResponse(f'<p class="text-sm text-green-400">{msg}</p>')


@router.post("/rescan")
async def trigger_rescan(request: Request):
    try:
        await request.app.state.ta.trigger_rescan()
        return HTMLResponse(
            '<span class="text-green-400 text-xs font-medium">Rescan started</span>'
        )
    except Exception:
        return HTMLResponse(
            '<span class="text-red-400 text-xs font-medium">Rescan failed</span>'
        )


@router.post("/ignore-shorts-streams")
async def ignore_shorts_streams(request: Request):
    ta = request.app.state.ta
    videos = await ta.get_all_pending()
    to_ignore = [v for v in videos if v.get("vid_type") in ("shorts", "streams")]

    if not to_ignore:
        return HTMLResponse(
            '<p class="text-sm" style="color:var(--c-text3)">No shorts or streams in the pending queue.</p>'
        )

    tasks = [ta.ignore_video(v["youtube_id"]) for v in to_ignore]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    ignored = sum(1 for r in results if not isinstance(r, Exception))
    errors = len(results) - ignored

    msg = f"Ignored {ignored} short{'s' if ignored != 1 else ''}/stream{'s' if ignored != 1 else ''}."
    if errors:
        msg += f" ({errors} failed)"
    return HTMLResponse(f'<p class="text-sm text-green-400">{msg}</p>')


@router.post("/scan-subscriptions")
async def scan_subscriptions(request: Request):
    try:
        await request.app.state.ta.scan_subscriptions()
        return HTMLResponse(
            '<span class="text-green-400 text-xs font-medium">Subscription scan started</span>'
        )
    except Exception:
        return HTMLResponse(
            '<span class="text-red-400 text-xs font-medium">Scan failed</span>'
        )


@router.post("/vid-type-toggle")
async def vid_type_toggle(request: Request, vid_type: str = Form(...), enabled: str = Form(...)):
    ta = request.app.state.ta
    is_enabled = enabled == "true"
    size = 50 if is_enabled else 0
    key = "shorts_channel_size" if vid_type == "shorts" else "live_channel_size"
    label = "Shorts" if vid_type == "shorts" else "Streams"
    try:
        await ta.update_ta_config({"subscriptions": {key: size}})
        state = "enabled" if is_enabled else "disabled"
        color = "text-green-400" if is_enabled else "text-gray-400"
        return HTMLResponse(
            f'<span class="{color} text-xs font-medium">{label} {state}</span>'
        )
    except Exception:
        return HTMLResponse(
            '<span class="text-red-400 text-xs font-medium">Update failed</span>'
        )


@router.post("/downloads")
async def save_downloads(
    request: Request,
    integrate_sponsorblock: str = Form("false"),
    autodelete_days: str = Form(""),
    subtitle: str = Form(""),
    subtitle_source: str = Form(""),
    subtitle_index: str = Form("false"),
    comment_max: str = Form(""),
    comment_sort: str = Form("top"),
    integrate_ryd: str = Form("false"),
    add_metadata: str = Form("false"),
    format: str = Form(""),
    format_sort: str = Form(""),
    sleep_interval: str = Form("10"),
    limit_speed: str = Form(""),
    throttledratelimit: str = Form(""),
    extractor_lang: str = Form(""),
):
    def _str(v: str) -> str | None:
        return v.strip() or None

    def _int(v: str) -> int | None:
        v = v.strip()
        return int(v) if v.isdigit() else None

    def _bool(v: str) -> bool:
        return v == "true"

    payload = {
        "downloads": {
            "integrate_sponsorblock": _bool(integrate_sponsorblock),
            "autodelete_days": _int(autodelete_days),
            "subtitle": _str(subtitle),
            "subtitle_source": _str(subtitle_source),
            "subtitle_index": _bool(subtitle_index),
            "comment_max": _str(comment_max),
            "comment_sort": comment_sort or "top",
            "integrate_ryd": _bool(integrate_ryd),
            "add_metadata": _bool(add_metadata),
            "format": _str(format),
            "format_sort": _str(format_sort),
            "sleep_interval": int(sleep_interval) if sleep_interval.strip().isdigit() else 10,
            "limit_speed": _int(limit_speed),
            "throttledratelimit": _int(throttledratelimit),
            "extractor_lang": _str(extractor_lang),
        }
    }
    try:
        await request.app.state.ta.update_ta_config(payload)
        return HTMLResponse(
            '<span class="text-green-400 text-sm font-medium">Settings saved</span>'
        )
    except Exception:
        return HTMLResponse(
            '<span class="text-red-400 text-sm font-medium">Save failed</span>'
        )


@router.post("/page-size")
async def save_page_size(page_size: int = Form(...)):
    page_size = max(10, min(200, page_size))
    app_settings.set("page_size", page_size)
    return HTMLResponse(
        f'<span class="text-green-400 text-xs font-medium">Saved — showing {page_size} per page</span>'
    )


@router.post("/scan-interval")
async def save_scan_interval(interval: int = Form(...)):
    app_settings.set("scan_interval_minutes", interval if interval > 0 else None)
    if interval > 0:
        label = f"{interval} min" if interval < 60 else f"{interval // 60}h"
        msg = f"Scanning every {label}"
    else:
        msg = "Auto-scan disabled"
    return HTMLResponse(f'<span class="text-green-400 text-xs font-medium">{msg}</span>')
