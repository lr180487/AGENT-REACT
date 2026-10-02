from __future__ import annotations
from typing import Any
import httpx
from app.config import settings

class GoogleSearchError(RuntimeError):
    pass

async def google_search(query: str, *, num_results: int = 5, safe: str | None = None) -> dict[str, Any]:
    if not settings.GOOGLE_API_KEY or not settings.GOOGLE_CSE_ID:
        raise GoogleSearchError("Google Search no está configurado: define GOOGLE_API_KEY y GOOGLE_CSE_ID.")
    params = {
        "key": settings.GOOGLE_API_KEY,
        "cx": settings.GOOGLE_CSE_ID,
        "q": query,
        "num": max(1, min(int(num_results), 10)),
        "safe": safe or settings.GOOGLE_SAFESEARCH,
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get("https://www.googleapis.com/customsearch/v1", params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        raise GoogleSearchError(f"Google Search HTTP error: {exc}") from exc
    items = data.get("items") or []
    return {
        "tool": "google_search",
        "query": query,
        "total_results": data.get("searchInformation", {}).get("totalResults"),
        "results": [
            {"title": item.get("title"), "url": item.get("link"), "snippet": item.get("snippet"), "display_link": item.get("displayLink")}
            for item in items
        ],
    }

try:
    from langchain_core.tools import StructuredTool
    langchain_google_search_tool = StructuredTool.from_function(
        coroutine=google_search,
        name="google_search",
        description="Busca información pública en Google mediante Programmable Search. Úsala cuando necesites información externa o actualizada.",
    )
except Exception:
    langchain_google_search_tool = None
