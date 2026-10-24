"""Tutor request/response schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class TutorSessionCreateRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=256)
    tutor_mode: Literal["socratic", "hint", "debug", "encourage"] = "socratic"
    path_id: int | None = None
    node_id: int | None = None
    resource_id: int | None = None
    question_id: int | None = None
    profile_adapt_enabled: bool = Field(True, description="是否启用用户画像适配")
    answer_detail: Literal["brief", "normal", "detailed"] = "normal"
    show_steps: bool = True
    deep_mode: bool = Field(False, description="深度模式：原理拆解+案例+易错点")
    web_search_enabled: bool = Field(False, description="是否启用联网搜索")
    document_ids: list[str] = Field(default_factory=list, description="关联文档 ID 列表")


class KnowledgePointItem(BaseModel):
    point_code: str
    point_name: str
    domain: str
    difficulty: int


class RelatedResourceItem(BaseModel):
    resource_id: int
    title: str
    type_code: str
    type_name: str
    topic: str


class WebSearchSource(BaseModel):
    title: str
    url: str = ""
    snippet: str = ""


class DocCitation(BaseModel):
    doc_id: str
    filename: str
    page: int = 1
    snippet: str = ""


class TutorMessageMeta(BaseModel):
    knowledge_points: list[KnowledgePointItem] = Field(default_factory=list)
    related_resources: list[RelatedResourceItem] = Field(default_factory=list)
    message_type: str = "text"
    strategy_used: str | None = None
    hint_level: int = 0
    is_exercise: bool = False
    web_sources: list[WebSearchSource] = Field(default_factory=list)
    doc_citations: list[DocCitation] = Field(default_factory=list)
    slides: list[dict[str, Any]] = Field(default_factory=list)
    multimodal: dict[str, Any] | None = None
    disclaimer: str | None = None
    web_search_timeout: bool = False


class TutorMessageItem(BaseModel):
    id: int
    round_no: int
    role: str
    content: str
    message_type: str = "text"
    strategy_used: str | None = None
    meta: TutorMessageMeta | None = None
    created_at: datetime


class TutorSessionResponse(BaseModel):
    session_no: str
    topic: str
    tutor_mode: str
    zpd_level: int
    status: int
    total_rounds: int
    profile_summary: str = ""
    messages: list[TutorMessageItem] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    profile_adapt_enabled: bool = True
    answer_detail: str = "normal"
    show_steps: bool = True
    deep_mode: bool = False
    web_search_enabled: bool = False
    document_ids: list[str] = Field(default_factory=list)


class TutorMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=8000)
    request_full_answer: bool = Field(False, description="用户追问要求完整解析")
    retry_assistant: bool = Field(False, description="重试生成助手回复，不重复插入用户消息")
    web_search_enabled: bool | None = Field(None, description="本次消息是否联网，None 用会话默认")
    deep_mode: bool | None = Field(None, description="本次消息是否深度模式，None 用会话默认")
    force_lecture: bool = Field(False, description="强制走讲解大纲流程")
    confirmed_outline: list[dict[str, Any]] | None = Field(None, description="用户确认后的大纲")


class TutorMessageResponse(BaseModel):
    session_no: str
    round_no: int
    assistant_message: str
    meta: TutorMessageMeta


class TutorDocumentUploadResponse(BaseModel):
    doc_id: str
    filename: str
    page_count: int
    truncated: bool = False
    preview: str = ""


class TutorDocumentItem(BaseModel):
    doc_id: str
    filename: str
    page_count: int
    preview: str = ""


class TutorOutlineConfirmRequest(BaseModel):
    outline: list[dict[str, Any]] = Field(..., min_length=1)


class TutorMultimodalRequest(BaseModel):
    action: Literal["image", "video", "tts"]
    prompt: str = Field(..., min_length=1, max_length=2000)
    source_text: str | None = Field(None, description="TTS 源文本")


class TutorMultimodalResponse(BaseModel):
    action: str
    payload: dict[str, Any]


class TutorBindDocumentsRequest(BaseModel):
    document_ids: list[str] = Field(default_factory=list)


class TutorSessionSettingsRequest(BaseModel):
    """会话运行时设置 — 深度/联网等可实时切换。"""
    document_ids: list[str] | None = None
    deep_mode: bool | None = None
    web_search_enabled: bool | None = None
    answer_detail: Literal["brief", "normal", "detailed"] | None = None
    show_steps: bool | None = None
    profile_adapt_enabled: bool | None = None
    tutor_mode: Literal["socratic", "hint", "debug", "encourage"] | None = None


class TutorLectureGenerateRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=500)
    source_text: str | None = Field(None, description="可选：基于某条 AI 回答生成")


class TutorLectureSideAskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    slide_index: int = Field(0, ge=0)
    history: list[dict[str, Any]] = Field(default_factory=list)


class TutorLectureQuizSubmitRequest(BaseModel):
    slide_index: int = Field(..., ge=0)
    answers: list[str] = Field(..., min_length=1)


class TutorLectureSummary(BaseModel):
    topic: str
    knowledge_point_count: int = 0
    quiz_count: int = 0
    correct_count: int = 0
    total_quizzes: int = 0
    accuracy: float = 0.0
    mastery: str = "待评估"
    recommendations: list[str] = Field(default_factory=list)
