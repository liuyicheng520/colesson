"""User profile maintenance service."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthException, ValidationException
from app.core.security import hash_password, verify_password
from app.models.sys import SysUser
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserResponse
from app.schemas.user import ChangePasswordRequest, UserUpdateRequest
from app.services.auth_service import AuthService
from app.utils.avatar_image import detect_image_format, process_avatar

MAX_AVATAR_BYTES = 2 * 1024 * 1024


class UserService:
    EDITABLE_FIELDS = frozenset(
        {"nickname", "real_name", "major", "email", "phone", "student_no", "bio", "avatar_url"}
    )

    def __init__(self, db: Session) -> None:
        self.db = db
        self.user_repo = UserRepository(db)
        self.settings = get_settings()

    def _to_response(self, user: SysUser) -> UserResponse:
        return AuthService(self.db).get_me(user)

    def _ensure_unique(self, user: SysUser, req: UserUpdateRequest) -> None:
        if self.user_repo.get_by_nickname(req.nickname, exclude_user_id=user.id):
            raise ValidationException("昵称已被使用，请更换")
        if self.user_repo.get_by_email(str(req.email), exclude_user_id=user.id):
            raise ValidationException("邮箱已被注册，请更换")
        if req.student_no and self.user_repo.get_by_student_no(req.student_no, exclude_user_id=user.id):
            raise ValidationException("学号已被使用，请更换")

    def update_profile(self, user: SysUser, req: UserUpdateRequest) -> UserResponse:
        self._ensure_unique(user, req)
        user.nickname = req.nickname.strip()
        user.real_name = req.real_name.strip()
        user.major = req.major.strip()
        user.email = str(req.email)
        user.phone = req.phone
        user.student_no = req.student_no
        user.bio = req.bio
        return self._to_response(self.user_repo.save(user))

    def change_password(self, user: SysUser, req: ChangePasswordRequest) -> None:
        if not verify_password(req.old_password, user.password_hash):
            raise AuthException(ErrorCode.AUTH_INVALID_CREDENTIALS, "当前密码不正确")
        if req.old_password == req.new_password:
            raise ValidationException("新密码不能与当前密码相同")
        user.password_hash = hash_password(req.new_password)
        self.user_repo.save(user)

    async def upload_avatar(self, user: SysUser, file: UploadFile) -> UserResponse:
        data = await file.read()
        if len(data) == 0:
            raise ValidationException("上传文件为空")
        if len(data) > MAX_AVATAR_BYTES:
            raise ValidationException("头像大小不能超过 2MB")

        fmt = detect_image_format(data, file.filename or "", file.content_type)
        if not fmt:
            raise ValidationException("仅支持 JPG/PNG 格式头像")

        try:
            processed = process_avatar(data, fmt)
        except ValueError as exc:
            raise ValidationException(str(exc)) from exc

        ext = ".png" if fmt == "png" else ".jpg"
        upload_dir = Path(self.settings.upload_dir) / "avatars"
        upload_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{user.id}_{uuid.uuid4().hex[:12]}{ext}"
        filepath = upload_dir / filename
        filepath.write_bytes(processed)

        if user.avatar_url and user.avatar_url.startswith("/uploads/avatars/"):
            old_name = user.avatar_url.rsplit("/", 1)[-1].split("?")[0]
            old_path = Path(self.settings.upload_dir) / "avatars" / old_name
            if old_path.is_file():
                old_path.unlink(missing_ok=True)

        user.avatar_url = f"/uploads/avatars/{filename}?v={uuid.uuid4().hex[:8]}"
        return self._to_response(self.user_repo.save(user))
