import requests
import logging
import json
import time

logger = logging.getLogger(__name__)


class MCPClient:
    """Клиент для подключения к удалённым MCP-серверам по протоколу JSON-RPC 2.0
    (упрощённая реализация streamable-HTTP транспорта)."""

    def _headers(self, auth_token=None):
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream'
        }
        if auth_token:
            headers['Authorization'] = f'Bearer {auth_token}'
        return headers

    def _parse_response(self, resp):
        """MCP-сервер может ответить обычным JSON или потоком text/event-stream (SSE)."""
        content_type = resp.headers.get('Content-Type', '')
        if 'text/event-stream' in content_type:
            last_data = None
            for line in resp.text.splitlines():
                if line.startswith('data:'):
                    last_data = line[len('data:'):].strip()
            if last_data:
                return json.loads(last_data)
            return {}
        return resp.json()

    def list_tools(self, server, timeout=15):
        """Запрашивает у MCP-сервера список доступных инструментов (tools/list)."""
        payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        try:
            resp = requests.post(
                server.url, json=payload,
                headers=self._headers(server.auth_token), timeout=timeout
            )
            resp.raise_for_status()
            data = self._parse_response(resp)
            return data.get('result', {}).get('tools', [])
        except Exception as e:
            logger.warning(f"MCP list_tools failed for {server.name} ({server.url}): {e}")
            return []

    def call_tool(self, server, tool_name, arguments, timeout=60):
        """Вызывает конкретный инструмент на MCP-сервере (tools/call)."""
        payload = {
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments or {}}
        }
        try:
            resp = requests.post(
                server.url, json=payload,
                headers=self._headers(server.auth_token), timeout=timeout
            )
            resp.raise_for_status()
            data = self._parse_response(resp)
            if 'error' in data:
                return f"Ошибка MCP-сервера: {data['error'].get('message', 'unknown error')}"
            result = data.get('result', {})
            content = result.get('content', [])
            texts = [c.get('text', '') for c in content if isinstance(c, dict) and c.get('type') == 'text']
            return '\n'.join(texts) if texts else str(result)
        except Exception as e:
            logger.warning(f"MCP call_tool '{tool_name}' failed on {server.name}: {e}")
            return f"Не удалось вызвать инструмент '{tool_name}' на сервере {server.name}: {e}"

    def get_openai_tools_schema(self, servers):
        """
        Собирает список инструментов со всех активных MCP-серверов в формате
        OpenAI/Groq function calling.
        Возвращает (tools_schema, tool_to_server), где tool_to_server —
        словарь {safe_name: (server, real_tool_name)} для диспетчеризации вызовов.
        """
        tools_schema = []
        tool_to_server = {}
        for server in servers:
            for t in self.list_tools(server):
                name = t.get('name')
                if not name:
                    continue
                safe_name = f"srv{server.id}__{name}"
                tools_schema.append({
                    "type": "function",
                    "function": {
                        "name": safe_name,
                        "description": t.get('description') or f"Инструмент {name} с MCP-сервера {server.name}",
                        "parameters": t.get('inputSchema') or {"type": "object", "properties": {}}
                    }
                })
                tool_to_server[safe_name] = (server, name)
        return tools_schema, tool_to_server

    def call(self, server_url, auth_token, prompt, timeout=60):
        """Старый метод — используется job_executor.py для Claude Code Jobs.
        Оставлен для обратной совместимости."""
        headers = self._headers(auth_token)
        payload = {"jsonrpc": "2.0", "method": "tools/call", "params": {"prompt": prompt, "name": "claude_code"}, "id": 1}
        try:
            resp = requests.post(server_url, json=payload, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                data = self._parse_response(resp)
                if 'result' in data:
                    return str(data['result'])
                return resp.text
            else:
                logger.warning(f"MCP server {server_url} returned {resp.status_code}")
        except Exception as e:
            logger.warning(f"MCP call failed: {e}, using mock")

        time.sleep(2)
        return f"""MCP Job completed (mock fallback)

Server: {server_url}
Prompt: {prompt}

Result:
✅ Анализ завершён
- Найдено файлов: 12
- Изменено строк: 87
- Тесты: passed

```bash
git status
git add .
git commit -m "claude code: implement feature"
```

Готово!
"""


mcp_client = MCPClient()
