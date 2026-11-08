"""Admin audit service — operation logs, exception monitoring, retention."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenException, NotFoundException
from app.models.sys import SysExceptionLog, SysOperationLog, SysUser
from app.schemas.admin_audit import (
    AuditOverviewStats,
    ExceptionLogItem,
    ExceptionTrendItem,
    OperationLogItem,
    PurgeLogsResponse,
)

logger = logging.getLogger(__name__)

LOG_RETENTION_DAYS = 90


class AdminAuditService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _assert_perm(self, operator_id: int, perm_code: str) -> None:
        from app.repositories.permission_repository import PermissionRepository

        if perm_code not in PermissionRepository(self.db).get_user_permission_codes(operator_id):
            raise ForbiddenException(f"缺少权限: {perm_code}")

    def _username_map(self, user_ids: set[int]) -> dict[int, str]:
        if not user_ids:
            return {}
        rows = self.db.query(SysUser.id, SysUser.username).filter(SysUser.id.in_(user_ids)).all()
        return {r.id: r.username for r in rows}

    def get_overview(self, operator_id: int) -> AuditOverviewStats:
        self._assert_perm(operator_id, "menu:operation-logs")
        now = datetime.utcnow()
        since_24h = now - timedelta(hours=24)
        op_total = self.db.query(func.count(SysOperationLog.id)).scalar() or 0
        op_failed = (
            self.db.query(func.count(SysOperationLog.id))
            .filter(SysOperationLog.status == 0, SysOperationLog.created_at >= since_24h)
            .scalar()
            or 0
        )
        exc_total = self.db.query(func.count(SysExceptionLog.id)).scalar() or 0
        exc_unresolved = (
            self.db.query(func.count(SysExceptionLog.id)).filter(SysExceptionLog.is_resolved == 0).scalar() or 0
        )
        exc_24h = (
            self.db.query(func.count(SysExceptionLog.id)).filter(SysExceptionLog.created_at >= since_24h).scalar() or 0
        )
        return AuditOverviewStats(
            operation_total=op_total,
            operation_failed_24h=op_failed,
            exception_total=exc_total,
            exception_unresolved=exc_unresolved,
            exception_24h=exc_24h,
            log_retention_days=LOG_RETENTION_DAYS,
        )

    def list_operation_logs(
        self,
        operator_id: int,
        *,
        module: str | None = None,
        action: str | None = None,
        status: int | None = None,
        user_id: int | None = None,
        keyword: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[OperationLogItem], int]:
        self._assert_perm(operator_id, "menu:operation-logs")
        q = self.db.query(SysOperationLog)
        if module:
            q = q.filter(SysOperationLog.module == module)
        if action:
            q = q.filter(SysOperationLog.action == action)
        if status is not None:
            q = q.filter(SysOperationLog.status == status)
        if user_id is not None:
            q = q.filter(SysOperationLog.user_id == user_id)
        if keyword:
            like = f"%{keyword}%"
            q = q.filter(
                (SysOperationLog.request_url.ilike(like))
                | (SysOperationLog.error_message.ilike(like))
            )
        if date_from:
            q = q.filter(SysOperationLog.created_at >= date_from)
        if date_to:
            q = q.filter(SysOperationLog.created_at <= date_to)
        total = q.count()
        rows = (
            q.order_by(SysOperationLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        names = self._username_map({r.user_id for r in rows if r.user_id})
        items = [
            OperationLogItem(
                id=r.id,
                user_id=r.user_id,
                username=names.get(r.user_id) if r.user_id else None,
                module=r.module,
                action=r.action,
                target_type=r.target_type,
                target_id=r.target_id,
                request_method=r.request_method,
                request_url=r.request_url,
                response_code=r.response_code,
                ip_address=r.ip_address,
                duration_ms=r.duration_ms,
                status=r.status,
                error_message=r.error_message,
                created_at=r.created_at,
            )
            for r in rows
        ]
        return items, total

    def list_exception_logs(
        self,
        operator_id: int,
        *,
        severity: str | None = None,
        is_resolved: int | None = None,
        keyword: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ExceptionLogItem], int]:
        self._assert_perm(operator_id, "menu:exception-monitor")
        q = self.db.query(SysExceptionLog)
        if severity:
            q = q.filter(SysExceptionLog.severity == severity)
        if is_resolved is not None:
            q = q.filter(SysExceptionLog.is_resolved == is_resolved)
        if keyword:
            like = f"%{keyword}%"
            q = q.filter(
                (SysExceptionLog.message.ilike(like))
                | (SysExceptionLog.error_type.ilike(like))
                | (SysExceptionLog.request_url.ilike(like))
            )
        if date_from:
            q = q.filter(SysExceptionLog.created_at >= date_from)
        if date_to:
            q = q.filter(SysExceptionLog.created_at <= date_to)
        total = q.count()
        rows = (
            q.order_by(SysExceptionLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        names = self._username_map({r.user_id for r in rows if r.user_id})
        items = [
            ExceptionLogItem(
                id=r.id,
                error_code=r.error_code,
                error_type=r.error_type,
                message=r.message,
                request_method=r.request_method,
                request_url=r.request_url,
                user_id=r.user_id,
                username=names.get(r.user_id) if r.user_id else None,
                ip_address=r.ip_address,
                severity=r.severity,
                is_resolved=r.is_resolved,
                created_at=r.created_at,
            )
            for r in rows
        ]
        return items, total

    def get_exception_trends(self, operator_id: int, days: int = 7) -> list[ExceptionTrendItem]:
        self._assert_perm(operator_id, "menu:exception-monitor")
        since = datetime.utcnow() - timedelta(days=days - 1)
        rows = (
            self.db.query(func.date(SysExceptionLog.created_at).label("d"), func.count(SysExceptionLog.id))
            .filter(SysExceptionLog.created_at >= since.replace(hour=0, minute=0, second=0))
            .group_by(func.date(SysExceptionLog.created_at))
            .order_by(func.date(SysExceptionLog.created_at))
            .all()
        )
        count_map = {str(d): c for d, c in rows}
        out: list[ExceptionTrendItem] = []
        for i in range(days):
            day = (since + timedelta(days=i)).strftime("%Y-%m-%d")
            out.append(ExceptionTrendItem(date=day, count=count_map.get(day, 0)))
        return out

    def resolve_exception(self, operator_id: int, exc_id: int, is_resolved: int) -> ExceptionLogItem:
        self._assert_perm(operator_id, "menu:exception-monitor")
        row = self.db.get(SysExceptionLog, exc_id)
        if not row:
            raise NotFoundException(message="异常记录不存在")
        row.is_resolved = is_resolved
        self.db.commit()
        self.db.refresh(row)
        username = None
        if row.user_id:
            u = self.db.get(SysUser, row.user_id)
            username = u.username if u else None
        return ExceptionLogItem(
            id=row.id,
            error_code=row.error_code,
            error_type=row.error_type,
            message=row.message,
            request_method=row.request_method,
            request_url=row.request_url,
            user_id=row.user_id,
            username=username,
            ip_address=row.ip_address,
            severity=row.severity,
            is_resolved=row.is_resolved,
            created_at=row.created_at,
        )

    def purge_old_logs(self, operator_id: int | None = None, days: int = LOG_RETENTION_DAYS) -> PurgeLogsResponse:
        if operator_id is not None:
            self._assert_perm(operator_id, "btn:log:purge")
        cutoff = datetime.utcnow() - timedelta(days=days)
        op_deleted = (
            self.db.query(SysOperationLog).filter(SysOperationLog.created_at < cutoff).delete(synchronize_session=False)
        )
        exc_deleted = (
            self.db.query(SysExceptionLog).filter(SysExceptionLog.created_at < cutoff).delete(synchronize_session=False)
        )
        self.db.commit()
        logger.info("Purged logs older than %s days: op=%s exc=%s", days, op_deleted, exc_deleted)
        return PurgeLogsResponse(
            operation_deleted=op_deleted,
            exception_deleted=exc_deleted,
            retention_days=days,
        )
