"""Redis client wrapper."""

from functools import lru_cache

import redis

from app.core.config import get_settings


@lru_cache
def get_redis_client() -> redis.Redis:
    settings = get_settings()
    # 本地未起 Redis 时要快速失败，避免拖垮每个 HTTP 请求的事件循环
    return redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=0.25,
        socket_timeout=0.5,
        retry_on_timeout=False,
    )


def reset_redis_client() -> None:
    """清除缓存客户端（Redis 恢复后可重建连接）。"""
    get_redis_client.cache_clear()
