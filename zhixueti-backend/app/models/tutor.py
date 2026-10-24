"""Tutor ORM models."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, SmallInteger, String, Text, func
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TutTutorSession(Base):
    __tablename__ = "tut_tutor_session"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    path_id: Mapped[int | None] = mapped_column(BigInteger)
    node_id: Mapped[int | None] = mapped_column(BigInteger)
    resource_id: Mapped[int | None] = mapped_column(BigInteger)
    tutor_mode: Mapped[str] = mapped_column(String(32), default="socratic")
    topic: Mapped[str] = mapped_column(String(256), nullable=False)
    zpd_level: Mapped[int] = mapped_column(SmallInteger, default=2)
    emotion_state: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[int] = mapped_column(SmallInteger, default=0)
    total_rounds: Mapped[int] = mapped_column(Integer, default=0)
    understanding_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    agent_task_id: Mapped[int | None] = mapped_column(BigInteger)
    profile_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    ext_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


class TutTutorMessage(Base):
    __tablename__ = "tut_tutor_message"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    round_no: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(32), default="text")
    strategy_used: Mapped[str | None] = mapped_column(String(32))
    code_snippet: Mapped[str | None] = mapped_column(Text)
    llm_call_id: Mapped[int | None] = mapped_column(BigInteger)
    token_count: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
