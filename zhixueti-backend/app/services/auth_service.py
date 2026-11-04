"""Authentication service."""

from sqlalchemy.orm import Session

from jwt import PyJWTError, ExpiredSignatureError

from app.core.config import get_settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthException, ValidationException
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.models.sys import SysUser
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse, UserResponse


# 登录失败锁定（进程内存实现，无需 Redis；按 用户名+IP 计数）
_LOGIN_FAIL_LIMIT = 5
_LOGIN_FAIL_WINDOW_SEC = 900  # 15 分钟窗口
_LOGIN_LOCK_SEC = 900

_login_failures: dict[str, tuple[float, int]] = {}
_login_locks: dict[str, float] = {}


def _login_key(username: str | None, ip: str | None) -> str:
    return f"{(username or '').strip().lower()}|{ip or '-'}"


def _login_failure_record(username: str | None, ip: str | None) -> None:
    import time as _time

    now = _time.time()
    key = _login_key(username, ip)
    count, since = _login_failures.get(key, (0, now))
    if now - since > _LOGIN_FAIL_WINDOW_SEC:
        count, since = 0, now
    _login_failures[key] = (count + 1, since)


def _login_lockout_check(username: str | None, ip: str | None) -> None:
    import time as _time

    now = _time.time()
    key = _login_key(username, ip)
    locked_until = _login_locks.get(key, 0)
    if now < locked_until:
        raise AuthException(ErrorCode.AUTH_INVALID_CREDENTIALS, "失败次数过多，账号已临时锁定，请 15 分钟后再试")
    count, since = _login_failures.get(key, (0, now))
    if count >= _LOGIN_FAIL_LIMIT and now - since <= _LOGIN_FAIL_WINDOW_SEC:
        _login_locks[key] = now + _LOGIN_LOCK_SEC
        _login_failures.pop(key, None)
        raise AuthException(ErrorCode.AUTH_INVALID_CREDENTIALS, "失败次数过多，账号已临时锁定，请 15 分钟后再试")


def _login_failure_clear(username: str | None, ip: str | None) -> None:
    _login_failures.pop(_login_key(username, ip), None)
    _login_locks.pop(_login_key(username, ip), None)


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.user_repo = UserRepository(db)
        self.settings = get_settings()

    def register(self, req: RegisterRequest) -> UserResponse:
        if self.user_repo.get_by_username(req.username):
            raise ValidationException("用户名已存在")
        role_code = "ROLE_TEACHER" if req.user_type == 2 else "ROLE_STUDENT"
        user = SysUser(
            username=req.username,
            password_hash=hash_password(req.password),
            email=req.email,
            nickname=req.nickname or req.username,
            major=req.major,
            grade=req.grade,
            user_type=req.user_type,
            status=1,
        )
        user = self.user_repo.create(user, role_code=role_code)
        return self._to_response(user)

    def refresh(self, refresh_token: str) -> TokenResponse:
        try:
            payload = decode_token(refresh_token)
        except ExpiredSignatureError as exc:
            raise AuthException(ErrorCode.AUTH_TOKEN_EXPIRED)
        except PyJWTError:
            raise AuthException(ErrorCode.AUTH_TOKEN_INVALID, "刷新Token无效")
        if payload.get("type") != "refresh":
            raise AuthException(ErrorCode.AUTH_TOKEN_INVALID, "Token类型错误")
        try:
            user_id = int(payload.get("sub", ""))
        except (TypeError, ValueError):
            raise AuthException(ErrorCode.AUTH_TOKEN_INVALID, "Token无效")
        user = self.user_repo.get_by_id(user_id)
        if not user or user.status != 1:
            raise AuthException(ErrorCode.AUTH_USER_DISABLED)
        access = create_access_token(user.id, {"username": user.username, "user_type": user.user_type})
        refresh = create_refresh_token(user.id)
        return TokenResponse(
            access_token=access,
            refresh_token=refresh,
            expires_in=self.settings.jwt_access_token_expire_minutes * 60,
        )

    def login(self, req: LoginRequest, ip: str | None = None) -> TokenResponse:
        _login_lockout_check(req.username, ip)
        user = self.user_repo.get_by_username(req.username)
        if not user or not verify_password(req.password, user.password_hash):
            _login_failure_record(req.username, ip)
            raise AuthException(ErrorCode.AUTH_INVALID_CREDENTIALS)
        _login_failure_clear(req.username, ip)
        if user.status != 1:
            raise AuthException(ErrorCode.AUTH_USER_DISABLED)
        self.user_repo.update_login(user, ip)
        access = create_access_token(user.id, {"username": user.username, "user_type": user.user_type})
        refresh = create_refresh_token(user.id)
        return TokenResponse(
            access_token=access,
            refresh_token=refresh,
            expires_in=self.settings.jwt_access_token_expire_minutes * 60,
        )

    _ROLE_BY_USER_TYPE = {1: "ROLE_STUDENT", 2: "ROLE_TEACHER", 3: "ROLE_SUPER_ADMIN"}

    def sync_account(
        self, req, ip: str | None = None, user_type: int = 1, nickname: str | None = None
    ) -> TokenResponse:
        """宿主桥接：宿主持有唯一账号源，这里只做镜像。

        - 不存在则按宿主给出 user_type 创建；
        - 已存在则同步密码，并**以宿主为准**校正 user_type/角色；
        - 绝不无条件降级（历史缺陷：任何账号登录后被强制改成学生）。
        """
        username = (req.username or "").strip()
        password = req.password or ""
        if not username or len(username) > 64:
            raise ValidationException("用户名长度应为 1~64 个字符")
        if len(password) < 6 or len(password) > 64:
            raise ValidationException("密码长度应为 6~64 个字符")
        user_type = user_type if user_type in self._ROLE_BY_USER_TYPE else 1
        role_code = self._ROLE_BY_USER_TYPE[user_type]

        user = self.user_repo.get_by_username(username)
        if user is None:
            created = SysUser(
                username=username,
                password_hash=hash_password(password),
                nickname=(nickname or username)[:64],
                user_type=user_type,
                status=1,
            )
            self.user_repo.create(created, role_code=role_code)
            return self.login(req, ip)

        if user.status != 1:
            raise AuthException(ErrorCode.AUTH_USER_DISABLED)

        changed = False
        self.user_repo.update_password(user, hash_password(password))
        if user.user_type != user_type:
            user.user_type = user_type
            self.db.add(user)
            changed = True
        if changed:
            self.db.commit()
            self.db.refresh(user)
        # 角色与 user_type 保持一致（宿主持有角色定义）
        current_roles = set(self.user_repo.get_roles(user.id))
        if role_code not in current_roles:
            self.user_repo.set_roles(user.id, [role_code])
        return self.login(req, ip)

    def sync_student(self, req: LoginRequest, ip: str | None = None) -> TokenResponse:
        """兼容旧调用：等价于按学生类型同步。"""
        return self.sync_account(req, ip, user_type=1)

    def get_me(self, user: SysUser) -> UserResponse:
        return self._to_response(user)

    def _to_response(self, user: SysUser) -> UserResponse:
        roles = self.user_repo.get_roles(user.id)
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            phone=user.phone,
            student_no=user.student_no,
            nickname=user.nickname,
            real_name=user.real_name,
            avatar_url=user.avatar_url,
            user_type=user.user_type,
            major=user.major,
            bio=user.bio,
            grade=user.grade,
            status=user.status,
            roles=roles,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
        )
