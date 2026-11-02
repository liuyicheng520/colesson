"""Shared orchestration context passed between agents."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OrchestrationContext:
    """Runtime context for multi-agent resource generation."""

    task_id: int
    task_no: str
    user_id: int
    topic: str
    goal: str | None
    difficulty: int
    node_id: int | None
    resource_types: list[str]
    profile_snapshot: dict[str, Any] | None = None
    profile_dimensions: list[dict[str, Any]] = field(default_factory=list)
    learning_diagnosis: dict[str, Any] | None = None
    orchestrator_plan: dict[str, Any] | None = None
    kb_context: str = ""
    kb_citations: list[dict[str, Any]] = field(default_factory=list)
    resource_ids: list[int] = field(default_factory=list)
    partial_previews: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    # 单次生成自定义约束（画像之外）
    ignore_profile: bool = False
    supplement: str | None = None
    use_scene: str | None = None
    content_focus: list[str] = field(default_factory=list)
    content_length: str | None = None
    special_requirements: str | None = None

    def profile_summary(self) -> str:
        if self.ignore_profile:
            return "用户本次选择忽略画像，请勿套用既往学情，按主题与自定义约束从零适配生成。"
        if not self.profile_dimensions:
            return "暂无用户画像，按中等水平通用生成。"
        lines = []
        for d in self.profile_dimensions:
            name = d.get("dimension_name", d.get("dimension_code", ""))
            val = d.get("dimension_value", {})
            conf = d.get("confidence", 0)
            lines.append(f"- {name}(置信度{conf:.0%}): {val}")
        return "\n".join(lines)

    def diagnosis_summary(self) -> str:
        if not self.learning_diagnosis:
            return ""
        d = self.learning_diagnosis
        parts = [
            f"知识薄弱点: {', '.join(d.get('weak_points', [])) or '待评估'}",
            f"适配学习风格: {d.get('learning_style', '综合型')}",
            f"建议难度: {d.get('recommended_difficulty', self.difficulty)}/5",
            f"重点关注: {d.get('focus_areas', [])}",
        ]
        return "\n".join(parts)

    def generation_brief(self) -> str:
        """画像外的单次补充需求与高级自定义参数。"""
        lines: list[str] = []
        if self.supplement:
            lines.append(f"补充需求: {self.supplement}")
        if self.use_scene:
            lines.append(f"使用场景: {self.use_scene}")
        if self.content_focus:
            lines.append(f"内容侧重: {', '.join(self.content_focus)}")
        if self.content_length:
            lines.append(f"内容篇幅: {self.content_length}")
        if self.special_requirements:
            lines.append(f"特殊要求: {self.special_requirements}")
        return "\n".join(lines) if lines else "无额外自定义约束"

    def kb_summary(self) -> str:
        return (self.kb_context or "").strip()
