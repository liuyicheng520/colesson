"""Security context passed through LLM call chain."""

from dataclasses import dataclass, field


@dataclass
class SecurityContext:
    target_type: str = "message"
    target_id: int | None = None
    topic: str | None = None
    knowledge_scope: list[str] = field(default_factory=list)
    allow_off_topic: bool = False
    require_citation: bool = True
    source_module: str = "llm"
