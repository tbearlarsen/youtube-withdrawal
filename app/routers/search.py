from fastapi import APIRouter, Request

from app.templating import templates

router = APIRouter()


@router.get("/search")
async def search_page(request: Request, q: str = ""):
    results = {}
    if q:
        results = await request.app.state.ta.search(q)
    return templates.TemplateResponse(
        request,
        "pages/search.html",
        {
            "query": q,
            "results": results,
            "active_page": "search",
        },
    )
