import requests
import logging
import json
import time
import re

logger = logging.getLogger(__name__)

# Встроенные инструменты которые всегда показываются в UI если нет подключенных MCP
BUILTIN_TOOLS = [
    {
        'name': 'web_search',
        'description': '🔍 Поиск в интернете через Google',
        'source': 'builtin',
        'icon': '🔍'
    },
    {
        'name': 'fetch_url',
        'description': '🌐 Чтение любого сайта по ссылке',
        'source': 'builtin',
        'icon': '🌐'
    },
    {
        'name': 'code_execution',
        'description': '💻 Анализ и объяснение кода',
        'source': 'builtin',
        'icon': '💻'
    },
    {
        'name': 'extract_artifacts',
        'description': '📄 Извлечение артефактов (код, HTML, документы)',
        'source': 'builtin',
        'icon': '📄'
    },
    {
        'name': 'extended_thinking',
        'description': '🧠 Расширенное мышление (пошаговое решение)',
        'source': 'builtin',
        'icon': '🧠'
    },
    {
        'name': 'agent_mode',
        'description': '🤖 Автоматический агентный режим для сложных задач',
        'source': 'builtin',
        'icon': '🤖'
    },
    {
        'name': 'image_analysis',
        'description': '🖼️ Анализ изображений (через Claude Vision)',
        'source': 'builtin',
        'icon': '🖼️'
    },
    {
        'name': 'file_management',
        'description': '📁 Управление артефактами и файлами',
        'source': 'builtin',
        'icon': '📁'
    }
]


class MCPClient:
    """Клиент для MCP-серверов с поддержкой обоих протоколов:
    - JSON-RPC 2.0 over HTTP POST (стандарт)
    - Streamable HTTP / SSE (использует Composio и новые MCP серверы)
    """

    def _headers(self, auth_token=None):
        h = {
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream'
        }
        if auth_token:
            h['Authorization'] = f'Bearer {auth_token}'
        return h

    def _parse_sse_or_json(self, resp):
        """Парсит ответ независимо от Content-Type (обычный JSON или SSE-поток)."""
        ct = resp.headers.get('Content-Type', '')
        text = resp.text

        # SSE / event-stream
        if 'event-stream' in ct or text.startswith('data:'):
            last_data = None
            for line in text.splitlines():
                if line.startswith('data:'):
                    last_data = line[5:].strip()
            if last_data and last_data != '[DONE]':
                try:
                    return json.loads(last_data)
                except Exception:
                    pass
            return {}

        # Обычный JSON
        try:
            return resp.json()
        except Exception:
            return {}

    def list_tools(self, server, timeout=15):
        """
        Запрашивает список инструментов у MCP-сервера.
        Поддерживает оба протокола автоматически.
        """
        url = server.url.rstrip('/')
        auth = server.auth_token
        payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}

        # Метод 1: прямой POST (JSON-RPC)
        try:
            resp = requests.post(url, json=payload, headers=self._headers(auth), timeout=timeout)
            if resp.status_code == 200:
                data = self._parse_sse_or_json(resp)
                tools = data.get('result', {}).get('tools', [])
                if tools:
                    return tools
        except Exception as e:
            logger.debug(f'MCP POST failed for {server.name}: {e}')

        # Метод 2: GET /tools (некоторые серверы отдают через GET)
        try:
            tools_url = url + '/tools' if not url.endswith('/tools') else url
            resp = requests.get(tools_url, headers=self._headers(auth), timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                # разные форматы ответа
                if isinstance(data, list):
                    return data
                tools = data.get('tools') or data.get('result', {}).get('tools', [])
                if tools:
                    return tools
        except Exception as e:
            logger.debug(f'MCP GET /tools failed for {server.name}: {e}')

        # Метод 3: POST на /mcp (некоторые серверы принимают запросы на /mcp)
        try:
            mcp_url = url if url.endswith('/mcp') else url + '/mcp'
            resp = requests.post(mcp_url, json=payload, headers=self._headers(auth), timeout=timeout)
            if resp.status_code in (200, 202):
                data = self._parse_sse_or_json(resp)
                tools = data.get('result', {}).get('tools', [])
                if tools:
                    return tools
        except Exception as e:
            logger.debug(f'MCP POST /mcp failed for {server.name}: {e}')

        # Метод 4: извлекаем список инструментов через info/manifest (Composio-стиль)
        try:
            for endpoint in ['/info', '/manifest', '/capabilities', '']:
                try:
                    resp = requests.get(url + endpoint, headers=self._headers(auth), timeout=5)
                    if resp.status_code == 200:
                        data = resp.json()
                        # Composio возвращает tools на верхнем уровне
                        tools = (data.get('tools') or data.get('actions') or
                                 data.get('result', {}).get('tools', []))
                        if tools:
                            return tools if isinstance(tools[0], dict) else \
                                   [{'name': t, 'description': ''} for t in tools]
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f'MCP info endpoints failed for {server.name}: {e}')

        logger.warning(f'Could not get tools from MCP server {server.name} ({server.url})')
        return []

    def call_tool(self, server, tool_name, arguments, timeout=60):
        """Вызывает инструмент на MCP-сервере."""
        url = server.url.rstrip('/')
        auth = server.auth_token
        payload = {
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments or {}}
        }
        try:
            resp = requests.post(url, json=payload, headers=self._headers(auth), timeout=timeout)
            resp.raise_for_status()
            data = self._parse_sse_or_json(resp)
            if 'error' in data:
                return f"Ошибка MCP: {data['error'].get('message', 'unknown')}"
            result = data.get('result', {})
            content = result.get('content', [])
            texts = [c.get('text', '') for c in content if isinstance(c, dict) and c.get('type') == 'text']
            return '\n'.join(texts) if texts else str(result)
        except Exception as e:
            logger.warning(f"MCP call_tool '{tool_name}' failed on {server.name}: {e}")
            return f"Не удалось вызвать '{tool_name}' на {server.name}: {e}"

    def get_openai_tools_schema(self, servers):
        """Собирает схему инструментов всех серверов для OpenAI function-calling."""
        tools_schema = []
        tool_to_server = {}
        for server in servers:
            for t in self.list_tools(server):
                name = t.get('name') if isinstance(t, dict) else str(t)
                if not name:
                    continue
                safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', f'srv{server.id}__{name}')[:64]
                tools_schema.append({
                    "type": "function",
                    "function": {
                        "name": safe_name,
                        "description": (t.get('description') if isinstance(t, dict) else '') or
                                       f"Инструмент {name} с MCP-сервера {server.name}",
                        "parameters": (t.get('inputSchema') if isinstance(t, dict) else None) or
                                      {"type": "object", "properties": {}}
                    }
                })
                tool_to_server[safe_name] = (server, name)
        return tools_schema, tool_to_server

    def get_builtin_tools(self):
        """Возвращает список встроенных инструментов."""
        return BUILTIN_TOOLS

    def call(self, server_url, auth_token, prompt, timeout=60):
        """Старый метод — используется job_executor.py."""
        headers = self._headers(auth_token)
        payload = {"jsonrpc": "2.0", "method": "tools/call",
                   "params": {"prompt": prompt, "name": "claude_code"}, "id": 1}
        try:
            resp = requests.post(server_url, json=payload, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                data = self._parse_sse_or_json(resp)
                if 'result' in data:
                    return str(data['result'])
                return resp.text
        except Exception as e:
            logger.warning(f'MCP call failed: {e}')
        time.sleep(2)
        return f"Mock MCP result for: {prompt}"


mcp_client = MCPClient()
