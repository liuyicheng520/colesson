"""Unified LLM gateway with multi-provider routing and security pipeline."""

import logging
from collections.abc import AsyncIterator

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppException
from app.llm.base import BaseLLMProvider, LLMResult
from app.llm.providers.mock import MockProvider
from app.llm.providers.openai_compat import OpenAICompatibleProvider
from app.models.agent import AgtLlmCallLog
from app.repositories.agent_repository import AgentRepository

logger = logging.getLogger(__name__)


class LLMGateway:
    def __init__(self, db: Session | None = None) -> None:
        self.db = db
        self.settings = get_settings()
        self._providers: dict[str, BaseLLMProvider] = {}
        self._init_providers()

    def _init_providers(self) -> None:
        self._providers = {"mock": MockProvider()}
        qwen_key = self._resolve_key(self.settings.qwen_api_key, "llm.qwen.api_key")
        deepseek_key = self._resolve_key(self.settings.deepseek_api_key, "llm.deepseek.api_key")
        spark_key = self._resolve_key(self.settings.spark_api_key, "llm.spark.api_key")
        if qwen_key:
            self._providers["qwen"] = OpenAICompatibleProvider(
                "qwen", qwen_key, self.settings.qwen_base_url, self.settings.qwen_model
            )
        if deepseek_key:
            self._providers["deepseek"] = OpenAICompatibleProvider(
                "deepseek", deepseek_key, self.settings.deepseek_base_url, self.settings.deepseek_model
            )
        if spark_key:
            self._providers["spark"] = OpenAICompatibleProvider(
                "spark", spark_key, self.settings.spark_base_url, self.settings.spark_model
            )

    def _resolve_key(self, env_val: str, config_key: str) -> str:
        if self.db:
            from app.services.config_service import ConfigService

            secret = ConfigService(self.db).get_secret(config_key)
            if secret:
                return secret
        return env_val

    def _default_provider(self) -> str:
        # 文本类默认网关：有 DeepSeek 密钥时一律走 deepseek（多模态另有独立服务）
        if "deepseek" in self._providers:
            return "deepseek"
        configured = self.settings.llm_default_provider
        if self.db:
            from app.services.config_service import ConfigService, LLM_DEFAULT_PROVIDER

            configured = ConfigService(self.db).get_raw(LLM_DEFAULT_PROVIDER, configured)
        return configured or "mock"

    def _fallback_provider(self) -> str:
        if self.db:
            from app.services.config_service import ConfigService, LLM_FALLBACK_PROVIDER

            return ConfigService(self.db).get_raw(LLM_FALLBACK_PROVIDER, self.settings.llm_fallback_provider)
        return self.settings.llm_fallback_provider

    def _content_safety_enabled(self) -> bool:
        if self.db:
            from app.services.config_service import ConfigService, CONTENT_SAFETY

            return ConfigService(self.db).get_bool(CONTENT_SAFETY, self.settings.content_safety_enabled)
        return self.settings.content_safety_enabled

    def get_provider(self, name: str | None = None) -> BaseLLMProvider:
        if self.db:
            self._init_providers()
        provider_name = name or self._default_provider()
        if provider_name in self._providers:
            return self._providers[provider_name]
        fallback = self._fallback_provider()
        if fallback in self._providers:
            logger.warning("Provider %s unavailable, fallback to %s", provider_name, fallback)
            return self._providers[fallback]
        return self._providers["mock"]

    async def chat(
        self,
        messages: list[dict[str, str]],
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        user_id: int | None = None,
        task_id: int | None = None,
        agent_run_id: int | None = None,
        stream: bool = False,
        skip_security: bool = False,
        context: "SecurityContext | None" = None,
    ) -> LLMResult:
        if self.db and self._content_safety_enabled() and not skip_security:
            from app.security.pipeline import SecurityPipeline

            result, _ = await SecurityPipeline(self.db).secure_chat(
                messages,
                provider=provider,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                user_id=user_id,
                task_id=task_id,
                agent_run_id=agent_run_id,
                context=context,
            )
            return result

        return await self._raw_chat(
            messages,
            provider,
            model,
            temperature,
            max_tokens,
            user_id,
            task_id,
            agent_run_id,
            stream,
        )

    async def _raw_chat(
        self,
        messages: list[dict[str, str]],
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        user_id: int | None = None,
        task_id: int | None = None,
        agent_run_id: int | None = None,
        stream: bool = False,
    ) -> LLMResult:
        llm = self.get_provider(provider)
        try:
            result = await llm.chat(messages, model, temperature, max_tokens)
        except Exception as exc:
            logger.exception("LLM call failed: %s", exc)
            fallback = self._fallback_provider()
            # 超时/连接失败不再串行重试备用提供商，避免 120s+120s 拖垮前端
            if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError)):
                raise AppException(ErrorCode.LLM_PROVIDER_ERROR, "大模型响应超时，请稍后重试", http_status=504)
            if provider != fallback:
                return await self._raw_chat(
                    messages,
                    provider=fallback,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    user_id=user_id,
                    task_id=task_id,
                    agent_run_id=agent_run_id,
                )
            raise AppException(ErrorCode.LLM_PROVIDER_ERROR, str(exc), http_status=502)

        if self.db:
            AgentRepository(self.db).log_llm_call(
                AgtLlmCallLog(
                    task_id=task_id,
                    agent_run_id=agent_run_id,
                    user_id=user_id,
                    provider=result.provider,
                    model_name=result.model,
                    prompt_tokens=result.prompt_tokens,
                    completion_tokens=result.completion_tokens,
                    total_tokens=result.total_tokens,
                    latency_ms=result.latency_ms,
                    is_stream=1 if stream else 0,
                    status=1,
                )
            )
        return result

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        user_id: int | None = None,
        task_id: int | None = None,
        skip_security: bool = False,
        context: "SecurityContext | None" = None,
    ) -> AsyncIterator[str]:
        if self.db and self._content_safety_enabled() and not skip_security:
            from app.security.pipeline import SecurityPipeline

            async for chunk in SecurityPipeline(self.db).secure_stream(
                messages,
                provider=provider,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                user_id=user_id,
                task_id=task_id,
                context=context,
            ):
                yield chunk
            return

        llm = self.get_provider(provider)
        async for chunk in llm.stream_chat(messages, model, temperature, max_tokens):
            yield chunk
