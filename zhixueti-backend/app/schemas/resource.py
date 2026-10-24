"""Resource request/response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ResourceGenerateRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=128, description="生成主题")
    goal: str | None = Field(None, max_length=512, description="学习目标")
    resource_types: list[str] = Field(
        default=["document", "question", "mindmap", "reading", "code", "video"],
        description="资源类型: document/question/mindmap/reading/code/video",
    )
    difficulty: int = Field(3, ge=1, le=5, description="难度等级")
    node_id: int | None = Field(None, description="关联路径节点ID")
    # 画像 + 单次自定义双驱动
    ignore_profile: bool = Field(False, description="本次忽略画像，完全自定义")
    supplement: str | None = Field(None, max_length=500, description="本次生成补充需求")
    use_scene: str | None = Field(
        None,
        max_length=32,
        description="使用场景: 课前预习/课堂巩固/期末复习/课程实验/竞赛备考",
    )
    content_focus: list[str] = Field(
        default_factory=list,
        description="内容侧重: 理论概念/实战演练/项目案例/应试习题/前沿新技术",
    )
    content_length: str | None = Field(
        None,
        max_length=32,
        description="内容篇幅: 精简版/标准课堂版/深度拓展版",
    )
    special_requirements: str | None = Field(None, max_length=1000, description="特殊要求")


class ResourceResponse(BaseModel):
    id: int
    resource_no: str
    type_code: str
    type_name: str
    title: str
    summary: str | None = None
    topic: str
    difficulty: int
    status: int
    audit_status: int
    fact_check_status: int
    citation_count: int
    agent_task_id: int | None = None
    created_at: datetime
    published_at: datetime | None = None
    detail: dict[str, Any] | None = None
    author_name: str | None = Field(None, description="作者昵称（广场公开资源）")

    model_config = {"from_attributes": True}


class ResourceListQuery(BaseModel):
    type_code: str | None = None
    topic: str | None = None
    status: int | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class AnimationRenderRequest(BaseModel):
    resource_id: int = Field(..., description="视频/动画资源ID")
    provider: str = Field("remotion", description="渲染引擎: remotion/spark_video/canvas_2d")
    quality: str = Field("720p", description="输出质量")
