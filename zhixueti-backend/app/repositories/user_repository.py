"""User repository."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import ValidationException
from app.models.sys import SysRole, SysUser, SysUserRole


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: int) -> SysUser | None:
        return (
            self.db.query(SysUser)
            .filter(SysUser.id == user_id, SysUser.deleted_at.is_(None))
            .first()
        )

    def get_by_username(self, username: str) -> SysUser | None:
        return (
            self.db.query(SysUser)
            .filter(SysUser.username == username, SysUser.deleted_at.is_(None))
            .first()
        )

    def get_by_nickname(self, nickname: str, exclude_user_id: int | None = None) -> SysUser | None:
        q = self.db.query(SysUser).filter(SysUser.nickname == nickname, SysUser.deleted_at.is_(None))
        if exclude_user_id:
            q = q.filter(SysUser.id != exclude_user_id)
        return q.first()

    def get_by_email(self, email: str, exclude_user_id: int | None = None) -> SysUser | None:
        q = self.db.query(SysUser).filter(SysUser.email == email, SysUser.deleted_at.is_(None))
        if exclude_user_id:
            q = q.filter(SysUser.id != exclude_user_id)
        return q.first()

    def get_by_student_no(self, student_no: str, exclude_user_id: int | None = None) -> SysUser | None:
        q = self.db.query(SysUser).filter(SysUser.student_no == student_no, SysUser.deleted_at.is_(None))
        if exclude_user_id:
            q = q.filter(SysUser.id != exclude_user_id)
        return q.first()

    def save(self, user: SysUser) -> SysUser:
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_roles(self, user_id: int) -> list[str]:
        rows = (
            self.db.query(SysRole.role_code)
            .join(SysUserRole, SysUserRole.role_id == SysRole.id)
            .filter(SysUserRole.user_id == user_id)
            .all()
        )
        return [r[0] for r in rows]

    def create(self, user: SysUser, role_code: str = "ROLE_STUDENT") -> SysUser:
        self.db.add(user)
        self.db.flush()
        role = self.db.query(SysRole).filter(SysRole.role_code == role_code).first()
        if not role:
            raise ValidationException(f"系统角色未初始化: {role_code}")
        self.db.add(SysUserRole(user_id=user.id, role_id=role.id))
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_login(self, user: SysUser, ip: str | None) -> None:
        user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
        user.last_login_ip = ip
        self.db.commit()

    def list_users(
        self,
        *,
        user_type: int | None = None,
        status: int | None = None,
        keyword: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SysUser], int]:
        q = self.db.query(SysUser).filter(SysUser.deleted_at.is_(None))
        if user_type is not None:
            q = q.filter(SysUser.user_type == user_type)
        if status is not None:
            q = q.filter(SysUser.status == status)
        if created_from is not None:
            q = q.filter(SysUser.created_at >= created_from)
        if created_to is not None:
            q = q.filter(SysUser.created_at <= created_to)
        if keyword:
            like = f"%{keyword}%"
            q = q.filter(
                (SysUser.username.like(like))
                | (SysUser.real_name.like(like))
                | (SysUser.nickname.like(like))
            )
        total = q.count()
        items = (
            q.order_by(SysUser.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def set_roles(self, user_id: int, role_codes: list[str]) -> None:
        self.db.query(SysUserRole).filter(SysUserRole.user_id == user_id).delete()
        for code in role_codes:
            role = self.db.query(SysRole).filter(SysRole.role_code == code).first()
            if role:
                self.db.add(SysUserRole(user_id=user_id, role_id=role.id))
        self.db.commit()

    def update_status(self, user: SysUser, status: int) -> SysUser:
        user.status = status
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_password(self, user: SysUser, password_hash: str) -> SysUser:
        user.password_hash = password_hash
        self.db.commit()
        self.db.refresh(user)
        return user
