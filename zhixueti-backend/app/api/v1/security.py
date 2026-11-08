"""Content security admin & audit API."""

from pydantic import BaseModel, Field

from fastapi import APIRouter, Query

from app.core.deps import CurrentAdmin, CurrentUser, DbSession
from app.core.response import ApiResponse
from app.models.agent import AgtLlmCallLog
from app.models.path import SecSensitiveWord
from app.schemas.security import (
    AuditItemResponse,
    AuditReviewRequest,
    LlmLogItemResponse,
    SensitiveWordRequest,
    SensitiveWordResponse,
    TakedownRequest,
)
from app.security.input_guard import InputGuard
from app.security.pipeline import SecurityPipeline
from app.security.repository import SecurityRepository

router = APIRouter()


def _audit_item(a) -> dict:
    """ORM → 响应字典，避免序列化校验失败。"""
    return AuditItemResponse.model_validate(a, from_attributes=True).model_dump(mode="json")


class InputCheckRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=8000)


@router.post("/check-input", summary="输入侧安全检测")
def check_input(
    req: InputCheckRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[dict]:
    guard = InputGuard(db)
    filtered, labels = guard.filter_text(req.content)
    guard.check_relevance(req.content)
    return ApiResponse.success({"passed": True, "filtered": filtered, "labels": labels})


@router.get("/audits", summary="审核记录列表")
def list_audits(
    _: CurrentAdmin,
    db: DbSession,
    audit_result: int | None = None,
    target_type: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ApiResponse[dict]:
    items, total = SecurityRepository(db).list_audits(audit_result, target_type, page, page_size)
    return ApiResponse.success(
        {
            "items": [_audit_item(a) for a in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.put("/audits/{audit_id}/review", summary="人工审核")
def review_audit(
    audit_id: int,
    req: AuditReviewRequest,
    admin: CurrentAdmin,
    db: DbSession,
) -> ApiResponse[AuditItemResponse]:
    repo = SecurityRepository(db)
    audit = repo.get_audit(audit_id)
    if not audit:
        from app.core.exceptions import NotFoundException
        from app.core.error_codes import ErrorCode

        raise NotFoundException(ErrorCode.NOT_FOUND, "审核记录不存在")
    audit.audit_result = req.audit_result
    audit.audit_note = req.audit_note
    audit.auditor_id = admin.id
    audit.audit_type = "manual"
    db.commit()
    db.refresh(audit)
    return ApiResponse.success(_audit_item(audit))


@router.post("/takedown", summary="下架违规内容")
def takedown_content(
    req: TakedownRequest,
    admin: CurrentAdmin,
    db: DbSession,
) -> ApiResponse[dict]:
    repo = SecurityRepository(db)
    if req.target_type == "resource":
        ok = repo.takedown_resource(req.target_id, admin.id, req.reason)
        if not ok:
            from app.core.exceptions import NotFoundException
            from app.core.error_codes import ErrorCode

            raise NotFoundException(ErrorCode.NOT_FOUND, "资源不存在")
        return ApiResponse.success({"target_type": req.target_type, "target_id": req.target_id, "status": "takedown"})
    return ApiResponse.success({"message": "已记录下架请求", "target_id": req.target_id})


@router.get("/sensitive-words", summary="敏感词列表")
def list_sensitive_words(_: CurrentAdmin, db: DbSession) -> ApiResponse[list[SensitiveWordResponse]]:
    words = SecurityRepository(db).list_sensitive_words()
    return ApiResponse.success(
        [SensitiveWordResponse.model_validate(w, from_attributes=True).model_dump() for w in words]
    )


@router.post("/sensitive-words", summary="添加敏感词")
def add_sensitive_word(
    req: SensitiveWordRequest,
    _: CurrentAdmin,
    db: DbSession,
) -> ApiResponse[SensitiveWordResponse]:
    word = SecurityRepository(db).add_sensitive_word(
        SecSensitiveWord(
            word=req.word,
            word_type=req.word_type,
            category=req.category,
            replacement=req.replacement,
            status=1,
        )
    )
    return ApiResponse.success(SensitiveWordResponse.model_validate(word))


@router.get("/llm-logs", summary="LLM调用追溯日志")
def list_llm_logs(
    _: CurrentAdmin,
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ApiResponse[dict]:
    q = db.query(AgtLlmCallLog)
    total = q.count()
    logs = q.order_by(AgtLlmCallLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = []
    for log in logs:
        ext = log.ext_json or {}
        items.append(
            LlmLogItemResponse(
                id=log.id,
                user_id=log.user_id,
                task_id=log.task_id,
                provider=log.provider,
                model_name=log.model_name,
                prompt_tokens=log.prompt_tokens,
                completion_tokens=log.completion_tokens,
                total_tokens=log.total_tokens,
                latency_ms=log.latency_ms,
                is_stream=log.is_stream,
                status=log.status,
                request_hash=log.request_hash,
                prompt_preview=str(ext.get("prompt_snapshot", ""))[:500] or None,
                response_preview=ext.get("response_preview"),
                validation=ext.get("validation"),
                created_at=log.created_at,
            )
        )
    return ApiResponse.success({"items": items, "total": total, "page": page, "page_size": page_size})
