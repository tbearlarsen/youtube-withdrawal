from fastapi import APIRouter, Request

from app.templating import templates

router = APIRouter()


@router.get("/downloads")
async def downloads_page(request: Request, page: int = 0):
    ta = request.app.state.ta
    data = await ta.get_video_list(page=page, sort="published", order="desc")
    return templates.TemplateResponse(
        request,
        "pages/downloads.html",
        {
            "videos": data.get("data", []),
            "paginate": data.get("paginate"),
            "active_page": "downloads",
            "show_channel": True,
        },
    )
