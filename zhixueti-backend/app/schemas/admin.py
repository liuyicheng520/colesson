"""Admin API schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AdminMenuItem(BaseModel):
    path: str
    title: str
    icon: str = ""
    perm_code: str
    sort: int = 0
    children: list["AdminMenuItem"] = Field(default_factory=list)


class AdminMenuConfigItem(BaseModel):
    perm_code: str
    path: str
    title: str
    icon: str = ""
    sort: int


class AdminMenuUpdateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=32)
    sort: int = Field(..., ge=0, le=9999)


class AdminUserListItem(BaseModel):
    id: int
    username: str
    nickname: str
    real_name: str | None = None
    email: str | None = None
    student_no: str | None = None
    major: str | None = None
    grade: int | None = None
    user_type: int
    status: int
    roles: list[str] = Field(default_factory=list)
    profile_completeness: float | None = None
    last_login_at: datetime | None = None
    created_at: datetime


class AdminUserListResponse(BaseModel):
    items: list[AdminUserListItem]
    total: int
    page: int
    page_size: int


class AdminUserDetailResponse(BaseModel):
    id: int
    username: str
    nickname: str
    real_name: str | None = None
    email: str | None = None
    phone: str | None = None
    student_no: str | None = None
    major: str | None = None
    bio: str | None = None
    grade: int | None = None
    user_type: int
    status: int
    roles: list[str] = Field(default_factory=list)
    avatar_url: str | None = None
    last_login_at: datetime | None = None
    last_login_ip: str | None = None
    created_at: datetime
    profile: dict[str, Any] | None = None
    learning_stats: dict[str, Any] | None = None
    recent_tutor_sessions: list[dict[str, Any]] = Field(default_factory=list)


class AdminUserStatusRequest(BaseModel):
    status: int = Field(..., ge=0, le=2, description="0=禁用 1=正常")


class AdminUserBatchStatusRequest(BaseModel):
    ids: list[int] = Field(..., min_length=1, max_length=100)
    status: int = Field(..., ge=0, le=1, description="0=禁用 1=正常")


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=6, max_length=64)


class AdminProfilePatchRequest(BaseModel):
    dimension_code: str
    value: dict[str, Any]


class AdminAccountCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6, max_length=64)
    nickname: str = Field("", max_length=64)
    real_name: str | None = Field(None, max_length=32)
    role_code: str = Field(..., description="ROLE_SUPER_ADMIN | ROLE_CONTENT_ADMIN | ROLE_OPS_ADMIN")


class AdminAccountUpdateRequest(BaseModel):
    nickname: str | None = None
    real_name: str | None = None
    status: int | None = Field(None, ge=0, le=1)
    role_code: str | None = None


class AdminMeResponse(BaseModel):
    permissions: list[str] = Field(default_factory=list)
    menus: list[AdminMenuItem] = Field(default_factory=list)
