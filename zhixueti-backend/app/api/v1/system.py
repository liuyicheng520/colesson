"""Public system API — site info, feature flags, announcements, student feedback."""

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, UploadFile

from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.core.exceptions import ValidationException
from app.core.response import ApiResponse
from app.schemas.admin_ops import (
    LoginLogItem,
    PublicSystemInfo,
    StudentFeedbackCreateRequest,
    StudentFeedbackItem,
)
from app.services.admin_ops_service import AdminOpsService
from app.services.config_service import ConfigService

router = APIRouter()


@router.get("/public", summary="站点公开信息", response_model=ApiResponse[PublicSystemInfo])
def public_info(db: DbSession) -> ApiResponse[PublicSystemInfo]:
    cfg = ConfigService(db)
    site = cfg.site_info()
    # 暴露 AI 是否处于 Mock 模式，供前端展示「演示内容」提示
    features = {**cfg.feature_flags(), "ai_mock_mode": get_settings().llm_default_provider == "mock"}
    return ApiResponse.success(
        PublicSystemInfo(
            site_name=site["site_name"],
            site_logo_url=site["site_logo_url"],
            site_icp_no=site["site_icp_no"],
            site_footer_text=site["site_footer_text"],
            features=features,
            announcements=AdminOpsService(db).public_announcements(),
        )
    )


@router.post("/feedback", summary="提交问题反馈")
def submit_feedback(
    req: StudentFeedbackCreateRequest, current_user: CurrentUser, db: DbSession
) -> ApiResponse[dict]:
    data = AdminOpsService(db).submit_feedback(current_user, req)
    return ApiResponse.success(data)


@router.get("/feedback/mine", summary="我的反馈记录")
def list_my_feedback(
    current_user: CurrentUser,
    db: DbSession,
    page: int = 1,
    page_size: int = 20,
) -> ApiResponse[dict]:
    items, total = AdminOpsService(db).list_my_feedback(
        current_user.id, page=page, page_size=min(page_size, 50)
    )
    return ApiResponse.success(
        {
            "items": [i.model_dump() if hasattr(i, "model_dump") else i for i in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.get("/login-logs", summary="我的登录日志", response_model=ApiResponse[list[LoginLogItem]])
def list_login_logs(current_user: CurrentUser, db: DbSession) -> ApiResponse[list[LoginLogItem]]:
    items = AdminOpsService(db).list_my_login_logs(current_user.id)
    return ApiResponse.success(items)


@router.post("/feedback/screenshot", summary="上传反馈截图")
async def upload_feedback_screenshot(
    current_user: CurrentUser,
    file: UploadFile = File(...),
) -> ApiResponse[dict]:
    allowed = {"image/jpeg", "image/png", "image/jpg", "image/webp"}
    if file.content_type not in allowed and not (file.filename or "").lower().endswith(
        (".jpg", ".jpeg", ".png", ".webp")
    ):
        raise ValidationException(message="仅支持 JPG/PNG/WebP 截图")
    data = await file.read()
    if len(data) > 3 * 1024 * 1024:
        raise ValidationException(message="截图不能超过 3MB")
    # 魔数级校验：必须能作为图片解码并重编码，杜绝伪装成图片的任意文件
    try:
        from io import BytesIO

        from PIL import Image

        with Image.open(BytesIO(data)) as img:
            img.verify()
        with Image.open(BytesIO(data)) as img2:
            fmt = (img2.format or "").lower()
            img2.convert("RGB").save(buf := BytesIO(), format="PNG")
    except Exception:
        raise ValidationException(message="文件不是有效的 JPG/PNG/WebP 图片")
    safe_ext = {"jpeg": ".jpg", "jpg": ".jpg", "png": ".png", "webp": ".webp"}.get(fmt)
    if not safe_ext:
        raise ValidationException(message="仅支持 JPG/PNG/WebP 截图")
    upload_root = Path(get_settings().upload_dir)
    dest_dir = upload_root / "feedback"
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = f"{current_user.id}_{uuid4().hex[:12]}{safe_ext}"
    (dest_dir / name).write_bytes(data)
    return ApiResponse.success({"url": f"/uploads/feedback/{name}"})
