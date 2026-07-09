import os
import logging
import requests
from config import Config

logger = logging.getLogger(__name__)


def google_search(query, num_results=5):
    """
    Выполняет поиск через Google Custom Search JSON API.
    Возвращает отформатированную строку с результатами,
    либо None, если ключи не настроены или поиск не удался.
    """
    api_key = Config.GOOGLE_API_KEY
    cse_id = Config.GOOGLE_CSE_ID

    if not api_key or not cse_id:
        logger.warning("Google Search пропущен: не заданы GOOGLE_API_KEY / GOOGLE_CSE_ID в .env")
        return None

    try:
        resp = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "key": api_key,
                "cx": cse_id,
                "q": query,
                "num": num_results
            },
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        if not items:
            return None

        lines = []
        for i, item in enumerate(items, 1):
            title = item.get("title", "")
            snippet = item.get("snippet", "").replace("\n", " ")
            link = item.get("link", "")
            lines.append(f"{i}. {title}\n{snippet}\nИсточник: {link}")
        return "\n\n".join(lines)

    except requests.exceptions.RequestException as e:
        logger.exception("Ошибка Google Search API")
        return None
