import json
from pathlib import Path

_FILE = Path("data/deleted.json")


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


def get_all() -> set[str]:
    return _load()
