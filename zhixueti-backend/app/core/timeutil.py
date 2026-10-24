"""Beijing timezone helpers for API timestamps."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

BEIJING_TZ = timezone(timedelta(hours=8))


def utc_now_naive() -> datetime:
    """UTC wall-clock without tzinfo (legacy DB storage)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def beijing_now_naive() -> datetime:
    """Beijing wall-clock without tzinfo."""
    return datetime.now(BEIJING_TZ).replace(tzinfo=None)


def to_beijing_iso(dt: datetime | None) -> str | None:
    """Serialize a stored datetime as Beijing ISO string with offset."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Treat naive values as UTC (matches most service writes)
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BEIJING_TZ).isoformat(timespec="seconds")
