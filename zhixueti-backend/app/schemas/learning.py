"""Learning statistics schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BehaviorEventItem(BaseModel):
    event_type: str = Field(..., description="事件类型")
    event_target: str | None = Field(None, description="目标类型")
    target_id: int | None = Field(None, description="目标ID")
    event_data: dict[str, Any] | None = Field(None, description="事件详情")
    page_url: str | None = None
    client_ts: datetime | None = None


class BehaviorBatchRequest(BaseModel):
    session_id: int | None = Field(None, description="学习会话ID")
    events: list[BehaviorEventItem] = Field(..., min_length=1, max_length=50)


class LearningSessionStartRequest(BaseModel):
    path_id: int | None = None
    node_id: int | None = None
    session_type: str = Field("study", description="study/tutor/assessment/profile")
    device_type: str | None = None


class TrendPoint(BaseModel):
    date: str
    minutes: float


class MasteryItem(BaseModel):
    name: str
    value: float


class RecentRecord(BaseModel):
    resource_name: str
    study_time: str
    duration_minutes: float
    node_name: str | None = None


class LearningStatsResponse(BaseModel):
    total_study_hours: float = 0
    resources_learned: int = 0
    knowledge_points_completed: int = 0
    avg_accuracy: float | None = None  # 无真实作答数据时为 None（前端显示暂无）
    study_hours_change_pct: float | None = None
    resources_change_pct: float | None = None
    knowledge_change_pct: float | None = None
    accuracy_change_pct: float | None = None
    trend_7d: list[TrendPoint] = Field(default_factory=list)
    trend_30d: list[TrendPoint] = Field(default_factory=list)
    mastery_items: list[MasteryItem] = Field(default_factory=list)
    path_progress_rate: float = 0
    path_completed_nodes: int = 0
    path_total_nodes: int = 0
    path_title: str | None = None
    recent_records: list[RecentRecord] = Field(default_factory=list)
    has_data: bool = False
