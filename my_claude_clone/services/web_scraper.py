import logging, requests, re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

def fetch_url(url: str, timeout: int = 12) -> dict:
    try:
        parsed = urlparse(url)
        if not parsed.scheme:
            url = 'https://' + url
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; ClaudeClone/1.0)'}
        r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        r.raise_for_status()
        text = re.sub(r'<script.*?</script>', '', r.text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style.*?</style>',  '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = '\n'.join(line.strip() for line in text.splitlines() if line.strip())
        text = text[:5000]
        title_m = re.search(r'<title[^>]*>(.*?)</title>', r.text, re.IGNORECASE | re.DOTALL)
        title = title_m.group(1).strip()[:100] if title_m else urlparse(url).netloc
        return {'success': True, 'title': title, 'text': text, 'url': url}
    except Exception as e:
        logger.warning('fetch_url %s: %s', url, e)
        return {'success': False, 'error': str(e), 'url': url}
