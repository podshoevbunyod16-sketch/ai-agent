import json
import re
import time
import logging
import requests
import threading

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
    """
    MCP-клиент с поддержкой четырёх протоколов:

    A) Streamable HTTP (современный, 2025+):
       POST /mcp  ->  JSON или SSE-поток

    B) SSE двухэтапный (2024, Composio /sse):
       1) GET /sse              — получаем строку "endpoint" с адресом /messages?...
       2) POST /messages?...    — отправляем tools/list
       3) ответ приходит обратно через SSE-поток

    C) REST GET /tools — упрощённые серверы

    D) POST /tools/list — альтернативное именование
    """

    # ------------------------------------------------------------------ #
    #  helpers
    # ------------------------------------------------------------------ #
    def _hdrs(self, auth=None, accept_sse=False):
        h = {'Content-Type': 'application/json'}
        h['Accept'] = 'text/event-stream' if accept_sse else 'application/json, text/event-stream'
        if auth:
            h['Authorization'] = f'Bearer {auth}'
        return h

    def _extract_tools(self, data):
        """JSON/SSE ответ → [{name, description}, ...]"""
        if not data:
            return []
        # JSON-RPC 2.0
        t = data.get('result', {}).get('tools')
        if t:
            return t
        # Плоский список
        if isinstance(data.get('tools'), list):
            return data['tools']
        # Composio actions
        if isinstance(data.get('actions'), list):
            return [{'name': a.get('name', ''), 'description': a.get('description', '')}
                    for a in data['actions'] if isinstance(a, dict)]
        # Сам массив
        if isinstance(data, list):
            return [{'name': x} if isinstance(x, str) else x for x in data]
        return []

    def _parse_sse_text(self, text):
        """SSE-текст → последний JSON-объект из data:"""
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

    def _get_messages_url(self, base_url, auth, timeout=8):
        """
        Шаг 1 двухэтапного SSE: GET /sse  →  получаем URL для POST.
        Composio отвечает: event: endpoint\ndata: /messages?sessionId=...
        """
        try:
            resp = requests.get(
                base_url,
                headers=self._hdrs(auth, accept_sse=True),
                timeout=timeout,
                stream=True
            )
            if resp.status_code != 200:
                return None

            messages_path = None
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith('data:'):
                    val = line[5:].strip()
                    # путь вида /messages?sessionId=xxx
                    if val.startswith('/'):
                        messages_path = val
                        break
                    # или полный URL
                    if val.startswith('http'):
                        return val
                # некоторые серверы отдают event: endpoint
                if line.startswith('event:') and 'endpoint' in line:
                    continue

            resp.close()

            if messages_path:
                # Строим полный URL
                from urllib.parse import urlparse
                parsed = urlparse(base_url)
                return f"{parsed.scheme}://{parsed.netloc}{messages_path}"
        except Exception as e:
            logger.debug('SSE get_messages_url failed: %s', e)
        return None

    # ------------------------------------------------------------------ #
    #  list_tools  -  публичный метод
    # ------------------------------------------------------------------ #
    def list_tools(self, server, timeout=15):
        url  = server.url.rstrip('/')
        auth = server.auth_token
        rpc  = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {}}

        # ===== A: Streamable HTTP (POST на /mcp или базовый URL) =====
        for endpoint in ([url] if url.endswith('/mcp') else [url + '/mcp', url]):
            try:
                r = requests.post(endpoint, json=rpc,
                                  headers=self._hdrs(auth), timeout=timeout)
                if r.status_code == 200:
                    ct = r.headers.get('Content-Type', '')
                    if 'event-stream' in ct:
                        data = self._parse_sse_text(r.text)
                    else:
                        data = r.json()
                    tools = self._extract_tools(data)
                    if tools:
                        logger.info('MCP %s: Streamable HTTP OK (%d tools)', server.name, len(tools))
                        return tools
            except Exception as e:
                logger.debug('Streamable HTTP attempt failed (%s): %s', server.name, e)

        # ===== B: Двухэтапный SSE (Composio /sse) =====
        sse_url = url if url.endswith('/sse') else url + '/sse'
        try:
            # Шаг 1: GET /sse -> получить messages URL
            messages_url = self._get_messages_url(sse_url, auth, timeout=timeout)
            if messages_url:
                # Шаг 2: POST initialize
                init_rpc = {'jsonrpc': '2.0', 'id': 0, 'method': 'initialize',
                            'params': {'protocolVersion': '2024-11-05',
                                       'capabilities': {},
                                       'clientInfo': {'name': 'claude-clone', 'version': '1.0'}}}
                requests.post(messages_url, json=init_rpc,
                              headers=self._hdrs(auth), timeout=8)

                # Шаг 3: в фоновом потоке читаем SSE ответ + POST tools/list
                result_holder = []
                err_holder    = []

                def listen_sse():
                    try:
                        r2 = requests.get(sse_url, headers=self._hdrs(auth, accept_sse=True),
                                          timeout=timeout, stream=True)
                        buf = ''
                        for chunk in r2.iter_content(chunk_size=512, decode_unicode=True):
                            buf += chunk
                            if len(result_holder) or len(buf) > 30000:
                                break
                    except Exception as e:
                        err_holder.append(str(e))

                t = threading.Thread(target=listen_sse, daemon=True)
                t.start()
                time.sleep(0.3)  # даём потоку время открыться

                r3 = requests.post(messages_url, json=rpc,
                                   headers=self._hdrs(auth), timeout=timeout)
                t.join(timeout=timeout)

                # Парсим ответ tools/list из POST
                if r3.status_code == 200:
                    data = self._parse_sse_text(r3.text) if 'event-stream' in \
                           r3.headers.get('Content-Type', '') else r3.json()
                    tools = self._extract_tools(data)
                    if tools:
                        logger.info('MCP %s: SSE dual-endpoint OK (%d tools)', server.name, len(tools))
                        return tools
        except Exception as e:
            logger.debug('SSE dual-endpoint failed (%s): %s', server.name, e)

        # ===== C: REST GET /tools =====
        try:
            r = requests.get(url + '/tools', headers=self._hdrs(auth), timeout=8)
            if r.status_code == 200:
                tools = self._extract_tools(r.json())
                if tools:
                    logger.info('MCP %s: REST GET /tools OK (%d tools)', server.name, len(tools))
                    return tools
        except Exception:
            pass

        # ===== D: GET /info /manifest /capabilities =====
        for ep in ['/info', '/manifest', '/capabilities']:
            try:
                r = requests.get(url + ep, headers=self._hdrs(auth), timeout=5)
                if r.status_code == 200:
                    tools = self._extract_tools(r.json())
                    if tools:
                        return tools
            except Exception:
                pass

        logger.warning('list_tools: не удалось получить инструменты от %s (%s)', server.name, server.url)
        return []

    # ------------------------------------------------------------------ #
    #  call_tool
    # ------------------------------------------------------------------ #
    def call_tool(self, server, tool_name, arguments, timeout=60):
        url  = server.url.rstrip('/')
        auth = server.auth_token
        rpc  = {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
                 'params': {'name': tool_name, 'arguments': arguments or {}}}

        # Streamable HTTP — POST на /mcp
        target = url if url.endswith('/mcp') else url + '/mcp'
        try:
            r = requests.post(target, json=rpc, headers=self._hdrs(auth), timeout=timeout)
            if r.status_code != 200:
                # fallback: POST на базовый URL
                r = requests.post(url, json=rpc, headers=self._hdrs(auth), timeout=timeout)
            r.raise_for_status()
            ct = r.headers.get('Content-Type', '')
            data = self._parse_sse_text(r.text) if 'event-stream' in ct else r.json()
            if 'error' in data:
                return f"Ошибка MCP: {data['error'].get('message', data['error'])}"
            result  = data.get('result', {})
            content = result.get('content', [])
            texts   = [c['text'] for c in content if isinstance(c, dict) and c.get('type') == 'text']
            return '\n'.join(texts) if texts else str(result)
        except Exception as e:
            logger.warning("call_tool '%s' @ %s: %s", tool_name, server.name, e)
            return f"Не удалось вызвать '{tool_name}': {e}"

    # ------------------------------------------------------------------ #
    #  helpers для агент
    # ------------------------------------------------------------------ #
    def get_openai_tools_schema(self, servers):
        schema, tool_map = [], {}
        for srv in servers:
            for t in self.list_tools(srv):
                name = t.get('name') if isinstance(t, dict) else str(t)
                if not name:
                    continue
                safe = re.sub(r'[^a-zA-Z0-9_]', '_', f'srv{srv.id}__{name}')[:64]
                schema.append({'type': 'function', 'function': {
                    'name': safe,
                    'description': (t.get('description') if isinstance(t, dict) else '') or
                                   f'MCP инструмент {name} ({srv.name})',
                    'parameters': (t.get('inputSchema') if isinstance(t, dict) else None) or
                                  {'type': 'object', 'properties': {}}
                }})
                tool_map[safe] = (srv, name)
        return schema, tool_map

    def get_builtin_tools(self):
        return BUILTIN_TOOLS

    # старый метод для job_executor
    def call(self, server_url, auth_token, prompt, timeout=60):
        headers = self._hdrs(auth_token)
        payload = {'jsonrpc': '2.0', 'method': 'tools/call',
                   'params': {'prompt': prompt, 'name': 'claude_code'}, 'id': 1}
        try:
            r = requests.post(server_url, json=payload, headers=headers, timeout=timeout)
            if r.status_code == 200:
                data = self._parse_sse_text(r.text) if 'event-stream' in \
                       r.headers.get('Content-Type', '') else r.json()
                return str(data.get('result', r.text))
        except Exception as e:
            logger.warning('MCP.call failed: %s', e)
        return f'Mock MCP result for: {prompt}'


mcp_client = MCPClient()
