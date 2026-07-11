import os, re, json, logging
from config import Config

logger = logging.getLogger(__name__)


def extract_artifacts(text):
    pattern = r'```(\w+)?\n([\s\S]*?)```'
    out = []
    for lang, code in re.findall(pattern, text):
        out.append({'language': lang.strip() or 'text', 'content': code.strip(),
                    'title': f'{lang or "code"} snippet'})
    return out


class AIClient:
    def __init__(self):
        self.provider = Config.AI_PROVIDER
        self.model    = Config.AI_MODEL

    def chat(self, messages, extended_thinking=False):
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
            logger.exception('AI chat error')
            return f'Ошибка AI: {str(e)}'

    def chat_stream(self, messages, tools=None, tool_executor=None):
        # SSE generator: yields text tokens or JSON event strings
        try:
            if self.provider == 'groq' and Config.GROQ_API_KEY:
                yield from self._groq_chat_stream(messages, tools, tool_executor)
            else:
                yield self.chat(messages)
        except Exception as e:
            logger.exception('AI stream error')
            yield f'Ошибка: {str(e)}'

    def _anthropic_chat(self, messages, extended_thinking=False):
        from anthropic import Anthropic
        client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        system_msg, chat_msgs = '', []
        for m in messages:
            if m['role'] == 'system': system_msg = m['content']
            else: chat_msgs.append({'role': m['role'], 'content': m['content']})
        kwargs = dict(
            model='claude-3-5-sonnet-20241022' if 'claude' not in self.model else self.model,
            max_tokens=2048, system=system_msg or 'Ты полезный AI-ассистент.',
            messages=chat_msgs)
        if extended_thinking:
            kwargs['thinking'] = {'type': 'enabled', 'budget_tokens': 5000}
        return client.messages.create(**kwargs).content[0].text

    def _openrouter_chat(self, messages):
        from openai import OpenAI
        client = OpenAI(base_url='https://openrouter.ai/api/v1', api_key=Config.OPENROUTER_API_KEY)
        return client.chat.completions.create(
            model=self.model if '/' in self.model else 'anthropic/claude-3.5-sonnet',
            messages=messages, temperature=0.7).choices[0].message.content

    def _groq_chat(self, messages):
        from openai import OpenAI
        client = OpenAI(api_key=Config.GROQ_API_KEY, base_url='https://api.groq.com/openai/v1')
        model_name = self.model if ('llama' in self.model or 'mixtral' in self.model) else 'llama-3.3-70b-versatile'
        return client.chat.completions.create(model=model_name, messages=messages).choices[0].message.content

    def _groq_chat_stream(self, messages, tools=None, tool_executor=None):
        from openai import OpenAI
        client = OpenAI(api_key=Config.GROQ_API_KEY, base_url='https://api.groq.com/openai/v1')
        model_name = self.model if ('llama' in self.model or 'mixtral' in self.model) else 'llama-3.3-70b-versatile'
        work = list(messages)
        if tools:
            for _ in range(4):
                check = client.chat.completions.create(
                    model=model_name, messages=work, tools=tools, tool_choice='auto', max_tokens=1024)
                choice = check.choices[0]
                tcs = getattr(choice.message, 'tool_calls', None)
                if not tcs: break
                for tc in tcs:
                    yield json.dumps({'event': 'tool_start', 'name': tc.function.name}) + '\n'
                work.append({'role': 'assistant', 'content': choice.message.content or '',
                    'tool_calls': [{'id': tc.id, 'type': 'function',
                    'function': {'name': tc.function.name, 'arguments': tc.function.arguments}}
                    for tc in tcs]})
                for tc in tcs:
                    try:    args = json.loads(tc.function.arguments or '{}')
                    except: args = {}
                    result = tool_executor(tc.function.name, args) if tool_executor else 'Инструмент недоступен'
                    yield json.dumps({'event': 'tool_done', 'name': tc.function.name, 'result': str(result)[:300]}) + '\n'
                    work.append({'role': 'tool', 'tool_call_id': tc.id, 'content': str(result)[:4000]})
        stream = client.chat.completions.create(model=model_name, messages=work, stream=True)
        for chunk in stream:
            d = chunk.choices[0].delta
            if d and d.content: yield d.content
        yield json.dumps({'event': 'done'}) + '\n'

    def _mock_chat(self, messages):
        last = next((m['content'] for m in reversed(messages) if m['role'] == 'user'), 'Привет')
        return f'Mock ответ на: "{last[:60]}"\n\nВключи реальный ИИ в .env:\n  AI_PROVIDER=groq\n  GROQ_API_KEY=your_key'


ai_client = AIClient()
