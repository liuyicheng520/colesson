"""Content validation agent — fact accuracy check."""

import json
import re
from dataclasses import dataclass, field

from app.llm.gateway import LLMGateway


@dataclass
class ValidationResult:
    passed: bool = True
    risk_level: int = 0
    issues: list[str] = field(default_factory=list)
    suspicious_segments: list[str] = field(default_factory=list)
    needs_regenerate: bool = False
    fact_check_detail: dict | None = None


class FactValidatorAgent:
    VALIDATOR_PROMPT = (
        "你是内容校验智能体，负责事实准确性与合规核查。分析 AI 生成内容，返回 JSON：\n"
        '{"passed":bool,"risk_level":0-3,"issues":[],"suspicious_segments":[],"needs_regenerate":bool}\n'
        "risk_level: 0=无问题 1=轻微存疑 2=中度错误 3=严重事实错误\n"
        "needs_regenerate: risk_level>=3 或存在明显编造数据/错误公式时为 true\n"
        "suspicious_segments: 存疑原文片段列表\n"
        "仅返回 JSON。"
    )

    EDUCATIONAL_VALIDATOR_PROMPT = (
        "你是教育内容校验智能体。待审核内容为正常学科学习材料（讲义、习题、知识图谱、拓展阅读等）。\n"
        "审核原则：\n"
        "1. 纯学科知识点、例题、公式推导、教学讲解 → 直接 passed=true, risk_level=0\n"
        "2. 轻微表述不严谨或缺少引用 → risk_level=1，passed=true，needs_regenerate=false\n"
        "3. 仅当存在明显事实错误、编造数据、或违法低俗敏感内容时 → risk_level>=3, passed=false\n"
        "4. 不要因为「缺少权威引用」或「教学简化」而判定不通过\n"
        "返回 JSON："
        '{"passed":bool,"risk_level":0-3,"issues":[],"suspicious_segments":[],"needs_regenerate":bool}\n'
        "仅返回 JSON。"
    )

    def __init__(self, llm: LLMGateway) -> None:
        self.llm = llm

    def _parse(self, raw: str) -> dict:
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"\{[\s\S]*\}", text)
            if m:
                try:
                    return json.loads(m.group())
                except json.JSONDecodeError:
                    pass
        return {"passed": True, "risk_level": 0, "issues": [], "needs_regenerate": False}

    async def validate(
        self,
        content: str,
        topic: str | None = None,
        knowledge_scope: list[str] | None = None,
        educational_mode: bool = False,
    ) -> ValidationResult:
        if len(content.strip()) < 20:
            return ValidationResult(passed=True)

        scope = ", ".join(knowledge_scope or []) or "通用教育知识"
        system_prompt = self.EDUCATIONAL_VALIDATOR_PROMPT if educational_mode else self.VALIDATOR_PROMPT
        result = await self.llm.chat(
            [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"主题: {topic or '未指定'}\n知识范围: {scope}\n"
                        f"内容类型: {'学科学习材料' if educational_mode else '通用'}\n\n"
                        f"待校验内容:\n{content[:4000]}"
                    ),
                },
            ],
            temperature=0.1,
            max_tokens=800,
            skip_security=True,
        )
        data = self._parse(result.content)
        risk = int(data.get("risk_level", 0))
        # 教育模式下：risk 0-2 均放行，仅 risk>=3 拦截
        if educational_mode:
            passed = bool(data.get("passed", True)) and risk < 3
            needs_regen = risk >= 3
        else:
            passed = bool(data.get("passed", True)) and risk < 3
            needs_regen = bool(data.get("needs_regenerate")) or risk >= 3
        return ValidationResult(
            passed=passed,
            risk_level=risk,
            issues=data.get("issues") or [],
            suspicious_segments=data.get("suspicious_segments") or [],
            needs_regenerate=needs_regen,
            fact_check_detail=data,
        )

    @staticmethod
    def mark_suspicious(content: str, validation: ValidationResult) -> str:
        """Build admin-facing validation notice (do not append to student-visible content)."""
        if not validation.suspicious_segments and not validation.issues:
            return content
        lines = ["\n\n---", "⚠️ **内容校验提示**（以下部分存疑，请核实）："]
        for seg in validation.suspicious_segments[:5]:
            lines.append(f"- [存疑] {seg}")
        for issue in validation.issues[:5]:
            if issue not in validation.suspicious_segments:
                lines.append(f"- {issue}")
        return content.rstrip() + "\n".join(lines)

    _VALIDATION_NOTICE_RE = re.compile(
        r"\n---\s*\n⚠️ \*\*内容校验提示\*\*[\s\S]*",
        re.MULTILINE,
    )

    @staticmethod
    def strip_validation_notice(content: str) -> str:
        """Remove validation notice block from text shown to students."""
        return FactValidatorAgent._VALIDATION_NOTICE_RE.sub("", content).rstrip()
