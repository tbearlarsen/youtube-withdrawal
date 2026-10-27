import json
from pathlib import Path

_FILE = Path("data/kept.json")


def _load() -> set[str]:
    if not _FILE.exists():
        return set()
    try:
        return set(json.loads(_FILE.read_text()))
    except Exception:
        return set()


def _save(ids: set[str]) -> None:
    _FILE.parent.mkdir(exist_ok=True)
    _FILE.write_text(json.dumps(sorted(ids)))


def add(video_id: str) -> None:
    ids = _load()
    ids.add(video_id)
    _save(ids)


def remove(video_id: str) -> None:
    ids = _load()
    if video_id in ids:
        ids.discard(video_id)
        _save(ids)


def is_kept(video_id: str) -> bool:
    return video_id in _load()


def get_all() -> set[str]:
    return _load()
