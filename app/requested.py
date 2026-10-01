import json
import time
from pathlib import Path

_FILE = Path("data/requested.json")

# Videos added by URL only enter TA's queue once TA's background task has run,
# so reconciliation must not drop them as stale straight away. In-memory only:
# a restart within the grace window is the one case it doesn't cover.
_GRACE_SECONDS = 10 * 60
_added_at: dict[str, float] = {}


def _load() -> set[str]:
    if not _FILE.exists():
        return set()
    try:
        return set(json.loads(_FILE.read_text()))
    except Exception:
        return set()


def _save(ids: set[str]) -> None:
    _FILE.parent.mkdir(exist_ok=True)
    _FILE.write_text(json.dumps(list(ids)))


def add(video_id: str) -> None:
    ids = _load()
    ids.add(video_id)
    _save(ids)
    _added_at[video_id] = time.monotonic()


def remove(video_id: str) -> None:
    ids = _load()
    ids.discard(video_id)
    _save(ids)


def get_all() -> set[str]:
    return _load()


def prune(pending_ids: set[str]) -> None:
    """Drop tracked IDs no longer pending in TA (downloaded or removed), sparing recent additions."""
    now = time.monotonic()
    ids = _load()
    keep = {
        v for v in ids
        if v in pending_ids or now - _added_at.get(v, float("-inf")) < _GRACE_SECONDS
    }
    if keep != ids:
        _save(keep)
