from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi.templating import Jinja2Templates
from app import app_settings

templates = Jinja2Templates(directory="app/templates")


def _ta_thumb(url: str | None) -> str:
    """Convert a TA cache URL or path to our local proxy URL."""
    if not url:
        return ""
    if url.startswith("http"):
        path = urlparse(url).path.lstrip("/")
    else:
        path = url.lstrip("/")
    return f"/ta-cache/{path}"


def _format_published(date_str: str | None) -> str:
    """Format TA date strings to 'Jan 15, 2026'. Handles YYYYMMDD, YYYY-MM-DD, and full ISO timestamps."""
    if not date_str:
        return ""
    s = str(date_str)
    try:
        return datetime.strptime(s[:8], "%Y%m%d").strftime("%b %d, %Y")
    except ValueError:
        pass
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").strftime("%b %d, %Y")
    except ValueError:
        pass
    return s


def _time_ago(refresh_str: str | None) -> str:
    """Convert an ISO timestamp to a relative 'X hours ago' string."""
    if not refresh_str:
        return "never"
    try:
        dt = datetime.fromisoformat(refresh_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        diff = datetime.now(timezone.utc) - dt
        hours = int(diff.total_seconds() / 3600)
        if hours < 1:
            return "just now"
        if hours < 24:
            return f"{hours}h ago"
        return f"{hours // 24}d ago"
    except Exception:
        return str(refresh_str)


templates.env.filters["ta_thumb"] = _ta_thumb
templates.env.filters["format_published"] = _format_published
templates.env.filters["time_ago"] = _time_ago
templates.env.globals["watch_url"] = lambda: app_settings.get("watch_url") or ""
