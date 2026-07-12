import json
import re
import time
import logging
import requests
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

BUILTIN_TOOLS = [
    {'name': 'web_search',        'description': '🔍 Поиск в интернете через Google',       'source': 'builtin'},
    {'name': 'fetch_url',         'description': '🌐 Чтение любого сайта по ссылке',          'source': 'builtin'},
    {'name': 'code_execution',    'description': '💻 Анализ и объяснение кода',        'source': 'builtin'},
    {'name': 'extract_artifacts', 'description': '📄 Извлечение артефактов',              'source': 'builtin'},
    {'name': 'extended_thinking', 'description': '🧠 Расширенное мышление',         'source': 'builtin'},
    {'name': 'agent_mode',        'description': '🤖 Автоматический агентный режим',    'source': 'builtin'},
    {'name': 'image_analysis',    'description': '🖼️ Анализ изображений (Vision)',  'source': 'builtin'},
    {'name': 'file_management',   'description': '📁 Управление файлами',               'source': 'builtin'},
]


class MCPClient:

    def _hdrs(self, auth=None, accept_sse=False):
        h = {'Content-Type': 'application/json',
             'Accept': 'text/event-stream' if accept_sse
                       else 'application/json, text/event-stream'}
        if auth:
            h['Authorization'] = f'Bearer {auth}'
        return h

    def _resolve_final_url(self, url, auth, timeout=8):
        """
        Разрешает цепочку 301/302 через HEAD-запросы
        (без открытия SSE потока).
        """
        current = url
        for _ in range(5):
            try:
                r = requests.head(current, headers=self._hdrs(auth),
                                  allow_redirects=False, timeout=timeout)
                if r.status_code in (301, 302, 307, 308):
                    location = r.headers.get('Location', '')
                    if not location:
                        break
                    if location.startswith('/'):
                        p = urlparse(current)
                        location = f"{p.scheme}://{p.netloc}{location}"
                    logger.info('MCP redirect: %s -> %s', current, location)
                    current = location
                else:
                    break
            except Exception as e:
                logger.debug('HEAD redirect failed: %s', e)
                break
        return current

    def _extract_tools(self, data):
        if not data:
            return []
        t = data.get('result', {}).get('tools')
        if t:
            return t
        if isinstance(data.get('tools'), list):
            return data['tools']
        if isinstance(data.get('actions'), list):
            return [{'name': a.get('name', ''), 'description': a.get('description', '')}
                    for a in data['actions'] if isinstance(a, dict)]
        if isinstance(data, list):
            return [{'name': x} if isinstance(x, str) else x for x in data]
        return []

    def _parse_sse_text(self, text):
        last = None
        for line in text.splitlines():
            s = line.strip()
            if s.startswith('data:'):
                val = s[5:].strip()
                if val and val != '[DONE]':
                    last = val
        if last:
            try:
                return json.loads(last)
            except Exception:
                pass
        return {}

    def _sse_get_messages_url(self, sse_url, auth, timeout=10):
        """
        GET /sse без follow_redirects + stream=True.
        Читаем строки пока не найдём data: /messages?...
        """
        try:
            resp = requests.get(
                sse_url,
                headers=self._hdrs(auth, accept_sse=True),
                allow_redirects=False,   # НЕ следуем редиректам в потоке!
                timeout=timeout,
                stream=True
            )

            # Если пришёл редирект — повторим на новый URL
            if resp.status_code in (301, 302, 307, 308):
                new_url = resp.headers.get('Location', '')
                if new_url:
                    if new_url.startswith('/'):
                        p = urlparse(sse_url)
                        new_url = f"{p.scheme}://{p.netloc}{new_url}"
                    resp.close()
                    return self._sse_get_messages_url(new_url, auth, timeout)
                resp.close()
                return None

            if resp.status_code != 200:
                resp.close()
                return None

            base = f"{urlparse(resp.url).scheme}://{urlparse(resp.url).netloc}"
            messages_path = None
            lines_read = 0

            for raw_line in resp.iter_lines(decode_unicode=True):
                lines_read += 1
                if lines_read > 50:
                    break
                if not raw_line:
                    continue
                logger.debug('SSE: %r', raw_line)
                if raw_line.startswith('data:'):
                    val = raw_line[5:].strip()
                    if val.startswith('/'):
                        messages_path = val
                        break
                    if val.startswith('http'):
                        resp.close()
                        return val

            resp.close()
            if messages_path:
                return base + messages_path

        except Exception as e:
            logger.debug('_sse_get_messages_url error: %s', e)
        return None

    # -------------------------------------------------------------- #
    def list_tools(self, server, timeout=15):
        raw_url = server.url.rstrip('/')
        auth    = server.auth_token

        # Разрешаем 301/302 через HEAD (без потока)
        url = self._resolve_final_url(raw_url, auth)
        rpc = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {}}

        # === A: Streamable HTTP (POST) ===
        for ep in ([url] if url.endswith('/mcp') else [url + '/mcp', url]):
            try:
                r = requests.post(ep, json=rpc, headers=self._hdrs(auth),
                                  allow_redirects=True, timeout=timeout)
                if r.status_code == 200:
                    ct = r.headers.get('Content-Type', '')
                    data = self._parse_sse_text(r.text) if 'event-stream' in ct \
                           else r.json()
                    tools = self._extract_tools(data)
                    if tools:
                        logger.info('MCP %s: Streamable HTTP OK (%d tools)',
                                    server.name, len(tools))
                        return tools
            except Exception as e:
                logger.debug('A failed (%s): %s', server.name, e)

        # === B: SSE dual-endpoint ===
        sse_candidates = [url] if url.endswith('/sse') else [url + '/sse', url]
        for sse_url in sse_candidates:
            try:
                messages_url = self._sse_get_messages_url(sse_url, auth, timeout)
                if not messages_url:
                    continue
                logger.info('MCP %s: SSE messages_url=%s', server.name, messages_url)

                # initialize
                init_rpc = {'jsonrpc': '2.0', 'id': 0, 'method': 'initialize',
                            'params': {'protocolVersion': '2024-11-05',
                                       'capabilities': {},
                                       'clientInfo': {'name': 'claude-clone',
                                                      'version': '1.0'}}}
                requests.post(messages_url, json=init_rpc,
                              headers=self._hdrs(auth),
                              allow_redirects=True, timeout=8)

                # tools/list
                r3 = requests.post(messages_url, json=rpc,
                                   headers=self._hdrs(auth),
                                   allow_redirects=True, timeout=timeout)
                if r3.status_code in (200, 202):
                    ct = r3.headers.get('Content-Type', '')
                    data = self._parse_sse_text(r3.text) if 'event-stream' in ct \
                           else r3.json()
                    tools = self._extract_tools(data)
                    if tools:
                        logger.info('MCP %s: SSE OK (%d tools)',
                                    server.name, len(tools))
                        return tools
            except Exception as e:
                logger.debug('B failed (%s %s): %s', server.name, sse_url, e)

        # === C: REST GET /tools ===
        try:
            r = requests.get(url + '/tools', headers=self._hdrs(auth),
                             allow_redirects=True, timeout=8)
            if r.status_code == 200:
                tools = self._extract_tools(r.json())
                if tools:
                    return tools
        except Exception:
            pass

        # === D: /info /manifest /capabilities ===
        for ep in ['/info', '/manifest', '/capabilities']:
            try:
                r = requests.get(url + ep, headers=self._hdrs(auth),
                                 allow_redirects=True, timeout=5)
                if r.status_code == 200:
                    tools = self._extract_tools(r.json())
                    if tools:
                        return tools
            except Exception:
                pass

        logger.warning('list_tools: нет инструментов %s (%s)',
                       server.name, server.url)
        return []

    def call_tool(self, server, tool_name, arguments, timeout=60):
        url  = self._resolve_final_url(server.url.rstrip('/'), server.auth_token)
        auth = server.auth_token
        rpc  = {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
                 'params': {'name': tool_name, 'arguments': arguments or {}}}
        for target in ([url] if url.endswith('/mcp') else [url + '/mcp', url]):
            try:
                r = requests.post(target, json=rpc, headers=self._hdrs(auth),
                                  allow_redirects=True, timeout=timeout)
                r.raise_for_status()
                ct = r.headers.get('Content-Type', '')
                data = self._parse_sse_text(r.text) if 'event-stream' in ct \
                       else r.json()
                if 'error' in data:
                    return f"Ошибка: {data['error'].get('message', data['error'])}"
                result  = data.get('result', {})
                content = result.get('content', [])
                texts   = [c['text'] for c in content
                           if isinstance(c, dict) and c.get('type') == 'text']
                return '\n'.join(texts) if texts else str(result)
            except Exception as e:
                logger.debug('call_tool %s: %s', target, e)
        return f"Не удалось вызвать '{tool_name}'"

    def get_openai_tools_schema(self, servers):
        schema, tool_map = [], {}
        for srv in servers:
            for t in self.list_tools(srv):
                name = t.get('name') if isinstance(t, dict) else str(t)
                if not name:
                    continue
                safe = re.sub(r'[^a-zA-Z0-9_]', '_',
                              f'srv{srv.id}__{name}')[:64]
                schema.append({'type': 'function', 'function': {
                    'name': safe,
                    'description': (t.get('description')
                                    if isinstance(t, dict) else '') or
                                   f'MCP {name} ({srv.name})',
                    'parameters': (t.get('inputSchema')
                                   if isinstance(t, dict) else None) or
                                  {'type': 'object', 'properties': {}}
                }})
                tool_map[safe] = (srv, name)
        return schema, tool_map

    def get_builtin_tools(self):
        return BUILTIN_TOOLS

    def call(self, server_url, auth_token, prompt, timeout=60):
        """Legacy метод для job_executor."""
        payload = {'jsonrpc': '2.0', 'method': 'tools/call',
                   'params': {'prompt': prompt, 'name': 'claude_code'}, 'id': 1}
        try:
            r = requests.post(server_url, json=payload,
                              headers=self._hdrs(auth_token),
                              allow_redirects=True, timeout=timeout)
            if r.status_code == 200:
                ct = r.headers.get('Content-Type', '')
                data = self._parse_sse_text(r.text) \
                       if 'event-stream' in ct else r.json()
                return str(data.get('result', r.text))
        except Exception as e:
            logger.warning('MCP.call: %s', e)
        return f'Mock: {prompt}'


mcp_client = MCPClient()
