"""Learning path schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class PathPlanRequest(BaseModel):
    goal: str = Field(..., min_length=1, max_length=512, description="学习目标")
    domain: str = Field("machine_learning", max_length=64, description="学习领域")
    title: str | None = Field(None, max_length=256, description="路径标题")
    ignore_profile: bool = Field(False, description="忽略画像，生成通用标准路径")
    supplement: str | None = Field(None, max_length=500, description="路径定制补充需求")
    adaptive: bool = Field(False, description="是否为基于学情的自适应重规划")


class NodeResourceItem(BaseModel):
    resource_id: int
    title: str
    type_code: str
    type_name: str
    resource_role: str = "primary"
    is_learned: bool = False


class PathNodeResponse(BaseModel):
    id: int
    node_code: str
    node_name: str
    node_type: str
    phase: str = Field("", description="intro/intermediate/advanced")
    phase_name: str = Field("", description="入门/进阶/提升")
    description: str | None = None
    sort_order: int
    difficulty: int
    estimated_min: int
    status: int = Field(0, description="用户节点进度状态")
    mastery_score: Decimal | None = None
    resources: list[int] = Field(default_factory=list)
    resource_items: list[NodeResourceItem] = Field(default_factory=list)
    expected_resource_types: list[str] = Field(default_factory=list)
    is_weak: bool = False
    is_adaptive: bool = False
    prereq_names: list[str] = Field(default_factory=list)
    learned_resource_count: int = 0
    total_resource_count: int = 0


class PathPhaseResponse(BaseModel):
    phase: str
    phase_name: str
    description: str = ""
    node_ids: list[int] = Field(default_factory=list)
    completed_count: int = 0
    total_count: int = 0


class PathEdgeResponse(BaseModel):
    from_node_id: int
    to_node_id: int
    edge_type: str


class PathResponse(BaseModel):
    id: int
    path_no: str
    title: str
    goal: str
    path_version: int
    total_nodes: int
    estimated_hours: Decimal
    status: int
    progress_rate: Decimal = Decimal("0")
    path_mode: Literal["profile", "standard"] = "profile"
    nodes: list[PathNodeResponse] = Field(default_factory=list)
    phases: list[PathPhaseResponse] = Field(default_factory=list)
    edges: list[PathEdgeResponse] = Field(default_factory=list)
    profile_snapshot: dict[str, Any] | None = None
    weak_focus: list[str] = Field(default_factory=list)
    adaptive_node_count: int = 0
    created_at: datetime


class PathSummaryResponse(BaseModel):
    """路径列表轻量摘要，避免一次加载全部节点资源。"""

    id: int
    path_no: str
    title: str
    goal: str
    path_version: int
    total_nodes: int
    estimated_hours: Decimal
    status: int
    progress_rate: Decimal = Decimal("0")
    path_mode: Literal["profile", "standard"] = "profile"
    weak_focus: list[str] = Field(default_factory=list)
    adaptive_node_count: int = 0
    created_at: datetime
    nodes: list[PathNodeResponse] = Field(default_factory=list)  # 列表接口恒为空，兼容前端类型


class NodeProgressUpdateRequest(BaseModel):
    status: int = Field(..., ge=0, le=4, description="0=锁定 1=可学习 2=学习中 3=已完成")
    study_duration_sec: int | None = Field(None, ge=0)
    mastery_score: Decimal | None = Field(None, ge=0, le=1)
    resource_id: int | None = Field(None, description="本次完成学习的资源ID（单资源进度）")
    mark_resource_done: bool = Field(False, description="是否将 resource_id 标记为已学习")


class NodeResourcePushRequest(BaseModel):
    resource_ids: list[int] = Field(..., min_length=1, description="要关联的资源ID列表")
    resource_role: str = Field("primary", description="primary/supplementary/remedial")


class PathReplanRequest(BaseModel):
    """预留：对接学习效果评估模块后触发路径重规划。"""
    trigger_type: Literal["assessment", "manual", "behavior", "tutor"] = "manual"
    trigger_ref_id: int | None = None
    reason: str | None = Field(None, max_length=512)


class PathReplanResponse(BaseModel):
    path_id: int
    old_version: int
    new_version: int
    status: str = "pending"
    message: str
