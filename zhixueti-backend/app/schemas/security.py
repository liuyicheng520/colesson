"""Content security API schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    audit_no: str
    target_type: str
    target_id: int
    content_snapshot: str | None
    audit_type: str
    audit_result: int
    risk_level: int
    risk_labels: list[Any] | None = None
    risk_detail: dict[str, Any] | None = None
    auditor_id: int | None = None
    audit_note: str | None = None
    created_at: datetime


class AuditReviewRequest(BaseModel):
    audit_result: int = Field(..., ge=0, le=2, description="0=拒绝 1=通过 2=待复核")
    audit_note: str | None = Field(None, max_length=512)


class TakedownRequest(BaseModel):
    target_type: str = Field("resource", description="resource/message/tutor")
    target_id: int
    reason: str = Field(..., min_length=1, max_length=512)


class SensitiveWordRequest(BaseModel):
    word: str = Field(..., min_length=1, max_length=128)
    word_type: str = Field("block", description="block/warn/replace")
    category: str = Field("other", max_length=64)
    replacement: str | None = None


class SensitiveWordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    word: str
    word_type: str
    category: str
    replacement: str | None
    status: int


class LlmLogItemResponse(BaseModel):
    id: int
    user_id: int | None
    task_id: int | None
    provider: str
    model_name: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int | None
    is_stream: int
    status: int
    request_hash: str | None
    prompt_preview: str | None = None
    response_preview: str | None = None
    validation: dict[str, Any] | None = None
    created_at: datetime
