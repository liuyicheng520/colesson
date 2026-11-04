"""Authentication API."""

import secrets

from fastapi import APIRouter, Request

from app.core.config import get_settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthException

from app.core.deps import CurrentUser, DbSession
from app.core.response import ApiResponse
from app.schemas.auth import LoginRequest, SyncAccountRequest, RefreshRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/register", summary="用户注册", response_model=ApiResponse[UserResponse])
def register(req: RegisterRequest, db: DbSession) -> ApiResponse[UserResponse]:
    """
    注册新用户。

    - **username**: 3~64字符
    - **password**: 6~64字符
    - **user_type**: 1=学生 2=教师
    """
    data = AuthService(db).register(req)
    return ApiResponse.success(data)


@router.post("/login", summary="用户登录", response_model=ApiResponse[TokenResponse])
def login(req: LoginRequest, request: Request, db: DbSession) -> ApiResponse[TokenResponse]:
    """登录获取 JWT Token。"""
    ip = request.client.host if request.client else None
    data = AuthService(db).login(req, ip)
    return ApiResponse.success(data)


def _require_bridge(request: Request) -> None:
    settings = get_settings()
    provided = request.headers.get("X-Host-Secret", "")
    if not settings.host_bridge_secret or not secrets.compare_digest(provided, settings.host_bridge_secret):
        raise AuthException(ErrorCode.AUTH_TOKEN_INVALID, "缺少有效的桥接凭证")


@router.post("/sync-account", summary="宿主同步账号（学生/教师/管理员）并登录", response_model=ApiResponse[TokenResponse])
def sync_account(req: SyncAccountRequest, request: Request, db: DbSession) -> ApiResponse[TokenResponse]:
    """单一账号体系：宿主是唯一账号源，本服务按宿主给出的身份创建/校正镜像账号。

    必须携带 X-Host-Secret；未配置共享密钥时直接拒绝。
    """
    _require_bridge(request)
    ip = request.client.host if request.client else None
    data = AuthService(db).sync_account(
        req, ip, user_type=req.user_type, nickname=req.nickname
    )
    return ApiResponse.success(data)


@router.post("/sync-student", summary="宿主同步学生账号并登录（兼容旧接口）", response_model=ApiResponse[TokenResponse])
def sync_student(req: LoginRequest, request: Request, db: DbSession) -> ApiResponse[TokenResponse]:
    """兼容旧调用：等价的按学生身份同步。"""
    _require_bridge(request)
    ip = request.client.host if request.client else None
    data = AuthService(db).sync_student(req, ip)
    return ApiResponse.success(data)


@router.post("/refresh", summary="刷新Token", response_model=ApiResponse[TokenResponse])
def refresh(req: RefreshRequest, db: DbSession) -> ApiResponse[TokenResponse]:
    """使用 refresh_token 获取新的 access_token。"""
    data = AuthService(db).refresh(req.refresh_token)
    return ApiResponse.success(data)


@router.get("/me", summary="获取当前用户", response_model=ApiResponse[UserResponse])
def me(current_user: CurrentUser, db: DbSession) -> ApiResponse[UserResponse]:
    data = AuthService(db).get_me(current_user)
    return ApiResponse.success(data)
