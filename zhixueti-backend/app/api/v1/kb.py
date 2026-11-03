"""Knowledge base management API."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.deps import CurrentAdmin, CurrentUser
from app.core.response import ApiResponse
from app.services.vector_kb_service import get_vector_kb_service

router = APIRouter()


@router.get("/status", summary="向量知识库状态")
def kb_status(_: CurrentUser) -> ApiResponse[dict]:
    return ApiResponse.success(get_vector_kb_service().status())


@router.post("/reindex", summary="重建向量知识库索引")
async def kb_reindex(
    _admin: CurrentAdmin,
    force: bool = Query(False, description="强制全量重建"),
) -> ApiResponse[dict]:
    svc = get_vector_kb_service()
    result = await svc.reindex(force=force)
    return ApiResponse.success(result)


@router.get("/search", summary="测试知识库检索")
async def kb_search(
    _: CurrentUser,
    q: str = Query(..., min_length=1, description="检索问题"),
    top_k: int = Query(6, ge=1, le=20),
) -> ApiResponse[dict]:
    ctx, cites = await get_vector_kb_service().search(q, top_k=top_k)
    return ApiResponse.success({"context": ctx, "citations": cites})
