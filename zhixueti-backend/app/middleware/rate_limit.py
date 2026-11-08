"""Rate limiting middleware using Redis (with fail-fast circuit breaker)."""

import logging
import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.config import get_settings
from app.core.error_codes import ErrorCode
from app.core.response import ApiResponse
from app.db.redis_client import get_redis_client, reset_redis_client

logger = logging.getLogger(__name__)

# Redis 不可用时跳过限流一段时间，避免每个请求阻塞 2s+
_redis_down_until = 0.0
_REDIS_COOLDOWN_SEC = 30.0


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in ("/health", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        global _redis_down_until
        now = time.monotonic()
        if now < _redis_down_until:
            return await call_next(request)

        settings = get_settings()
        client_ip = request.client.host if request.client else "unknown"
        key = f"rate_limit:{client_ip}:{int(time.time()) // settings.rate_limit_window_seconds}"

        try:
            redis_client = get_redis_client()
            count = redis_client.incr(key)
            if count == 1:
                redis_client.expire(key, settings.rate_limit_window_seconds)
            if count > settings.rate_limit_requests:
                body = ApiResponse.fail(
                    code=ErrorCode.RATE_LIMIT_EXCEEDED,
                    message="请求过于频繁，请稍后再试",
                ).model_dump(mode="json")
                return Response(
                    content=__import__("json").dumps(body, ensure_ascii=False),
                    status_code=429,
                    media_type="application/json",
                )
        except Exception as exc:
            # 熔断：后续 30s 内不再尝试 Redis，请求零阻塞放行
            _redis_down_until = time.monotonic() + _REDIS_COOLDOWN_SEC
            reset_redis_client()
            logger.warning("Redis unavailable, rate limit skipped for %.0fs: %s", _REDIS_COOLDOWN_SEC, exc)

        return await call_next(request)
