"""Operation log middleware — records API calls with failure details."""

import asyncio
import logging
import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.db.session import SessionLocal
from app.models.sys import SysOperationLog

logger = logging.getLogger(__name__)

_SKIP_PREFIXES = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/uploads/",
    "/",
)


def _should_skip(path: str, method: str) -> bool:
    if method == "OPTIONS":
        return True
    # GET 读接口不写操作日志，避免 SQLite 写锁拖慢个人中心等并发加载
    if method == "GET":
        return True
    if path in ("/health", "/", "/docs", "/redoc", "/openapi.json"):
        return True
    if path.startswith("/uploads/"):
        return True
    if "/stream" in path:
        return True
    return False


class OperationLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if not path.startswith("/api/") or _should_skip(path, request.method):
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = int((time.perf_counter() - start) * 1000)

        user_id = getattr(request.state, "user_id", None)
        parts = path.strip("/").split("/")
        module = parts[2] if len(parts) > 2 else "unknown"
        error_message = getattr(request.state, "error_message", None)

        def _write_log() -> None:
            db = SessionLocal()
            try:
                log = SysOperationLog(
                    user_id=user_id,
                    module=module,
                    action=request.method,
                    request_method=request.method,
                    request_url=path[:512],
                    response_code=response.status_code,
                    ip_address=request.client.host if request.client else None,
                    user_agent=(request.headers.get("user-agent") or "")[:512] or None,
                    duration_ms=duration_ms,
                    status=1 if response.status_code < 400 else 0,
                    error_message=error_message,
                )
                db.add(log)
                db.commit()
            finally:
                db.close()

        try:
            await asyncio.to_thread(_write_log)
        except Exception as exc:
            logger.warning("Failed to write operation log: %s", exc)

        return response
