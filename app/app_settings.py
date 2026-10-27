import json
from pathlib import Path

_FILE = Path("data/settings.json")
_DEFAULTS = {
    "watch_url": "",
    "home_limit": 200,
    # Library visibility toggles (Home, Downloads, channel Downloaded tabs)
    "watched_filter": "all",  # all | unwatched | watched
    "hide_downloaded": False,
}

VISIBILITY_KEYS = ("hide_downloaded",)
WATCHED_FILTERS = ("all", "unwatched", "watched")


def _load() -> dict:
    if not _FILE.exists():
        return dict(_DEFAULTS)
    try:
        data = json.loads(_FILE.read_text())
    except Exception:
        return dict(_DEFAULTS)
    # hide_watched (bool) predates watched_filter
    if "watched_filter" not in data and data.pop("hide_watched", False):
        data["watched_filter"] = "unwatched"
    return {**_DEFAULTS, **data}


def _save(data: dict) -> None:
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(json.dumps(data, indent=2))


def get_all() -> dict:
    return _load()


def get(key: str):
    return _load().get(key, _DEFAULTS.get(key))


def set(key: str, value) -> None:
    data = _load()
    data[key] = value
    _save(data)


def visible_downloads(videos: list[dict], only_watched_ok: bool = True) -> list[dict]:
    """Downloaded videos filtered by watched_filter. Home mixes in pending videos,
    so it passes only_watched_ok=False and only ever hides watched ones."""
    f = get("watched_filter")
    if f == "unwatched":
        return [v for v in videos if not (v.get("player") or {}).get("watched")]
    if f == "watched" and only_watched_ok:
        return [v for v in videos if (v.get("player") or {}).get("watched")]
    return videos
