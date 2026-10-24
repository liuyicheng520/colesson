"""FastAPI application entry point."""

import json
import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from jwt import PyJWTError as JWTError
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.error_codes import ERROR_MESSAGES, ErrorCode
from app.core.exceptions import AppException
from app.core.logging import setup_logging
from app.core.response import ApiResponse
from app.core.security import decode_token
from app.middleware.operation_log import OperationLogMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from sqlalchemy.exc import OperationalError, SQLAlchemyError

settings = get_settings()
setup_logging(settings.debug)
logger = logging.getLogger(__name__)


def _resolve_frontend_dist() -> Path | None:
    raw = (settings.frontend_dist or "").strip()
    if raw:
        p = Path(raw)
        if not p.is_absolute():
            p = (Path(__file__).resolve().parents[1] / p).resolve()
        return p if p.is_dir() else None
    p = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    return p if p.is_dir() else None


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="智学体 - 个性化学习多智能体系统 API",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(OperationLogMiddleware)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    request.state.error_message = exc.message
    from app.utils.exception_logger import log_exception_from_request

    if exc.http_status >= 500:
        log_exception_from_request(request, exc, error_code=int(exc.code))
    body = ApiResponse.fail(code=int(exc.code), message=exc.message, data=exc.detail)
    return JSONResponse(status_code=exc.http_status, content=body.model_dump(mode="json"))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request.state.error_message = ERROR_MESSAGES[ErrorCode.VALIDATION_ERROR]
    body = ApiResponse.fail(
        code=ErrorCode.VALIDATION_ERROR,
        message=ERROR_MESSAGES[ErrorCode.VALIDATION_ERROR],
        data=exc.errors(),
    )
    return JSONResponse(status_code=422, content=body.model_dump(mode="json"))


@app.exception_handler(OperationalError)
async def db_operational_error_handler(request: Request, exc: OperationalError) -> JSONResponse:
    logger.exception("Database connection error: %s", exc)
    request.state.error_message = "数据库连接失败"
    from app.utils.exception_logger import log_exception_from_request

    log_exception_from_request(request, exc, error_code=ErrorCode.DATABASE_ERROR)
    msg = "数据库连接失败，请检查 backend/.env 中的数据库配置，或设置 USE_SQLITE=true 使用本地 SQLite"
    body = ApiResponse.fail(code=ErrorCode.DATABASE_ERROR, message=msg)
    return JSONResponse(status_code=503, content=body.model_dump(mode="json"))


@app.exception_handler(SQLAlchemyError)
async def db_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.exception("Database error: %s", exc)
    request.state.error_message = ERROR_MESSAGES[ErrorCode.DATABASE_ERROR]
    from app.utils.exception_logger import log_exception_from_request

    log_exception_from_request(request, exc, error_code=ErrorCode.DATABASE_ERROR)
    body = ApiResponse.fail(code=ErrorCode.DATABASE_ERROR, message=ERROR_MESSAGES[ErrorCode.DATABASE_ERROR])
    return JSONResponse(status_code=503, content=body.model_dump(mode="json"))


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception: %s", exc)
    request.state.error_message = ERROR_MESSAGES[ErrorCode.INTERNAL_ERROR]
    from app.utils.exception_logger import log_exception_from_request

    log_exception_from_request(request, exc, error_code=ErrorCode.INTERNAL_ERROR)
    body = ApiResponse.fail(code=ErrorCode.INTERNAL_ERROR, message=ERROR_MESSAGES[ErrorCode.INTERNAL_ERROR])
    return JSONResponse(status_code=500, content=json.loads(body.model_dump_json()))


@app.on_event("startup")
def on_startup() -> None:
    # 安全护栏：禁止使用源码内置的默认 JWT 密钥上线（可离线伪造任意用户 token）
    _default_jwt = "change-me-in-production-use-long-random-string"
    if settings.jwt_secret_key == _default_jwt:
        raise RuntimeError(
            "拒绝启动：JWT_SECRET_KEY 仍为源码默认值。请在 .env 中配置随机长密钥后再启动。"
        )
    if settings.serve_frontend:
        logger.warning("serve_frontend 已开启：SPA 由本服务直接托管，请确认 spa fallback 的路径校验需求")
    if settings.use_sqlite:
        from app.db.init_db import init_database

        init_database()
        logger.info("SQLite dev database ready: %s", settings.sqlite_path)


@app.middleware("http")
async def attach_user_id(request: Request, call_next):
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        try:
            payload = decode_token(auth.removeprefix("Bearer ").strip())
            if payload.get("type") == "access" and payload.get("sub"):
                request.state.user_id = int(payload["sub"])
        except (JWTError, ValueError, TypeError):
            pass
    response = await call_next(request)
    return response


@app.get("/", tags=["系统"], include_in_schema=False)
def root():
    """浏览器直接打开 API 端口：托管前端时回首页，否则给出引导页。"""
    if settings.serve_frontend:
        dist = _resolve_frontend_dist()
        index = dist / "index.html" if dist else None
        if index and index.is_file():
            return FileResponse(index)
    frontend_url = settings.cors_origin_list[0] if settings.cors_origin_list else "http://localhost:3000"
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{settings.app_name}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 640px; margin: 48px auto; padding: 0 20px; line-height: 1.6; color: #1f2937; }}
    h1 {{ font-size: 1.5rem; }}
    a {{ color: #2563eb; }}
    code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 4px; }}
    .ok {{ color: #059669; }}
  </style>
</head>
<body>
  <h1>{settings.app_name} — 后端服务</h1>
  <p class="ok">✓ 服务运行正常（版本 {settings.app_version}）</p>
  <p>你当前访问的是 <strong>API 端口</strong>，返回 JSON 是正常现象，不是网页应用。</p>
  <p>请在浏览器打开前端地址使用系统：</p>
  <p><a href="{frontend_url}">{frontend_url}</a>（登录页：<a href="{frontend_url}/login">{frontend_url}/login</a>）</p>
  <p>接口文档：<a href="/docs">/docs</a> · 健康检查：<a href="/health">/health</a></p>
</body>
</html>"""
    return HTMLResponse(content=html)


@app.get("/health", tags=["系统"])
def health_check() -> ApiResponse[dict]:
    return ApiResponse.success({"status": "ok", "version": settings.app_version})


app.include_router(api_router, prefix=settings.api_prefix)

# 头像等静态资源
upload_path = Path(settings.upload_dir)
upload_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(upload_path)), name="uploads")


# 可执行文件模式：同端口托管 SPA，前后端同域，避免代理卡顿/404
_frontend_dist = _resolve_frontend_dist() if settings.serve_frontend else None
if _frontend_dist is not None:
    assets_dir = _frontend_dist / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        base = _frontend_dist.resolve()
        candidate = (base / full_path).resolve()
        # 防目录穿越：仅返回解析后仍位于前端目录内的文件
        if full_path and candidate.is_file() and str(candidate).startswith(str(base) + os.sep):
            return FileResponse(candidate)
        return FileResponse(base / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        reload_excludes=[
            "logs",
            "logs/*",
            "data",
            "data/*",
            "*.log",
            "*.db",
            "*.db-journal",
        ],
    )
