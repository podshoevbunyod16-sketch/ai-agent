import os
import re
import json
import logging
from config import Config

logger = logging.getLogger(__name__)


def extract_artifacts(text):
    """Извлекает блоки кода ```lang ... ```"""
    pattern = r'```(\w+)?\n(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    artifacts = []
    for lang, code in matches:
        artifacts.append({
            'language': lang.strip() if lang else 'text',
            'content': code.strip(),
            'title': f"{lang or 'code'} snippet"
        })
    return artifacts


class AIClient:
    def __init__(self):
        self.provider = Config.AI_PROVIDER
        self.model = Config.AI_MODEL

    def chat(self, messages, extended_thinking=False):
        """messages: list of dict {role, content}"""
        try:
            if self.provider == 'anthropic' and Config.ANTHROPIC_API_KEY:
                return self._anthropic_chat(messages, extended_thinking)
            elif self.provider == 'openrouter' and Config.OPENROUTER_API_KEY:
                return self._openrouter_chat(messages)
            elif self.provider == 'groq' and Config.GROQ_API_KEY:
                return self._groq_chat(messages)
            else:
                return self._mock_chat(messages)
        except Exception as e:
            logger.exception("AI chat error")
            return f"Ошибка AI провайдера: {str(e)}\n\n[Mock fallback]\n{self._mock_chat(messages)}"

    def chat_stream(self, messages, tools=None, tool_executor=None):
        """
        Потоковая генерация ответа (генератор, отдаёт куски текста по мере готовности).

        Если переданы tools (MCP-инструменты в формате OpenAI function calling) —
        сначала выполняется цикл вызова инструментов (не потоково, максимум 4 итерации),
        а уже финальный текстовый ответ пользователю стримится по кусочкам.

        tool_executor(tool_name, arguments_dict) -> str   — функция вызова MCP-инструмента.
        """
        try:
            if self.provider == 'groq' and Config.GROQ_API_KEY:
                yield from self._groq_chat_stream(messages, tools, tool_executor)
            else:
                answer = self.chat(messages)
                yield answer
        except Exception as e:
            logger.exception("AI stream error")
            yield f"\n\n⚠️ Ошибка AI провайдера: {str(e)}"

    def _anthropic_chat(self, messages, extended_thinking=False):
        from anthropic import Anthropic
        client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        system_msg = ""
        chat_msgs = []
        for m in messages:
            if m['role'] == 'system':
                system_msg = m['content']
            else:
                chat_msgs.append({"role": m['role'], "content": m['content']})
        resp = client.messages.create(
            model=self.model if 'claude' in self.model else "claude-3-5-sonnet-20241022",
            max_tokens=2048,
            system=system_msg or "Ты Claude, полезный AI-ассистент от Anthropic.",
            messages=chat_msgs
        )
        return resp.content[0].text

    def _openrouter_chat(self, messages):
        from openai import OpenAI
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=Config.OPENROUTER_API_KEY,
        )
        completion = client.chat.completions.create(
            model=self.model if '/' in self.model else "anthropic/claude-3.5-sonnet",
            messages=messages,
            temperature=0.7,
        )
        return completion.choices[0].message.content

    def _groq_chat(self, messages):
        from openai import OpenAI
        client = OpenAI(
            api_key=Config.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1"
        )
        completion = client.chat.completions.create(
            model=self.model if 'llama' in self.model or 'mixtral' in self.model else "llama-3.3-70b-versatile",
            messages=messages
        )
        return completion.choices[0].message.content

    def _groq_chat_stream(self, messages, tools=None, tool_executor=None):
        from openai import OpenAI
        client = OpenAI(
            api_key=Config.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1"
        )
        model_name = self.model if 'llama' in self.model or 'mixtral' in self.model else "llama-3.3-70b-versatile"
        work_messages = list(messages)

        if tools:
            tool_check = client.chat.completions.create(
                model=model_name,
                messages=work_messages,
                tools=tools,
                tool_choice="auto",
                max_tokens=1024,
            )
            choice = tool_check.choices[0]
            tool_calls = getattr(choice.message, 'tool_calls', None)

            loop_count = 0
            while tool_calls and loop_count < 4:
                loop_count += 1
                work_messages.append({
                    "role": "assistant",
                    "content": choice.message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                        } for tc in tool_calls
                    ]
                })
                for tc in tool_calls:
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    result_text = tool_executor(tc.function.name, args) if tool_executor else "Инструмент недоступен"
                    work_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": str(result_text)[:4000]
                    })
                tool_check = client.chat.completions.create(
                    model=model_name,
                    messages=work_messages,
                    tools=tools,
                    tool_choice="auto",
                    max_tokens=1024,
                )
                choice = tool_check.choices[0]
                tool_calls = getattr(choice.message, 'tool_calls', None)

        stream = client.chat.completions.create(
            model=model_name,
            messages=work_messages,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    def _mock_chat(self, messages):
        last_user = next((m['content'] for m in reversed(messages) if m['role'] == 'user'), 'Привет')
        if any(k in last_user.lower() for k in ['код', 'code', 'python', 'react', 'html', 'функци', 'скрипт', 'artifact', 'артефакт']):
            return f"""Отлично, вот решение для: "{last_user[:80]}"

Я создал артефакт согласно вашей задаче, где вы можете его отредактировать.

```python
# Claude Code Artifact
def solve_problem(input_data):
    \"\"\"Умное решение от Claude\"\"\"
    print("Обработка:", input_data)
    result = {{
        "status": "success",
        "processed": input_data.upper(),
        "tokens": len(input_data.split())
    }}
    return result

if __name__ == "__main__":
    print(solve_problem("{last_user[:30]}"))
```
"""
        return f"""Привет! Я Claude Clone — ваш AI-ассистент.

Вы спросили: "{last_user}"

Вот мой ответ в стиле Claude:

- Я могу помочь с кодом, анализом, поиском
- Артефакты автоматически создаются из кода
- Подключайте MCP-серверы и Claude Code Jobs"""


ai_client = AIClient()
