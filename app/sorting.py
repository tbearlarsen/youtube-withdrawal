"""Shared video ordering. TA's download list comes back in queue-insertion order (not publish
order), and its `published` field arrives in more than one format, so sort in-app on a normalized key."""

import re

SORT_OPTIONS = {
    "newest":   "Newest",
    "oldest":   "Oldest",
    "title":    "Title A → Z",
    "longest":  "Longest",
    "shortest": "Shortest",
}
DEFAULT_SORT = "newest"


def published_key(video: dict) -> str:
    """Sortable YYYYMMDD[HHMMSS] from TA's ISO timestamp (or a bare YYYYMMDD / YYYY-MM-DD); '' if missing."""
    digits = re.sub(r"\D", "", str(video.get("published") or ""))
    return digits[:14]


_UNIT_SECONDS = {"h": 3600, "m": 60, "s": 1}


def duration_seconds(video: dict) -> int:
    """Seconds, or 0 if unknown. Downloaded videos carry int player.duration; queue items carry a
    string like '39m 10s' / '1h 02m 03s' (confirmed against the live TA 2026-10-02), or 'H:MM:SS'."""
    player = video.get("player") or {}
    if isinstance(player.get("duration"), (int, float)):
        return int(player["duration"])
    raw = video.get("duration")
    if isinstance(raw, (int, float)):
        return int(raw)
    text = str(raw or "").strip().lower()
    units = re.findall(r"(\d+)\s*([hms])", text)
    if units:
        return sum(int(n) * _UNIT_SECONDS[u] for n, u in units)
    if re.fullmatch(r"\d+(:\d+)*", text):
        seconds = 0
        for part in text.split(":"):
            seconds = seconds * 60 + int(part)
        return seconds
    return 0


def sort_videos(videos: list[dict], sort: str) -> list[dict]:
    """Return videos ordered by one of SORT_OPTIONS; ties fall back to newest first."""
    by_newest = sorted(videos, key=published_key, reverse=True)
    if sort == "oldest":
        # Undated videos go last here too, not first.
        return sorted(videos, key=lambda v: (published_key(v) == "", published_key(v)))
    if sort == "title":
        return sorted(by_newest, key=lambda v: (v.get("title") or "").casefold())
    if sort == "longest":
        return sorted(by_newest, key=duration_seconds, reverse=True)
    if sort == "shortest":
        # Unknown durations (0) go last rather than looking like the shortest videos.
        return sorted(by_newest, key=lambda v: (duration_seconds(v) == 0, duration_seconds(v)))
    return by_newest
