"""Admin audit & monitoring schemas — Phase 4."""

from datetime import datetime

from pydantic import BaseModel, Field


class OperationLogItem(BaseModel):
    id: int
    user_id: int | None = None
    username: str | None = None
    module: str
    action: str
    target_type: str | None = None
    target_id: int | None = None
    request_method: str | None = None
    request_url: str | None = None
    response_code: int | None = None
    ip_address: str | None = None
    duration_ms: int | None = None
    status: int
    error_message: str | None = None
    created_at: datetime


class ExceptionLogItem(BaseModel):
    id: int
    error_code: int | None = None
    error_type: str
    message: str
    request_method: str | None = None
    request_url: str | None = None
    user_id: int | None = None
    username: str | None = None
    ip_address: str | None = None
    severity: str
    is_resolved: int
    created_at: datetime


class AuditOverviewStats(BaseModel):
    operation_total: int
    operation_failed_24h: int
    exception_total: int
    exception_unresolved: int
    exception_24h: int
    log_retention_days: int = 90


class ExceptionTrendItem(BaseModel):
    date: str
    count: int


class ExceptionResolveRequest(BaseModel):
    is_resolved: int = Field(..., ge=0, le=1)


class PurgeLogsResponse(BaseModel):
    operation_deleted: int
    exception_deleted: int
    retention_days: int
