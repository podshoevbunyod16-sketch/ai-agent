import requests
import logging
import json
import time
import re

logger = logging.getLogger(__name__)

BUILTIN_TOOLS = [
    {'name': 'web_search',        'description': '🔍 Поиск в интернете через Google',          'source': 'builtin'},
    {'name': 'fetch_url',         'description': '🌐 Чтение любого сайта по ссылке',           'source': 'builtin'},
    {'name': 'code_execution',    'description': '💻 Анализ и объяснение кода',         'source': 'builtin'},
    {'name': 'extract_artifacts', 'description': '📄 Извлечение артефактов (код, HTML)', 'source': 'builtin'},
    {'name': 'extended_thinking', 'description': '🧠 Расширенное мышление',          'source': 'builtin'},
    {'name': 'agent_mode',        'description': '🤖 Автоматический агентный режим',     'source': 'builtin'},
    {'name': 'image_analysis',    'description': '🖼️ Анализ изображений (Claude Vision)',   'source': 'builtin'},
    {'name': 'file_management',   'description': '📁 Управление файлами и артефактами',  'source': 'builtin'},
]


class MCPClient:
    """
    Клиент для MCP-серверов. Поддерживает 3 протокола:
      1. JSON-RPC 2.0 over HTTP POST (стандарт)
      2. SSE (text/event-stream) — Composio, mcp.run и др.
      3. REST GET /tools — упрощённые серверы
    """

    # ------------------------------------------------------------------ #
    #  Внутренние методы
    # ------------------------------------------------------------------ #
    def _headers(self, auth_token=None):
        h = {
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream',
        }
        if auth_token:
            h['Authorization'] = f'Bearer {auth_token}'
        return h

    def _parse_response(self, resp):
        """Парсит JSON или SSE-поток и возвращает словарь."""
        ct = resp.headers.get('Content-Type', '')
        raw = resp.text

        if 'event-stream' in ct or (raw.strip().startswith('event:') or raw.strip().startswith('data:')):
            # Ищем последний блок data: с результатом (tools/list)
            last = None
            for line in raw.splitlines():
                s = line.strip()
                if s.startswith('data:'):
                    payload = s[5:].strip()
                    if payload and payload != '[DONE]':
                        last = payload
            if last:
                try:
                    return json.loads(last)
                except Exception:
                    pass
            return {}

        try:
            return resp.json()
        except Exception:
            return {}

    def _tools_from_data(self, data):
        """Извлекает список tools из любого формата ответа."""
        if not data:
            return []
        # JSON-RPC result
        tools = data.get('result', {}).get('tools', [])
        if tools:
            return tools
        # Плоский список
        if isinstance(data.get('tools'), list):
            return data['tools']
        # Composio-стиль: {"actions": [...]}
        if isinstance(data.get('actions'), list):
            return [{'name': a.get('name', a) if isinstance(a, dict) else a,
                     'description': a.get('description', '') if isinstance(a, dict) else ''}
                    for a in data['actions']]
        # Простой список строк
        if isinstance(data, list):
            return [{'name': x} if isinstance(x, str) else x for x in data]
        return []

    # ------------------------------------------------------------------ #
    #  Публичные методы
    # ------------------------------------------------------------------ #
    def list_tools(self, server, timeout=12):
        """
        Получает список инструментов с MCP-сервера.
        Попытки: JSON-RPC POST → SSE POST → GET /tools → GET /info
        """
        url   = server.url.rstrip('/')
        auth  = server.auth_token
        rpc   = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        hdrs  = self._headers(auth)

        # --- 1. Стандартный JSON-RPC POST ---
        try:
            r = requests.post(url, json=rpc, headers=hdrs, timeout=timeout)
            if r.status_code == 200:
                tools = self._tools_from_data(self._parse_response(r))
                if tools:
                    return tools
        except Exception as e:
            logger.debug('MCP attempt 1 failed (%s): %s', server.name, e)

        # --- 2. Composio-формат: URL заканчивается на /sse ---
        sse_url = url if url.endswith('/sse') else url + '/sse'
        try:
            # Для SSE инициализация и запрос tools/list
            r = requests.post(sse_url, json=rpc, headers=hdrs,
                              timeout=timeout, stream=True)
            if r.status_code == 200:
                # Читаем SSE-поток
                buffer = ''
                for chunk in r.iter_content(chunk_size=1024, decode_unicode=True):
                    buffer += chunk
                    if len(buffer) > 50000:
                        break  # защита от бесконечных потоков
                tools = self._tools_from_data(self._parse_response_text(buffer))
                if tools:
                    return tools
        except Exception as e:
            logger.debug('MCP attempt 2 SSE failed (%s): %s', server.name, e)

        # --- 3. GET /tools ---
        for ep in ['/tools', '']:
            try:
                r = requests.get(url + ep, headers=hdrs, timeout=8)
                if r.status_code == 200:
                    tools = self._tools_from_data(self._parse_response(r))
                    if tools:
                        return tools
            except Exception as e:
                logger.debug('MCP GET %s failed (%s): %s', ep, server.name, e)

        # --- 4. GET /info, /manifest, /capabilities ---
        for ep in ['/info', '/manifest', '/capabilities']:
            try:
                r = requests.get(url + ep, headers=hdrs, timeout=6)
                if r.status_code == 200:
                    tools = self._tools_from_data(r.json())
                    if tools:
                        return tools
            except Exception:
                pass

        logger.warning('Could not get tools from MCP server %s (%s)', server.name, server.url)
        return []

    def _parse_response_text(self, text):
        """Парсит SSE-текст без requests.Response."""
        last = None
        for line in text.splitlines():
            s = line.strip()
            if s.startswith('data:'):
                payload = s[5:].strip()
                if payload and payload != '[DONE]':
                    last = payload
        if last:
            try:
                return json.loads(last)
            except Exception:
                pass
        return {}

    def call_tool(self, server, tool_name, arguments, timeout=60):
        """Вызывает инструмент на MCP-сервере."""
        url = server.url.rstrip('/')
        payload = {
            'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
            'params': {'name': tool_name, 'arguments': arguments or {}}
        }
        try:
            r = requests.post(url, json=payload,
                              headers=self._headers(server.auth_token), timeout=timeout)
            r.raise_for_status()
            data = self._parse_response(r)
            if 'error' in data:
                return f"Ошибка MCP: {data['error'].get('message','unknown')}"
            result  = data.get('result', {})
            content = result.get('content', [])
            texts   = [c.get('text', '') for c in content
                       if isinstance(c, dict) and c.get('type') == 'text']
            return '\n'.join(texts) if texts else str(result)
        except Exception as e:
            logger.warning("MCP call_tool '%s' failed on %s: %s", tool_name, server.name, e)
            return f"Не удалось вызвать '{tool_name}': {e}"

    def get_openai_tools_schema(self, servers):
        """Схема всех инструментов для OpenAI function-calling."""
        tools_schema   = []
        tool_to_server = {}
        for server in servers:
            for t in self.list_tools(server):
                name = t.get('name') if isinstance(t, dict) else str(t)
                if not name:
                    continue
                safe = re.sub(r'[^a-zA-Z0-9_]', '_', f'srv{server.id}__{name}')[:64]
                tools_schema.append({
                    'type': 'function',
                    'function': {
                        'name': safe,
                        'description': (t.get('description') if isinstance(t, dict) else '') or
                                       f'MCP инструмент {name} ({server.name})',
                        'parameters': (t.get('inputSchema') if isinstance(t, dict) else None) or
                                      {'type': 'object', 'properties': {}}
                    }
                })
                tool_to_server[safe] = (server, name)
        return tools_schema, tool_to_server

    def get_builtin_tools(self):
        return BUILTIN_TOOLS

    # Старый метод для job_executor
    def call(self, server_url, auth_token, prompt, timeout=60):
        headers = self._headers(auth_token)
        payload = {'jsonrpc': '2.0', 'method': 'tools/call',
                   'params': {'prompt': prompt, 'name': 'claude_code'}, 'id': 1}
        try:
            r = requests.post(server_url, json=payload, headers=headers, timeout=timeout)
            if r.status_code == 200:
                data = self._parse_response(r)
                return str(data.get('result', r.text))
        except Exception as e:
            logger.warning('MCP call failed: %s', e)
        time.sleep(1)
        return f'Mock MCP result for: {prompt}'


mcp_client = MCPClient()
