"""Learning behavior ORM models."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, SmallInteger, String, func
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LrnLearningSession(Base):
    __tablename__ = "lrn_learning_session"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    path_id: Mapped[int | None] = mapped_column(BigInteger)
    node_id: Mapped[int | None] = mapped_column(BigInteger)
    session_type: Mapped[str] = mapped_column(String(32), default="study")
    device_type: Mapped[str | None] = mapped_column(String(32))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    duration_sec: Mapped[int | None] = mapped_column(Integer)
    ext_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())


class LrnBehaviorEvent(Base):
    __tablename__ = "lrn_behavior_event"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    session_id: Mapped[int | None] = mapped_column(BigInteger)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_target: Mapped[str | None] = mapped_column(String(64))
    target_id: Mapped[int | None] = mapped_column(BigInteger)
    event_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    page_url: Mapped[str | None] = mapped_column(String(512))
    client_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())


class LrnUserProgressSummary(Base):
    __tablename__ = "lrn_user_progress_summary"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    path_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_nodes: Mapped[int] = mapped_column(Integer, default=0)
    completed_nodes: Mapped[int] = mapped_column(Integer, default=0)
    progress_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.0000"))
    total_study_sec: Mapped[int] = mapped_column(Integer, default=0)
    last_node_id: Mapped[int | None] = mapped_column(BigInteger)
    last_study_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    ext_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )
