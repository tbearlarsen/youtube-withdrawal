"""Mark downloaded videos as watched in the user's YouTube account.

Every video TubeArchivist has downloaded gets a yt-dlp --mark-watched run with the
user's logged-in cookies, so it shows up in their YouTube watch history. TA has a
cookie setting but no mark-watched feature, and turning on TA's own cookie would run
every scan/download as the user's account — so the cookie lives only here.

Pacing, to keep the account's activity looking like a person:
- Videos downloaded after this job first ran ("new") are marked on the next check
  (~every 30 min), with a 1–3 min gap between videos.
- Videos downloaded before that ("backlog") are marked one at a time, at most one
  per ~hour, only between 08:00 and 23:00 Europe/Copenhagen.

The feature is off while the cookie file doesn't exist. State lives in
data/yt_history.json (canonical for "already sent to YouTube").
"""
import asyncio
import json
import random
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from app.config import settings

_FILE = Path("data/yt_history.json")
_TZ = ZoneInfo("Europe/Copenhagen")

CHECK_INTERVAL = (20 * 60, 40 * 60)   # seconds between checks
NEW_GAP = (60, 180)                   # seconds between consecutive new-video marks
BACKLOG_MIN_GAP = 55 * 60             # seconds between backlog marks
ACTIVE_HOURS = (8, 23)                # local hours when backlog marks may run
MAX_ATTEMPTS = 3                      # per video, before it's skipped
ALERT_AFTER = 3                       # consecutive failed runs before an ntfy alert
YTDLP_UPDATE_EVERY = 24 * 3600

# yt-dlp messages that mean the video itself can't be watched — skip it, don't alert
_UNAVAILABLE = re.compile(
    r"Video unavailable|Private video|has been removed|members-only|Join this channel|"
    r"account associated with this video has been terminated|This live event will begin",
    re.I,
)
_LOGGED_OUT = re.compile(r"cookies are no longer valid|Sign in to confirm", re.I)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load() -> dict:
    try:
        data = json.loads(_FILE.read_text())
    except Exception:
        data = {}
    data.setdefault("started_at", None)
    data.setdefault("marked", {})          # youtube_id -> ISO time marked
    data.setdefault("skipped", {})         # youtube_id -> reason
    data.setdefault("attempts", {})        # youtube_id -> failed attempt count
    data.setdefault("last_backlog_mark", None)
    data.setdefault("consecutive_failures", 0)
    data.setdefault("alerted", False)
    data.setdefault("last_error", None)
    data.setdefault("last_run", None)
    return data


def _save(data: dict) -> None:
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(json.dumps(data, indent=2))


def cookie_path() -> Path:
    return Path(settings.yt_cookie_file)


def enabled() -> bool:
    return cookie_path().is_file()


def _downloaded_at(video: dict) -> float:
    try:
        return float(video.get("date_downloaded") or 0)
    except (TypeError, ValueError):
        return 0.0


async def _ytdlp_mark(video_id: str) -> tuple[bool, str]:
    """Run yt-dlp --mark-watched on one video. Returns (ok, output tail).

    yt-dlp works on a temp copy of the cookie file and saves YouTube's rotated
    session cookies into it; those are written back into the real file (in place,
    keeping its owner/mode) only if the result still looks like a logged-in jar.
    """
    src = cookie_path()
    with tempfile.TemporaryDirectory() as tmp:
        jar = Path(tmp) / "cookies.txt"
        shutil.copyfile(src, jar)
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp", "-v",
            "--cookies", str(jar),
            "--mark-watched", "--skip-download", "--no-progress",
            "--ignore-no-formats-error",
            "--extractor-args", f"youtubepot-bgutilhttp:base_url={settings.pot_provider_url}",
            f"https://www.youtube.com/watch?v={video_id}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            out_b, _ = await asyncio.wait_for(proc.communicate(), timeout=180)
        except asyncio.TimeoutError:
            proc.kill()
            return False, "yt-dlp timed out after 180s"
        out = out_b.decode(errors="replace")

        new_jar = jar.read_text(errors="replace") if jar.exists() else ""
        if new_jar.startswith("# Netscape HTTP Cookie File") and "LOGIN_INFO" in new_jar:
            with open(src, "w") as f:
                f.write(new_jar)

    lines = [l for l in out.splitlines() if not l.startswith("[debug] ")]
    tail = "\n".join(lines[-6:])
    logged_in = "Found YouTube account cookies" in out
    ok = (
        proc.returncode == 0
        and logged_in
        and "Marking fully watched" in out
        and "Unable to mark" not in out
    )
    if not logged_in and not _LOGGED_OUT.search(tail):
        tail = "yt-dlp did not find logged-in YouTube cookies\n" + tail
    return ok, tail


async def _notify(title: str, message: str, priority: str = "default") -> None:
    if not (settings.ntfy_url and settings.ntfy_topic):
        return
    headers = {"Title": title, "Tags": "tv", "Priority": priority}
    if settings.ntfy_token:
        headers["Authorization"] = f"Bearer {settings.ntfy_token}"
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            await c.post(f"{settings.ntfy_url.rstrip('/')}/{settings.ntfy_topic}",
                         content=message.encode(), headers=headers)
    except Exception as e:
        print(f"[yt-history] ntfy failed: {e}", file=sys.stderr)


async def mark_one(video: dict, data: dict) -> bool:
    """Mark a single video, update state. Returns True on success."""
    vid = video["youtube_id"]
    ok, tail = await _ytdlp_mark(vid)
    data["last_run"] = _now()
    if ok:
        data["marked"][vid] = _now()
        data["attempts"].pop(vid, None)
        if data["alerted"]:
            await _notify("YouTube history sync recovered",
                          f"Marking works again ({video.get('title', vid)}).")
        data["consecutive_failures"] = 0
        data["alerted"] = False
        data["last_error"] = None
        print(f"[yt-history] marked {vid}", file=sys.stderr)
        _save(data)
        return True

    if _UNAVAILABLE.search(tail):
        data["skipped"][vid] = tail.splitlines()[-1][:300] if tail else "unavailable"
        data["attempts"].pop(vid, None)
        print(f"[yt-history] skipped {vid}: unavailable", file=sys.stderr)
        _save(data)
        return False

    # Only blame the video itself when the setup is otherwise healthy; a dead cookie or
    # broken yt-dlp must not burn through every video's attempts.
    systemic = bool(_LOGGED_OUT.search(tail)) or "did not find logged-in" in tail \
        or data["consecutive_failures"] >= ALERT_AFTER - 1
    if not systemic:
        data["attempts"][vid] = data["attempts"].get(vid, 0) + 1
    if data["attempts"].get(vid, 0) >= MAX_ATTEMPTS:
        data["skipped"][vid] = f"failed {MAX_ATTEMPTS} times: " + (tail.splitlines()[-1][:250] if tail else "")
        data["attempts"].pop(vid, None)
    data["consecutive_failures"] += 1
    data["last_error"] = {"at": _now(), "video": vid, "output": tail[-1500:]}
    print(f"[yt-history] failed {vid}:\n{tail}", file=sys.stderr)
    if data["consecutive_failures"] >= ALERT_AFTER and not data["alerted"]:
        hint = ("The YouTube cookie looks logged out — export a fresh one from a private window "
                "into /docker/youtube-withdrawal/secrets/youtube-cookies.txt."
                if _LOGGED_OUT.search(tail) or "did not find logged-in" in tail
                else "See the Settings page (YouTube History) for the last error.")
        await _notify("YouTube history sync failing",
                      f"{data['consecutive_failures']} failed runs in a row. {hint}\n\n{tail[-600:]}",
                      priority="high")
        data["alerted"] = True
    _save(data)
    return False


async def run_once(ta) -> None:
    """One check: mark all new downloads, then at most one backlog video."""
    data = _load()
    if not data["started_at"]:
        data["started_at"] = datetime.now(timezone.utc).timestamp()
        _save(data)

    videos = await ta.get_all_videos()
    done = set(data["marked"]) | set(data["skipped"])
    todo = [v for v in videos if v.get("youtube_id") and v["youtube_id"] not in done]
    new = sorted((v for v in todo if _downloaded_at(v) >= data["started_at"]), key=_downloaded_at)
    backlog = sorted((v for v in todo if _downloaded_at(v) < data["started_at"]),
                     key=_downloaded_at, reverse=True)

    if data["consecutive_failures"] >= ALERT_AFTER:
        # Broken state: one probe per check until a run succeeds again.
        probe = (new or backlog)[:1]
        if probe and await mark_one(probe[0], data):
            await asyncio.sleep(random.uniform(*NEW_GAP))
            await run_once(ta)  # healthy again: carry on normally
        return

    for i, video in enumerate(new):
        if i:
            await asyncio.sleep(random.uniform(*NEW_GAP))
        if not await mark_one(video, data) and data["consecutive_failures"] >= ALERT_AFTER:
            return  # something systemic; don't keep hammering

    if not backlog or data["consecutive_failures"] >= ALERT_AFTER:
        return
    hour = datetime.now(_TZ).hour
    if not (ACTIVE_HOURS[0] <= hour < ACTIVE_HOURS[1]):
        return
    last = data["last_backlog_mark"]
    if last and datetime.now(timezone.utc).timestamp() - last < BACKLOG_MIN_GAP:
        return
    if new:
        await asyncio.sleep(random.uniform(*NEW_GAP))
    data["last_backlog_mark"] = datetime.now(timezone.utc).timestamp()
    _save(data)
    await mark_one(backlog[0], data)


async def _update_ytdlp() -> None:
    """Keep yt-dlp current (YouTube breaks old versions); mirrors TA_AUTO_UPDATE_YTDLP.
    Only yt-dlp itself — the bgutil plugin stays pinned to the provider server's version."""
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "pip", "install", "-q", "--no-cache-dir", "-U", "yt-dlp[default]",
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    if proc.returncode != 0:
        print(f"[yt-history] yt-dlp update failed: {err.decode(errors='replace')[-300:]}", file=sys.stderr)


async def loop(ta) -> None:
    last_update = 0.0
    await asyncio.sleep(60)
    while True:
        try:
            if enabled():
                now = datetime.now(timezone.utc).timestamp()
                if now - last_update > YTDLP_UPDATE_EVERY:
                    await _update_ytdlp()
                    last_update = now
                await run_once(ta)
        except Exception as e:
            print(f"[yt-history] check failed: {e!r}", file=sys.stderr)
        await asyncio.sleep(random.uniform(*CHECK_INTERVAL))


def status(downloaded_ids: set[str] | None = None) -> dict:
    data = _load()
    done = set(data["marked"]) | set(data["skipped"])
    return {
        "enabled": enabled(),
        "marked": len(data["marked"]),
        "skipped": data["skipped"],
        "remaining": len(downloaded_ids - done) if downloaded_ids is not None else None,
        "last_run": data["last_run"],
        "last_error": data["last_error"],
        "alerted": data["alerted"],
    }
