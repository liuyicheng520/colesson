"""Resource ORM models."""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Integer, SmallInteger, String, Text, func
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ResResourceTypeDef(Base):
    __tablename__ = "res_resource_type_def"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    type_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    type_name: Mapped[str] = mapped_column(String(64), nullable=False)
    extension_table: Mapped[str] = mapped_column(String(64), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(64))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[int] = mapped_column(SmallInteger, default=1)
    ext_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


class ResResource(Base):
    __tablename__ = "res_resource"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    resource_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    type_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    topic: Mapped[str] = mapped_column(String(128), nullable=False)
    difficulty: Mapped[int] = mapped_column(SmallInteger, default=3)
    language: Mapped[str] = mapped_column(String(16), default="zh-CN")
    status: Mapped[int] = mapped_column(SmallInteger, default=0)
    audit_status: Mapped[int] = mapped_column(SmallInteger, default=0)
    fact_check_status: Mapped[int] = mapped_column(SmallInteger, default=0)
    citation_count: Mapped[int] = mapped_column(Integer, default=0)
    agent_task_id: Mapped[int | None] = mapped_column(BigInteger)
    storage_path: Mapped[str | None] = mapped_column(String(512))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    profile_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    ext_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))


class ResResourceCitation(Base):
    __tablename__ = "res_resource_citation"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    resource_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_title: Mapped[str | None] = mapped_column(String(512))
    source_url: Mapped[str | None] = mapped_column(String(1024))
    source_type: Mapped[str] = mapped_column(String(32), default="rag")
    kb_chunk_id: Mapped[int | None] = mapped_column(BigInteger)
    verify_status: Mapped[int] = mapped_column(SmallInteger, default=0)
    confidence: Mapped[float | None] = mapped_column()
    position_start: Mapped[int | None] = mapped_column(Integer)
    position_end: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())


class ResDocument(Base):
    __tablename__ = "res_document"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    resource_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    content_html: Mapped[str | None] = mapped_column(Text)
    chapter_count: Mapped[int] = mapped_column(Integer, default=0)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    has_formula: Mapped[int] = mapped_column(SmallInteger, default=0)
    has_diagram: Mapped[int] = mapped_column(SmallInteger, default=0)
    ext_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


class ResMindmap(Base):
    __tablename__ = "res_mindmap"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    resource_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    map_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    node_count: Mapped[int] = mapped_column(Integer, default=0)
    max_depth: Mapped[int] = mapped_column(SmallInteger, default=1)
    render_config: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    svg_path: Mapped[str | None] = mapped_column(String(512))
    png_path: Mapped[str | None] = mapped_column(String(512))
    ext_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


class ResReading(Base):
    __tablename__ = "res_reading"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    resource_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    reading_list: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    ext_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


class ResVideo(Base):
    __tablename__ = "res_video"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    resource_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    script_content: Mapped[str] = mapped_column(Text, nullable=False)
    storyboard: Mapped[list[Any] | None] = mapped_column(JSON)
    duration_sec: Mapped[int] = mapped_column(Integer, default=0)
    video_url: Mapped[str | None] = mapped_column(String(512))
    animation_type: Mapped[str] = mapped_column(String(32), default="remotion")
    animation_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    subtitle_srt: Mapped[str | None] = mapped_column(Text)
    ext_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


class ResCodeCase(Base):
    __tablename__ = "res_code_case"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    resource_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    language: Mapped[str] = mapped_column(String(32), nullable=False)
    code_content: Mapped[str] = mapped_column(Text, nullable=False)
    test_cases: Mapped[list[Any] | None] = mapped_column(JSON)
    explanation: Mapped[str | None] = mapped_column(Text)
    dependencies: Mapped[list[Any] | None] = mapped_column(JSON)
    is_runnable: Mapped[int] = mapped_column(SmallInteger, default=1)
    run_result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    ext_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


class ResQuestion(Base):
    __tablename__ = "res_question"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    resource_id: Mapped[int | None] = mapped_column(BigInteger)
    question_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    question_type: Mapped[str] = mapped_column(String(32), nullable=False)
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[Any] | None] = mapped_column(JSON)
    answer: Mapped[Any] = mapped_column(JSON, nullable=False)
    analysis: Mapped[str | None] = mapped_column(Text)
    knowledge_point: Mapped[str] = mapped_column(String(128), nullable=False)
    difficulty: Mapped[int] = mapped_column(SmallInteger, default=3)
    error_type: Mapped[str | None] = mapped_column(String(64))
    ext_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )
