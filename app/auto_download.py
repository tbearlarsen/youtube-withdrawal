import json
from pathlib import Path

_PATH = Path("data/auto_download.json")


def _load() -> list[str]:
    try:
        return json.loads(_PATH.read_text())
    except Exception:
        return []


def _save(ids: list[str]) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(json.dumps(ids))


def get_all() -> list[str]:
    return _load()


def is_auto(channel_id: str) -> bool:
    return channel_id in _load()


def enable(channel_id: str) -> None:
    ids = _load()
    if channel_id not in ids:
        ids.append(channel_id)
        _save(ids)


def disable(channel_id: str) -> None:
    ids = _load()
    if channel_id in ids:
        ids.remove(channel_id)
        _save(ids)


def toggle(channel_id: str) -> bool:
    """Toggle auto-download. Returns new enabled state."""
    ids = _load()
    if channel_id in ids:
        ids.remove(channel_id)
        _save(ids)
        return False
    ids.append(channel_id)
    _save(ids)
    return True
