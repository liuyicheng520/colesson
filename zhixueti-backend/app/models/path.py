"""Learning path ORM models."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, SmallInteger, String, Text, func
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PthKnowledgePoint(Base):
    __tablename__ = "pth_knowledge_point"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    point_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    point_name: Mapped[str] = mapped_column(String(128), nullable=False)
    domain: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(BigInteger)
    difficulty: Mapped[int] = mapped_column(SmallInteger, default=3)
    estimated_min: Mapped[int] = mapped_column(Integer, default=30)
    description: Mapped[str | None] = mapped_column(Text)
    prerequisite_ids: Mapped[list[Any] | None] = mapped_column(JSON)
    ext_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[int] = mapped_column(SmallInteger, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


class PthLearningPath(Base):
    __tablename__ = "pth_learning_path"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    path_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    profile_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    goal: Mapped[str] = mapped_column(String(512), nullable=False)
    path_version: Mapped[int] = mapped_column(Integer, default=1)
    total_nodes: Mapped[int] = mapped_column(Integer, default=0)
    estimated_hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("0.00"))
    status: Mapped[int] = mapped_column(SmallInteger, default=0)
    agent_task_id: Mapped[int | None] = mapped_column(BigInteger)
    profile_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    ext_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


class PthPathNode(Base):
    __tablename__ = "pth_path_node"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    path_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    node_code: Mapped[str] = mapped_column(String(64), nullable=False)
    node_name: Mapped[str] = mapped_column(String(256), nullable=False)
    node_type: Mapped[str] = mapped_column(String(32), default="learn")
    knowledge_point_id: Mapped[int | None] = mapped_column(BigInteger)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    difficulty: Mapped[int] = mapped_column(SmallInteger, default=3)
    estimated_min: Mapped[int] = mapped_column(Integer, default=30)
    is_required: Mapped[int] = mapped_column(SmallInteger, default=1)
    unlock_condition: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    description: Mapped[str | None] = mapped_column(Text)
    ext_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


class PthPathNodeEdge(Base):
    __tablename__ = "pth_path_node_edge"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    path_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    from_node_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    to_node_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    edge_type: Mapped[str] = mapped_column(String(32), default="prerequisite")
    weight: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("1.0000"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())


class PthNodeResource(Base):
    __tablename__ = "pth_node_resource"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    node_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    resource_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    resource_role: Mapped[str] = mapped_column(String(32), default="primary")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_required: Mapped[int] = mapped_column(SmallInteger, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())


class PthNodeProgress(Base):
    __tablename__ = "pth_node_progress"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    path_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    node_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[int] = mapped_column(SmallInteger, default=0)
    mastery_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    study_duration_sec: Mapped[int] = mapped_column(Integer, default=0)
    visit_count: Mapped[int] = mapped_column(Integer, default=0)
    first_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    last_study_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    ext_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


class SecContentAudit(Base):
    __tablename__ = "sec_content_audit"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    audit_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_snapshot: Mapped[str | None] = mapped_column(Text)
    audit_type: Mapped[str] = mapped_column(String(32), default="auto")
    audit_provider: Mapped[str] = mapped_column(String(32), default="internal")
    audit_result: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    risk_level: Mapped[int] = mapped_column(SmallInteger, default=0)
    risk_labels: Mapped[list[Any] | None] = mapped_column(JSON)
    risk_detail: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    auditor_id: Mapped[int | None] = mapped_column(BigInteger)
    audit_note: Mapped[str | None] = mapped_column(String(512))
    agent_run_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


class SecSensitiveWord(Base):
    __tablename__ = "sec_sensitive_word"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    word: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    word_type: Mapped[str] = mapped_column(String(32), default="block")
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    replacement: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[int] = mapped_column(SmallInteger, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )
