"""Resource center API."""

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.core.response import ApiResponse, PageData
from app.schemas.resource import AnimationRenderRequest, ResourceGenerateRequest, ResourceResponse
from app.services.resource_service import ResourceService

router = APIRouter()


@router.get("", summary="资源列表", response_model=ApiResponse[PageData[ResourceResponse]])
def list_resources(
    current_user: CurrentUser,
    db: DbSession,
    type_code: str | None = Query(None, description="资源类型编码"),
    topic: str | None = Query(None, description="主题关键词"),
    status: int | None = Query(None, description="资源状态"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ApiResponse[PageData[ResourceResponse]]:
    items, total = ResourceService(db).list_resources(
        current_user, type_code, topic, status, page, page_size
    )
    return ApiResponse.success(PageData.build(items, total, page, page_size))


@router.get("/public", summary="资源广场列表（已发布公开资源）", response_model=ApiResponse[PageData[ResourceResponse]])
def list_public_resources(
    _: CurrentUser,
    db: DbSession,
    type_code: str | None = Query(None, description="资源类型编码"),
    topic: str | None = Query(None, description="主题关键词"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ApiResponse[PageData[ResourceResponse]]:
    items, total = ResourceService(db).list_public_resources(type_code, topic, page, page_size)
    return ApiResponse.success(PageData.build(items, total, page, page_size))


@router.get("/public/{resource_id}", summary="资源广场详情（已发布公开资源）", response_model=ApiResponse[ResourceResponse])
def get_public_resource(
    resource_id: int,
    _: CurrentUser,
    db: DbSession,
) -> ApiResponse[ResourceResponse]:
    data = ResourceService(db).get_public_resource(resource_id)
    return ApiResponse.success(data)


@router.get("/{resource_id}", summary="资源详情", response_model=ApiResponse[ResourceResponse])
def get_resource(
    resource_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[ResourceResponse]:
    data = ResourceService(db).get_resource(current_user, resource_id)
    return ApiResponse.success(data)


@router.post("/generate", summary="触发多智能体协同生成", response_model=ApiResponse[dict])
async def generate_resources(
    req: ResourceGenerateRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[dict]:
    """
    多智能体协同生成个性化学习资源（异步）。

    架构：总协调 → 学情分析 → 5 分工智能体并行 → 校验 → 审核 → 入库
    立即返回 task_no，通过 GET /agents/tasks/{task_no}/stream 追踪进度。
    """
    data = await ResourceService(db).start_generation(current_user, req)
    return ApiResponse.success(data)


@router.post("/animation/render", summary="教学动画渲染（预留接口）", response_model=ApiResponse[dict])
def render_animation(
    req: AnimationRenderRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[dict]:
    """
    预留多模态教学动画渲染接口。

    当前返回脚本就绪状态；后续可接入 Remotion / 讯飞视频生成 / Canvas 动画引擎。
    """
    _ = current_user, db
    return ApiResponse.success(
        {
            "resource_id": req.resource_id,
            "status": "pending",
            "message": "动画渲染接口已预留，当前仅支持脚本+分镜预生成",
            "render_providers": ["remotion", "spark_video", "canvas_2d"],
        }
    )
