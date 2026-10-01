from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, Response

from app import categories
from app.favorites import get_favorites
from app.templating import templates

router = APIRouter()


def _refresh() -> Response:
    return Response(headers={"HX-Refresh": "true"})


@router.get("/categories")
async def categories_page(request: Request, show: str = "all"):
    channels = await request.app.state.ta.get_all_subscribed_channels()
    assignments = categories.get_assignments()
    if show == "uncategorized":
        channels = [c for c in channels if c["channel_id"] not in assignments]
    channels.sort(key=lambda c: c.get("channel_name", "").lower())
    return templates.TemplateResponse(
        request,
        "pages/categories.html",
        {
            "categories": categories.get_categories(),
            "assignments": assignments,
            "channels": channels,
            "favorites": set(get_favorites()),
            "show": show,
            "active_page": "channels",
            "active_section": "library",
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
