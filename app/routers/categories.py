from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, Response

from app import auto_download as auto_dl, categories
from app.favorites import get_favorites
from app.routers.channels import pending_counts
from app.templating import templates

router = APIRouter()


def _refresh() -> Response:
    return Response(headers={"HX-Refresh": "true"})


@router.get("/categories")
async def categories_overview(request: Request):
    """Subscribed channels grouped by category, in category order, Uncategorized last."""
    ta = request.app.state.ta
    channels = await ta.get_all_subscribed_channels()
    channels.sort(key=lambda c: c.get("channel_name", "").lower())
    sections = categories.group_channels(channels)
    counts = await pending_counts(ta, channels)
    for i, section in enumerate(sections, 1):
        section["anchor"] = f"cat-{i}"
        section["pending"] = sum(counts.get(c["channel_id"], 0) for c in section["channels"])
    return templates.TemplateResponse(
        request,
        "pages/categories.html",
        {
            "sections": sections,
            "has_categories": bool(categories.get_categories()),
            "favorites": set(get_favorites()),
            "pending_counts": counts,
            "auto_download_ids": set(auto_dl.get_all()),
            "active_page": "categories",
        },
    )


@router.get("/categories/manage")
async def categories_manage(request: Request, show: str = "all"):
    channels = await request.app.state.ta.get_all_subscribed_channels()
    assignments = categories.get_assignments()
    if show == "uncategorized":
        channels = [c for c in channels if c["channel_id"] not in assignments]
    channels.sort(key=lambda c: c.get("channel_name", "").lower())
    return templates.TemplateResponse(
        request,
        "pages/categories_manage.html",
        {
            "categories": categories.get_categories(),
            "assignments": assignments,
            "channels": channels,
            "favorites": set(get_favorites()),
            "show": show,
            "active_page": "categories",
        },
    )


@router.post("/categories")
async def add_category(name: str = Form("")):
    categories.add_category(name)
    return _refresh()


@router.post("/categories/rename")
async def rename_category(old: str = Form(...), new: str = Form("")):
    categories.rename_category(old, new)
    return _refresh()


@router.post("/categories/delete")
async def delete_category(name: str = Form(...)):
    categories.delete_category(name)
    return _refresh()


@router.post("/categories/move")
async def move_category(name: str = Form(...), offset: int = Form(...)):
    categories.move_category(name, offset)
    return _refresh()


@router.post("/channels/{channel_id}/category")
async def set_channel_category(channel_id: str, category: str = Form("")):
    categories.set_category(channel_id, category or None)
    return HTMLResponse("")
