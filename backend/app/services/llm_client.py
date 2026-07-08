"""
Unified LLM client for Groq and OpenRouter.
Both APIs are OpenAI-compatible, so we use httpx with dynamic base_url/api_key.
"""
import json
from typing import AsyncGenerator, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings


class LLMClientError(Exception):
    pass


class LLMClient:
    """Unified client for Groq and OpenRouter."""

    # Provider configs
    PROVIDERS = {
        "groq": {
            "base_url": settings.GROQ_BASE_URL,
            "api_key": settings.GROQ_API_KEY,
        },
        "openrouter": {
            "base_url": settings.OPENROUTER_BASE_URL,
            "api_key": settings.OPENROUTER_API_KEY,
        },
    }

    def __init__(self, provider: Optional[str] = None):
        self.provider = (provider or settings.DEFAULT_LLM_PROVIDER).lower()
        cfg = self.PROVIDERS.get(self.provider)
        if not cfg:
            raise LLMClientError(f"Unknown provider: {self.provider}")
        if not cfg["api_key"]:
            raise LLMClientError(f"API key not set for provider: {self.provider}")
        self.base_url = cfg["base_url"].rstrip("/")
        self.api_key = cfg["api_key"]
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(120.0, connect=10.0),
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def chat_completion(
        self,
        messages: list,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[List[dict]] = None,
        stream: bool = False,
    ) -> dict:
        """Non-streaming chat completion. Returns full response dict."""
        payload = {
            "model": model or settings.DEFAULT_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        # OpenRouter requires extra headers
        headers = {}
        if self.provider == "openrouter":
            headers["HTTP-Referer"] = settings.FRONTEND_URL
            headers["X-Title"] = "AI Chat Agent"

        resp = await self.client.post("/chat/completions", json=payload, headers=headers)

        if resp.status_code != 200:
            try:
                err = resp.json()
                detail = err.get("error", {}).get("message", resp.text)
            except Exception:
                detail = resp.text
            raise LLMClientError(f"{self.provider} API error {resp.status_code}: {detail}")

        return resp.json()

    async def chat_completion_stream(
        self,
        messages: list,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[List[dict]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Streaming SSE: yields JSON lines (content/tool_calls/usage/finish).
        Each yielded line is a JSON string to be sent as SSE data: ...\n\n.
        """
        payload = {
            "model": model or settings.DEFAULT_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {}
        if self.provider == "openrouter":
            headers["HTTP-Referer"] = settings.FRONTEND_URL
            headers["X-Title"] = "AI Chat Agent"

        async with self.client.stream(
            "POST", "/chat/completions", json=payload, headers=headers
        ) as resp:
            if resp.status_code != 200:
                err_text = await resp.aread()
                raise LLMClientError(
                    f"{self.provider} stream error {resp.status_code}: {err_text.decode()}"
                )

            async for line in resp.aiter_lines():
                line = line.strip()
                if not line or line == "data: [DONE]":
                    continue
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        yield json.dumps({"type": "done"})
                        continue
                    try:
                        chunk = json.loads(data)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})

                        # Content token
                        if delta.get("content"):
                            yield json.dumps({
                                "type": "content",
                                "content": delta["content"],
                            })

                        # Tool calls
                        if delta.get("tool_calls"):
                            yield json.dumps({
                                "type": "tool_calls",
                                "tool_calls": delta["tool_calls"],
                            })

                        # Finish reason
                        finish = chunk.get("choices", [{}])[0].get("finish_reason")
                        if finish:
                            usage = chunk.get("usage")
                            yield json.dumps({
                                "type": "finish",
                                "reason": finish,
                                "usage": usage,
                            })

                    except json.JSONDecodeError:
                        continue

    async def list_models(self) -> List[dict]:
        """Fetch available models — uses OpenRouter endpoint."""
        url = "https://openrouter.ai/api/v1/models"
        try:
            r = await self.client.get(url)
            if r.status_code == 200:
                data = r.json()
                return data.get("data", [])
        except Exception:
            pass

        # Fallback: return known Groq models
        return [
            {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B", "provider": "groq"},
            {"id": "llama-3.1-8b-instant", "name": "Llama 3.1 8B", "provider": "groq"},
            {"id": "mixtral-8x7b-32768", "name": "Mixtral 8x7B", "provider": "groq"},
            {"id": "gemma2-9b-it", "name": "Gemma 2 9B", "provider": "groq"},
            {"id": "deepseek-r1-distill-llama-70b", "name": "DeepSeek R1 Distill", "provider": "groq"},
        ]

    async def close(self):
        await self.client.aclose()


# Singleton for reuse
_llm_clients: dict = {}


def get_llm_client(provider: Optional[str] = None) -> LLMClient:
    p = provider or settings.DEFAULT_LLM_PROVIDER
    if p not in _llm_clients:
        _llm_clients[p] = LLMClient(p)
    return _llm_clients[p]
