"""OpenAI-compatible LLM provider (Qwen / DeepSeek)."""

import time
from collections.abc import AsyncIterator

import httpx

from app.llm.base import BaseLLMProvider, LLMResult


class OpenAICompatibleProvider(BaseLLMProvider):
    def __init__(
        self,
        provider_name: str,
        api_key: str,
        base_url: str,
        default_model: str,
    ) -> None:
        self.provider_name = provider_name
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResult:
        model = model or self.default_model
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        start = time.perf_counter()
        # 长讲义可达 8k tokens，超时放宽；连接 10s 内必须建立
        read_timeout = 300 if max_tokens and max_tokens >= 4096 else 90
        timeout = httpx.Timeout(read_timeout, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        latency = int((time.perf_counter() - start) * 1000)
        usage = data.get("usage", {})
        choice = data["choices"][0]
        content = choice["message"]["content"]
        return LLMResult(
            content=content,
            provider=self.provider_name,
            model=model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            latency_ms=latency,
            finish_reason=str(choice.get("finish_reason") or ""),
        )

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        model = model or self.default_model
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=10.0)) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    chunk = line[6:]
                    if chunk.strip() == "[DONE]":
                        break
                    import json

                    data = json.loads(chunk)
                    delta = data["choices"][0].get("delta", {})
                    if rc := delta.get("reasoning_content"):
                        yield f"\x01T\x01{rc}"
                    if text := delta.get("content"):
                        yield f"\x01C\x01{text}"
