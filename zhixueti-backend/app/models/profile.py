"""User profile ORM models."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, SmallInteger, String, Text, func
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UsrProfileDimensionDef(Base):
    __tablename__ = "usr_profile_dimension_def"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    dimension_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    dimension_name: Mapped[str] = mapped_column(String(64), nullable=False)
    dimension_desc: Mapped[str | None] = mapped_column(String(256))
    value_schema: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    collect_method: Mapped[str] = mapped_column(String(32), default="dialogue")
    weight: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("1.0000"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_required: Mapped[int] = mapped_column(SmallInteger, default=1)
    status: Mapped[int] = mapped_column(SmallInteger, default=1)
    ext_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


class UsrProfile(Base):
    __tablename__ = "usr_profile"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    profile_version: Mapped[int] = mapped_column(Integer, default=1)
    completeness: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.0000"))
    avg_confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.0000"))
    learning_goal: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[int] = mapped_column(SmallInteger, default=0)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    ext_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


class UsrProfileDimensionValue(Base):
    __tablename__ = "usr_profile_dimension_value"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    dimension_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    dimension_value: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.5000"))
    source_type: Mapped[str] = mapped_column(String(32), default="dialogue")
    source_ref_id: Mapped[int | None] = mapped_column(BigInteger)
    ext_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


class UsrProfileEvolutionLog(Base):
    __tablename__ = "usr_profile_evolution_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    dimension_id: Mapped[int | None] = mapped_column(BigInteger)
    old_version: Mapped[int] = mapped_column(Integer, nullable=False)
    new_version: Mapped[int] = mapped_column(Integer, nullable=False)
    old_value: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    new_value: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger_ref_id: Mapped[int | None] = mapped_column(BigInteger)
    change_reason: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())


class UsrProfileDialogueSession(Base):
    __tablename__ = "usr_profile_dialogue_session"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    profile_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    session_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[int] = mapped_column(SmallInteger, default=0)
    current_round: Mapped[int] = mapped_column(Integer, default=0)
    target_dimensions: Mapped[list[Any] | None] = mapped_column(JSON)
    completed_dimensions: Mapped[list[Any] | None] = mapped_column(JSON)
    agent_task_id: Mapped[int | None] = mapped_column(BigInteger)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    ext_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


class UsrProfileDialogueMessage(Base):
    __tablename__ = "usr_profile_dialogue_message"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    round_no: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_dims: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    token_count: Mapped[int | None] = mapped_column(Integer)
    llm_call_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
