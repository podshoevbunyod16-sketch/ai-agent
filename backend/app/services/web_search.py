"""
Tavily Web Search integration.
Free tier: 1,000 API calls/month. Sign up at https://app.tavily.com/home
"""
import httpx
from app.core.config import settings


async def tavily_search(query: str, max_results: int = 5) -> dict:
    """
    Execute a web search via Tavily API.
    Returns a dict with "results" list and "answer" (AI summary).
    """
    if not settings.TAVILY_API_KEY:
        return {
            "error": "Tavily API key not configured. Get one at https://app.tavily.com/home",
            "results": [],
            "answer": "",
        }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{settings.TAVILY_BASE_URL}/search",
                headers={"Authorization": f"Bearer {settings.TAVILY_API_KEY}"},
                json={
                    "query": query,
                    "max_results": max(min(max_results, 10), 1),
                    "search_depth": "basic",
                    "include_answer": True,
                    "include_raw_content": False,
                },
            )
            if resp.status_code == 200:
                return resp.json()
            else:
                return {
                    "error": f"Tavily API returned {resp.status_code}: {resp.text}",
                    "results": [],
                    "answer": "",
                }
        except Exception as e:
            return {
                "error": f"Search request failed: {str(e)}",
                "results": [],
                "answer": "",
            }
