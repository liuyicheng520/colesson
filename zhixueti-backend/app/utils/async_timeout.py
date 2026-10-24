"""asyncio.timeout compatible with Python 3.10 (asyncio.timeout is 3.11+)."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


@asynccontextmanager
async def async_timeout(seconds: float) -> AsyncIterator[None]:
    if sys.version_info >= (3, 11):
        async with asyncio.timeout(seconds):
            yield
        return

    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    if task is None:
        yield
        return

    timed_out = False

    def _on_timeout() -> None:
        nonlocal timed_out
        timed_out = True
        task.cancel()

    handle = loop.call_later(seconds, _on_timeout)
    try:
        yield
    except asyncio.CancelledError:
        if timed_out:
            raise TimeoutError("operation timed out") from None
        raise
    finally:
        handle.cancel()
