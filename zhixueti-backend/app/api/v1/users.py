"""User profile API — 个人中心维护。"""

from fastapi import APIRouter, File, UploadFile

from app.core.deps import CurrentUser, DbSession
from app.core.response import ApiResponse
from app.schemas.auth import UserResponse
from app.schemas.user import ChangePasswordRequest, UserUpdateRequest
from app.services.user_service import UserService

router = APIRouter()


@router.put("/me", summary="更新当前用户资料", response_model=ApiResponse[UserResponse])
def update_me(req: UserUpdateRequest, current_user: CurrentUser, db: DbSession) -> ApiResponse[UserResponse]:
    """仅允许修改白名单字段，禁止篡改注册时间、角色等敏感信息。"""
    data = UserService(db).update_profile(current_user, req)
    return ApiResponse.success(data)


@router.post("/me/avatar", summary="上传头像", response_model=ApiResponse[UserResponse])
async def upload_avatar(
    current_user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(...),
) -> ApiResponse[UserResponse]:
    user = await UserService(db).upload_avatar(current_user, file)
    return ApiResponse.success(user)


@router.put("/me/password", summary="修改密码", response_model=ApiResponse[dict])
def change_password(
    req: ChangePasswordRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[dict]:
    UserService(db).change_password(current_user, req)
    return ApiResponse.success({"message": "密码修改成功"})
