from fastapi import APIRouter, Request

from app.templating import templates

router = APIRouter()


@router.get("/downloads")
async def downloads_page(request: Request):
    videos = await request.app.state.ta.get_all_videos()
    return templates.TemplateResponse(
        request,
        "pages/downloads.html",
        {
            "videos": videos,
            "active_page": "downloads",
            "active_section": "library",
            "show_channel": True,
        },
    )
