import re

SEARCH_KEYWORDS = ['найти','поиск','поищи','найди','ищи','узнай','проверь','latest','recent','актуально','сейчас','сегодня','последние','что нового','расскажи о','новости','текущий']
ANALYSIS_KEYWORDS = ['анализ','анализируй','проанализируй','посмотри','прочитай','что на сайте','что там','fetch','прочти','разбери','изучи сайт']
URL_PATTERN = re.compile(r'https?://[^\s]+')

def extract_urls(text):
    return URL_PATTERN.findall(text)

def detect_mode(prompt: str) -> dict:
    lo = prompt.lower()
    urls = extract_urls(prompt)
    needs_web_search = any(k in lo for k in SEARCH_KEYWORDS) and len(prompt) > 10
    needs_url_fetch  = bool(urls) and any(k in lo for k in ANALYSIS_KEYWORDS + ['что','какой','расскажи','summarize'])
    if urls and not needs_url_fetch:
        needs_url_fetch = True
    agent_mode = needs_web_search or needs_url_fetch
    return {'agent_mode': agent_mode, 'needs_web_search': needs_web_search,
            'needs_url_fetch': needs_url_fetch, 'urls': urls}
