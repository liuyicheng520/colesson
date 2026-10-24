"""Agent and LLM schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentDefinitionResponse(BaseModel):
    id: int
    agent_code: str
    agent_name: str
    agent_type: str
    description: str | None = None
    default_model: str
    status: int

    model_config = {"from_attributes": True}


class AgentDefinitionUpdateRequest(BaseModel):
    agent_name: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = Field(None, max_length=2000)
    default_model: str | None = Field(None, min_length=1, max_length=64)
    prompt_template: str | None = Field(None, max_length=20000)
    timeout_sec: int | None = Field(None, ge=5, le=600)
    max_retry: int | None = Field(None, ge=0, le=10)
    status: int | None = Field(None, ge=0, le=1)


class TaskCreateRequest(BaseModel):
    task_type: str = Field(..., description="任务类型")
    task_name: str = Field(..., max_length=256)
    input_params: dict[str, Any] = Field(default_factory=dict)


class AgentRunResponse(BaseModel):
    id: int
    agent_code: str
    agent_name: str
    status: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    output_preview: str | None = None


class TaskStageResponse(BaseModel):
    stage_code: str
    stage_name: str
    stage_order: int
    status: int
    progress: int
    message: str | None = None


class TaskResponse(BaseModel):
    id: int
    task_no: str
    task_type: str
    task_name: str
    status: int
    progress: int
    current_stage: str | None = None
    output_result: dict[str, Any] | None = None
    error_message: str | None = None
    stages: list[TaskStageResponse] = Field(default_factory=list)
    agent_runs: list[AgentRunResponse] = Field(default_factory=list)
    partial_previews: list[dict[str, Any]] = Field(default_factory=list)
    learning_diagnosis: dict[str, Any] | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class CollaborationMessageRequest(BaseModel):
    task_id: int
    collaboration_type: str = Field(..., description="debate/consistency_check/fact_verify/handoff")
    topic: str
    initiator_run_id: int
    initiator_msg: str
    responder_run_id: int | None = None


class LLMChatRequest(BaseModel):
    messages: list[dict[str, str]] = Field(..., min_length=1, description="OpenAI格式消息")
    provider: str | None = Field(None, description="qwen/deepseek/spark/mock")
    model: str | None = None
    temperature: float = Field(0.7, ge=0, le=2)
    max_tokens: int = Field(2048, ge=1, le=8192)
    stream: bool = False


class LLMChatResponse(BaseModel):
    content: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int


class ContentAuditRequest(BaseModel):
    content: str = Field(..., min_length=1, description="待审核内容")
    target_type: str = Field("resource", description="审核对象类型")
    target_id: int | None = None
