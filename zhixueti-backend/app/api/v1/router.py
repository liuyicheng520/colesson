"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1 import admin, admin_audit, admin_content, admin_ops, agents, auth, behavior, kb, llm, mcp, paths, profiles, resources, security, system, tutor, users

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(users.router, prefix="/users", tags=["用户中心"])
api_router.include_router(admin.router, prefix="/admin", tags=["管理端"])
api_router.include_router(admin_content.router, prefix="/admin", tags=["管理端-内容"])
api_router.include_router(admin_ops.router, prefix="/admin", tags=["管理端-运营"])
api_router.include_router(admin_audit.router, prefix="/admin", tags=["管理端-审计"])
api_router.include_router(system.router, prefix="/system", tags=["系统公开"])
api_router.include_router(security.router, prefix="/security", tags=["内容安全"])
api_router.include_router(profiles.router, prefix="/profiles", tags=["用户画像"])
api_router.include_router(behavior.router, prefix="/behavior", tags=["学习行为"])
api_router.include_router(resources.router, prefix="/resources", tags=["资源中心"])
api_router.include_router(paths.router, prefix="/paths", tags=["学习路径"])
api_router.include_router(tutor.router, prefix="/tutor", tags=["智能答疑"])
api_router.include_router(agents.router, prefix="/agents", tags=["多智能体"])
api_router.include_router(kb.router, prefix="/kb", tags=["向量知识库"])
api_router.include_router(llm.router, prefix="/llm", tags=["大模型网关"])
api_router.include_router(mcp.router, prefix="/mcp", tags=["MCP 工具服务"])
