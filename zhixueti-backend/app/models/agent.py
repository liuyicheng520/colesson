"""Agent ORM models."""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Integer, SmallInteger, String, Text, func
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgtAgentDefinition(Base):
    __tablename__ = "agt_agent_definition"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    agent_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    agent_name: Mapped[str] = mapped_column(String(128), nullable=False)
    agent_type: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    default_model: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_template: Mapped[str | None] = mapped_column(Text)
    input_schema: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    output_schema: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    timeout_sec: Mapped[int] = mapped_column(Integer, default=120)
    max_retry: Mapped[int] = mapped_column(SmallInteger, default=3)
    status: Mapped[int] = mapped_column(SmallInteger, default=1)
    ext_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


class AgtTask(Base):
    __tablename__ = "agt_task"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)
    task_name: Mapped[str] = mapped_column(String(256), nullable=False)
    input_params: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    output_result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[int] = mapped_column(SmallInteger, default=0)
    progress: Mapped[int] = mapped_column(SmallInteger, default=0)
    current_stage: Mapped[str | None] = mapped_column(String(64))
    total_stages: Mapped[int] = mapped_column(SmallInteger, default=7)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    ext_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


class AgtTaskStage(Base):
    __tablename__ = "agt_task_stage"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    stage_code: Mapped[str] = mapped_column(String(64), nullable=False)
    stage_name: Mapped[str] = mapped_column(String(128), nullable=False)
    stage_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[int] = mapped_column(SmallInteger, default=0)
    progress: Mapped[int] = mapped_column(SmallInteger, default=0)
    message: Mapped[str | None] = mapped_column(String(512))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    ext_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


class AgtAgentRun(Base):
    __tablename__ = "agt_agent_run"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    agent_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    run_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    parent_run_id: Mapped[int | None] = mapped_column(BigInteger)
    input_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    output_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[int] = mapped_column(SmallInteger, default=0)
    retry_count: Mapped[int] = mapped_column(SmallInteger, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    ext_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


class AgtCollaborationLog(Base):
    __tablename__ = "agt_collaboration_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    collaboration_type: Mapped[str] = mapped_column(String(32), nullable=False)
    initiator_run_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    responder_run_id: Mapped[int | None] = mapped_column(BigInteger)
    topic: Mapped[str] = mapped_column(String(256), nullable=False)
    initiator_msg: Mapped[str] = mapped_column(Text, nullable=False)
    responder_msg: Mapped[str | None] = mapped_column(Text)
    resolution: Mapped[str | None] = mapped_column(Text)
    resolution_status: Mapped[int] = mapped_column(SmallInteger, default=0)
    round_no: Mapped[int] = mapped_column(SmallInteger, default=1)
    ext_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())


class AgtLlmCallLog(Base):
    __tablename__ = "agt_llm_call_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[int | None] = mapped_column(BigInteger)
    agent_run_id: Mapped[int | None] = mapped_column(BigInteger)
    user_id: Mapped[int | None] = mapped_column(BigInteger)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    call_type: Mapped[str] = mapped_column(String(32), default="chat")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    is_stream: Mapped[int] = mapped_column(SmallInteger, default=0)
    status: Mapped[int] = mapped_column(SmallInteger, default=1)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(512))
    request_hash: Mapped[str | None] = mapped_column(String(64))
    ext_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
