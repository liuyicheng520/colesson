"""Admin operations API — Phase 3 analytics, settings, announcements, feedback."""

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.core.deps import CurrentAdmin, CurrentUser, DbSession
from app.core.response import ApiResponse
from app.schemas.admin_ops import (
    AdminOverviewStats,
    AdminTrendStats,
    AnnouncementCreateRequest,
    AnnouncementItem,
    AnnouncementUpdateRequest,
    FeatureUsageItem,
    FeedbackItem,
    FeedbackReplyRequest,
    StudentFeedbackCreateRequest,
    SystemSettingsResponse,
    SystemSettingsUpdateRequest,
    TopTopicItem,
)
from app.services.admin_analytics_service import AdminAnalyticsService
from app.services.admin_ops_service import AdminOpsService
from app.services.config_service import ConfigService
from app.schemas.admin_ops import PublicSystemInfo

router = APIRouter()


class PageFeedbackResponse(BaseModel):
    items: list[FeedbackItem]
    total: int
    page: int
    page_size: int


@router.get("/analytics/overview", summary="运营数据总览", response_model=ApiResponse[AdminOverviewStats])
def analytics_overview(current_user: CurrentAdmin, db: DbSession) -> ApiResponse[AdminOverviewStats]:
    from app.repositories.permission_repository import PermissionRepository

    if "menu:dashboard" not in PermissionRepository(db).get_user_permission_codes(current_user.id):
        from app.core.exceptions import ForbiddenException

        raise ForbiddenException("缺少权限: menu:dashboard")
    data = AdminAnalyticsService(db).get_overview()
    return ApiResponse.success(AdminOverviewStats(**data))


@router.get("/analytics/trends", summary="趋势数据", response_model=ApiResponse[AdminTrendStats])
def analytics_trends(
    current_user: CurrentAdmin,
    db: DbSession,
    days: int = Query(7, ge=7, le=30),
) -> ApiResponse[AdminTrendStats]:
    from app.repositories.permission_repository import PermissionRepository

    if "menu:dashboard" not in PermissionRepository(db).get_user_permission_codes(current_user.id):
        from app.core.exceptions import ForbiddenException

        raise ForbiddenException("缺少权限: menu:dashboard")
    data = AdminAnalyticsService(db).get_trends(days)
    return ApiResponse.success(AdminTrendStats(**data))


@router.get("/analytics/feature-usage", summary="功能使用占比", response_model=ApiResponse[list[FeatureUsageItem]])
def analytics_feature_usage(current_user: CurrentAdmin, db: DbSession) -> ApiResponse[list[FeatureUsageItem]]:
    from app.repositories.permission_repository import PermissionRepository

    if "menu:dashboard" not in PermissionRepository(db).get_user_permission_codes(current_user.id):
        from app.core.exceptions import ForbiddenException

        raise ForbiddenException("缺少权限: menu:dashboard")
    items = AdminAnalyticsService(db).get_feature_usage()
    return ApiResponse.success([FeatureUsageItem(**i) for i in items])


@router.get("/analytics/top-topics", summary="热门知识点 TOP10", response_model=ApiResponse[list[TopTopicItem]])
def analytics_top_topics(current_user: CurrentAdmin, db: DbSession) -> ApiResponse[list[TopTopicItem]]:
    from app.repositories.permission_repository import PermissionRepository

    if "menu:dashboard" not in PermissionRepository(db).get_user_permission_codes(current_user.id):
        from app.core.exceptions import ForbiddenException

        raise ForbiddenException("缺少权限: menu:dashboard")
    items = AdminAnalyticsService(db).get_top_topics(10)
    return ApiResponse.success([TopTopicItem(**i) for i in items])


@router.get("/settings/system", summary="系统设置", response_model=ApiResponse[SystemSettingsResponse])
def get_system_settings(current_user: CurrentAdmin, db: DbSession) -> ApiResponse[SystemSettingsResponse]:
    return ApiResponse.success(AdminOpsService(db).get_system_settings(current_user.id))


@router.put("/settings/system", summary="更新系统设置", response_model=ApiResponse[SystemSettingsResponse])
def update_system_settings(
    req: SystemSettingsUpdateRequest, current_user: CurrentAdmin, db: DbSession
) -> ApiResponse[SystemSettingsResponse]:
    return ApiResponse.success(AdminOpsService(db).update_system_settings(current_user.id, req))


@router.get("/announcements", summary="公告列表", response_model=ApiResponse[list[AnnouncementItem]])
def list_announcements(current_user: CurrentAdmin, db: DbSession) -> ApiResponse[list[AnnouncementItem]]:
    return ApiResponse.success(AdminOpsService(db).list_announcements(current_user.id))


@router.post("/announcements", summary="发布公告", response_model=ApiResponse[AnnouncementItem])
def create_announcement(
    req: AnnouncementCreateRequest, current_user: CurrentAdmin, db: DbSession
) -> ApiResponse[AnnouncementItem]:
    return ApiResponse.success(AdminOpsService(db).create_announcement(current_user.id, req))


@router.put("/announcements/{ann_id}", summary="编辑公告", response_model=ApiResponse[AnnouncementItem])
def update_announcement(
    ann_id: int, req: AnnouncementUpdateRequest, current_user: CurrentAdmin, db: DbSession
) -> ApiResponse[AnnouncementItem]:
    return ApiResponse.success(AdminOpsService(db).update_announcement(current_user.id, ann_id, req))


@router.delete("/announcements/{ann_id}", summary="删除公告")
def delete_announcement(ann_id: int, current_user: CurrentAdmin, db: DbSession) -> ApiResponse[dict]:
    AdminOpsService(db).delete_announcement(current_user.id, ann_id)
    return ApiResponse.success({"id": ann_id, "deleted": True})


@router.get("/feedback", summary="反馈工单列表")
def list_feedback(
    current_user: CurrentAdmin,
    db: DbSession,
    status: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ApiResponse[PageFeedbackResponse]:
    items, total = AdminOpsService(db).list_feedback(
        current_user.id, status=status, page=page, page_size=page_size
    )
    return ApiResponse.success(PageFeedbackResponse(items=items, total=total, page=page, page_size=page_size))


@router.put("/feedback/{feedback_id}", summary="处理反馈工单", response_model=ApiResponse[FeedbackItem])
def reply_feedback(
    feedback_id: int,
    req: FeedbackReplyRequest,
    current_user: CurrentAdmin,
    db: DbSession,
) -> ApiResponse[FeedbackItem]:
    return ApiResponse.success(AdminOpsService(db).reply_feedback(current_user.id, feedback_id, req))
