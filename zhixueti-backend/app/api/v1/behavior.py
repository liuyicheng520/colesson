"""Learning behavior API."""

from fastapi import APIRouter, Request

from app.core.deps import CurrentUser, DbSession
from app.core.response import ApiResponse
from app.schemas.learning import BehaviorBatchRequest, LearningSessionStartRequest, LearningStatsResponse
from app.services.behavior_service import BehaviorService
from app.services.learning_stats_service import LearningStatsService
from app.services.profile_behavior_service import ProfileBehaviorService

router = APIRouter()


@router.get("/stats", summary="获取当前用户学习数据统计")
def get_learning_stats(
    current_user: CurrentUser,
    db: DbSession,
    include_trend_30d: bool = True,
) -> ApiResponse[LearningStatsResponse]:
    """学习数据看板 — 强制按 JWT 用户 ID 聚合，不接收 userId 参数。"""
    data = LearningStatsService(db).get_stats(current_user, include_trend_30d=include_trend_30d)
    return ApiResponse.success(data)


@router.post("/sessions/start", summary="开始学习会话")
def start_session(
    req: LearningSessionStartRequest,
    request: Request,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[dict]:
    ip = request.client.host if request.client else None
    session = BehaviorService(db).start_session(
        current_user, req.path_id, req.node_id, req.session_type, req.device_type, ip
    )
    return ApiResponse.success({"session_id": session.id})


@router.post("/sessions/{session_id}/end", summary="结束学习会话")
def end_session(session_id: int, current_user: CurrentUser, db: DbSession) -> ApiResponse[dict]:
    BehaviorService(db).end_session(session_id, current_user.id)
    return ApiResponse.success({"session_id": session_id})


@router.post("/events/batch", summary="批量上报行为事件")
def batch_events(
    req: BehaviorBatchRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[dict]:
    """
    批量上报学习行为埋点。

    支持事件类型: page_view, resource_open, video_play, code_run, quiz_submit, scroll, help_request
    """
    count = BehaviorService(db).batch_track(current_user, req.session_id, req.events)
    # 学习行为上报后静默刷新画像（服务内 6h 节流）
    try:
        ProfileBehaviorService(db).refresh_from_behavior(current_user)
    except Exception:
        pass
    return ApiResponse.success({"accepted": count})
