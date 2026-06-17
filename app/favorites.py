import json
from pathlib import Path

_FILE = Path("data/favorites.json")


def _load() -> list[str]:
    if not _FILE.exists():
        return []
    try:
        return json.loads(_FILE.read_text())
    except Exception:
        return []


def _save(ids: list[str]) -> None:
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(json.dumps(ids))


def get_favorites() -> list[str]:
    return _load()


def is_favorite(channel_id: str) -> bool:
    return channel_id in _load()


def toggle_favorite(channel_id: str) -> bool:
    """Toggle and return new state (True = now a favorite)."""
    ids = _load()
    if channel_id in ids:
        ids.remove(channel_id)
        _save(ids)
        return False
    ids.append(channel_id)
    _save(ids)
    return True
