import json
from pathlib import Path

_FILE = Path("data/settings.json")
_DEFAULTS = {
    "page_size": 60,
    "scan_interval_minutes": 30,
}


def _load() -> dict:
    if not _FILE.exists():
        return dict(_DEFAULTS)
    try:
        return {**_DEFAULTS, **json.loads(_FILE.read_text())}
    except Exception:
        return dict(_DEFAULTS)


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
