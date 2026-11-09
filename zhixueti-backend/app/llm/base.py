"""LLM provider base class."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass
class LLMResult:
    content: str
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0
    finish_reason: str = ""
    # 模型请求的工具调用列表（OpenAI 风格）：[{id, type, function: {name, arguments}}]
    tool_calls: list[dict] | None = None


class BaseLLMProvider(ABC):
    provider_name: str
    # 提供商是否支持 OpenAI 风格 tools/function calling；网关据此决定是否透传
    supports_tools: bool = False

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
    ) -> LLMResult:
        ...

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        ...
