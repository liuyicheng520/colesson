"""Auth request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64, description="登录用户名")
    password: str = Field(..., min_length=6, max_length=64, description="密码")
    email: EmailStr | None = Field(None, description="邮箱")
    nickname: str | None = Field(None, max_length=64, description="昵称")
    major: str | None = Field(None, max_length=128, description="专业")
    grade: int | None = Field(None, ge=2020, le=2026, description="入学年级，如 2024 表示 2024 级")
    user_type: int = Field(1, ge=1, le=2, description="用户类型: 1=学生 2=教师")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="刷新Token")


class LoginRequest(BaseModel):
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class SyncAccountRequest(BaseModel):
    """宿主同步账号（单一账号体系）：宿主为唯一账号源，Python 侧只做镜像。"""

    username: str = Field(..., min_length=1, max_length=64, description="用户名")
    password: str = Field(..., min_length=6, max_length=64, description="密码")
    user_type: int = Field(1, ge=1, le=3, description="用户类型: 1=学生 2=教师 3=管理员")
    nickname: str | None = Field(None, max_length=64, description="昵称")


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="访问Token")
    refresh_token: str = Field(..., description="刷新Token")
    token_type: str = Field(default="bearer", description="Token类型")
    expires_in: int = Field(..., description="过期时间(秒)")


class UserResponse(BaseModel):
    id: int
    username: str
    email: str | None = None
    phone: str | None = None
    student_no: str | None = None
    nickname: str
    real_name: str | None = None
    avatar_url: str | None = None
    user_type: int
    major: str | None = None
    bio: str | None = None
    grade: int | None = None
    status: int
    roles: list[str] = Field(default_factory=list)
    created_at: datetime
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}
