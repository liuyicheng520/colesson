"""Content safety — two-tier audit with educational content leniency."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppException
from app.llm.gateway import LLMGateway
from app.security.content_classifier import (
    check_semantic_violations,
    format_audit_failure_message,
    is_educational_content,
)
from app.security.context import SecurityContext
from app.security.fact_validator import FactValidatorAgent
from app.security.input_guard import InputGuard
from app.security.pipeline import SecurityPipeline


@dataclass
class AuditResult:
    passed: bool
    risk_level: int
    risk_labels: list[str]
    audit_id: int | None = None
    detail: dict | None = None
    failure_reason: str = ""


class ContentSafetyService:
    """两级审核：基础敏感词过滤 + 语义合规校验。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.pipeline = SecurityPipeline(db)
        self.llm = LLMGateway(db)
        self.input_guard = InputGuard(db)
        self.validator = FactValidatorAgent(self.llm)

    def filter_sensitive_words(self, content: str) -> tuple[str, list[str]]:
        return self.input_guard.filter_text(content)

    async def validate_content(
        self,
        content: str,
        *,
        topic: str | None = None,
        content_type: str = "resource",
        educational_mode: bool | None = None,
    ) -> None:
        """一级：敏感词硬拦截；二级：语义 + 事实校验（学科内容放宽）。"""
        if not self.settings.content_safety_enabled:
            return

        # 一级：敏感词
        _, word_labels = self.filter_sensitive_words(content)

        # 二级：语义违规（违法/低俗/敏感）
        semantic_reasons = check_semantic_violations(content)
        if semantic_reasons:
            raise AppException(
                ErrorCode.CONTENT_UNSAFE,
                format_audit_failure_message(semantic_reasons=semantic_reasons),
                detail={"reasons": semantic_reasons, "tier": "semantic"},
            )

        edu_mode = educational_mode if educational_mode is not None else is_educational_content(content, topic)
        validation = await self.validator.validate(
            content, topic=topic, educational_mode=edu_mode
        )

        # 学科内容：仅 risk>=3 拦截（截断、篇幅不完整等质量问题交由校验提示与人工复核，
        # 不再等同安全违规阻断入库）；非学科：passed=false 或 risk>=3 均拦截
        blocked = validation.risk_level >= 3 or (not validation.passed and not edu_mode)
        if blocked:
            reason = format_audit_failure_message(
                word_labels=word_labels,
                fact_issues=validation.issues,
                risk_level=validation.risk_level,
            )
            raise AppException(
                ErrorCode.CONTENT_UNSAFE,
                reason,
                detail={
                    "issues": validation.issues,
                    "risk_level": validation.risk_level,
                    "tier": "fact_check",
                    "educational_mode": edu_mode,
                },
            )

    async def llm_self_check(self, content: str, topic: str | None = None) -> dict:
        edu = is_educational_content(content, topic)
        validation = await self.validator.validate(content, topic=topic, educational_mode=edu)
        return {
            "safe": validation.passed and validation.risk_level < 3,
            "risk_level": validation.risk_level,
            "labels": ["fact_check"],
            "issues": validation.issues,
            "needs_citation": validation.risk_level >= 1 and not edu,
        }

    async def audit_and_persist(
        self,
        content: str,
        target_type: str,
        target_id: int,
        auditor_id: int | None = None,
        topic: str | None = None,
    ) -> AuditResult:
        if not self.settings.content_safety_enabled:
            return AuditResult(passed=True, risk_level=0, risk_labels=[])

        filtered, word_labels = self.filter_sensitive_words(content)
        semantic_reasons = check_semantic_violations(filtered)
        if semantic_reasons:
            reason = format_audit_failure_message(semantic_reasons=semantic_reasons)
            self._log_rejected_audit(filtered, target_type, target_id, reason, semantic_reasons)
            raise AppException(
                ErrorCode.CONTENT_UNSAFE,
                reason,
                detail={"reasons": semantic_reasons, "tier": "semantic"},
            )

        ctx = SecurityContext(
            target_type=target_type,
            target_id=target_id,
            topic=topic or filtered[:128],
        )
        edu = is_educational_content(filtered, topic)
        validation = await self.pipeline.validate_output(
            filtered, [], ctx, auditor_id, None, target_id
        )
        passed = validation.passed and validation.risk_level < 3

        if not passed:
            reason = format_audit_failure_message(
                word_labels=word_labels,
                fact_issues=validation.issues,
                risk_level=validation.risk_level,
            )
            raise AppException(
                ErrorCode.CONTENT_UNSAFE,
                reason,
                detail={
                    "issues": validation.issues,
                    "audit_id": validation.fact_check_detail.get("audit_id") if validation.fact_check_detail else None,
                    "risk_level": validation.risk_level,
                    "educational_mode": edu,
                },
            )

        return AuditResult(
            passed=True,
            risk_level=validation.risk_level,
            risk_labels=list(set(word_labels + ["fact_check"])),
            audit_id=validation.fact_check_detail.get("audit_id") if validation.fact_check_detail else None,
            detail=validation.fact_check_detail,
        )

    def _log_rejected_audit(
        self, content: str, target_type: str, target_id: int, reason: str, issues: list
    ) -> None:
        """审核拒绝时写入日志记录。"""
        import uuid
        from app.models.path import SecContentAudit

        audit = SecContentAudit(
            audit_no=str(uuid.uuid4()),
            target_type=target_type,
            target_id=target_id,
            content_snapshot=content[:3000],
            audit_type="auto",
            audit_provider="content_classifier",
            audit_result=0,
            risk_level=3,
            risk_labels=["semantic_violation"],
            risk_detail={"reason": reason, "issues": issues},
        )
        self.db.add(audit)
        self.db.commit()

    @staticmethod
    def extract_citations(content: str) -> list[dict]:
        import re

        sentences = re.split(r"[。！？\n]", content)
        claims = []
        factual_patterns = [r"\d+%", r"\d+年", r"研究表明", r"根据.*数据", r"定义[为是]", r"公式"]
        for s in sentences:
            s = s.strip()
            if len(s) < 10:
                continue
            if any(re.search(p, s) for p in factual_patterns):
                claims.append({"claim_text": s, "verify_status": 0})
        return claims[:20]
