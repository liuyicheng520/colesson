"""System module ORM models."""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Integer, SmallInteger, String, Text, func
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SysUser(Base):
    __tablename__ = "sys_user"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(128), unique=True)
    phone: Mapped[str | None] = mapped_column(String(20))
    student_no: Mapped[str | None] = mapped_column(String(32), unique=True)
    nickname: Mapped[str] = mapped_column(String(64), default="")
    real_name: Mapped[str | None] = mapped_column(String(32))
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    user_type: Mapped[int] = mapped_column(SmallInteger, default=1)
    major: Mapped[str | None] = mapped_column(String(128))
    bio: Mapped[str | None] = mapped_column(String(50))
    grade: Mapped[int | None] = mapped_column(SmallInteger)
    status: Mapped[int] = mapped_column(SmallInteger, default=1)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    last_login_ip: Mapped[str | None] = mapped_column(String(45))
    ext_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class SysRole(Base):
    __tablename__ = "sys_role"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    role_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    role_name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(256))
    status: Mapped[int] = mapped_column(SmallInteger, default=1)
    ext_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


class SysUserRole(Base):
    __tablename__ = "sys_user_role"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())


class SysPermission(Base):
    __tablename__ = "sys_permission"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    perm_code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    perm_name: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(32), default="api")
    resource_path: Mapped[str | None] = mapped_column(String(256))
    parent_id: Mapped[int] = mapped_column(BigInteger, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[int] = mapped_column(SmallInteger, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


class SysRolePermission(Base):
    __tablename__ = "sys_role_permission"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    permission_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())


class SysConfig(Base):
    __tablename__ = "sys_config"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    config_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    config_value: Mapped[str] = mapped_column(Text, nullable=False)
    config_type: Mapped[str] = mapped_column(String(32), default="string")
    description: Mapped[str | None] = mapped_column(String(256))
    is_encrypted: Mapped[int] = mapped_column(SmallInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


class SysAnnouncement(Base):
    __tablename__ = "sys_announcement"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[int] = mapped_column(SmallInteger, default=1)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


class SysFeedback(Base):
    __tablename__ = "sys_feedback"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    category: Mapped[str] = mapped_column(String(32), default="general")
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[int] = mapped_column(SmallInteger, default=0)
    admin_reply: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


class SysOperationLog(Base):
    __tablename__ = "sys_operation_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger)
    module: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(64))
    target_id: Mapped[int | None] = mapped_column(BigInteger)
    request_method: Mapped[str | None] = mapped_column(String(16))
    request_url: Mapped[str | None] = mapped_column(String(512))
    request_params: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    response_code: Mapped[int | None] = mapped_column(Integer)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[int] = mapped_column(SmallInteger, default=1)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())


class SysExceptionLog(Base):
    __tablename__ = "sys_exception_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    error_code: Mapped[int | None] = mapped_column(Integer)
    error_type: Mapped[str] = mapped_column(String(128), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    stack_trace: Mapped[str | None] = mapped_column(Text)
    request_method: Mapped[str | None] = mapped_column(String(16))
    request_url: Mapped[str | None] = mapped_column(String(512))
    user_id: Mapped[int | None] = mapped_column(BigInteger)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    severity: Mapped[str] = mapped_column(String(16), default="error")
    is_resolved: Mapped[int] = mapped_column(SmallInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
