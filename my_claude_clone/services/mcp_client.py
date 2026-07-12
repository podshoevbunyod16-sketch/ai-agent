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

# Признаки что это Composio — будем использовать REST API v3.1
COMPOSIO_HOSTS = {'composio.dev', 'mcp.composio.dev', 'backend.composio.dev'}


class MCPClient:

    def _is_composio(self, url):
        host = urlparse(url).netloc.lower()
        return any(h in host for h in COMPOSIO_HOSTS)

    def _hdrs(self, auth=None, accept_sse=False):
        h = {'Content-Type': 'application/json',
             'Accept': 'text/event-stream' if accept_sse
                       else 'application/json, text/event-stream'}
        if auth:
            # Composio v3.1 требует x-api-key, остальные — Bearer
            if self._is_composio_key(auth):
                h['x-api-key'] = auth
            else:
                h['Authorization'] = f'Bearer {auth}'
        return h

    def _is_composio_key(self, key):
        return key and key.startswith('ak_')

    def _extract_tools(self, data):
        """JSON любого формата → [{name, description}]"""
        if not data:
            return []
        # Composio v3.1: {"items": [{"slug":..., "name":..., ...}]}
        if isinstance(data.get('items'), list):
            return [{'name': t.get('slug') or t.get('name', ''),
                     'description': t.get('description', '')}
                    for t in data['items'] if isinstance(t, dict)]
        # JSON-RPC 2.0
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

    # ------------------------------------------------------------------ #
    #  Composio REST v3.1
    # ------------------------------------------------------------------ #
    def _composio_list_tools(self, api_key, timeout=15, limit=50):
        """
        Composio v3.1 REST API:
        GET https://backend.composio.dev/api/v3.1/tools
        Header: x-api-key: ak_...
        Возвращает список {name, description} или []
        """
        url = 'https://backend.composio.dev/api/v3.1/tools'
        try:
            r = requests.get(
                url,
                headers={'x-api-key': api_key, 'Accept': 'application/json'},
                params={'limit': limit},
                timeout=timeout
            )
            if r.status_code == 200:
                tools = self._extract_tools(r.json())
                logger.info('Composio v3.1: %d инструментов', len(tools))
                return tools
            logger.warning('Composio v3.1 HTTP %d: %s', r.status_code, r.text[:200])
        except Exception as e:
            logger.warning('Composio v3.1 error: %s', e)
        return []

    def _composio_call_tool(self, api_key, tool_slug, arguments, timeout=30):
        """
        Composio v3.1 вызов инструмента:
        POST https://backend.composio.dev/api/v3.1/tools/{slug}/execute
        """
        url = f'https://backend.composio.dev/api/v3.1/tools/{tool_slug}/execute'
        try:
            r = requests.post(
                url,
                json={'input': arguments or {}},
                headers={'x-api-key': api_key, 'Content-Type': 'application/json'},
                timeout=timeout
            )
            r.raise_for_status()
            data = r.json()
            # Ответ может быть {"data": ...} или {"result": ...}
            result = data.get('data') or data.get('result') or data
            return json.dumps(result, ensure_ascii=False)[:4000]
        except Exception as e:
            logger.warning('Composio execute %s: %s', tool_slug, e)
            return f'Ошибка вызова {tool_slug}: {e}'

    # ------------------------------------------------------------------ #
    #  SSE dual-endpoint (для не-Composio серверов)
    # ------------------------------------------------------------------ #
    def _resolve_redirect(self, url, auth, timeout=6):
        current = url
        for _ in range(5):
            try:
                r = requests.head(current, headers={'Authorization': f'Bearer {auth}' if auth else ''},
                                  allow_redirects=False, timeout=timeout)
                if r.status_code in (301, 302, 307, 308):
                    loc = r.headers.get('Location', '')
                    if not loc:
                        break
                    if loc.startswith('/'):
                        p = urlparse(current)
                        loc = f"{p.scheme}://{p.netloc}{loc}"
                    current = loc
                else:
                    break
            except Exception:
                break
        return current

    def _sse_get_messages_url(self, sse_url, auth, timeout=10):
        try:
            resp = requests.get(
                sse_url,
                headers={'Accept': 'text/event-stream',
                         **({'Authorization': f'Bearer {auth}'} if auth else {})},
                allow_redirects=False,
                timeout=timeout,
                stream=True
            )
            if resp.status_code in (301, 302, 307, 308):
                loc = resp.headers.get('Location', '')
                resp.close()
                if loc:
                    if loc.startswith('/'):
                        p = urlparse(sse_url)
                        loc = f"{p.scheme}://{p.netloc}{loc}"
                    return self._sse_get_messages_url(loc, auth, timeout)
                return None
            if resp.status_code != 200:
                resp.close()
                return None
            base = f"{urlparse(resp.url).scheme}://{urlparse(resp.url).netloc}"
            for i, line in enumerate(resp.iter_lines(decode_unicode=True)):
                if i > 30:
                    break
                if line and line.startswith('data:'):
                    val = line[5:].strip()
                    if val.startswith('/'):
                        resp.close()
                        return base + val
                    if val.startswith('http'):
                        resp.close()
                        return val
            resp.close()
        except Exception as e:
            logger.debug('_sse_get_messages_url: %s', e)
        return None

    # ------------------------------------------------------------------ #
    #  Главный метод
    # ------------------------------------------------------------------ #
    def list_tools(self, server, timeout=15):
        url  = server.url.rstrip('/')
        auth = server.auth_token

        # === Composio: REST v3.1 ===
        if self._is_composio(url) or self._is_composio_key(auth):
            # Ключ может быть в auth_token или в URL
            api_key = auth
            if not api_key:
                # Пытаемся извлечь из URL
                m = re.search(r'/(ak_[^/]+)/', url)
                if m:
                    api_key = m.group(1)
            if api_key:
                return self._composio_list_tools(api_key, timeout)
            logger.warning('Composio: нет API ключа')
            return []

        # === Стандартный MCP: Streamable HTTP ===
        rpc = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {}}
        for ep in ([url] if url.endswith('/mcp') else [url + '/mcp', url]):
            try:
                r = requests.post(ep, json=rpc,
                                  headers=self._hdrs(auth),
                                  allow_redirects=True, timeout=timeout)
                if r.status_code == 200:
                    ct = r.headers.get('Content-Type', '')
                    data = self._parse_sse_text(r.text) if 'event-stream' in ct else r.json()
                    tools = self._extract_tools(data)
                    if tools:
                        return tools
            except Exception as e:
                logger.debug('Streamable HTTP failed (%s): %s', server.name, e)

        # === SSE dual-endpoint ===
        sse_url = url if url.endswith('/sse') else url + '/sse'
        try:
            messages_url = self._sse_get_messages_url(sse_url, auth, timeout)
            if messages_url:
                init = {'jsonrpc':'2.0','id':0,'method':'initialize',
                        'params':{'protocolVersion':'2024-11-05',
                                  'capabilities':{},'clientInfo':{'name':'claude-clone','version':'1.0'}}}
                requests.post(messages_url, json=init, headers=self._hdrs(auth),
                              allow_redirects=True, timeout=8)
                r3 = requests.post(messages_url, json=rpc, headers=self._hdrs(auth),
                                   allow_redirects=True, timeout=timeout)
                if r3.status_code in (200, 202):
                    ct = r3.headers.get('Content-Type', '')
                    data = self._parse_sse_text(r3.text) if 'event-stream' in ct else r3.json()
                    tools = self._extract_tools(data)
                    if tools:
                        return tools
        except Exception as e:
            logger.debug('SSE failed (%s): %s', server.name, e)

        # === REST GET /tools ===
        try:
            r = requests.get(url + '/tools', headers=self._hdrs(auth),
                             allow_redirects=True, timeout=8)
            if r.status_code == 200:
                tools = self._extract_tools(r.json())
                if tools:
                    return tools
        except Exception:
            pass

        logger.warning('list_tools: нет инструментов %s', server.name)
        return []

    def call_tool(self, server, tool_name, arguments, timeout=60):
        url  = server.url.rstrip('/')
        auth = server.auth_token

        # Composio REST
        if self._is_composio(url) or self._is_composio_key(auth):
            api_key = auth
            if not api_key:
                m = re.search(r'/(ak_[^/]+)/', url)
                if m:
                    api_key = m.group(1)
            if api_key:
                return self._composio_call_tool(api_key, tool_name, arguments, timeout)

        # Стандартный MCP
        rpc = {'jsonrpc':'2.0','id':2,'method':'tools/call',
               'params':{'name':tool_name,'arguments':arguments or {}}}
        for target in ([url] if url.endswith('/mcp') else [url+'/mcp', url]):
            try:
                r = requests.post(target, json=rpc, headers=self._hdrs(auth),
                                  allow_redirects=True, timeout=timeout)
                r.raise_for_status()
                ct = r.headers.get('Content-Type','')
                data = self._parse_sse_text(r.text) if 'event-stream' in ct else r.json()
                if 'error' in data:
                    return f"Ошибка: {data['error'].get('message',data['error'])}"
                result = data.get('result',{})
                texts = [c['text'] for c in result.get('content',[])
                         if isinstance(c,dict) and c.get('type')=='text']
                return '\n'.join(texts) if texts else str(result)
            except Exception as e:
                logger.debug('call_tool %s: %s', target, e)
        return f'Не удалось вызвать {tool_name}'

    def get_openai_tools_schema(self, servers):
        schema, tool_map = [], {}
        for srv in servers:
            for t in self.list_tools(srv):
                name = t.get('name') if isinstance(t, dict) else str(t)
                if not name:
                    continue
                safe = re.sub(r'[^a-zA-Z0-9_]', '_', f'srv{srv.id}__{name}')[:64]
                schema.append({'type':'function','function':{
                    'name': safe,
                    'description': (t.get('description') if isinstance(t,dict) else '') or
                                   f'MCP {name} ({srv.name})',
                    'parameters': (t.get('inputSchema') if isinstance(t,dict) else None) or
                                  {'type':'object','properties':{}}
                }})
                tool_map[safe] = (srv, name)
        return schema, tool_map

    def get_builtin_tools(self):
        return BUILTIN_TOOLS

    def call(self, server_url, auth_token, prompt, timeout=60):
        payload = {'jsonrpc':'2.0','method':'tools/call',
                   'params':{'prompt':prompt,'name':'claude_code'},'id':1}
        try:
            r = requests.post(server_url, json=payload,
                              headers=self._hdrs(auth_token),
                              allow_redirects=True, timeout=timeout)
            if r.status_code == 200:
                ct = r.headers.get('Content-Type','')
                data = self._parse_sse_text(r.text) if 'event-stream' in ct else r.json()
                return str(data.get('result', r.text))
        except Exception as e:
            logger.warning('MCP.call: %s', e)
        return f'Mock: {prompt}'


mcp_client = MCPClient()
