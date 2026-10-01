"""User-defined channel categories: an ordered list of names, and at most one per channel.

TubeArchivist has no notion of channel grouping, so this is canonical locally.
"""
import json
from pathlib import Path

_FILE = Path("data/categories.json")

UNCATEGORIZED = "__none__"


def _load() -> dict:
    data: dict = {}
    if _FILE.exists():
        try:
            data = json.loads(_FILE.read_text())
        except Exception:
            data = {}
    return {
        "categories": list(data.get("categories", [])),
        "assignments": dict(data.get("assignments", {})),
    }


def _save(data: dict) -> None:
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(json.dumps(data, indent=2))


def get_categories() -> list[str]:
    return _load()["categories"]


def get_assignments() -> dict[str, str]:
    """channel_id -> category name."""
    return _load()["assignments"]


def category_of(channel_id: str) -> str | None:
    return get_assignments().get(channel_id)


def set_category(channel_id: str, name: str | None) -> None:
    data = _load()
    if name and name in data["categories"]:
        data["assignments"][channel_id] = name
    else:
        data["assignments"].pop(channel_id, None)
    _save(data)


def add_category(name: str) -> bool:
    name = name.strip()
    data = _load()
    if not name or name == UNCATEGORIZED or name in data["categories"]:
        return False
    data["categories"].append(name)
    _save(data)
    return True


def rename_category(old: str, new: str) -> bool:
    new = new.strip()
    data = _load()
    if old not in data["categories"] or not new or new == UNCATEGORIZED or new in data["categories"]:
        return False
    data["categories"][data["categories"].index(old)] = new
    data["assignments"] = {
        cid: (new if cat == old else cat) for cid, cat in data["assignments"].items()
    }
    _save(data)
    return True


def delete_category(name: str) -> None:
    """Remove a category; its channels become uncategorized."""
    data = _load()
    if name in data["categories"]:
        data["categories"].remove(name)
    data["assignments"] = {cid: cat for cid, cat in data["assignments"].items() if cat != name}
    _save(data)


def move_category(name: str, offset: int) -> None:
    data = _load()
    cats = data["categories"]
    if name not in cats:
        return
    i = cats.index(name)
    j = max(0, min(len(cats) - 1, i + offset))
    cats.insert(j, cats.pop(i))
    _save(data)


def video_channel_id(video: dict) -> str | None:
    """Channel ID of a download-queue item (flat) or an indexed video (nested)."""
    return video.get("channel_id") or (video.get("channel") or {}).get("channel_id")


def group_videos(videos: list[dict]) -> list[dict]:
    """Split videos into sections in category order, Uncategorized last; empty sections dropped.

    Each section: {"key": category name or UNCATEGORIZED, "label": str, "videos": [...]}.
    Order within a section is preserved from the input.
    """
    data = _load()
    assignments = data["assignments"]
    buckets: dict[str, list[dict]] = {name: [] for name in data["categories"]}
    uncategorized: list[dict] = []
    for v in videos:
        cat = assignments.get(video_channel_id(v))
        (buckets[cat] if cat in buckets else uncategorized).append(v)
    sections = [
        {"key": name, "label": name, "videos": vids} for name, vids in buckets.items() if vids
    ]
    if uncategorized:
        sections.append({"key": UNCATEGORIZED, "label": "Uncategorized", "videos": uncategorized})
    return sections


def build_view(videos: list[dict], view: str = "grouped") -> dict:
    """Template context for a category-aware video page.

    Grouped (default): one section per category, every video shown, with a
    table of contents linking to each section's anchor. "list" (or no
    categories at all): one flat grid.
    """
    sections = group_videos(videos)
    for i, section in enumerate(sections, 1):
        section["anchor"] = f"cat-{i}"
        section["count"] = len(section["videos"])
    mode = "flat" if view == "list" or not get_categories() else "grouped"
    return {
        "toc": sections if get_categories() else [],
        "current_view": "list" if view == "list" else "grouped",
        "view_mode": mode,
        "videos": videos,
        "sections": sections if mode == "grouped" else [],
    }
