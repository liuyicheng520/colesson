"""Multi-agent scheduling API."""

import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.deps import CurrentAdmin, CurrentUser, DbSession
from app.core.response import ApiResponse
from app.db.session import SessionLocal
from app.schemas.agent import (
    AgentDefinitionResponse,
    AgentDefinitionUpdateRequest,
    CollaborationMessageRequest,
    TaskCreateRequest,
    TaskResponse,
)
from app.services.agent_service import AgentService

router = APIRouter()


@router.get("/definitions", summary="智能体列表", response_model=ApiResponse[list[AgentDefinitionResponse]])
def list_agents(db: DbSession, current_user: CurrentUser) -> ApiResponse[list[AgentDefinitionResponse]]:
    # 管理员可见禁用项，便于在配置页重新启用
    include_disabled = current_user.user_type == 3
    data = AgentService(db).list_agents(include_disabled=include_disabled)
    return ApiResponse.success(data)


@router.put(
    "/definitions/{agent_code}",
    summary="更新智能体配置（管理员）",
    response_model=ApiResponse[AgentDefinitionResponse],
)
def update_agent_definition(
    agent_code: str,
    req: AgentDefinitionUpdateRequest,
    current_user: CurrentAdmin,
    db: DbSession,
) -> ApiResponse[AgentDefinitionResponse]:
    data = AgentService(db).update_agent_definition(agent_code, req)
    return ApiResponse.success(data)


@router.post("/tasks", summary="创建编排任务", response_model=ApiResponse[TaskResponse])
def create_task(
    req: TaskCreateRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[TaskResponse]:
    data = AgentService(db).create_task(current_user, req)
    return ApiResponse.success(data)


@router.get("/tasks/{task_no}", summary="查询任务状态", response_model=ApiResponse[TaskResponse])
def get_task(task_no: str, current_user: CurrentUser, db: DbSession) -> ApiResponse[TaskResponse]:
    data = AgentService(db).get_task(current_user, task_no)
    return ApiResponse.success(data)


@router.post("/tasks/{task_no}/cancel", summary="取消任务", response_model=ApiResponse[TaskResponse])
def cancel_task(task_no: str, current_user: CurrentUser, db: DbSession) -> ApiResponse[TaskResponse]:
    data = AgentService(db).cancel_task(current_user, task_no)
    return ApiResponse.success(data)


@router.get("/tasks/{task_no}/stream", summary="SSE任务进度流（含智能体状态）")
async def stream_task_progress(task_no: str, current_user: CurrentUser, db: DbSession):
    """SSE 流式推送：整体进度 + 7 阶段 + 各智能体执行状态 + 中间预览。"""

    async def event_generator():
        # 长讲义 / 多资源并行时单任务可达数分钟，勿在 2 分钟切断 SSE
        for _ in range(900):
            session = SessionLocal()
            try:
                task = AgentService(session).get_task(current_user, task_no)
                payload = task.model_dump(mode="json")
                yield f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
                if task.status in (2, 3, 4, 5):
                    break
            finally:
                session.close()
            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/collaboration", summary="发布协作消息")
def publish_collaboration(
    req: CollaborationMessageRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[dict]:
    from app.core.exceptions import ForbiddenException
    svc = AgentService(db)
    task = svc.agent_repo.get_task_by_id(req.task_id)
    if task is None:
        raise ForbiddenException("任务不存在")
    if task.user_id != current_user.id and current_user.user_type != 3:
        raise ForbiddenException("无权向该任务写入协作消息")
    collab = svc.publish_collaboration(
        req.task_id,
        req.collaboration_type,
        req.topic,
        req.initiator_run_id,
        req.initiator_msg,
        req.responder_run_id,
    )
    return ApiResponse.success({"collaboration_id": collab.id})
