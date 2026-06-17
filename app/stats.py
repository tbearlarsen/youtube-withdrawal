import json
from datetime import datetime
from pathlib import Path

_FILE = Path("data/stats.json")


def _load() -> dict:
    if not _FILE.exists():
        return {}
    try:
        return json.loads(_FILE.read_text())
    except Exception:
        return {}


def _save(data: dict) -> None:
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(json.dumps(data))


def _week_key() -> str:
    return datetime.now().strftime("%Y-W%W")


def increment_requests() -> None:
    data = _load()
    key = _week_key()
    data[key] = data.get(key, 0) + 1
    _save(data)


def get_weekly_requests() -> int:
    return _load().get(_week_key(), 0)
