"""Profile request/response schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class DimensionProgressItem(BaseModel):
    dimension_code: str
    dimension_name: str
    description: str = ""
    status: Literal["pending", "active", "completed"] = "pending"
    confidence: float = 0.0
    fusion_confidence: float = 0.0
    display_score: float = 0.0
    dimension_value: dict[str, Any] | None = None
    source_contributions: list[dict[str, Any]] = Field(default_factory=list)
    updated_at: str | None = None
    questions_answered: int = 0
    questions_total: int = 1


class DimensionValueResponse(BaseModel):
    dimension_code: str
    dimension_name: str
    dimension_value: dict[str, Any]
    confidence: Decimal
    source_type: str
    updated_at: datetime
    display_score: float = 0.0


class ProfileResponse(BaseModel):
    id: int
    user_id: int
    profile_version: int
    completeness: Decimal
    avg_confidence: Decimal
    learning_goal: str | None = None
    status: int
    confirmed_at: datetime | None = None
    dimensions: list[DimensionValueResponse] = Field(default_factory=list)
    dimension_progress: list[DimensionProgressItem] = Field(default_factory=list)
    core_dimension_count: int = 6
    completed_dimension_count: int = 0
    total_question_count: int = 6
    completed_question_count: int = 0
    is_profile_built: bool = False
    created_at: datetime
    updated_at: datetime


class ProfileDimensionUpdateRequest(BaseModel):
    dimension_code: str = Field(..., description="维度编码 D1~D6")
    dimension_value: dict[str, Any] = Field(..., description="维度值JSON")
    confidence: Decimal = Field(Decimal("0.8"), ge=0, le=1, description="置信度")
    source_type: str = Field("manual", description="来源类型")


class DialogueHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class DialogueStartResponse(BaseModel):
    session_no: str
    profile_id: int
    task_no: str
    message: str = Field(description="Agent首条引导语 / 最近一条助手消息")
    messages: list[DialogueHistoryMessage] = Field(
        default_factory=list,
        description="完整对话历史（断点续聊 / 完成后回看）",
    )
    current_dimension_code: str
    current_dimension_name: str
    completeness: Decimal
    dimension_progress: list[DimensionProgressItem] = Field(default_factory=list)
    completed_question_count: int = 0
    total_question_count: int = 6
    current_question_index: int = 1


class DialogueMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000, description="用户消息")


class DialogueMessageResponse(BaseModel):
    session_no: str
    round_no: int
    assistant_message: str
    extracted_dims: dict[str, Any] | None = None
    updated_dimensions: list[str] = Field(default_factory=list)
    completeness: Decimal
    is_completed: bool = False
    current_dimension_code: str | None = None
    current_dimension_name: str | None = None
    dimension_progress: list[DimensionProgressItem] = Field(default_factory=list)
    completed_count: int = 0
    total_count: int = 6
    completed_question_count: int = 0
    total_question_count: int = 6
    current_question_index: int = 1


class DialogueSwitchDimensionRequest(BaseModel):
    dimension_code: str = Field(..., description="目标维度 D1~D6")


class QuestionnaireOption(BaseModel):
    id: str
    label: str


class QuestionnaireItemResponse(BaseModel):
    dimension_code: str
    question: str
    options: list[QuestionnaireOption]


class QuestionnaireAnswerItem(BaseModel):
    dimension_code: str
    option_id: str


class QuestionnaireSubmitRequest(BaseModel):
    answers: list[QuestionnaireAnswerItem] = Field(..., min_length=6, max_length=6)


class AssessmentQuestionResponse(BaseModel):
    id: str
    topic: str
    stem: str
    options: list[str]
    difficulty: float
    discrimination: float


class AssessmentAnswerItem(BaseModel):
    question_id: str
    selected_index: int = Field(..., ge=0, le=3)


class AssessmentSubmitRequest(BaseModel):
    answers: list[AssessmentAnswerItem]
    theta: float | None = Field(None, description="前端 IRT 计算的能力值")
    standard_error: float | None = None


class BehaviorAvailabilityResponse(BaseModel):
    has_data: bool
    resources_learned: int = 0


class BehaviorGenerateResponse(BaseModel):
    profile: ProfileResponse
    features_used: dict[str, Any] = Field(default_factory=dict)
    updated_dimensions: list[str] = Field(default_factory=list)


class BehaviorRefreshResponse(BaseModel):
    refreshed: bool
    reason: str | None = None
    updated_dimensions: list[str] = Field(default_factory=list)


class ProfileModesMetaResponse(BaseModel):
    behavior_available: bool
    has_profile_data: bool
    preferred_mode: str | None = None
