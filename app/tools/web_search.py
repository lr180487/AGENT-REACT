from __future__ import annotations
import httpx
from app.config import settings

class WebSearchTool:
    name = "web_search"
    async def run(self, query: str) -> dict:
        if not settings.TAVILY_API_KEY:
            return {"tool": self.name, "available": False, "error": "TAVILY_API_KEY no configurada", "results": []}
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post("https://api.tavily.com/search", json={
                "api_key": settings.TAVILY_API_KEY, "query": query,
                "max_results": settings.WEB_SEARCH_MAX_RESULTS, "search_depth": "advanced",
            })
            r.raise_for_status()
            data = r.json()
        return {"tool": self.name, "available": True, "results": data.get("results", []), "query": query}
