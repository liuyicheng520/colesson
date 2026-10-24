"""FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends, Header, Request
from jwt import PyJWTError, ExpiredSignatureError
from sqlalchemy.orm import Session

from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthException, ForbiddenException
from app.core.security import decode_token
from app.db.session import get_db
from app.models.sys import SysRole, SysUser, SysUserRole
from app.repositories.user_repository import UserRepository

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    request: Request,
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> SysUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthException(ErrorCode.AUTH_TOKEN_INVALID, "缺少Authorization头")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = decode_token(token)
    except ExpiredSignatureError as exc:
        raise AuthException(ErrorCode.AUTH_TOKEN_EXPIRED)
    except PyJWTError:
        raise AuthException(ErrorCode.AUTH_TOKEN_INVALID)
    if payload.get("type") != "access":
        raise AuthException(ErrorCode.AUTH_TOKEN_INVALID, "Token类型错误")
    user_id = payload.get("sub")
    if not user_id:
        raise AuthException(ErrorCode.AUTH_TOKEN_INVALID)
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        raise AuthException(ErrorCode.AUTH_TOKEN_INVALID, "Token无效")
    user = UserRepository(db).get_by_id(uid)
    if not user:
        raise AuthException(ErrorCode.USER_NOT_FOUND)
    if user.status != 1:
        raise AuthException(ErrorCode.AUTH_USER_DISABLED)
    request.state.user_id = user.id
    return user


def get_current_admin(
    current_user: Annotated[SysUser, Depends(get_current_user)],
    db: DbSession,
) -> SysUser:
    roles = (
        db.query(SysRole.role_code)
        .join(SysUserRole, SysUserRole.role_id == SysRole.id)
        .filter(SysUserRole.user_id == current_user.id)
        .all()
    )
    role_codes = {r[0] for r in roles}
    admin_roles = {"ROLE_ADMIN", "ROLE_SUPER_ADMIN", "ROLE_CONTENT_ADMIN", "ROLE_OPS_ADMIN"}
    if current_user.user_type == 3 or role_codes & admin_roles:
        return current_user
    raise ForbiddenException("需要管理员权限")


CurrentUser = Annotated[SysUser, Depends(get_current_user)]
CurrentAdmin = Annotated[SysUser, Depends(get_current_admin)]


def assert_user_ownership(owner_id: int, current_user: SysUser, resource_name: str = "资源") -> None:
    """鉴权兜底：确保数据归属当前登录用户。"""
    if owner_id != current_user.id:
        from app.core.exceptions import NotFoundException
        from app.core.error_codes import ErrorCode

        raise NotFoundException(ErrorCode.NOT_FOUND, f"{resource_name}不存在或无权访问")
