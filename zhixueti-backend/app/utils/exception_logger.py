"""Persist server exceptions for admin monitoring."""

from __future__ import annotations

import logging
import traceback
from typing import Any

from app.db.session import SessionLocal
from app.models.sys import SysExceptionLog

logger = logging.getLogger(__name__)

MAX_STACK = 4000
MAX_MESSAGE = 2000


def log_exception(
    *,
    error_type: str,
    message: str,
    error_code: int | None = None,
    stack_trace: str | None = None,
    request_method: str | None = None,
    request_url: str | None = None,
    user_id: int | None = None,
    ip_address: str | None = None,
    severity: str = "error",
) -> None:
    try:
        db = SessionLocal()
        row = SysExceptionLog(
            error_code=error_code,
            error_type=error_type[:128],
            message=(message or "")[:MAX_MESSAGE],
            stack_trace=(stack_trace or "")[:MAX_STACK] or None,
            request_method=request_method,
            request_url=(request_url or "")[:512] or None,
            user_id=user_id,
            ip_address=ip_address,
            severity=severity[:16],
            is_resolved=0,
        )
        db.add(row)
        db.commit()
        db.close()
    except Exception as exc:
        logger.warning("Failed to write exception log: %s", exc)


def log_exception_from_request(request: Any, exc: Exception, *, error_code: int | None = None) -> None:
    user_id = getattr(getattr(request, "state", None), "user_id", None)
    ip = request.client.host if request.client else None
    log_exception(
        error_type=type(exc).__name__,
        message=str(exc),
        error_code=error_code,
        stack_trace=traceback.format_exc(),
        request_method=request.method,
        request_url=str(request.url.path),
        user_id=user_id,
        ip_address=ip,
    )
