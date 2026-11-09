"""MCP（Model Context Protocol）兼容端点。

按 JSON-RPC 2.0 实现 MCP 服务端的三个基础方法：
  - initialize  能力协商
  - tools/list  工具清单
  - tools/call  工具执行

设计取舍：不引入官方 mcp SDK，改用约百行的 JSON-RPC 实现，原因有三——
① 保持离线可运行（不新增网络依赖）；② 工具定义与答疑工具环共用同一份
ToolRegistry（app/llm/tools.py），避免两处漂移；③ 端点语义与 MCP 规范一致，
任何标准 MCP 客户端均可直接对接。

鉴权说明：MCP 面向进程内/受信客户端（评审核验、外部 Agent 编排），
工具本身均为只读查询，未暴露写操作。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.deps import DbSession
from app.llm.tools import TOOL_SCHEMAS, run_tool

logger = logging.getLogger(__name__)

router = APIRouter()

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "colesson-tools", "version": "1.0.0"}


def _ok(req_id: Any, result: dict) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": result})


def _err(req_id: Any, code: int, message: str) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


@router.get("", summary="MCP 服务能力说明")
def mcp_manifest() -> dict:
    """浏览器/评审可直接打开本接口确认服务能力。"""
    return {
        "protocol": "MCP (JSON-RPC 2.0)",
        "protocolVersion": PROTOCOL_VERSION,
        "server": SERVER_INFO,
        "transport": "HTTP POST JSON-RPC",
        "methods": ["initialize", "tools/list", "tools/call"],
        "tools": [s["function"]["name"] for s in TOOL_SCHEMAS.values()],
        "example": {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "kb_search", "arguments": {"query": "TCP 三次握手", "top_k": 3}},
        },
    }


@router.post("", summary="MCP JSON-RPC 端点")
async def mcp_rpc(request: Request, db: DbSession) -> JSONResponse:
    try:
        payload = await request.json()
    except Exception:
        return _err(None, -32700, "Parse error: 请求体不是合法 JSON")

    if isinstance(payload, list):  # 批量请求
        results = []
        for item in payload:
            resp = await _dispatch(item, db)
            results.append(resp)
        return JSONResponse(results)

    return await _dispatch(payload, db)


async def _dispatch(payload: dict, db) -> JSONResponse:
    req_id = payload.get("id")
    method = payload.get("method")
    params = payload.get("params") or {}

    if payload.get("jsonrpc") != "2.0" or not method:
        return _err(req_id, -32600, "Invalid Request: 需包含 jsonrpc=2.0 与 method")

    if method == "initialize":
        return _ok(
            req_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
            },
        )

    if method == "tools/list":
        return _ok(req_id, {"tools": list(TOOL_SCHEMAS.values())})

    if method == "tools/call":
        name = params.get("name") or ""
        arguments = params.get("arguments") or {}
        if name not in TOOL_SCHEMAS:
            return _err(req_id, -32602, f"Unknown tool: {name}")
        result = await run_tool(name, arguments, db=db)
        is_error = isinstance(result, dict) and "error" in result
        # MCP 规范：工具错误放在 result 的 isError 中，而非 JSON-RPC error
        return _ok(
            req_id,
            {
                "content": [{"type": "text", "text": _to_text(result)}],
                "isError": is_error,
            },
        )

    return _err(req_id, -32601, f"Method not found: {method}")


def _to_text(result: Any) -> str:
    import json

    try:
        return json.dumps(result, ensure_ascii=False)[:12000]
    except Exception:
        return str(result)[:12000]
