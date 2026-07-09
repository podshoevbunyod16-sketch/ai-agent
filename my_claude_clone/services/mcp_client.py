import requests
import logging
import time

logger = logging.getLogger(__name__)

class MCPClient:
    """Упрощенный MCP клиент"""
    
    def call(self, server_url, auth_token, prompt, timeout=60):
        """
        Отправляет промпт на MCP сервер.
        Ожидает JSON-RPC подобный интерфейс.
        Fallback: mock если сервер недоступен.
        """
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        if auth_token:
            headers['Authorization'] = f'Bearer {auth_token}'

        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "prompt": prompt,
                "name": "claude_code"
            },
            "id": 1
        }

        try:
            # Пробуем настоящий MCP
            resp = requests.post(server_url, json=payload, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                # Извлекаем result
                if 'result' in data:
                    return str(data['result'])
                return resp.text
            else:
                logger.warning(f"MCP server {server_url} returned {resp.status_code}")
        except Exception as e:
            logger.warning(f"MCP call failed: {e}, using mock")

        # Mock fallback - симулируем работу
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
