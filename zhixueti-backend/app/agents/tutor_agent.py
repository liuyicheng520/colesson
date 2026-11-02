"""Tutor agent — personalized multimodal Socratic tutoring prompts."""

from __future__ import annotations

import re
from typing import Any

EXERCISE_PATTERNS = [
    r"题|习题|作业|考试|选择|填空|计算|证明|为什么选|怎么做|答案|错题|做不对|做错了",
    r"^\s*\d+[\.\)、]",
    r"[A-D][\.、\)]",
]

FULL_ANSWER_PATTERNS = [
    r"完整解析|直接给答案|告诉我答案|还是不懂|没看懂|请讲解|详细解释|展开说",
]


def is_exercise_question(content: str) -> bool:
    return any(re.search(p, content, re.I) for p in EXERCISE_PATTERNS)


TOPIC_SWITCH_PATTERNS = [
    r"讲解|介绍|什么是|拓展|延伸|总结一下|换个话题|讲一下|说说",
]


def is_exercise_followup(content: str, request_full: bool) -> bool:
    """Continue exercise thread only for short answers / explicit full-answer requests."""
    if wants_full_answer(content, request_full):
        return True
    if any(re.search(p, content, re.I) for p in TOPIC_SWITCH_PATTERNS):
        return False
    return len((content or "").strip()) <= 120


def resolve_is_exercise(content: str, prev_is_exercise: bool, request_full: bool) -> bool:
    if is_exercise_question(content):
        return True
    if prev_is_exercise and is_exercise_followup(content, request_full):
        return True
    return False


def wants_full_answer(content: str, request_full: bool) -> bool:
    if request_full:
        return True
    return any(re.search(p, content, re.I) for p in FULL_ANSWER_PATTERNS)


def profile_summary_text(snapshot: dict[str, Any] | None) -> str:
    if not snapshot:
        return "暂无画像，按中等水平通用辅导。"
    dims = snapshot.get("dimensions") or {}
    lines = []
    d1 = dims.get("D1") or {}
    if d1:
        lines.append(f"- 知识基础: 领域={d1.get('domain','?')}, 水平={d1.get('level',2)}/5, 缺口={d1.get('gaps',[])}")
    d2 = dims.get("D2") or {}
    if d2:
        lines.append(f"- 认知风格: {d2.get('style','综合型')}")
    d3 = dims.get("D3") or {}
    if d3:
        lines.append(f"- 学习目标: {d3.get('goal','未设定')}")
    d5 = dims.get("D5") or {}
    weak = d5.get("weakPoints") or []
    if weak:
        topics = [w.get("topic", "") for w in weak if isinstance(w, dict)]
        lines.append(f"- 易错点: {', '.join(topics[:5])}")
    d6 = dims.get("D6") or {}
    if d6:
        lines.append(f"- 学习节奏: {d6.get('pace','medium')}, 单次{d6.get('sessionMinutes','?')}分钟")
    if snapshot.get("major"):
        lines.insert(0, f"- 专业: {snapshot['major']}")
    return "\n".join(lines) if lines else "画像信息有限，按中等水平辅导。"


def adapt_style_instructions(snapshot: dict[str, Any] | None) -> str:
    if not snapshot:
        return "讲解适中详细，概念+例子+小结。"
    dims = snapshot.get("dimensions") or {}
    level = int((dims.get("D1") or {}).get("level") or 2)
    style = (dims.get("D2") or {}).get("style") or "verbal"
    if level <= 2:
        detail = "用户基础偏弱：用通俗语言、分步骤、多举例、避免跳步，每步解释「为什么」。"
    elif level >= 4:
        detail = "用户基础较好：简洁核心推导，侧重拓展应用、对比辨析、进阶思考，少讲基础定义。"
    else:
        detail = "用户中等水平：概念清晰+关键步骤+1个例子，适度拓展。"
    style_map = {
        "visual": "多用 Mermaid 流程图/概念图辅助理解。",
        "verbal": "侧重文字分步解析，结构清晰。",
        "sequential": "严格按步骤 1→2→3 递进讲解。",
        "global": "先给整体框架再展开细节。",
    }
    return f"{detail}\n{style_map.get(style, style_map['verbal'])}"


def build_tutor_system_prompt(
    *,
    mode: str,
    profile_snapshot: dict[str, Any] | None,
    hint_level: int,
    is_exercise: bool,
    exercise_context: str | None,
    knowledge_context: str | None,
    profile_adapt_enabled: bool = True,
    answer_detail: str = "normal",
    show_steps: bool = True,
    deep_mode: bool = False,
    doc_context: str | None = None,
    web_context: str | None = None,
    web_sources: list | None = None,
) -> str:
    if profile_adapt_enabled and profile_snapshot:
        profile_text = profile_summary_text(profile_snapshot)
        style_text = adapt_style_instructions(profile_snapshot)
    else:
        profile_text = "未启用画像适配，按通用中等水平辅导。"
        style_text = "讲解适中详细，概念+例子+小结。"

    if deep_mode:
        detail_rules = {
            "brief": (
                "【深度模式 + 简洁 — 必须严格遵守】\n"
                "1. 总字数不少于 600 字\n"
                "2. 必须包含 ## 原理背景、## 分步推导、## 案例演示 三个二级标题\n"
                "3. 省略冗长铺垫，每节只保留核心内容"
            ),
            "normal": (
                "【深度模式 — 必须严格遵守】\n"
                "1. 总字数不少于 800 字\n"
                "2. 必须按顺序包含以下五个二级标题（缺一不可）：\n"
                "   ## 原理背景\n"
                "   ## 分步推导\n"
                "   ## 案例演示\n"
                "   ## 易错点提醒\n"
                "   ## 拓展延伸\n"
                "3. 每部分都要有实质内容，禁止空泛套话"
            ),
            "detailed": (
                "【深度模式 + 详细 — 必须严格遵守】\n"
                "1. 总字数不少于 1000 字\n"
                "2. 必须包含上述五个二级标题，每节内容充实、有例子\n"
                "3. 可增加对比辨析与小结"
            ),
        }
    else:
        detail_rules = {
            "brief": (
                "【简洁 — 必须严格遵守】\n"
                "1. 总字数 150 字以内\n"
                "2. 只给核心结论和最关键的一步，省略背景与延伸"
            ),
            "normal": (
                "【标准 — 必须严格遵守】\n"
                "1. 总字数 300 字左右\n"
                "2. 讲清概念 + 关键步骤 + 简短小结"
            ),
            "detailed": (
                "【详细 — 必须严格遵守】\n"
                "1. 总字数 500–800 字\n"
                "2. 包含原理背景、分步推导、例子或类比、易错点提醒\n"
                "3. 结构清晰，可使用二级标题分段"
            ),
        }

    if deep_mode:
        detail_rules["_think"] = (
            "内部推理过程放在 \u003cthink\u003e 与 \u003c/think\u003e 标签内，仅写 3-5 条要点；"
            "标签外只输出正式回答，禁止重复思考内容"
        )

    doc_block = ""
    if doc_context:
        doc_block = f"\n## 参考文档（优先依据，标注页码）\n{doc_context[:8000]}\n"
    web_block = ""
    if web_context:
        src_lines = ""
        if web_sources:
            src_lines = "\n".join(f"- [{s.get('title','来源')}]({s.get('url','')})" for s in web_sources[:5])
        web_limit = 1500 if deep_mode and doc_context else 3000
        web_block = f"\n## 知识库与检索资料（优先依据，需结合用户问题作答）\n{web_context[:web_limit]}\n{src_lines}\n"

    step_rule = (
        "使用「步骤1/2/3」结构分步讲解。"
        if show_steps
        else "可合并步骤，以连贯段落说明，不必强制分步编号。"
    )

    exercise_rules = ""
    if is_exercise:
        if hint_level <= 0:
            exercise_rules = (
                "【习题启发式规则 — 当前为思路提示阶段】\n"
                "1. 绝不直接给出最终答案或完整解题过程\n"
                "2. 给出：考察知识点 + 解题思路框架 + 1-2个引导性问题\n"
                "3. 可提示第一步该做什么，但不写出完整计算/推导\n"
                "4. 末尾鼓励用户尝试后追问\n"
            )
        elif hint_level == 1:
            exercise_rules = (
                "【习题启发式规则 — 进阶提示】\n"
                "1. 给出更具体的中间步骤提示，仍保留最后一步让用户完成\n"
                "2. 指出常见错误陷阱\n"
            )
        else:
            exercise_rules = (
                "【习题解析 — 完整解答阶段】\n"
                "用户已追问，现在可以给出完整分步解析和最终答案。\n"
                "用「步骤1/2/3」结构，每步说明原理。\n"
            )

    mode_rules = {
        "socratic": (
            "【基础讲解模式 — 必须严格遵守】\n"
            "1. 直接、清晰地讲解概念与原理：概念 → 原理 → 应用\n"
            "2. 可以给出明确结论与完整步骤，帮助用户快速理解\n"
            "3. 语气专业清晰，侧重知识传递"
        ),
        "hint": (
            "【应试提分模式 — 必须严格遵守】\n"
            "1. 聚焦考点、答题技巧与常见题型\n"
            "2. 标注「得分要点」「易错点」「阅卷关注点」\n"
            "3. 遇到练习题：先给思路框架与提示，不直接给出完整答案（除非用户明确要求）"
        ),
        "debug": (
            "【错题调试模式 — 必须严格遵守】\n"
            "1. 分析错误原因，定位知识漏洞\n"
            "2. 给出纠正路径与同类题防范建议"
        ),
        "encourage": (
            "【启发引导模式 — 必须严格遵守】\n"
            "1. 优先用引导性提问启发思考，少直接给出完整结论\n"
            "2. 每次回答末尾留 1–2 个思考问题，鼓励用户先尝试\n"
            "3. 语气温和，肯定努力，小步推进"
        ),
    }

    detail_block = detail_rules.get(answer_detail, detail_rules["normal"])
    if deep_mode and detail_rules.get("_think"):
        detail_block = f"{detail_block}\n4. {detail_rules['_think']}"

    return f"""你是智学体多模态智能辅导助手。

## 用户画像
{profile_text}

## 个性化策略
{style_text}

## 回答偏好
{detail_block}
{step_rule}

## 辅导模式
{mode_rules.get(mode, mode_rules['socratic'])}

{exercise_rules}

## 输出格式（必须遵守）
1. 使用 Markdown，复杂问题用「## 步骤 N」分步输出（# 后必须有空格）
2. 需要图解时使用 ```mermaid 代码块（flowchart/graph TD 等）
3. 代码演示使用带语言标注的代码块（```python 等），确保可运行或接近可运行
4. 数学公式用 LaTeX（$...$ 或 $$...$$）
5. 语气友好、专业、鼓励
6. 必须完整写完当前段落和最后一个章节，禁止在句中或列表项中途突然停止
7. 写完后自检：是否满足上方「回答偏好」的字数与结构要求

## 关联上下文
{knowledge_context or '暂无知识点匹配'}
{exercise_context or ''}
{doc_block}
{web_block}

hint_level={hint_level}（0=仅思路, 1=进阶提示, 2+=完整解析）
{"【深度模式已开启】" if deep_mode else ""}
"""


def detect_message_type(content: str, is_exercise: bool, hint_level: int) -> tuple[str, str]:
    if is_exercise and hint_level <= 1:
        return "hint", "socratic_hint"
    if "```" in content and ("python" in content or "java" in content or "javascript" in content):
        return "code", "code_demo"
    if "```mermaid" in content:
        return "text", "multimodal"
    return "text", "explanation" if not is_exercise else "exercise_resolve"
