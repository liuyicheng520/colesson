"""Citation enforcement for anti-hallucination."""

CITATION_POLICY = """
【强制输出规范 — 防幻觉溯源】
1. 回答末尾必须包含「📚 知识依据与参考范围」段落
2. 列出：知识点依据、参考范围（如教材章节/课程标准/通用学科共识）、溯源说明
3. 不确定的内容必须用 [存疑] 标注
4. 禁止编造具体统计数据、论文引用、年份事件，除非有明确依据
"""

CITATION_HEADER = "## 📚 知识依据与参考范围"


def inject_citation_policy(messages: list[dict[str, str]], knowledge_scope: list[str] | None = None) -> list[dict[str, str]]:
    if not messages:
        return messages
    scope_hint = ""
    if knowledge_scope:
        scope_hint = f"\n当前知识范围：{', '.join(knowledge_scope)}"
    policy = CITATION_POLICY + scope_hint

    out = [dict(m) for m in messages]
    if out[0].get("role") == "system":
        out[0]["content"] = out[0]["content"] + "\n\n" + policy
    else:
        out.insert(0, {"role": "system", "content": policy.strip()})
    return out


def ensure_citation_block(content: str, knowledge_scope: list[str] | None = None) -> str:
    if CITATION_HEADER in content or "知识依据" in content:
        return content
    scope = "、".join(knowledge_scope) if knowledge_scope else "通用学科知识库与课程标准"
    footer = (
        f"\n\n{CITATION_HEADER}\n"
        f"- **知识点依据**：基于上述回答涉及的核心概念\n"
        f"- **参考范围**：{scope}\n"
        f"- **溯源说明**：内容由 AI 辅助生成，关键结论请以教材与教师讲解为准\n"
    )
    return content.rstrip() + footer


def strip_citation_block(content: str) -> str:
    """Remove trailing knowledge-citation section from LLM output."""
    if not content:
        return content
    markers = [
        CITATION_HEADER,
        "## 📚 知识依据与参考范围",
        "📚 **知识依据与参考范围**",
        "📚 知识依据与参考范围",
        "**📚 知识依据与参考范围**",
        "\n\n## 📚",
    ]
    text = content
    for marker in markers:
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx]
    # Fallback: line starting with 知识依据
    lines = text.split("\n")
    cut = len(lines)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("📚") and "知识依据" in stripped:
            cut = i
            break
        if stripped.startswith("- **知识点依据") or stripped.startswith("* **知识点依据"):
            cut = i
            break
        if stripped.startswith("- **参考范围") or stripped.startswith("* **参考范围"):
            cut = i
            break
    text = "\n".join(lines[:cut])
    return text.rstrip()
