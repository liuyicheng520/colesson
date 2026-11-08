"""Admin audit & monitoring API — Phase 4."""

from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.core.deps import CurrentAdmin, DbSession
from app.core.response import ApiResponse
from app.schemas.admin_audit import (
    AuditOverviewStats,
    ExceptionLogItem,
    ExceptionResolveRequest,
    ExceptionTrendItem,
    OperationLogItem,
    PurgeLogsResponse,
)
from app.services.admin_audit_service import AdminAuditService

router = APIRouter()


class PageOperationLogsResponse(BaseModel):
    items: list[OperationLogItem]
    total: int
    page: int
    page_size: int


class PageExceptionLogsResponse(BaseModel):
    items: list[ExceptionLogItem]
    total: int
    page: int
    page_size: int


@router.get("/audit/overview", summary="审计监控概览", response_model=ApiResponse[AuditOverviewStats])
def audit_overview(current_user: CurrentAdmin, db: DbSession) -> ApiResponse[AuditOverviewStats]:
    return ApiResponse.success(AdminAuditService(db).get_overview(current_user.id))


@router.get("/audit/operation-logs", summary="操作日志列表")
def list_operation_logs(
    current_user: CurrentAdmin,
    db: DbSession,
    module: str | None = Query(None),
    action: str | None = Query(None),
    status: int | None = Query(None),
    user_id: int | None = Query(None),
    keyword: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ApiResponse[PageOperationLogsResponse]:
    items, total = AdminAuditService(db).list_operation_logs(
        current_user.id,
        module=module,
        action=action,
        status=status,
        user_id=user_id,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return ApiResponse.success(
        PageOperationLogsResponse(items=items, total=total, page=page, page_size=page_size)
    )


@router.get("/audit/exception-logs", summary="异常日志列表")
def list_exception_logs(
    current_user: CurrentAdmin,
    db: DbSession,
    severity: str | None = Query(None),
    is_resolved: int | None = Query(None),
    keyword: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ApiResponse[PageExceptionLogsResponse]:
    items, total = AdminAuditService(db).list_exception_logs(
        current_user.id,
        severity=severity,
        is_resolved=is_resolved,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return ApiResponse.success(
        PageExceptionLogsResponse(items=items, total=total, page=page, page_size=page_size)
    )


@router.get("/audit/exception-trends", summary="异常趋势", response_model=ApiResponse[list[ExceptionTrendItem]])
def exception_trends(
    current_user: CurrentAdmin,
    db: DbSession,
    days: int = Query(7, ge=7, le=30),
) -> ApiResponse[list[ExceptionTrendItem]]:
    items = AdminAuditService(db).get_exception_trends(current_user.id, days)
    return ApiResponse.success(items)


@router.put("/audit/exception-logs/{exc_id}", summary="标记异常处理状态", response_model=ApiResponse[ExceptionLogItem])
def resolve_exception(
    exc_id: int,
    req: ExceptionResolveRequest,
    current_user: CurrentAdmin,
    db: DbSession,
) -> ApiResponse[ExceptionLogItem]:
    item = AdminAuditService(db).resolve_exception(current_user.id, exc_id, req.is_resolved)
    return ApiResponse.success(item)


@router.post("/audit/purge", summary="清理过期日志", response_model=ApiResponse[PurgeLogsResponse])
def purge_logs(current_user: CurrentAdmin, db: DbSession) -> ApiResponse[PurgeLogsResponse]:
    result = AdminAuditService(db).purge_old_logs(current_user.id)
    return ApiResponse.success(result)
