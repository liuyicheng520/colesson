"""Admin dashboard & user management API."""

from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.core.deps import CurrentAdmin, DbSession
from app.core.response import ApiResponse
from app.models.agent import AgtTask
from app.models.resource import ResResource
from app.models.sys import SysUser
from app.schemas.admin import (
    AdminAccountCreateRequest,
    AdminAccountUpdateRequest,
    AdminMeResponse,
    AdminMenuConfigItem,
    AdminMenuItem,
    AdminMenuUpdateRequest,
    AdminProfilePatchRequest,
    AdminResetPasswordRequest,
    AdminUserBatchStatusRequest,
    AdminUserDetailResponse,
    AdminUserListResponse,
    AdminUserStatusRequest,
)
from app.services.admin_user_service import AdminUserService
from app.services.permission_service import PermissionService

router = APIRouter()


class AdminStatsResponse(BaseModel):
    user_count: int = Field(..., description="注册用户总数")
    resource_count: int = Field(..., description="资源总数")
    task_count: int = Field(..., description="智能体任务总数")
    published_count: int = Field(..., description="已发布资源数")
    published_rate: float = Field(..., description="发布率(0~100)")


@router.get("/stats", summary="管理端统计数据", response_model=ApiResponse[AdminStatsResponse])
def admin_stats(_: CurrentAdmin, db: DbSession) -> ApiResponse[AdminStatsResponse]:
    user_count = db.query(SysUser).filter(SysUser.deleted_at.is_(None)).count()
    resource_q = db.query(ResResource).filter(ResResource.deleted_at.is_(None))
    resource_count = resource_q.count()
    published_count = resource_q.filter(ResResource.status == 2).count()
    task_count = db.query(AgtTask).count()
    published_rate = round(published_count / resource_count * 100, 1) if resource_count else 0.0
    return ApiResponse.success(
        AdminStatsResponse(
            user_count=user_count,
            resource_count=resource_count,
            task_count=task_count,
            published_count=published_count,
            published_rate=published_rate,
        )
    )


@router.get("/me", summary="当前管理员权限与菜单", response_model=ApiResponse[AdminMeResponse])
def admin_me(current_user: CurrentAdmin, db: DbSession) -> ApiResponse[AdminMeResponse]:
    svc = PermissionService(db)
    perms = svc.get_user_permissions(current_user.id)
    menus = [
        AdminMenuItem(
            path=m["path"],
            title=m["title"],
            icon=m["icon"],
            perm_code=m["perm_code"],
            sort=m["sort"],
        )
        for m in svc.get_user_menus(current_user.id)
    ]
    return ApiResponse.success(AdminMeResponse(permissions=perms, menus=menus))


@router.get("/menus", summary="菜单配置列表", response_model=ApiResponse[list[AdminMenuConfigItem]])
def list_menu_config(current_user: CurrentAdmin, db: DbSession) -> ApiResponse[list[AdminMenuConfigItem]]:
    svc = PermissionService(db)
    if not svc.user_has_permission(current_user.id, "menu:menus"):
        from app.core.exceptions import ForbiddenException

        raise ForbiddenException("缺少权限: menu:menus")
    items = [
        AdminMenuConfigItem(
            perm_code=m["perm_code"],
            path=m["path"],
            title=m["title"],
            icon=m["icon"],
            sort=m["sort"],
        )
        for m in svc.list_menu_config()
    ]
    return ApiResponse.success(items)


@router.put("/menus/{perm_code}", summary="更新菜单名称与排序", response_model=ApiResponse[AdminMenuConfigItem])
def update_menu_config(
    perm_code: str,
    req: AdminMenuUpdateRequest,
    current_user: CurrentAdmin,
    db: DbSession,
) -> ApiResponse[AdminMenuConfigItem]:
    updated = PermissionService(db).update_menu_config(
        current_user.id, perm_code, title=req.title, sort=req.sort
    )
    return ApiResponse.success(AdminMenuConfigItem(**updated))


@router.get("/users", summary="学生用户列表", response_model=ApiResponse[AdminUserListResponse])
def list_students(
    current_user: CurrentAdmin,
    db: DbSession,
    keyword: str | None = Query(None),
    status: int | None = Query(None),
    created_from: datetime | None = Query(None, description="注册时间起（含）"),
    created_to: datetime | None = Query(None, description="注册时间止（含）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ApiResponse[AdminUserListResponse]:
    data = AdminUserService(db).list_students(
        current_user.id,
        keyword=keyword,
        status=status,
        created_from=created_from,
        created_to=created_to,
        page=page,
        page_size=page_size,
    )
    return ApiResponse.success(data)


@router.get("/users/{user_id}", summary="学生用户详情", response_model=ApiResponse[AdminUserDetailResponse])
def get_student_detail(
    user_id: int, current_user: CurrentAdmin, db: DbSession
) -> ApiResponse[AdminUserDetailResponse]:
    data = AdminUserService(db).get_student_detail(current_user.id, user_id)
    return ApiResponse.success(data)


@router.put("/users/{user_id}/status", summary="启用/禁用学生账号")
def set_student_status(
    user_id: int,
    req: AdminUserStatusRequest,
    current_user: CurrentAdmin,
    db: DbSession,
) -> ApiResponse[dict]:
    AdminUserService(db).set_user_status(current_user.id, user_id, req.status)
    return ApiResponse.success({"user_id": user_id, "status": req.status})


@router.post("/users/batch-status", summary="批量启用/禁用学生账号")
def batch_student_status(
    req: AdminUserBatchStatusRequest,
    current_user: CurrentAdmin,
    db: DbSession,
) -> ApiResponse[dict]:
    count = AdminUserService(db).batch_set_user_status(current_user.id, req.ids, req.status)
    return ApiResponse.success({"updated": count, "status": req.status})


@router.put("/users/{user_id}/password", summary="重置学生密码")
def reset_student_password(
    user_id: int,
    req: AdminResetPasswordRequest,
    current_user: CurrentAdmin,
    db: DbSession,
) -> ApiResponse[dict]:
    AdminUserService(db).reset_password(current_user.id, user_id, req.new_password)
    return ApiResponse.success({"user_id": user_id, "reset": True})


@router.patch("/users/{user_id}/profile", summary="修正学生画像维度")
def patch_student_profile(
    user_id: int,
    req: AdminProfilePatchRequest,
    current_user: CurrentAdmin,
    db: DbSession,
) -> ApiResponse[dict]:
    AdminUserService(db).patch_profile_dimension(current_user.id, user_id, req)
    return ApiResponse.success({"user_id": user_id, "dimension_code": req.dimension_code})


@router.get("/admins", summary="管理员账号列表", response_model=ApiResponse[AdminUserListResponse])
def list_admins(
    current_user: CurrentAdmin,
    db: DbSession,
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ApiResponse[AdminUserListResponse]:
    data = AdminUserService(db).list_admins(
        current_user.id, keyword=keyword, page=page, page_size=page_size
    )
    return ApiResponse.success(data)


@router.post("/admins", summary="创建管理员账号")
def create_admin(
    req: AdminAccountCreateRequest,
    current_user: CurrentAdmin,
    db: DbSession,
) -> ApiResponse[dict]:
    user = AdminUserService(db).create_admin(current_user.id, req)
    return ApiResponse.success({"id": user.id, "username": user.username})


@router.put("/admins/{admin_id}", summary="编辑管理员账号")
def update_admin(
    admin_id: int,
    req: AdminAccountUpdateRequest,
    current_user: CurrentAdmin,
    db: DbSession,
) -> ApiResponse[dict]:
    user = AdminUserService(db).update_admin(current_user.id, admin_id, req)
    return ApiResponse.success({"id": user.id, "username": user.username, "status": user.status})
