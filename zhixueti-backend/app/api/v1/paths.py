"""Learning path API."""

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.core.response import ApiResponse
from app.schemas.path import (
    NodeProgressUpdateRequest,
    NodeResourcePushRequest,
    PathPlanRequest,
    PathReplanRequest,
    PathResponse,
    PathSummaryResponse,
)
from app.services.path_service import PathService

router = APIRouter()


@router.post("/plan", summary="规划个性化学习路径", response_model=ApiResponse[PathResponse])
async def plan_path(
    req: PathPlanRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[PathResponse]:
    """基于6维画像生成「入门→进阶→提升」三阶段学习路径。"""
    data = await PathService(db).plan_path(current_user, req)
    return ApiResponse.success(data)


@router.get("", summary="我的学习路径列表", response_model=ApiResponse[list[PathSummaryResponse]])
def list_paths(current_user: CurrentUser, db: DbSession) -> ApiResponse[list[PathSummaryResponse]]:
    data = PathService(db).list_paths(current_user)
    return ApiResponse.success(data)


@router.get("/{path_id}", summary="路径详情", response_model=ApiResponse[PathResponse])
def get_path(path_id: int, current_user: CurrentUser, db: DbSession) -> ApiResponse[PathResponse]:
    data = PathService(db).get_path(current_user, path_id)
    return ApiResponse.success(data)


@router.put("/nodes/{node_id}/progress", summary="更新节点进度", response_model=ApiResponse[PathResponse])
def update_node_progress(
    node_id: int,
    req: NodeProgressUpdateRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[PathResponse]:
    data = PathService(db).update_node_progress(
        current_user,
        node_id,
        req.status,
        req.study_duration_sec,
        req.mastery_score,
        resource_id=req.resource_id,
        mark_resource_done=req.mark_resource_done,
    )
    return ApiResponse.success(data)


@router.post("/nodes/{node_id}/resources", summary="推送资源到节点")
def push_resources(
    node_id: int,
    req: NodeResourcePushRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[dict]:
    PathService(db).push_resources_to_node(current_user, node_id, req.resource_ids, req.resource_role)
    return ApiResponse.success({"node_id": node_id, "resource_ids": req.resource_ids})


@router.post("/{path_id}/replan", summary="自适应路径重规划", response_model=ApiResponse[PathResponse])
async def request_replan(
    path_id: int,
    req: PathReplanRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[PathResponse]:
    """基于当前路径与学情生成自适应重规划路径。"""
    data = await PathService(db).request_replan(current_user, path_id, req)
    return ApiResponse.success(data)
