"""Admin user management service."""

from __future__ import annotations

from decimal import Decimal

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenException, NotFoundException, ValidationException
from app.core.security import hash_password
from app.models.sys import SysUser
from app.repositories.permission_repository import PermissionRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.tutor_repository import TutorRepository
from app.repositories.user_repository import UserRepository
from app.schemas.admin import (
    AdminAccountCreateRequest,
    AdminAccountUpdateRequest,
    AdminProfilePatchRequest,
    AdminUserDetailResponse,
    AdminUserListItem,
    AdminUserListResponse,
)

ADMIN_ROLE_CODES = {"ROLE_SUPER_ADMIN", "ROLE_CONTENT_ADMIN", "ROLE_OPS_ADMIN", "ROLE_ADMIN"}


class AdminUserService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.user_repo = UserRepository(db)
        self.profile_repo = ProfileRepository(db)
        self.tutor_repo = TutorRepository(db)
        self.perm_repo = PermissionRepository(db)

    def _assert_perm(self, operator_id: int, perm_code: str) -> None:
        if perm_code not in self.perm_repo.get_user_permission_codes(operator_id):
            raise ForbiddenException(f"缺少权限: {perm_code}")

    def list_students(
        self,
        operator_id: int,
        *,
        keyword: str | None = None,
        status: int | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> AdminUserListResponse:
        self._assert_perm(operator_id, "menu:users")
        items, total = self.user_repo.list_users(
            user_type=1,
            status=status,
            keyword=keyword,
            created_from=created_from,
            created_to=created_to,
            page=page,
            page_size=page_size,
        )
        result: list[AdminUserListItem] = []
        for u in items:
            profile = self.profile_repo.get_by_user_id(u.id)
            completeness = float(profile.completeness) if profile and profile.completeness else None
            result.append(
                AdminUserListItem(
                    id=u.id,
                    username=u.username,
                    nickname=u.nickname,
                    real_name=u.real_name,
                    email=u.email,
                    student_no=u.student_no,
                    major=u.major,
                    grade=u.grade,
                    user_type=u.user_type,
                    status=u.status,
                    roles=self.user_repo.get_roles(u.id),
                    profile_completeness=completeness,
                    last_login_at=u.last_login_at,
                    created_at=u.created_at,
                )
            )
        return AdminUserListResponse(items=result, total=total, page=page, page_size=page_size)

    def get_student_detail(self, operator_id: int, user_id: int) -> AdminUserDetailResponse:
        self._assert_perm(operator_id, "menu:users")
        user = self.user_repo.get_by_id(user_id)
        if not user or user.user_type != 1:
            raise NotFoundException(message="学生用户不存在")

        profile = self.profile_repo.get_by_user_id(user.id)
        profile_data = None
        if profile:
            dims = self.profile_repo.get_dimension_values(profile.id)
            profile_data = {
                "completeness": float(profile.completeness or 0),
                "dimensions": {
                    str(dv.dimension_id): dv.dimension_value for dv in dims
                },
                "summary": getattr(profile, "summary_text", None) or profile.ext_json,
            }

        sessions = self.tutor_repo.list_user_sessions(user.id, limit=10)
        session_total = self.tutor_repo.count_user_sessions(user.id)
        recent = [
            {
                "session_no": s.session_no,
                "topic": s.topic,
                "total_rounds": s.total_rounds,
                "status": s.status,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
            for s in sessions
        ]

        return AdminUserDetailResponse(
            id=user.id,
            username=user.username,
            nickname=user.nickname,
            real_name=user.real_name,
            email=user.email,
            phone=user.phone,
            student_no=user.student_no,
            major=user.major,
            bio=user.bio,
            grade=user.grade,
            user_type=user.user_type,
            status=user.status,
            roles=self.user_repo.get_roles(user.id),
            avatar_url=user.avatar_url,
            last_login_at=user.last_login_at,
            last_login_ip=user.last_login_ip,
            created_at=user.created_at,
            profile=profile_data,
            learning_stats={"tutor_sessions": session_total},
            recent_tutor_sessions=recent,
        )

    def set_user_status(self, operator_id: int, user_id: int, status: int) -> None:
        self._assert_perm(operator_id, "btn:user:disable")
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundException(message="用户不存在")
        if user.id == operator_id:
            raise ValidationException("不能禁用当前登录账号")
        self.user_repo.update_status(user, status)

    def batch_set_user_status(self, operator_id: int, user_ids: list[int], status: int) -> int:
        self._assert_perm(operator_id, "btn:user:batch")
        count = 0
        for uid in user_ids:
            if uid == operator_id:
                continue
            user = self.user_repo.get_by_id(uid)
            if not user or user.user_type != 1:
                continue
            self.user_repo.update_status(user, status)
            count += 1
        return count

    def reset_password(self, operator_id: int, user_id: int, new_password: str) -> None:
        self._assert_perm(operator_id, "btn:user:reset_password")
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundException(message="用户不存在")
        self.user_repo.update_password(user, hash_password(new_password))

    def patch_profile_dimension(self, operator_id: int, user_id: int, req: AdminProfilePatchRequest) -> None:
        self._assert_perm(operator_id, "btn:user:edit_profile")
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundException(message="用户不存在")
        profile = self.profile_repo.get_by_user_id(user.id)
        if not profile:
            raise ValidationException("用户尚未构建画像")
        dim_def = self.profile_repo.get_dimension_def_by_code(req.dimension_code)
        if not dim_def:
            raise ValidationException(f"未知画像维度: {req.dimension_code}")
        self.profile_repo.upsert_dimension_value(
            profile.id,
            dim_def.id,
            req.value,
            Decimal("0.85"),
            "admin_manual",
        )

    def list_admins(
        self,
        operator_id: int,
        *,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> AdminUserListResponse:
        self._assert_perm(operator_id, "menu:admins")
        items, total = self.user_repo.list_users(
            user_type=3,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        result = [
            AdminUserListItem(
                id=u.id,
                username=u.username,
                nickname=u.nickname,
                real_name=u.real_name,
                email=u.email,
                user_type=u.user_type,
                status=u.status,
                roles=self.user_repo.get_roles(u.id),
                last_login_at=u.last_login_at,
                created_at=u.created_at,
            )
            for u in items
        ]
        return AdminUserListResponse(items=result, total=total, page=page, page_size=page_size)

    def create_admin(self, operator_id: int, req: AdminAccountCreateRequest) -> SysUser:
        self._assert_perm(operator_id, "btn:admin:create")
        if req.role_code not in ADMIN_ROLE_CODES:
            raise ValidationException("无效的管理员角色")
        if self.user_repo.get_by_username(req.username):
            raise ValidationException("用户名已存在")
        user = SysUser(
            username=req.username,
            password_hash=hash_password(req.password),
            nickname=req.nickname or req.username,
            real_name=req.real_name,
            user_type=3,
            status=1,
        )
        created = self.user_repo.create(user, role_code=req.role_code)
        return created

    def update_admin(self, operator_id: int, admin_id: int, req: AdminAccountUpdateRequest) -> SysUser:
        self._assert_perm(operator_id, "btn:admin:edit")
        user = self.user_repo.get_by_id(admin_id)
        if not user or user.user_type != 3:
            raise NotFoundException(message="管理员不存在")
        if req.nickname is not None:
            user.nickname = req.nickname
        if req.real_name is not None:
            user.real_name = req.real_name
        if req.status is not None:
            if admin_id == operator_id and req.status == 0:
                raise ValidationException("不能禁用当前登录账号")
            user.status = req.status
        self.db.commit()
        self.db.refresh(user)
        if req.role_code:
            if req.role_code not in ADMIN_ROLE_CODES:
                raise ValidationException("无效的管理员角色")
            self.user_repo.set_roles(user.id, [req.role_code])
        return user
