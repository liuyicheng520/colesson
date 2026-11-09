"""模型工具调用（Function Calling）注册表。

同一份工具定义同时服务两条通道：
1. 智能答疑的受控工具环（OpenAI 风格 tools 参数，见 tutor_service）；
2. MCP 兼容端点（JSON-RPC 2.0，见 app/api/v1/mcp.py）。

工具实现只做薄封装，业务逻辑复用既有 service，不新增业务路径。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ── 工具实现 ────────────────────────────────────────────────

async def tool_kb_search(query: str, top_k: int = 4) -> dict[str, Any]:
    """检索本地向量知识库（混合检索 + 质量加权）。"""
    from app.services.vector_kb_service import get_vector_kb_service

    top_k = max(1, min(int(top_k or 4), 8))
    svc = get_vector_kb_service()
    if not svc.enabled:
        return {"context": "", "citations": [], "chunks": 0, "note": "知识库未启用"}
    ctx, citations = await svc.search(query, top_k=top_k)
    return {
        "context": ctx[:6000],
        "citations": [
            {
                k: c.get(k)
                for k in ("doc_id", "filename", "score", "vector_score", "lexical_score", "source_quality", "quality_tier")
                if k in c
            }
            for c in citations
        ],
        "chunks": len(citations),
    }


def tool_profile_get(db: Session, user) -> dict[str, Any]:
    """读取学习画像六维详情。user 为 SysUser 实体。"""
    from app.services.profile_service import ProfileService

    detail = ProfileService(db).get_profile_detail(user)
    data = detail.model_dump() if hasattr(detail, "model_dump") else dict(detail)
    # 精简回传：只保留模型决策需要的字段
    dims = data.get("dimensions") or []
    return {
        "built": data.get("built"),
        "status": data.get("status"),
        "dimensions": [
            {
                "code": d.get("code"),
                "name": d.get("name"),
                "value": d.get("value"),
                "summary": str(d.get("summary") or "")[:200],
            }
            for d in dims
        ][:8],
    }


def tool_learning_stats_get(db: Session, user) -> dict[str, Any]:
    """读取学习统计（时长/资源/知识点/趋势）。user 为 SysUser 实体。"""
    from app.services.learning_stats_service import LearningStatsService

    stats = LearningStatsService(db).get_stats(user, include_trend_30d=False)
    data = stats.model_dump() if hasattr(stats, "model_dump") else dict(stats)
    return {
        "total_study_hours": data.get("total_study_hours"),
        "resources_learned": data.get("resources_learned"),
        "knowledge_points_completed": data.get("knowledge_points_completed"),
        "avg_accuracy": data.get("avg_accuracy"),
        "path_progress_rate": data.get("path_progress_rate"),
        "trend_7d": data.get("trend_7d") or [],
    }


# ── OpenAI 风格工具 schema ─────────────────────────────────

TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "kb_search": {
        "type": "function",
        "function": {
            "name": "kb_search",
            "description": "检索课程本地知识库（官方标准文档/教材语料），返回带来源引用的知识片段。回答课程概念问题前应优先调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索关键词或问题，使用课程术语"},
                    "top_k": {"type": "integer", "description": "返回片段数，默认 4，最大 8"},
                },
                "required": ["query"],
            },
        },
    },
    "profile_get": {
        "type": "function",
        "function": {
            "name": "profile_get",
            "description": "读取指定学生的学习画像（六维：知识基础/目标/风格/兴趣/薄弱点/时间）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "学生用户名"},
                },
                "required": ["username"],
            },
        },
    },
    "learning_stats_get": {
        "type": "function",
        "function": {
            "name": "learning_stats_get",
            "description": "读取指定学生的学习统计：学习时长、已学资源数、知识点完成数、正确率与路径进度。",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "学生用户名"},
                },
                "required": ["username"],
            },
        },
    },
}


def openai_tool_specs(names: list[str] | None = None) -> list[dict[str, Any]]:
    """按名称导出 OpenAI 风格工具定义；names 为空时导出全部。"""
    keys = names or list(TOOL_SCHEMAS)
    return [TOOL_SCHEMAS[k] for k in keys if k in TOOL_SCHEMAS]


# ── 统一执行入口 ───────────────────────────────────────────

async def run_tool(
    name: str,
    arguments: dict[str, Any] | str | None,
    *,
    db: Session | None = None,
    user=None,
) -> dict[str, Any]:
    """执行一次工具调用。

    - kb_search 不需要 db/user；
    - profile_get / learning_stats_get 优先使用传入的 user 实体（进程内调用），
      否则按 username 在 db 中查找（MCP 通道）。
    """
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments) if arguments.strip() else {}
        except json.JSONDecodeError:
            return {"error": f"工具参数不是合法 JSON: {arguments[:120]}"}
    args = arguments or {}

    try:
        if name == "kb_search":
            return await tool_kb_search(str(args.get("query", "")), int(args.get("top_k", 4) or 4))

        if name in ("profile_get", "learning_stats_get"):
            target = user
            if target is None:
                if db is None:
                    return {"error": "缺少数据库会话，无法查询用户"}
                from app.repositories.user_repository import UserRepository

                target = UserRepository(db).get_by_username(str(args.get("username", "")))
                if target is None:
                    return {"error": f"用户不存在: {args.get('username')}"}
            if name == "profile_get":
                return tool_profile_get(db, target)
            return tool_learning_stats_get(db, target)

        return {"error": f"未知工具: {name}"}
    except Exception as exc:  # 工具失败不阻断主链路
        logger.warning("tool %s failed: %s", name, exc)
        return {"error": f"工具执行失败: {exc}"}
