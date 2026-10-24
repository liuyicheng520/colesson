"""User profile maintenance schemas."""

import re

from pydantic import BaseModel, EmailStr, Field, field_validator


PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")


class UserUpdateRequest(BaseModel):
    """白名单字段 — 禁止修改 username / user_type / created_at 等敏感项。"""

    nickname: str = Field(..., min_length=2, max_length=20, description="昵称")
    real_name: str = Field(..., min_length=2, max_length=10, description="真实姓名")
    major: str = Field(..., min_length=2, max_length=128, description="专业年级，如软件工程2024级")
    email: EmailStr = Field(..., description="邮箱")
    phone: str | None = Field(None, max_length=11, description="手机号")
    student_no: str | None = Field(None, max_length=32, description="学号")
    bio: str | None = Field(None, max_length=50, description="个人简介/学习目标")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is None or v.strip() == "":
            return None
        v = v.strip()
        if not PHONE_PATTERN.match(v):
            raise ValueError("手机号格式不正确，请输入11位中国大陆手机号")
        return v

    @field_validator("student_no")
    @classmethod
    def normalize_student_no(cls, v: str | None) -> str | None:
        if v is None or v.strip() == "":
            return None
        return v.strip()

    @field_validator("bio")
    @classmethod
    def normalize_bio(cls, v: str | None) -> str | None:
        if v is None or v.strip() == "":
            return None
        return v.strip()


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=6, max_length=64, description="当前密码")
    new_password: str = Field(..., min_length=6, max_length=64, description="新密码")


class AvatarUploadResponse(BaseModel):
    avatar_url: str = Field(..., description="头像访问地址")
