"""LLM gateway API."""

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.deps import CurrentUser, DbSession
from app.core.response import ApiResponse
from app.llm.gateway import LLMGateway
from app.llm.safety import ContentSafetyService
from app.schemas.agent import ContentAuditRequest, LLMChatRequest, LLMChatResponse
from app.security.context import SecurityContext

router = APIRouter()


@router.post("/chat", summary="大模型对话", response_model=ApiResponse[LLMChatResponse])
async def chat(req: LLMChatRequest, current_user: CurrentUser, db: DbSession):
    """
    统一大模型调用接口。

    - **provider**: qwen / deepseek / spark / mock
    - 自动记录 Token 消耗与调用日志
    """
    gateway = LLMGateway(db)
    result = await gateway.chat(
        req.messages,
        provider=req.provider,
        model=req.model,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        user_id=current_user.id,
        context=SecurityContext(target_type="message", source_module="llm_api"),
    )
    return ApiResponse.success(
        LLMChatResponse(
            content=result.content,
            provider=result.provider,
            model=result.model,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.total_tokens,
            latency_ms=result.latency_ms,
        )
    )


@router.post("/chat/stream", summary="大模型流式对话")
async def chat_stream(req: LLMChatRequest, current_user: CurrentUser, db: DbSession):
    """SSE 流式输出大模型响应。"""
    gateway = LLMGateway(db)
    ctx = SecurityContext(target_type="message", source_module="llm_api")

    async def stream():
        from app.llm.stream_markers import peel_stream_chunk

        async for chunk in gateway.stream_chat(
            req.messages,
            req.provider,
            req.model,
            req.temperature,
            req.max_tokens,
            user_id=current_user.id,
            context=ctx,
        ):
            kind, text = peel_stream_chunk(chunk or "")
            if kind == "think" or not text:
                continue
            yield f"data: {json.dumps({'content': text}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/audit", summary="内容安全审核")
async def audit_content(
    req: ContentAuditRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[dict]:
    """
    敏感词过滤 + 大模型自检。

    返回审核结果与风险等级。
    """
    safety = ContentSafetyService(db)
    target_id = req.target_id or 0
    result = await safety.audit_and_persist(req.content, req.target_type, target_id, current_user.id)
    return ApiResponse.success(
        {
            "passed": result.passed,
            "risk_level": result.risk_level,
            "risk_labels": result.risk_labels,
            "audit_id": result.audit_id,
        }
    )
