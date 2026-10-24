"""Admin content management API schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AdminResourceListItem(BaseModel):
    id: int
    resource_no: str
    user_id: int
    username: str | None = None
    type_code: str
    type_name: str
    title: str
    topic: str
    difficulty: int
    status: int
    fact_check_status: int
    created_at: datetime
    published_at: datetime | None = None


class AdminResourceListResponse(BaseModel):
    items: list[AdminResourceListItem]
    total: int
    page: int
    page_size: int


class AdminResourceStatusRequest(BaseModel):
    status: int = Field(..., ge=0, le=3, description="0=生成中 1=待审核 2=已发布 3=已拒绝")


class AdminResourceBatchStatusRequest(BaseModel):
    ids: list[int] = Field(..., min_length=1)
    status: int = Field(..., ge=1, le=3)


class AdminProfileDimensionItem(BaseModel):
    id: int
    dimension_code: str
    dimension_name: str
    dimension_desc: str | None = None
    collect_method: str
    weight: float
    sort_order: int
    is_required: int
    status: int
    guide_questions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class AdminProfileDimensionCreateRequest(BaseModel):
    dimension_code: str = Field(..., min_length=2, max_length=32)
    dimension_name: str = Field(..., min_length=1, max_length=64)
    dimension_desc: str | None = None
    collect_method: str = "dialogue"
    weight: float = 1.0
    sort_order: int = 0
    is_required: int = 1
    guide_questions: list[str] = Field(default_factory=list, max_length=10)


class AdminProfileDimensionUpdateRequest(BaseModel):
    dimension_name: str | None = None
    dimension_desc: str | None = None
    collect_method: str | None = None
    weight: float | None = None
    sort_order: int | None = None
    is_required: int | None = None
    status: int | None = None
    guide_questions: list[str] | None = None


class AdminProfileTagItem(BaseModel):
    code: str
    label: str
    category: str = "general"
    status: int = 1


class AdminProfileTagUpsertRequest(BaseModel):
    code: str
    label: str
    category: str = "general"
    status: int = 1


class AdminKnowledgePointItem(BaseModel):
    id: int
    point_code: str
    point_name: str
    domain: str
    difficulty: int
    estimated_min: int
    description: str | None = None
    prerequisite_ids: list[Any] | None = None
    status: int


class AdminKnowledgePointCreateRequest(BaseModel):
    point_code: str
    point_name: str
    domain: str = "machine_learning"
    difficulty: int = 3
    estimated_min: int = 30
    description: str | None = None
    prerequisite_ids: list[int] | None = None


class AdminKnowledgePointUpdateRequest(BaseModel):
    point_name: str | None = None
    domain: str | None = None
    difficulty: int | None = None
    estimated_min: int | None = None
    description: str | None = None
    prerequisite_ids: list[int] | None = None
    status: int | None = None


class AdminPathListItem(BaseModel):
    id: int
    path_no: str
    user_id: int
    username: str | None = None
    title: str
    goal: str
    total_nodes: int
    status: int
    created_at: datetime


class AdminPathDetailResponse(BaseModel):
    id: int
    path_no: str
    user_id: int
    username: str | None = None
    title: str
    goal: str
    total_nodes: int
    status: int
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)


class AdminLectureListItem(BaseModel):
    session_id: int
    session_no: str
    user_id: int
    username: str | None = None
    lecture_id: str
    title: str
    topic: str | None = None
    slide_count: int = 0
    created_at: str | None = None


class AdminImageListItem(BaseModel):
    session_id: int
    session_no: str
    user_id: int
    username: str | None = None
    round_no: str
    title: str
    caption: str | None = None
    created_at: str | None = None


class AdminDocumentListItem(BaseModel):
    doc_id: str
    user_id: int
    username: str | None = None
    session_no: str | None = None
    filename: str
    page_count: int
    audit_status: int
    file_size: int | None = None
    uploaded_at: str | None = None


class AdminDocumentAuditRequest(BaseModel):
    audit_status: int = Field(..., ge=0, le=2, description="0=待审 1=通过 2=驳回")
    reason: str | None = None


class AdminDocumentBatchItem(BaseModel):
    user_id: int
    doc_id: str


class AdminDocumentBatchAuditRequest(BaseModel):
    items: list[AdminDocumentBatchItem] = Field(..., min_length=1, max_length=50)
    audit_status: int = Field(..., ge=0, le=2)
    reason: str | None = None


class AdminDocumentSettingsResponse(BaseModel):
    audit_enabled: bool
    max_file_mb: int
    allowed_extensions: list[str]


class AdminDocumentSettingsRequest(BaseModel):
    audit_enabled: bool | None = None
    max_file_mb: int | None = Field(None, ge=1, le=500)
    allowed_extensions: list[str] | None = None


class AdminDocumentPreviewResponse(BaseModel):
    doc_id: str
    user_id: int
    filename: str
    page_count: int
    pages: list[dict[str, Any]] = Field(default_factory=list)
    full_text: str = ""
    truncated: bool = False


class AdminLecturePreviewResponse(BaseModel):
    session_id: int
    lecture_id: str
    title: str
    topic: str | None = None
    slides: list[dict[str, Any]] = Field(default_factory=list)
    video_url: str | None = None
    recommendations: list[str] = Field(default_factory=list)


class AdminImagePreviewResponse(BaseModel):
    session_id: int
    round_no: str
    title: str
    caption: str | None = None
    mermaid: str | None = None
    image_url: str | None = None


class AdminResourcePreviewResponse(BaseModel):
    id: int
    title: str
    type_code: str
    type_name: str
    status: int
    topic: str
    summary: str | None = None
    preview_type: str
    content: dict[str, Any] = Field(default_factory=dict)
