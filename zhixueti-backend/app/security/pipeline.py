"""Security pipeline orchestrator — embeds in all LLM calls."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.llm.gateway import LLMGateway
from app.models.agent import AgtLlmCallLog
from app.models.path import SecContentAudit
from app.repositories.agent_repository import AgentRepository
from app.security.citation import ensure_citation_block, inject_citation_policy
from app.security.context import SecurityContext
from app.security.fact_validator import FactValidatorAgent, ValidationResult
from app.security.input_guard import InputGuard


class SecurityPipeline:
    MAX_REGENERATE = 1

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.input_guard = InputGuard(db)
        self.llm = LLMGateway(db)
        self.validator = FactValidatorAgent(self.llm)
        self.agent_repo = AgentRepository(db)

    @property
    def enabled(self) -> bool:
        return self.settings.content_safety_enabled

    def guard_input(
        self,
        messages: list[dict[str, str]],
        user_id: int | None = None,
        context: SecurityContext | None = None,
    ) -> list[dict[str, str]]:
        if not self.enabled:
            return messages
        ctx = context or SecurityContext()
        return self.input_guard.guard_messages(messages, allow_off_topic=ctx.allow_off_topic)

    def inject_citation_policy(
        self,
        messages: list[dict[str, str]],
        context: SecurityContext | None = None,
    ) -> list[dict[str, str]]:
        if not self.enabled:
            return messages
        ctx = context or SecurityContext()
        if not ctx.require_citation:
            return messages
        return inject_citation_policy(messages, ctx.knowledge_scope)

    async def validate_output(
        self,
        content: str,
        messages: list[dict[str, str]],
        context: SecurityContext | None = None,
        user_id: int | None = None,
        task_id: int | None = None,
        target_id: int | None = None,
    ) -> ValidationResult:
        if not self.enabled:
            return ValidationResult(passed=True)
        ctx = context or SecurityContext()
        tid = target_id or ctx.target_id or 0

        validation = await self.validator.validate(content, ctx.topic, ctx.knowledge_scope)

        audit_result = 1 if validation.passed else (2 if validation.risk_level == 2 else 0)
        audit = SecContentAudit(
            audit_no=str(uuid.uuid4()),
            target_type=ctx.target_type,
            target_id=tid,
            content_snapshot=content[:3000],
            audit_type="auto",
            audit_provider="fact_validator_agent",
            audit_result=audit_result,
            risk_level=validation.risk_level,
            risk_labels=["fact_check"] + (["suspicious"] if validation.suspicious_segments else []),
            risk_detail={
                "issues": validation.issues,
                "suspicious_segments": validation.suspicious_segments,
                "needs_regenerate": validation.needs_regenerate,
                "fact_check": validation.fact_check_detail,
            },
        )
        self.db.add(audit)
        # 只用 flush，避免中途 commit 把调用方尚未完成的资源主表提前落库
        # （否则扩展表未写入时事务中断，会出现「有摘要、无正文」的孤儿资源）
        self.db.flush()
        self.db.refresh(audit)
        validation.fact_check_detail = {**(validation.fact_check_detail or {}), "audit_id": audit.id}
        return validation

    def post_process_output(
        self, content: str, validation: ValidationResult, context: SecurityContext | None = None
    ) -> str:
        ctx = context or SecurityContext()
        text = content
        if ctx.require_citation:
            text = ensure_citation_block(text, ctx.knowledge_scope)
        # Validation details are persisted in SecContentAudit for admin review only.
        return text

    async def secure_chat(
        self,
        messages: list[dict[str, str]],
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        user_id: int | None = None,
        task_id: int | None = None,
        agent_run_id: int | None = None,
        context: SecurityContext | None = None,
    ):
        """Wrap LLM chat with full security pipeline; returns (LLMResult-like dict, validation)."""
        from app.llm.base import LLMResult

        ctx = context or SecurityContext()
        guarded = self.guard_input(messages, user_id, ctx)
        enriched = self.inject_citation_policy(guarded, ctx)

        content = ""
        result: LLMResult | None = None
        validation = ValidationResult(passed=True)

        for attempt in range(self.MAX_REGENERATE + 1):
            result = await self.llm.chat(
                enriched,
                provider=provider,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                user_id=user_id,
                task_id=task_id,
                agent_run_id=agent_run_id,
                skip_security=True,
            )
            content = result.content
            validation = await self.validate_output(
                content, enriched, ctx, user_id, task_id, ctx.target_id
            )
            if not validation.needs_regenerate or attempt >= self.MAX_REGENERATE:
                break
            enriched = enriched + [
                {"role": "assistant", "content": content},
                {
                    "role": "user",
                    "content": (
                        f"内容校验发现事实问题：{'；'.join(validation.issues[:3])}。"
                        "请修正错误，保留知识依据段落，对不确定处标注[存疑]。"
                    ),
                },
            ]

        assert result is not None
        result.content = self.post_process_output(content, validation, ctx)
        self._log_call(
            enriched,
            result.content,
            result,
            user_id,
            task_id,
            agent_run_id,
            validation,
            is_stream=0,
        )
        return result, validation

    async def secure_stream(
        self,
        messages: list[dict[str, str]],
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        user_id: int | None = None,
        task_id: int | None = None,
        context: SecurityContext | None = None,
    ):
        """Yield chunks; validate and log after stream completes."""
        ctx = context or SecurityContext()
        guarded = self.guard_input(messages, user_id, ctx)
        enriched = self.inject_citation_policy(guarded, ctx)

        full = ""
        async for chunk in self.llm.stream_chat(
            enriched, provider, model, temperature, max_tokens, skip_security=True
        ):
            full += chunk
            yield chunk

        validation = await self.validate_output(full, enriched, ctx, user_id, task_id, ctx.target_id)
        processed = self.post_process_output(full, validation, ctx)
        if processed != full:
            suffix = processed[len(full) :]
            if suffix.strip():
                yield suffix

        from app.llm.base import LLMResult

        pseudo = LLMResult(
            content=processed,
            provider=provider or self.settings.llm_default_provider,
            model=model or "",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            latency_ms=0,
        )
        self._log_call(enriched, processed, pseudo, user_id, task_id, None, validation, is_stream=1)

    def _log_call(
        self,
        prompt_messages: list[dict[str, str]],
        response: str,
        result,
        user_id: int | None,
        task_id: int | None,
        agent_run_id: int | None,
        validation: ValidationResult,
        is_stream: int,
    ) -> None:
        prompt_text = json.dumps(prompt_messages, ensure_ascii=False)[:8000]
        req_hash = hashlib.sha256(prompt_text.encode()).hexdigest()[:32]
        self.agent_repo.log_llm_call(
            AgtLlmCallLog(
                task_id=task_id,
                agent_run_id=agent_run_id,
                user_id=user_id,
                provider=getattr(result, "provider", "unknown"),
                model_name=getattr(result, "model", "unknown"),
                call_type="chat",
                prompt_tokens=getattr(result, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(result, "completion_tokens", 0) or 0,
                total_tokens=getattr(result, "total_tokens", 0) or 0,
                latency_ms=getattr(result, "latency_ms", None),
                is_stream=is_stream,
                status=1 if validation.passed else 2,
                ext_json={
                    "prompt_snapshot": prompt_messages,
                    "response_preview": response[:2000],
                    "validation": {
                        "passed": validation.passed,
                        "risk_level": validation.risk_level,
                        "issues": validation.issues,
                        "needs_regenerate": validation.needs_regenerate,
                    },
                    "logged_at": datetime.now(timezone.utc).isoformat(),
                },
                request_hash=req_hash,
            )
        )
