"""Admin ops schemas — analytics, system config, announcements, feedback."""

from datetime import datetime

from pydantic import BaseModel, Field


class AdminOverviewStats(BaseModel):
    total_users: int
    dau_users: int
    total_study_hours: float
    qa_total: int
    multimodal_total: int


class AdminTrendStats(BaseModel):
    days: int
    dates: list[str]
    registrations: list[int]
    qa_counts: list[int]
    lecture_counts: list[int]


class FeatureUsageItem(BaseModel):
    name: str
    value: int


class TopTopicItem(BaseModel):
    topic: str
    count: int


class SystemSettingsResponse(BaseModel):
    llm_default_provider: str
    llm_fallback_provider: str
    content_safety_enabled: bool
    profile_min_completeness: float
    rate_limit_requests: int
    tutor_max_tokens: int
    tutor_stream_timeout_sec: int
    feature_web_search: bool
    feature_deep_mode: bool
    feature_image_gen: bool
    feature_video_lecture: bool
    feature_voice_input: bool
    site_name: str
    site_logo_url: str
    site_icp_no: str
    site_footer_text: str
    has_qwen_key: bool
    has_deepseek_key: bool
    has_spark_key: bool
    has_serper_key: bool


class SystemSettingsUpdateRequest(BaseModel):
    llm_default_provider: str | None = None
    llm_fallback_provider: str | None = None
    content_safety_enabled: bool | None = None
    profile_min_completeness: float | None = None
    rate_limit_requests: int | None = Field(None, ge=10, le=5000)
    tutor_max_tokens: int | None = Field(None, ge=128, le=8192)
    tutor_stream_timeout_sec: int | None = Field(None, ge=10, le=120)
    feature_web_search: bool | None = None
    feature_deep_mode: bool | None = None
    feature_image_gen: bool | None = None
    feature_video_lecture: bool | None = None
    feature_voice_input: bool | None = None
    site_name: str | None = None
    site_logo_url: str | None = None
    site_icp_no: str | None = None
    site_footer_text: str | None = None
    qwen_api_key: str | None = None
    deepseek_api_key: str | None = None
    spark_api_key: str | None = None
    spark_api_secret: str | None = None
    serper_api_key: str | None = None


class AnnouncementItem(BaseModel):
    id: int
    title: str
    content: str
    status: int
    priority: int
    published_at: datetime | None = None
    created_at: datetime


class AnnouncementCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=128)
    content: str = Field(..., min_length=1)
    status: int = Field(1, ge=0, le=1)
    priority: int = 0


class AnnouncementUpdateRequest(BaseModel):
    title: str | None = Field(None, max_length=128)
    content: str | None = None
    status: int | None = Field(None, ge=0, le=1)
    priority: int | None = None


class FeedbackItem(BaseModel):
    id: int
    user_id: int
    username: str | None = None
    category: str
    title: str
    content: str
    status: int
    admin_reply: str | None = None
    created_at: datetime


class FeedbackReplyRequest(BaseModel):
    status: int = Field(..., ge=0, le=2)
    admin_reply: str | None = None


class StudentFeedbackCreateRequest(BaseModel):
    category: str = "general"
    title: str = Field(..., min_length=1, max_length=128)
    content: str = Field(..., min_length=1, max_length=4000)
    screenshot_url: str | None = Field(None, max_length=512)


class StudentFeedbackItem(BaseModel):
    id: int
    category: str
    title: str
    content: str
    status: int
    admin_reply: str | None = None
    created_at: datetime


class LoginLogItem(BaseModel):
    id: int
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime
    success: bool = True


class PublicSystemInfo(BaseModel):
    site_name: str
    site_logo_url: str
    site_icp_no: str
    site_footer_text: str
    features: dict[str, bool]
    announcements: list[AnnouncementItem]
