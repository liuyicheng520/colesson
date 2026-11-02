"""Runtime system configuration backed by sys_config table."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.config_repository import ConfigRepository

# Keys used across admin + student flows
DOCUMENT_AUDIT_ENABLED = "document.audit_enabled"
DOCUMENT_MAX_FILE_MB = "document.max_file_mb"
DOCUMENT_ALLOWED_EXTENSIONS = "document.allowed_extensions"
PROFILE_TAG_LIBRARY = "profile.tag_library"

# Phase 3 — runtime system settings
LLM_DEFAULT_PROVIDER = "llm.default_provider"
LLM_FALLBACK_PROVIDER = "llm.fallback_provider"
CONTENT_SAFETY = "feature.content_safety_enabled"
PROFILE_MIN_COMPLETENESS = "profile.min_completeness"
RATE_LIMIT_REQUESTS = "rate_limit.requests"
TUTOR_MAX_TOKENS = "tutor.max_tokens"
TUTOR_STREAM_TIMEOUT = "tutor.stream_timeout_sec"
FEATURE_WEB_SEARCH = "feature.web_search_enabled"
FEATURE_DEEP_MODE = "feature.deep_mode_enabled"
FEATURE_IMAGE_GEN = "feature.image_gen_enabled"
FEATURE_VIDEO_LECTURE = "feature.video_lecture_enabled"
FEATURE_VOICE_INPUT = "feature.voice_input_enabled"
SITE_NAME = "site.name"
SITE_LOGO = "site.logo_url"
SITE_ICP = "site.icp_no"
SITE_FOOTER = "site.footer_text"

SECRET_KEYS = {
    "llm.qwen.api_key",
    "llm.deepseek.api_key",
    "llm.spark.api_key",
    "llm.spark.api_secret",
    "llm.serper.api_key",
}

DEFAULT_CONFIGS: list[tuple[str, str, str, str]] = [
    (DOCUMENT_AUDIT_ENABLED, "false", "boolean", "用户上传文档是否需审核后用于问答"),
    (DOCUMENT_MAX_FILE_MB, "100", "number", "单文件上传大小上限(MB)"),
    (DOCUMENT_ALLOWED_EXTENSIONS, '[".pdf",".docx",".doc",".pptx",".ppt"]', "json", "允许上传的文档扩展名"),
    (PROFILE_TAG_LIBRARY, "[]", "json", "画像标签库"),
    (LLM_DEFAULT_PROVIDER, "deepseek", "string", "默认LLM提供商"),
    (LLM_FALLBACK_PROVIDER, "mock", "string", "降级LLM提供商"),
    (PROFILE_MIN_COMPLETENESS, "0.80", "number", "画像最低完整度阈值"),
    (CONTENT_SAFETY, "true", "boolean", "启用内容安全审核"),
    (RATE_LIMIT_REQUESTS, "100", "number", "接口限流(次/分钟)"),
    (TUTOR_MAX_TOKENS, "1200", "number", "单轮对话最大token数"),
    (TUTOR_STREAM_TIMEOUT, "35", "number", "流式响应超时(秒)"),
    (FEATURE_WEB_SEARCH, "true", "boolean", "联网搜索功能开关"),
    (FEATURE_DEEP_MODE, "true", "boolean", "深度模式功能开关"),
    (FEATURE_IMAGE_GEN, "true", "boolean", "图像生成功能开关"),
    (FEATURE_VIDEO_LECTURE, "true", "boolean", "视频讲解功能开关"),
    (FEATURE_VOICE_INPUT, "true", "boolean", "语音输入功能开关"),
    (SITE_NAME, "智学体", "string", "站点名称"),
    (SITE_LOGO, "", "string", "站点Logo URL"),
    (SITE_ICP, "", "string", "备案号"),
    (SITE_FOOTER, "© 智学体智能教学系统", "string", "底部文案"),
]


class ConfigService:
    _cache: dict[str, str] = {}

    def __init__(self, db: Session) -> None:
        self.repo = ConfigRepository(db)
        self.db = db

    def seed_defaults(self) -> None:
        for key, value, ctype, desc in DEFAULT_CONFIGS:
            if not self.repo.get(key):
                self.repo.upsert(key, value, config_type=ctype, description=desc)

    def get_raw(self, key: str, default: str = "") -> str:
        if key in self._cache:
            return self._cache[key]
        row = self.repo.get(key)
        val = row.config_value if row else default
        self._cache[key] = val
        return val

    def get_bool(self, key: str, default: bool = False) -> bool:
        raw = self.get_raw(key, str(default).lower())
        return raw.lower() in ("1", "true", "yes", "on")

    def get_int(self, key: str, default: int = 0) -> int:
        try:
            return int(self.get_raw(key, str(default)))
        except ValueError:
            return default

    def get_json(self, key: str, default: Any = None) -> Any:
        raw = self.get_raw(key, "")
        if not raw:
            return default if default is not None else []
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return default if default is not None else []

    def set_value(self, key: str, value: str, *, config_type: str = "string", is_encrypted: bool = False) -> None:
        self.repo.upsert(key, value, config_type=config_type, is_encrypted=is_encrypted)
        self._cache[key] = value

    def set_secret(self, key: str, plain: str) -> None:
        from app.utils.secret_vault import encrypt_secret

        if not plain or plain == "******":
            return
        enc = encrypt_secret(plain)
        self.repo.upsert(key, enc, config_type="secret", is_encrypted=True)
        self._cache[key] = enc

    def get_secret(self, key: str) -> str:
        from app.utils.secret_vault import decrypt_secret

        raw = self.get_raw(key, "")
        if not raw:
            return ""
        row = self.repo.get(key)
        if row and row.is_encrypted:
            return decrypt_secret(raw)
        return raw

    def has_secret(self, key: str) -> bool:
        row = self.repo.get(key)
        return bool(row and row.config_value)

    def get_float(self, key: str, default: float = 0.0) -> float:
        try:
            return float(self.get_raw(key, str(default)))
        except ValueError:
            return default

    def feature_flags(self) -> dict[str, bool]:
        return {
            "web_search": self.get_bool(FEATURE_WEB_SEARCH, True),
            "deep_mode": self.get_bool(FEATURE_DEEP_MODE, True),
            "image_gen": self.get_bool(FEATURE_IMAGE_GEN, True),
            "video_lecture": self.get_bool(FEATURE_VIDEO_LECTURE, True),
            "voice_input": self.get_bool(FEATURE_VOICE_INPUT, True),
        }

    def site_info(self) -> dict[str, str]:
        return {
            "site_name": self.get_raw(SITE_NAME, "智学体"),
            "site_logo_url": self.get_raw(SITE_LOGO, ""),
            "site_icp_no": self.get_raw(SITE_ICP, ""),
            "site_footer_text": self.get_raw(SITE_FOOTER, ""),
        }

    def list_public_configs(self) -> list[dict[str, Any]]:
        rows = self.repo.list_all()
        return [
            {
                "config_key": r.config_key,
                "config_value": r.config_value if not r.is_encrypted else "******",
                "config_type": r.config_type,
                "description": r.description,
                "is_encrypted": bool(r.is_encrypted),
            }
            for r in rows
        ]

    def document_audit_enabled(self) -> bool:
        return self.get_bool(DOCUMENT_AUDIT_ENABLED, False)

    def document_max_bytes(self) -> int:
        return self.get_int(DOCUMENT_MAX_FILE_MB, 100) * 1024 * 1024

    def document_allowed_extensions(self) -> set[str]:
        ext = self.get_json(DOCUMENT_ALLOWED_EXTENSIONS, [".pdf", ".docx", ".doc", ".pptx", ".ppt"])
        return {str(e).lower() for e in ext}

    @classmethod
    def clear_cache(cls) -> None:
        cls._cache.clear()
