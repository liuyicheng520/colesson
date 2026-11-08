"""Admin operations — system settings, announcements, feedback."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenException, NotFoundException
from app.models.sys import SysAnnouncement, SysFeedback, SysOperationLog, SysUser
from app.repositories.permission_repository import PermissionRepository
from app.schemas.admin_ops import (
    AnnouncementCreateRequest,
    AnnouncementItem,
    AnnouncementUpdateRequest,
    FeedbackItem,
    FeedbackReplyRequest,
    StudentFeedbackCreateRequest,
    SystemSettingsResponse,
    SystemSettingsUpdateRequest,
)
from app.services.config_service import (
    CONTENT_SAFETY,
    FEATURE_DEEP_MODE,
    FEATURE_IMAGE_GEN,
    FEATURE_VIDEO_LECTURE,
    FEATURE_VOICE_INPUT,
    FEATURE_WEB_SEARCH,
    LLM_DEFAULT_PROVIDER,
    LLM_FALLBACK_PROVIDER,
    PROFILE_MIN_COMPLETENESS,
    RATE_LIMIT_REQUESTS,
    SITE_FOOTER,
    SITE_ICP,
    SITE_LOGO,
    SITE_NAME,
    TUTOR_MAX_TOKENS,
    TUTOR_STREAM_TIMEOUT,
    ConfigService,
)


class AdminOpsService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.perm_repo = PermissionRepository(db)
        self.config = ConfigService(db)

    def _assert_perm(self, operator_id: int, perm_code: str) -> None:
        if perm_code not in self.perm_repo.get_user_permission_codes(operator_id):
            raise ForbiddenException(f"缺少权限: {perm_code}")

    def get_system_settings(self, operator_id: int) -> SystemSettingsResponse:
        self._assert_perm(operator_id, "menu:settings")
        return SystemSettingsResponse(
            llm_default_provider=self.config.get_raw(LLM_DEFAULT_PROVIDER, "deepseek"),
            llm_fallback_provider=self.config.get_raw(LLM_FALLBACK_PROVIDER, "mock"),
            content_safety_enabled=self.config.get_bool(CONTENT_SAFETY, True),
            profile_min_completeness=self.config.get_float(PROFILE_MIN_COMPLETENESS, 0.8),
            rate_limit_requests=self.config.get_int(RATE_LIMIT_REQUESTS, 100),
            tutor_max_tokens=self.config.get_int(TUTOR_MAX_TOKENS, 1200),
            tutor_stream_timeout_sec=self.config.get_int(TUTOR_STREAM_TIMEOUT, 35),
            feature_web_search=self.config.get_bool(FEATURE_WEB_SEARCH, True),
            feature_deep_mode=self.config.get_bool(FEATURE_DEEP_MODE, True),
            feature_image_gen=self.config.get_bool(FEATURE_IMAGE_GEN, True),
            feature_video_lecture=self.config.get_bool(FEATURE_VIDEO_LECTURE, True),
            feature_voice_input=self.config.get_bool(FEATURE_VOICE_INPUT, True),
            site_name=self.config.get_raw(SITE_NAME, "智学体"),
            site_logo_url=self.config.get_raw(SITE_LOGO, ""),
            site_icp_no=self.config.get_raw(SITE_ICP, ""),
            site_footer_text=self.config.get_raw(SITE_FOOTER, ""),
            has_qwen_key=self.config.has_secret("llm.qwen.api_key"),
            has_deepseek_key=self.config.has_secret("llm.deepseek.api_key"),
            has_spark_key=self.config.has_secret("llm.spark.api_key"),
            has_serper_key=self.config.has_secret("llm.serper.api_key"),
        )

    def update_system_settings(self, operator_id: int, req: SystemSettingsUpdateRequest) -> SystemSettingsResponse:
        self._assert_perm(operator_id, "btn:settings:edit")
        mapping: list[tuple[str, str | None, str]] = [
            (LLM_DEFAULT_PROVIDER, req.llm_default_provider, "string"),
            (LLM_FALLBACK_PROVIDER, req.llm_fallback_provider, "string"),
            (PROFILE_MIN_COMPLETENESS, str(req.profile_min_completeness) if req.profile_min_completeness is not None else None, "number"),
            (RATE_LIMIT_REQUESTS, str(req.rate_limit_requests) if req.rate_limit_requests is not None else None, "number"),
            (TUTOR_MAX_TOKENS, str(req.tutor_max_tokens) if req.tutor_max_tokens is not None else None, "number"),
            (TUTOR_STREAM_TIMEOUT, str(req.tutor_stream_timeout_sec) if req.tutor_stream_timeout_sec is not None else None, "number"),
            (SITE_NAME, req.site_name, "string"),
            (SITE_LOGO, req.site_logo_url, "string"),
            (SITE_ICP, req.site_icp_no, "string"),
            (SITE_FOOTER, req.site_footer_text, "string"),
        ]
        for key, val, ctype in mapping:
            if val is not None:
                self.config.set_value(key, val, config_type=ctype)

        bool_map = [
            (CONTENT_SAFETY, req.content_safety_enabled),
            (FEATURE_WEB_SEARCH, req.feature_web_search),
            (FEATURE_DEEP_MODE, req.feature_deep_mode),
            (FEATURE_IMAGE_GEN, req.feature_image_gen),
            (FEATURE_VIDEO_LECTURE, req.feature_video_lecture),
            (FEATURE_VOICE_INPUT, req.feature_voice_input),
        ]
        for key, val in bool_map:
            if val is not None:
                self.config.set_value(key, str(val).lower(), config_type="boolean")

        if req.qwen_api_key:
            self.config.set_secret("llm.qwen.api_key", req.qwen_api_key)
        if req.deepseek_api_key:
            self.config.set_secret("llm.deepseek.api_key", req.deepseek_api_key)
        if req.spark_api_key:
            self.config.set_secret("llm.spark.api_key", req.spark_api_key)
        if req.spark_api_secret:
            self.config.set_secret("llm.spark.api_secret", req.spark_api_secret)
        if req.serper_api_key:
            self.config.set_secret("llm.serper.api_key", req.serper_api_key)

        ConfigService.clear_cache()
        return self.get_system_settings(operator_id)

    def list_announcements(self, operator_id: int) -> list[AnnouncementItem]:
        self._assert_perm(operator_id, "menu:settings")
        rows = self.db.query(SysAnnouncement).order_by(SysAnnouncement.priority.desc(), SysAnnouncement.id.desc()).all()
        return [self._ann_item(r) for r in rows]

    def create_announcement(self, operator_id: int, req: AnnouncementCreateRequest) -> AnnouncementItem:
        self._assert_perm(operator_id, "btn:settings:edit")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        row = SysAnnouncement(
            title=req.title,
            content=req.content,
            status=req.status,
            priority=req.priority,
            published_at=now if req.status == 1 else None,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self._ann_item(row)

    def update_announcement(self, operator_id: int, ann_id: int, req: AnnouncementUpdateRequest) -> AnnouncementItem:
        self._assert_perm(operator_id, "btn:settings:edit")
        row = self.db.query(SysAnnouncement).filter(SysAnnouncement.id == ann_id).first()
        if not row:
            raise NotFoundException(message="公告不存在")
        if req.title is not None:
            row.title = req.title
        if req.content is not None:
            row.content = req.content
        if req.priority is not None:
            row.priority = req.priority
        if req.status is not None:
            row.status = req.status
            if req.status == 1 and not row.published_at:
                row.published_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.commit()
        self.db.refresh(row)
        return self._ann_item(row)

    def delete_announcement(self, operator_id: int, ann_id: int) -> None:
        self._assert_perm(operator_id, "btn:settings:edit")
        row = self.db.query(SysAnnouncement).filter(SysAnnouncement.id == ann_id).first()
        if not row:
            raise NotFoundException(message="公告不存在")
        self.db.delete(row)
        self.db.commit()

    def list_feedback(
        self, operator_id: int, *, status: int | None = None, page: int = 1, page_size: int = 20
    ) -> tuple[list[FeedbackItem], int]:
        self._assert_perm(operator_id, "menu:settings")
        q = self.db.query(SysFeedback)
        if status is not None:
            q = q.filter(SysFeedback.status == status)
        total = q.count()
        rows = q.order_by(SysFeedback.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        user_ids = {r.user_id for r in rows}
        users = {
            u.id: u.username
            for u in self.db.query(SysUser).filter(SysUser.id.in_(user_ids)).all()
        } if user_ids else {}
        items = [
            FeedbackItem(
                id=r.id,
                user_id=r.user_id,
                username=users.get(r.user_id),
                category=r.category,
                title=r.title,
                content=r.content,
                status=r.status,
                admin_reply=r.admin_reply,
                created_at=r.created_at,
            )
            for r in rows
        ]
        return items, total

    def reply_feedback(self, operator_id: int, feedback_id: int, req: FeedbackReplyRequest) -> FeedbackItem:
        self._assert_perm(operator_id, "btn:settings:edit")
        row = self.db.query(SysFeedback).filter(SysFeedback.id == feedback_id).first()
        if not row:
            raise NotFoundException(message="工单不存在")
        row.status = req.status
        if req.admin_reply is not None:
            row.admin_reply = req.admin_reply
        self.db.commit()
        self.db.refresh(row)
        user = self.db.query(SysUser).filter(SysUser.id == row.user_id).first()
        return FeedbackItem(
            id=row.id,
            user_id=row.user_id,
            username=user.username if user else None,
            category=row.category,
            title=row.title,
            content=row.content,
            status=row.status,
            admin_reply=row.admin_reply,
            created_at=row.created_at,
        )

    def submit_feedback(self, user: SysUser, req: StudentFeedbackCreateRequest) -> dict:
        content = req.content
        if req.screenshot_url:
            content = f"{content}\n\n[截图]({req.screenshot_url})"
        row = SysFeedback(
            user_id=user.id,
            category=req.category,
            title=req.title,
            content=content,
            status=0,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return {"id": row.id, "status": row.status}

    def list_my_feedback(self, user_id: int, *, page: int = 1, page_size: int = 20):
        from app.schemas.admin_ops import StudentFeedbackItem

        q = self.db.query(SysFeedback).filter(SysFeedback.user_id == user_id)
        total = q.count()
        rows = (
            q.order_by(SysFeedback.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        items = [
            StudentFeedbackItem(
                id=r.id,
                category=r.category,
                title=r.title,
                content=r.content,
                status=r.status,
                admin_reply=r.admin_reply,
                created_at=r.created_at,
            )
            for r in rows
        ]
        return items, total

    def list_my_login_logs(self, user_id: int, *, limit: int = 20):
        from app.schemas.admin_ops import LoginLogItem

        # 优先按 module 过滤（有索引友好），避免全表 LIKE
        rows = (
            self.db.query(SysOperationLog)
            .filter(
                SysOperationLog.user_id == user_id,
                SysOperationLog.module == "auth",
                SysOperationLog.action == "POST",
            )
            .order_by(SysOperationLog.created_at.desc())
            .limit(limit)
            .all()
        )
        if not rows:
            rows = (
                self.db.query(SysOperationLog)
                .filter(
                    SysOperationLog.user_id == user_id,
                    SysOperationLog.module == "auth",
                )
                .order_by(SysOperationLog.created_at.desc())
                .limit(limit)
                .all()
            )
        return [
            LoginLogItem(
                id=r.id,
                ip_address=r.ip_address,
                user_agent=r.user_agent,
                created_at=r.created_at,
                success=bool(r.status == 1 and (r.response_code or 200) < 400),
            )
            for r in rows
        ]

    def public_announcements(self) -> list[AnnouncementItem]:
        rows = (
            self.db.query(SysAnnouncement)
            .filter(SysAnnouncement.status == 1)
            .order_by(SysAnnouncement.priority.desc(), SysAnnouncement.published_at.desc())
            .limit(5)
            .all()
        )
        return [self._ann_item(r) for r in rows]

    @staticmethod
    def _ann_item(r: SysAnnouncement) -> AnnouncementItem:
        return AnnouncementItem(
            id=r.id,
            title=r.title,
            content=r.content,
            status=r.status,
            priority=r.priority,
            published_at=r.published_at,
            created_at=r.created_at,
        )
