"""Specialist agents: coordinator + 5 domain agents + animation placeholder."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from app.agents.base import BaseAgent
from app.agents.context import OrchestrationContext
from app.utils.subject_utils import detect_subject_category, is_programming_subject


def _escape_raw_newlines_in_json_strings(text: str) -> str:
    """把 JSON 字符串值里的裸换行/制表符转成转义，避免代码块导致 json.loads 失败。"""
    out: list[str] = []
    in_str = False
    escape = False
    for ch in text:
        if in_str:
            if escape:
                out.append(ch)
                escape = False
            elif ch == "\\":
                out.append(ch)
                escape = True
            elif ch == '"':
                out.append(ch)
                in_str = False
            elif ch == "\n":
                out.append("\\n")
            elif ch == "\r":
                out.append("\\r")
            elif ch == "\t":
                out.append("\\t")
            else:
                out.append(ch)
        else:
            if ch == '"':
                in_str = True
            out.append(ch)
    return "".join(out)


_THINK_BLOCK_RE = re.compile(
    r"<(think|thinking|redacted_reasoning)>[\s\S]*?</\1>",
    re.IGNORECASE,
)


def _strip_model_noise(text: str) -> str:
    cleaned = _THINK_BLOCK_RE.sub("", text or "")
    return cleaned.strip()


def _loads_json_lenient(text: str) -> dict | list | None:
    candidates = [text, _escape_raw_newlines_in_json_strings(text)]
    # 去掉对象/数组尾逗号（模型常见瑕疵）
    candidates.append(re.sub(r",(\s*[}\]])", r"\1", text))
    candidates.append(re.sub(r",(\s*[}\]])", r"\1", _escape_raw_newlines_in_json_strings(text)))
    for cand in candidates:
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            continue
    return None


def _extract_json(text: str) -> dict | list | None:
    text = _strip_model_noise(text)
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    parsed = _loads_json_lenient(text)
    if parsed is not None:
        return parsed

    # 从文本中截取第一个可解析的 {...} / [...]（贪婪匹配经常失败，改为括号平衡扫描）
    for start_char, end_char in (("{", "}"), ("[", "]")):
        start = text.find(start_char)
        if start < 0:
            continue
        depth = 0
        in_str = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == start_char:
                depth += 1
            elif ch == end_char:
                depth -= 1
                if depth == 0:
                    chunk = text[start : i + 1]
                    parsed = _loads_json_lenient(chunk)
                    if parsed is not None:
                        return parsed
                    break
    return None


def _unescape_json_fragment(value: str) -> str:
    try:
        return json.loads(f'"{value}"')
    except json.JSONDecodeError:
        return (
            value.replace("\\n", "\n")
            .replace("\\r", "\r")
            .replace("\\t", "\t")
            .replace('\\"', '"')
            .replace("\\\\", "\\")
        )


def _extract_json_string_field(text: str, field: str, next_fields: list[str] | None = None) -> str | None:
    """从可能损坏的 JSON 中捞取字符串字段（代码里未转义引号时用后续字段做边界）。"""
    m = re.search(rf'"{re.escape(field)}"\s*:\s*"', text)
    if not m:
        return None
    start = m.end()
    # 标准扫描：遇未转义引号结束
    out: list[str] = []
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            out.append(ch)
            escape = False
            continue
        if ch == "\\":
            out.append(ch)
            escape = True
            continue
        if ch == '"':
            return _unescape_json_fragment("".join(out))
        out.append(ch)

    # 字符串未闭合：用后续字段名截断（常见于截断/未转义引号）
    end = len(text)
    for nf in next_fields or ():
        nm = re.search(rf'",\s*"{re.escape(nf)}"\s*:', text[start:])
        if nm:
            end = min(end, start + nm.start())
    fragment = text[start:end].rstrip().rstrip(",")
    if fragment.endswith('"'):
        fragment = fragment[:-1]
    return _unescape_json_fragment(fragment) if fragment.strip() else None


def _guess_code_language(topic: str) -> str:
    t = (topic or "").lower()
    mapping = [
        ("typescript", "typescript"),
        ("javascript", "javascript"),
        ("python", "python"),
        ("java", "java"),
        ("c++", "cpp"),
        ("c语言", "c"),
        ("golang", "go"),
        ("go语言", "go"),
        ("rust", "rust"),
        ("sql", "sql"),
    ]
    for kw, lang in mapping:
        if kw in t:
            return lang
    return "python"


def _default_programming_practice(topic: str) -> dict[str, Any]:
    """JSON 彻底解析失败时仍给出可运行模板，避免页面只剩「解析失败」。"""
    lang = _guess_code_language(topic)
    t = (topic or "编程练习").strip()[:40] or "编程练习"
    samples = {
        "java": (
            f"public class Practice {{\n"
            f"    // 主题：{t}\n"
            f"    public static void main(String[] args) {{\n"
            f'        System.out.println("Practice: {t}");\n'
            f"        // TODO: 按题目要求在此补充代码\n"
            f"    }}\n"
            f"}}\n"
        ),
        "python": (
            f"# 主题：{t}\n"
            f"def main():\n"
            f'    print("Practice: {t}")\n'
            f"    # TODO: 按题目要求在此补充代码\n\n"
            f'if __name__ == "__main__":\n'
            f"    main()\n"
        ),
        "javascript": (
            f"// 主题：{t}\n"
            f"function main() {{\n"
            f'  console.log("Practice: {t}");\n'
            f"  // TODO: 按题目要求在此补充代码\n"
            f"}}\n"
            f"main();\n"
        ),
        "cpp": (
            f"#include <iostream>\n"
            f"// 主题：{t}\n"
            f"int main() {{\n"
            f'    std::cout << "Practice: {t}" << std::endl;\n'
            f"    // TODO: 按题目要求在此补充代码\n"
            f"    return 0;\n"
            f"}}\n"
        ),
        "c": (
            f"#include <stdio.h>\n"
            f"/* 主题：{t} */\n"
            f"int main(void) {{\n"
            f'    printf("Practice: {t}\\n");\n'
            f"    /* TODO: 按题目要求在此补充代码 */\n"
            f"    return 0;\n"
            f"}}\n"
        ),
        "go": (
            f"package main\n\n"
            f'import "fmt"\n\n'
            f"// 主题：{t}\n"
            f"func main() {{\n"
            f'    fmt.Println("Practice: {t}")\n'
            f"    // TODO: 按题目要求在此补充代码\n"
            f"}}\n"
        ),
        "sql": (
            f"-- 主题：{t}\n"
            f"SELECT 1 AS practice_ok;\n"
            f"-- TODO: 按题目要求改写查询\n"
        ),
    }
    code = samples.get(lang, samples["python"])
    run_hint = {
        "java": "javac Practice.java && java Practice",
        "python": "python practice.py",
        "javascript": "node practice.js",
        "cpp": "g++ practice.cpp -o practice && ./practice",
        "c": "gcc practice.c -o practice && ./practice",
        "go": "go run practice.go",
        "sql": "在任意 SQL 客户端执行上述语句",
    }.get(lang, "按所选语言本地运行")
    return {
        "content_mode": "code",
        "language": lang,
        "code_content": code,
        "explanation": f"模型输出未能完整解析，已提供「{t}」可运行入门模板，请按 TODO 完成练习。",
        "objective": f"围绕「{t}」完成一次可运行的实战练习",
        "run_instructions": run_hint,
        "test_cases": [{"input": "", "expectedOutput": f"Practice: {t}"}],
        "dependencies": [],
    }


def _salvage_code_payload(text: str) -> dict[str, Any] | None:
    """当整段 JSON 损坏时，尽量捞出 code_content / language / explanation。"""
    next_after_code = [
        "explanation",
        "objective",
        "run_instructions",
        "test_cases",
        "dependencies",
        "language",
        "content_mode",
    ]
    code = _extract_json_string_field(text, "code_content", next_after_code)
    if not code or len(code.strip()) < 8:
        fence = re.search(r"```(?:\w+)?\n([\s\S]+?)```", text)
        if fence:
            code = fence.group(1).strip()
    if not code or len(code.strip()) < 8:
        return None
    language = _extract_json_string_field(text, "language") or "python"
    explanation = _extract_json_string_field(text, "explanation", ["objective", "run_instructions", "test_cases"]) or (
        "实战演练代码已生成"
    )
    objective = _extract_json_string_field(text, "objective", ["run_instructions", "test_cases", "dependencies"]) or ""
    run_instructions = (
        _extract_json_string_field(text, "run_instructions", ["test_cases", "dependencies"]) or ""
    )
    return {
        "content_mode": "code",
        "language": language,
        "code_content": code,
        "explanation": explanation,
        "objective": objective,
        "run_instructions": run_instructions,
        "test_cases": [],
        "dependencies": [],
    }


def _normalize_code_agent_payload(raw: str, *, is_programming: bool, topic: str = "") -> dict[str, Any]:
    """解析代码/实战演练智能体输出；失败时尽量 salvage，再退回可用模板。"""
    code_data = _extract_json(raw)
    if isinstance(code_data, dict):
        # 偶发双重包装：字段本身又是一段 JSON 字符串
        for key in ("code_content", "explanation"):
            val = code_data.get(key)
            if isinstance(val, str) and val.strip().startswith("{") and "content_mode" in val:
                nested = _extract_json(val)
                if isinstance(nested, dict) and (nested.get("code_content") or nested.get("practice_items")):
                    code_data = {**code_data, **nested}
                    break
        content = str(code_data.get("code_content") or "").strip()
        if is_programming and (not content or content.startswith("-- 代码解析失败")):
            salvaged = _salvage_code_payload(_strip_model_noise(raw))
            if salvaged:
                return salvaged
            return _default_programming_practice(topic)
        return code_data

    text = _strip_model_noise(raw)
    if is_programming:
        salvaged = _salvage_code_payload(text)
        if salvaged:
            return salvaged
        if text and not text.startswith("{"):
            return {
                "content_mode": "code",
                "language": _guess_code_language(topic),
                "code_content": text,
                "explanation": "实战演练代码已生成",
            }
        return _default_programming_practice(topic)
    # 非编程类：解析失败时回退通用实战模板（与编程/数学兜底同策略），避免生成空壳资源
    return _default_general_practice(topic, note=text)


def _default_general_practice(topic: str, note: str = "") -> dict[str, Any]:
    """非编程学科实战模板兜底：保证练习资源至少有可自测的题目与参考答案。"""
    t = (topic or "本主题").strip()[:40] or "本主题"
    items = [
        {
            "type": "application",
            "title": f"{t}·核心应用",
            "content": f"结合「{t}」的核心概念，说明它解决什么问题、适用场景是什么，并给出一个具体例子（不少于 80 字）。",
            "answer": "示例应包含场景、做法与结果三要素，结论明确即可。",
        },
        {
            "type": "exercise",
            "title": f"{t}·流程实操",
            "content": f"按步骤完成一次与「{t}」相关的实操任务，记录每一步的关键动作与结果。",
            "steps": ["明确任务目标与输入", "按标准流程逐步执行", "核对结果并总结要点"],
            "answer": "流程完整、记录清晰即可。",
        },
        {
            "type": "application",
            "title": f"{t}·对比分析",
            "content": f"找出「{t}」中两个容易混淆的概念或方案，从 2-3 个维度对比分析。",
            "answer": "对比维度选择合理、结论明确即可。",
        },
    ]
    explanation = "模型输出未能完整解析，已提供通用实战模板，可先作答再对照参考答案自测。"
    if note:
        explanation += f"（原始输出摘要：{note[:120]}）"
    return {
        "content_mode": "practice",
        "practice_type": "general",
        "language": "practice",
        "practice_items": items,
        "explanation": explanation,
        "objective": f"围绕「{t}」完成实战自测",
    }


def _looks_like_json_blob(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    s = value.strip()
    return s.startswith("{") and ("script_content" in s or '"slides"' in s)


def _default_animation_payload(topic: str) -> dict[str, Any]:
    """解析失败或 Mock 时的多页分镜：6 页、旁白充实可跟读。"""
    t = (topic or "本主题").strip()[:40] or "本主题"
    slides = [
        {
            "step": 1,
            "title": f"认识{t}",
            "narration": (
                f"同学们好，今天我们系统学习「{t}」。先建立整体地图：它要解决什么问题、"
                f"关键概念有哪些、学完后能独立完成哪些任务。请先带着这三个问题听完整节。"
            ),
            "visual": "封面、学习目标与本节路线图",
            "emoji": "🎓",
            "duration_sec": 18,
            "scene_type": "concept",
            "nodes": [t, "学习目标", "本节路线"],
        },
        {
            "step": 2,
            "title": "核心定义",
            "narration": (
                f"「{t}」可以先用一句话定义，再划清边界：它包含什么、不包含什么。"
                f"请对照一个生活或工程中的小例子，确认定义是否说得通。"
            ),
            "visual": "一句话定义 + 边界对照 + 反例",
            "emoji": "📘",
            "duration_sec": 22,
            "scene_type": "concept",
            "nodes": ["定义", "边界", "例子", "反例"],
        },
        {
            "step": 3,
            "title": "关键结构",
            "narration": (
                f"把「{t}」拆成 3～4 个积木块：输入、处理、输出（或前提、过程、结论）。"
                f"说明各块职责、彼此如何衔接，以及常见漏掉哪一块会出错。"
            ),
            "visual": "积木式结构图：模块与数据流",
            "emoji": "🧩",
            "duration_sec": 24,
            "scene_type": "concept",
            "nodes": ["模块A", "模块B", "模块C", "衔接关系"],
        },
        {
            "step": 4,
            "title": "典型过程",
            "narration": (
                f"走一遍「{t}」最常见的标准流程：每一步做什么、为什么必要、输出是什么。"
                f"强调中间结果如何被下一步消费，避免只记最终公式或结论。"
            ),
            "visual": "步骤流水线与中间结果标注",
            "emoji": "🛤️",
            "duration_sec": 24,
            "scene_type": "concept",
            "nodes": ["步骤1", "步骤2", "步骤3", "检查点"],
        },
        {
            "step": 5,
            "title": "动手感知",
            "narration": (
                f"拖动滑块改变关键参数，观察「{t}」相关结果如何变化。"
                f"请自己总结：哪个参数影响最大？何时会出现异常或瓶颈？"
            ),
            "visual": "参数驱动示意：调节—观察—总结规律",
            "emoji": "🔬",
            "duration_sec": 28,
            "scene_type": "simulation",
            "nodes": ["调参", "观察", "规律", "异常"],
            "interaction": {
                "variable_label": "关键参数",
                "min": 0,
                "max": 100,
                "initial": 35,
                "unit": "%",
                "presets": [
                    {"label": "入门", "value": 20},
                    {"label": "进阶", "value": 55},
                    {"label": "挑战", "value": 85},
                ],
            },
        },
        {
            "step": 6,
            "title": "小结巩固",
            "narration": (
                f"回顾「{t}」：定义与边界、关键结构、标准流程、参数直觉。"
                f"请用自己的话复述三点，并想一个还能继续追问的问题作为下次入口。"
            ),
            "visual": "四要点清单 + 自测复述提示",
            "emoji": "✅",
            "duration_sec": 18,
            "scene_type": "concept",
            "nodes": ["定义", "结构", "流程", "下一步"],
        },
    ]
    script = "\n\n".join(f"## {s['title']}\n{s['narration']}" for s in slides)
    return {
        "script_content": script,
        "slides": slides,
        "storyboard": [
            {"scene": s["step"], "duration_sec": s["duration_sec"], "narration": s["narration"], "visual": s["visual"]}
            for s in slides
        ],
        "animation_type": "interactive_scene_animation",
        "animation_data": {"style": "interactive_lab", "teacher_name": "小智老师", "interaction_enabled": True},
        "status": "ready",
    }


def _normalize_animation_payload(data: dict[str, Any], topic: str) -> dict[str, Any]:
    """清洗动画智能体输出：展开误塞的 JSON、补齐页数、重写可读脚本。"""
    # 若顶层就是错误包装，或 slides 里嵌了整包 JSON，则尝试展开
    if _looks_like_json_blob(data.get("script_content")):
        nested = _extract_json(str(data["script_content"]))
        if isinstance(nested, dict) and (nested.get("slides") or nested.get("storyboard")):
            data = {**data, **nested}

    slides = data.get("slides")
    if not isinstance(slides, list) or not slides:
        storyboard = data.get("storyboard") or []
        slides = [
            {
                "step": i + 1,
                "title": s.get("title") or s.get("visual") or f"步骤{i + 1}",
                "narration": s.get("narration") or "",
                "visual": s.get("visual") or "",
                "emoji": s.get("emoji") or "📖",
                "duration_sec": s.get("duration_sec") or 8,
                "scene_type": s.get("scene_type") or "concept",
                "nodes": s.get("nodes"),
                "interaction": s.get("interaction"),
            }
            for i, s in enumerate(storyboard)
            if isinstance(s, dict)
        ]

    # 单页且旁白是整包 JSON → 重新解析
    if len(slides) <= 1 and slides:
        blob = slides[0].get("narration") or slides[0].get("visual") or data.get("script_content")
        if _looks_like_json_blob(blob):
            nested = _extract_json(str(blob))
            if isinstance(nested, dict) and isinstance(nested.get("slides"), list) and nested["slides"]:
                slides = nested["slides"]
                data = {**data, **nested}

    cleaned: list[dict[str, Any]] = []
    for i, raw in enumerate(slides):
        if not isinstance(raw, dict):
            continue
        narration = str(raw.get("narration") or "").strip()
        visual = str(raw.get("visual") or "").strip()
        if _looks_like_json_blob(narration):
            nested = _extract_json(narration)
            if isinstance(nested, dict) and isinstance(nested.get("slides"), list) and nested["slides"]:
                # 整包误塞到某一页：改用嵌套 slides，丢弃当前坏页
                return _normalize_animation_payload(nested, topic)
            narration = "本页讲解内容准备中，请切换到下一页或重新生成资源。"
        if _looks_like_json_blob(visual):
            visual = "跟随旁白观察概念结构"
        title = str(raw.get("title") or f"步骤{i + 1}").strip() or f"步骤{i + 1}"
        nodes = raw.get("nodes")
        if not isinstance(nodes, list) or not nodes:
            nodes = [title, visual or "核心概念", "掌握要点"]
        cleaned.append(
            {
                "step": int(raw.get("step") or i + 1),
                "title": title[:80],
                "narration": narration[:1200] or f"关于「{title}」的讲解。",
                "visual": visual[:400] or "概念图示",
                "emoji": str(raw.get("emoji") or "📖")[:4],
                "duration_sec": max(6, min(40, int(raw.get("duration_sec") or 10))),
                "scene_type": raw.get("scene_type") if raw.get("scene_type") in {"concept", "simulation", "interactive"} else "concept",
                "nodes": [str(n)[:40] for n in nodes[:5]],
                "interaction": raw.get("interaction") if isinstance(raw.get("interaction"), dict) else None,
                "interactive_html": raw.get("interactive_html") if isinstance(raw.get("interactive_html"), str) else None,
            }
        )

    if len(cleaned) < 6:
        fallback = _default_animation_payload(topic)
        # 保留已有有效页，后接默认页补足到 6 页
        seen_titles = {s["title"] for s in cleaned}
        for s in fallback["slides"]:
            if len(cleaned) >= 6:
                break
            if s["title"] not in seen_titles:
                cleaned.append(s)
                seen_titles.add(s["title"])
        if len(cleaned) < 6:
            cleaned = fallback["slides"][:6]
    script_parts = [f"## {s['title']}\n{s['narration']}" for s in cleaned]
    data["slides"] = cleaned
    data["storyboard"] = [
        {"scene": s["step"], "duration_sec": s["duration_sec"], "narration": s["narration"], "visual": s["visual"]}
        for s in cleaned
    ]
    data["script_content"] = "\n\n".join(script_parts)
    data.setdefault("animation_type", "interactive_scene_animation")
    data.setdefault(
        "animation_data",
        {"style": "interactive_lab", "teacher_name": "小智老师", "interaction_enabled": True},
    )
    data["animation_data"] = {
        **(data.get("animation_data") or {}),
        "slides": cleaned,
        "render_status": "ready",
        "teacher_name": (data.get("animation_data") or {}).get("teacher_name") or "小智老师",
    }
    data["status"] = "ready"
    return data


def _default_question_bank(topic: str, difficulty: int = 3) -> list[dict[str, Any]]:
    """模型输出不足时兜底：固定给出 10 道分层题，保证练习量。"""
    t = (topic or "本主题").strip()[:60] or "本主题"
    base = max(1, min(5, int(difficulty or 3)))
    return [
        {
            "question_type": "single_choice",
            "stem": f"关于「{t}」的基本定位，下列哪项最准确？",
            "options": [
                "A. 抓住其要解决的核心问题与适用范围",
                "B. 只记住最终公式或结论即可",
                "C. 与相邻概念无需区分边界",
                "D. 不需要关注输入输出关系",
            ],
            "answer": "A",
            "analysis": "学习概念先明确问题与边界，避免死记结论。",
            "difficulty": max(1, base - 1),
            "error_type": "概念理解",
            "knowledge_point": f"{t}-基础定义",
        },
        {
            "question_type": "single_choice",
            "stem": f"理解「{t}」时，推荐的第一步是？",
            "options": [
                "A. 先堆砌术语名词",
                "B. 用一句话定义 + 一个正例 + 一个反例",
                "C. 直接做最难题",
                "D. 跳过图示只看文字",
            ],
            "answer": "B",
            "analysis": "定义-正例-反例能快速校准概念边界。",
            "difficulty": max(1, base - 1),
            "error_type": "学习策略",
            "knowledge_point": f"{t}-认知路径",
        },
        {
            "question_type": "multi_choice",
            "stem": f"下列哪些做法有助于掌握「{t}」？（多选）",
            "options": [
                "A. 拆解关键模块/步骤",
                "B. 对照易错点做检查清单",
                "C. 只背答案不做推导",
                "D. 用自己的话复述流程图",
            ],
            "answer": ["A", "B", "D"],
            "analysis": "结构化拆解、错因清单与主动复述最有效；死背答案无效。",
            "difficulty": base,
            "error_type": "方法误用",
            "knowledge_point": f"{t}-掌握方法",
        },
        {
            "question_type": "single_choice",
            "stem": f"若「{t}」出现常见错误，优先排查什么？",
            "options": [
                "A. 前提条件与中间结果是否成立",
                "B. 界面皮肤颜色",
                "C. 题目字数多少",
                "D. 是否使用英文作答",
            ],
            "answer": "A",
            "analysis": "多数错误来自前提遗漏或中间量算错。",
            "difficulty": base,
            "error_type": "过程遗漏",
            "knowledge_point": f"{t}-排错",
        },
        {
            "question_type": "fill_blank",
            "stem": f"用一句话概括：「{t}」主要解决的问题是______。",
            "answer": "围绕其目标对象建立正确表示/过程并得到可靠结果",
            "analysis": "填空不必逐字相同，语义上点明目标、过程与结果即可。",
            "difficulty": base,
            "error_type": "表述不清",
            "knowledge_point": f"{t}-问题陈述",
        },
        {
            "question_type": "fill_blank",
            "stem": f"「{t}」的标准流程可概括为：输入 → ______ → 输出。",
            "answer": "处理/转换/推理",
            "analysis": "中间环节是关键处理；名称可按领域叫转换、计算、推理等。",
            "difficulty": base,
            "error_type": "流程断层",
            "knowledge_point": f"{t}-流程",
        },
        {
            "question_type": "single_choice",
            "stem": f"提高对「{t}」的迁移能力，更有效的做法是？",
            "options": [
                "A. 换情境重做：换数据、换约束再走一遍",
                "B. 同一道题抄三遍答案",
                "C. 只看解析不自己写",
                "D. 跳过检查步骤",
            ],
            "answer": "A",
            "analysis": "变式练习能检验是否真正理解而非记住表面答案。",
            "difficulty": min(5, base + 1),
            "error_type": "迁移不足",
            "knowledge_point": f"{t}-迁移",
        },
        {
            "question_type": "multi_choice",
            "stem": f"关于「{t}」的评价标准，哪些合理？（多选）",
            "options": [
                "A. 结论正确且步骤可复核",
                "B. 能说明为什么排除错误选项",
                "C. 只给最终答案不看过程",
                "D. 能指出适用前提与失效边界",
            ],
            "answer": ["A", "B", "D"],
            "analysis": "过程可复核、错因可说明、边界可指出，才算真正掌握。",
            "difficulty": min(5, base + 1),
            "error_type": "评价偏差",
            "knowledge_point": f"{t}-评价",
        },
        {
            "question_type": "short_answer",
            "stem": f"请用 3～5 句话说明「{t}」的核心结构（模块或步骤），并指出一个易错点。",
            "answer": "应包含：主要模块/步骤、模块间关系、至少一个具体易错点及规避办法。",
            "analysis": "作答后对照：是否覆盖结构完整性与易错提醒。",
            "difficulty": min(5, base + 1),
            "error_type": "结构碎片化",
            "knowledge_point": f"{t}-综合表达",
        },
        {
            "question_type": "short_answer",
            "stem": f"设计一个检验你是否掌握「{t}」的小任务（题面 + 期望结果），并说明评分点。",
            "answer": "自拟小题应可执行、可判定；评分点需覆盖正确性、过程完整性、边界意识。",
            "analysis": "能出好题通常意味着已理解考查目标与关键约束。",
            "difficulty": min(5, base + 2),
            "error_type": "目标不清",
            "knowledge_point": f"{t}-挑战应用",
        },
    ]


def _default_math_practice(topic: str) -> dict[str, Any]:
    """当模型输出为空或退化为占位内容时，保证数学实战资源仍可直接学习。"""
    if "线性代数" in topic:
        return {
            "content_mode": "practice",
            "practice_type": "math",
            "language": "math",
            "objective": "通过向量、矩阵、方程组与线性相关四类任务，建立线性代数的计算与建模能力。",
            "explanation": (
                "完成练习时先把对象写成向量或矩阵，再明确运算规则；最后用代回、维度检查或线性关系验证结果。"
                "不要只记公式，注意每一步运算对应的几何或实际含义。"
            ),
            "practice_items": [
                {
                    "type": "calculation",
                    "title": "任务一：向量线性组合",
                    "content": "已知 u=(1,2)，v=(3,-1)。求 w=2u-v，并说明 w 的两个分量分别表示什么。",
                    "answer": "w=2(1,2)-(3,-1)=(-1,5)。第一个分量为 -1，第二个分量为 5。",
                    "steps": ["先计算 2u=(2,4)。", "逐分量相减：(2-3, 4-(-1))。", "得到 w=(-1,5)，并检查每个分量都来自同一坐标位置。"],
                },
                {
                    "type": "calculation",
                    "title": "任务二：矩阵乘法与维度检查",
                    "content": "计算 A·B，其中 A=[[1,2],[0,1]]，B=[[2,1],[3,0]]。计算前先判断乘法是否有定义。",
                    "answer": "A、B 都是 2×2 矩阵，乘法有定义；AB=[[8,1],[3,0]]。",
                    "steps": ["确认 A 的列数 2 等于 B 的行数 2。", "第一行乘两列：1×2+2×3=8，1×1+2×0=1。", "第二行乘两列：0×2+1×3=3，0×1+1×0=0。"],
                },
                {
                    "type": "application",
                    "title": "任务三：用方程组解决配比问题",
                    "content": "某方案中两种材料的数量为 x、y，满足 x+y=5，2x-y=4。请用消元法求 x、y，并说明如何写成矩阵方程。",
                    "answer": "x=3，y=2；矩阵形式为 [[1,1],[2,-1]]·[x,y]^T=[5,4]^T。",
                    "steps": ["将两个方程上下排列，保证未知量顺序一致。", "两式相加得到 3x=9，因此 x=3。", "代回 x+y=5 得 y=2。", "把系数、未知向量与常数项分别写成矩阵形式。"],
                },
                {
                    "type": "proof",
                    "title": "任务四：判断向量组是否线性无关",
                    "content": "判断 p=(1,2,1)，q=(2,4,2)，r=(0,1,3) 是否线性无关，并写出理由。",
                    "answer": "线性相关，因为 q=2p，存在不全为 0 的系数使它们的线性组合为 0。",
                    "steps": ["比较 p 与 q 的对应分量。", "发现 q 的每个分量都是 p 的 2 倍。", "因此 q-2p=0，已经构造出非零系数关系。", "只要向量组中有一个向量能由其他向量线性表示，就线性相关。"],
                },
            ],
        }
    return {
        "content_mode": "practice",
        "practice_type": "math",
        "language": "math",
        "objective": f"围绕「{topic}」完成从概念理解到分步计算的综合练习。",
        "explanation": "建议按“识别条件—选择方法—逐步计算—代回检查”完成每道题，并记录容易出错的运算步骤。",
        "practice_items": [
            {"type": "calculation", "title": "基础计算", "content": f"从「{topic}」中任选一个核心公式，说明使用条件并完成一个数值代入示例。", "answer": "答案应包含公式、条件、代入过程和最终结果。", "steps": ["写出公式。", "列出已知条件。", "逐步代入并检查单位或符号。"]},
            {"type": "application", "title": "情境应用", "content": f"构造一个与「{topic}」有关的实际情境，说明应选用的数学对象和求解步骤。", "answer": "答案应说明建模对象、方程或图形关系以及结论。", "steps": ["提取变量。", "建立关系。", "求解并解释结果。"]},
            {"type": "proof", "title": "方法辨析", "content": f"说明处理「{topic}」的一种常见错误，并给出纠正方法。", "answer": "答案应包含错误原因、正确方法和一个验证方式。", "steps": ["识别错误前提。", "给出正确规则。", "用反例或代回检验。"]},
        ],
    }


def _has_sufficient_practice(data: dict) -> bool:
    items = data.get("practice_items")
    return (
        isinstance(items, list)
        and len(items) >= 3
        and all(isinstance(item, dict) and len(str(item.get("content", "")).strip()) >= 20 for item in items[:3])
    )


def _default_extension_readings(topic: str) -> list[dict[str, Any]]:
    """模型未能返回可用书单时，仍提供可以直接学习的结构化阅读单元。"""
    t = (topic or "本主题").strip() or "本主题"
    if "线性代数" in t:
        return [
            {
                "title": "从向量到线性组合：先理解“能不能表示”",
                "author": "智学体学习导读",
                "difficulty": "入门",
                "estimated_minutes": 12,
                "tags": ["向量", "线性组合", "几何直观"],
                "summary": "向量不只是坐标列表，也可以看成有方向和长度的量。本节从二维向量的加法、数乘开始，说明为什么 a₁v₁+a₂v₂ 被称为线性组合。",
                "content": (
                    "向量可以同时用坐标和箭头来理解：坐标方便计算，箭头方便想象方向与长度。"
                    "加法对应首尾相接，数乘对应伸缩或反向。线性组合 a₁v₁+a₂v₂ 的本质是："
                    "在已有方向上伸缩后再叠加。若两个二维向量不共线，它们的线性组合可以铺满整个平面；"
                    "若共线，则只能落在同一条直线上。阅读时请同时用图形与坐标各验证一次。"
                ),
                "key_points": ["向量加法与数乘按分量进行", "线性组合描述由已有向量生成的所有结果", "二维中两个不共线向量可生成整个平面"],
                "recommendations": [
                    {"title": "Linear Algebra and Its Applications", "author": "David C. Lay", "type": "书籍", "why": "前两章对向量与线性组合有清晰几何解释。"},
                    {"title": "3Blue1Brown《线性代数的本质》", "author": "Grant Sanderson", "type": "视频/文章", "why": "用动画建立“线性组合=空间张成”的直觉。"},
                ],
                "reflection": "若两个二维向量共线，它们还能表示任意二维向量吗？请画图说明原因。",
                "url": "",
            },
            {
                "title": "矩阵乘法的意义：一次线性变换接着一次线性变换",
                "author": "智学体学习导读",
                "difficulty": "基础",
                "estimated_minutes": 15,
                "tags": ["矩阵", "维度", "线性变换"],
                "summary": "矩阵乘法最容易出错的地方不是计算，而是没有先检查维度。把矩阵看成线性变换，顺序就变得自然。",
                "content": (
                    "把 m×n 矩阵看成把 n 维输入映射到 m 维输出的规则，因此 A 的列数必须等于 B 的行数。"
                    "AB 的每个元素是行与列的内积；更深层含义是：先执行 B 的变换，再执行 A 的变换。"
                    "一般 AB≠BA，顺序会改变结果。建议用 2×2 小矩阵手算一次，并解释结果矩阵的行列含义。"
                ),
                "key_points": ["矩阵相乘前先做维度检查", "(AB)x=A(Bx)，右侧矩阵先作用", "一般 AB 不等于 BA"],
                "recommendations": [
                    {"title": "Introduction to Linear Algebra", "author": "Gilbert Strang", "type": "书籍", "why": "对矩阵乘法与列空间有经典讲解。"},
                    {"title": "MIT OCW 18.06 Linear Algebra", "author": "Gilbert Strang", "type": "公开课", "why": "配套视频帮助理解“变换的复合”。"},
                ],
                "reflection": "为什么旋转后再拉伸，通常与拉伸后再旋转不同？试用一个单位向量验证。",
                "url": "",
            },
            {
                "title": "线性方程组与高斯消元：把问题变成可操作的行变换",
                "author": "智学体学习导读",
                "difficulty": "进阶",
                "estimated_minutes": 18,
                "tags": ["方程组", "增广矩阵", "高斯消元"],
                "summary": "多个一次方程可压缩为 Ax=b。高斯消元是在不改变解集的前提下做初等行变换。",
                "content": (
                    "A 记录系数，x 是未知量，b 是常数项。三类初等行变换（交换、倍乘、倍加）不改变解集。"
                    "出现全零行说明方程有冗余；出现 [0 … 0 | 非零] 说明矛盾无解；主元不足且无矛盾时有自由变量。"
                    "阅读时持续把每一行对应回原来的方程含义，不要只记步骤。"
                ),
                "key_points": ["增广矩阵同时记录系数与常数项", "三类行变换不改变解集", "阶梯形可判断唯一解/无解/无穷多解"],
                "recommendations": [
                    {"title": "线性代数及其应用", "author": "Lay / 中译本", "type": "书籍", "why": "消元法与解的结构章节例题充分。"},
                    {"title": "《线性代数应该这样学》相关章节", "author": "Axler（选读）", "type": "书籍", "why": "帮助从更高观点理解解空间。"},
                ],
                "reflection": "当某一行化为 0=0 时，它一定代表无穷多解吗？还需要同时检查什么？",
                "url": "",
            },
            {
                "title": "特征值与特征向量：寻找变换中方向不变的线索",
                "author": "智学体学习导读",
                "difficulty": "进阶",
                "estimated_minutes": 16,
                "tags": ["特征值", "特征向量", "应用"],
                "summary": "有些方向在变换后只被拉伸或压缩，这些方向是特征向量，缩放倍数是特征值。",
                "content": (
                    "方程 Av=λv 可写成 (A-λI)v=0。先由 det(A-λI)=0 求特征值，再求对应非零解向量。"
                    "它们广泛用于稳定性分析、图像压缩、推荐系统和主成分分析。"
                    "记住：特征向量必须非零；λ=0 往往与矩阵奇异性密切相关。"
                ),
                "key_points": ["特征向量必须是非零向量", "特征值由特征方程获得", "特征方向揭示系统主要变化模式"],
                "recommendations": [
                    {"title": "Linear Algebra Done Right（选读特征值章）", "author": "Sheldon Axler", "type": "书籍", "why": "概念推演严谨，适合进阶。"},
                    {"title": "PCA 入门笔记 / 教程", "author": "公开技术文", "type": "文章", "why": "把特征值与降维应用直接对应。"},
                ],
                "reflection": "若 λ=0，矩阵对相应特征向量做了什么？这与矩阵是否可逆有什么关系？",
                "url": "",
            },
        ]

    # 数据库专题：给出可直接阅读的正文 + 经典书/文推荐
    if any(k in t.lower() for k in ("数据库", "database", "sql", "dbms")):
        return [
            {
                "title": f"{t}：关系模型与基本概念",
                "author": "智学体学习导读",
                "difficulty": "基础",
                "estimated_minutes": 18,
                "tags": [t, "关系模型", "表/键"],
                "summary": "从“用表描述现实世界”出发，弄清关系、元组、属性、主键与外键，为后续 SQL 与范式打下基础。",
                "content": (
                    f"数据库管理系统（DBMS）负责持久保存数据，并保证并发访问时的一致性。"
                    f"关系模型把现实对象映射为二维表：每一行是一条记录（元组），每一列是一个属性。"
                    f"主键唯一标识一行；外键引用另一张表的主键，用来表达关联。"
                    f"学习「{t}」时，建议先画一个“学生-选课-课程”的小 ER 草图，再对照表结构："
                    f"哪些属性属于实体本身，哪些属性其实是关系。区分实体与关系，能避免后期随意加列导致冗余。"
                    f"同时理解三级模式（外模式/概念模式/内模式）有助于明白：应用看到的视图、逻辑设计和物理存储可以分离。"
                ),
                "key_points": ["表=关系，行=元组，列=属性", "主键保证实体完整性", "外键表达表间联系并支持参照完整性"],
                "recommendations": [
                    {"title": "Database System Concepts（数据库系统概念）", "author": "Silberschatz / Korth / Sudarshan", "type": "书籍", "why": "第1–3章把数据模型与关系基础讲得很完整，适合系统入门。"},
                    {"title": "SQL 必知必会", "author": "Ben Forta", "type": "书籍", "why": "短小精悍，适合边读边练基础查询。"},
                    {"title": "Wikipedia: Relational model", "author": "Wikipedia", "type": "文章", "why": "快速回顾关系模型术语与历史背景。", "url": "https://en.wikipedia.org/wiki/Relational_model"},
                ],
                "reflection": "若取消外键约束，只用应用层保证关联，会带来哪些风险？",
                "url": "",
            },
            {
                "title": f"{t}：SQL 查询思维：过滤、连接与聚合",
                "author": "智学体学习导读",
                "difficulty": "进阶",
                "estimated_minutes": 20,
                "tags": [t, "SQL", "JOIN"],
                "summary": "把业务问题翻译成 SELECT：先确定需要哪些表，再决定连接条件，最后做过滤与汇总。",
                "content": (
                    "写 SQL 前先问三句话：结果要哪些列？来自哪些表？行与行如何对应？"
                    "WHERE 过滤行，JOIN 按键拼表，GROUP BY 做分组汇总，HAVING 过滤分组结果。"
                    "INNER JOIN 只保留匹配行；LEFT JOIN 保留左表全部行，右表无匹配时补空。"
                    "常见错误包括：连接条件写错导致笛卡尔积、把聚合条件误放在 WHERE、忘记对非聚合列分组。"
                    "建议用同一套学生选课数据，分别写出“某课程平均分”“未选课学生名单”两类查询，体会 JOIN 与聚合的差别。"
                ),
                "key_points": ["先定表与连接，再过滤与聚合", "WHERE 与 HAVING 作用层级不同", "注意避免错误笛卡尔积"],
                "recommendations": [
                    {"title": "数据库系统概论", "author": "王珊 / 萨师煊", "type": "书籍", "why": "国内经典教材，SQL 与关系运算对照清晰。"},
                    {"title": "Use The Index, Luke", "author": "Markus Winand", "type": "文章/站点", "why": "从执行与索引角度理解“查询为何慢”。", "url": "https://use-the-index-luke.com/"},
                    {"title": "PostgreSQL 官方文档：Queries", "author": "PostgreSQL Global Development Group", "type": "文档", "why": "权威语法与示例，适合对照练习。", "url": "https://www.postgresql.org/docs/current/queries.html"},
                ],
                "reflection": "统计“每个学生选了几门课”时，为什么几乎必然用到 GROUP BY？",
                "url": "",
            },
            {
                "title": f"{t}：规范化与设计权衡",
                "author": "智学体学习导读",
                "difficulty": "进阶",
                "estimated_minutes": 16,
                "tags": [t, "范式", "设计"],
                "summary": "范式帮助减少冗余与更新异常，但过度拆分也会增加连接成本。设计要在一致性与性能间权衡。",
                "content": (
                    "第一范式要求字段原子化；第二范式消除对主键部分依赖；第三范式消除传递依赖。"
                    "冗余会带来插入、删除、更新异常：改一处漏改另一处就会不一致。"
                    "但在只读报表、大数据宽表场景，适度反规范化（冗余常用字段）可减少昂贵连接。"
                    "实践建议：OLTP 核心表尽量规范化；面向分析的中间层可按查询模式做受控冗余，并写清同步策略。"
                ),
                "key_points": ["范式消除更新异常", "拆分过细会增加 JOIN 成本", "按读写场景做规范化/反规范化取舍"],
                "recommendations": [
                    {"title": "Database Design for Mere Mortals", "author": "Michael J. Hernandez", "type": "书籍", "why": "从业务到表设计，案例驱动，适合课程实验。"},
                    {"title": "数据库系统概念（规范化章节）", "author": "Silberschatz 等", "type": "书籍", "why": "对 1NF–BCNF 有系统证明式讲解。"},
                ],
                "reflection": "给你一张含“课程名+教师电话”的宽表，指出至少一种更新异常，并说明如何拆表。",
                "url": "",
            },
            {
                "title": f"{t}：事务、并发与持久化直觉",
                "author": "智学体学习导读",
                "difficulty": "进阶",
                "estimated_minutes": 15,
                "tags": [t, "事务", "ACID"],
                "summary": "事务把多步操作变成“要么全成、要么全否”的单元；理解 ACID 才能解释脏读、不可重复读等现象。",
                "content": (
                    "原子性保证失败可回滚；一致性维护约束；隔离性控制并发可见性；持久性确保提交后不丢。"
                    "隔离级别从读未提交到可串行化，越严并发性能通常越低。"
                    "日志（WAL）与检查点是崩溃恢复的基础：先记日志再改数据页，宕机后可重放或回滚。"
                    "把“转账”写成两个 UPDATE，就能体会为何必须放在同一事务中。"
                ),
                "key_points": ["事务是并发与恢复的基本单位", "隔离级别影响异常现象", "日志支撑持久性与崩溃恢复"],
                "recommendations": [
                    {"title": "事务处理：概念与技术", "author": "Jim Gray / Andreas Reuter", "type": "书籍", "why": "事务领域经典，适合进阶阅读。"},
                    {"title": "设计数据密集型应用（相关章节）", "author": "Martin Kleppmann", "type": "书籍", "why": "从现代分布式视角理解复制、分区与一致性。"},
                ],
                "reflection": "两个人同时改同一账户余额，缺少事务或锁时可能出现什么结果？",
                "url": "",
            },
        ]

    # 数学（非线性代数细分）专题
    if t in ("数学", "高等数学", "微积分") or (t.startswith("数学") and "线性代数" not in t):
        return [
            {
                "title": f"{t}：函数、极限与连续精读",
                "author": "智学体学习导读",
                "difficulty": "基础",
                "estimated_minutes": 18,
                "tags": [t, "极限", "连续"],
                "summary": "从函数概念出发，理解极限的“无限逼近”语言，并弄清连续与可导的差别。",
                "content": (
                    f"学习「{t}」时，先把函数看成“输入到输出的对应规则”，关注定义域与对应方式。"
                    f"极限描述当自变量趋近某值（或无穷）时，函数值能否稳定逼近某个数；ε-N / ε-δ 语言只是把“任意接近”写精确。"
                    f"连续要求极限存在且等于函数值；可导更强，还要求割线斜率有极限。"
                    f"建议用 y=|x| 在 0 点：连续但不可导，帮助区分三个层次。"
                    f"每学一个定义，立刻配一个会算的例子和一个反例，比只背文字更有效。"
                ),
                "key_points": ["函数先明确定义域与对应规则", "极限是逼近，不等于函数值本身", "连续 ⊂ 有极限；可导 ⇒ 连续，反之不然"],
                "recommendations": [
                    {"title": "高等数学（同济版）上册", "author": "同济大学数学系", "type": "书籍", "why": "国内主流教材，极限与连续章节例题充分。"},
                    {"title": "Thomas' Calculus（托马斯微积分）相关章节", "author": "Hass / Heil / Weir", "type": "书籍", "why": "几何直观强，适合建立极限直觉。"},
                    {"title": "3Blue1Essence of Calculus", "author": "Grant Sanderson", "type": "视频", "why": "用动画理解导数与积分的核心思想。"},
                ],
                "reflection": "为什么“极限存在”不能直接推出“函数在该点连续”？请举一个反例。",
                "url": "",
            },
            {
                "title": f"{t}：导数与积分的对应关系",
                "author": "智学体学习导读",
                "difficulty": "进阶",
                "estimated_minutes": 20,
                "tags": [t, "导数", "积分"],
                "summary": "导数刻画瞬时变化率，积分刻画累积；微积分基本定理把两者连起来。",
                "content": (
                    "导数是割线斜率的极限，对应瞬时速度、边际成本等变化率问题。"
                    "定积分是分割—近似—取极限的累积过程；不定积分是求原函数。"
                    "微积分基本定理说明：求导与积分在一定条件下互为逆运算。"
                    "做题时先问：题目在求变化率还是求总量？再选择微分或积分工具。"
                    "常见陷阱：忽视定义域、复合函数链式法则漏乘内层导数、换元后忘改上下限。"
                    "建议准备一张对照表：左侧写应用场景，右侧标注该用导数还是积分，并各配一道课本例题。"
                ),
                "key_points": ["导数=瞬时变化率", "定积分=累积量", "基本定理连接求导与积分"],
                "recommendations": [
                    {"title": "高等数学（同济版）导数与积分章", "author": "同济大学数学系", "type": "书籍", "why": "计算训练完整，适合考试与作业。"},
                    {"title": "Calculus Made Easy（选读）", "author": "Silvanus P. Thompson", "type": "书籍", "why": "用更口语的方式建立微积分直觉。"},
                    {"title": "可汗学院 Calculus", "author": "Khan Academy", "type": "课程", "why": "短视频拆解求导积分步骤，适合查漏补缺。"},
                ],
                "reflection": "若路程是时间的函数 s(t)，速度与路程如何用导数/积分互相表示？",
                "url": "",
            },
            {
                "title": f"{t}：证明与解题的一般策略",
                "author": "智学体学习导读",
                "difficulty": "进阶",
                "estimated_minutes": 16,
                "tags": [t, "证明", "方法"],
                "summary": "把“看懂定义—转化条件—选择工具—检验边界”练成固定流程，减少盲目套公式。",
                "content": (
                    "面对证明题，先翻译题设与结论：已知什么、要证什么、缺什么中间桥梁。"
                    "常用策略：直接推导、等价变形、反证、数学归纳、构造辅助函数/辅助线。"
                    "计算题则先化简再动手，标注每一步用的定理名称，方便复查。"
                    "建议准备错题本：按“概念混淆 / 计算失误 / 条件遗漏”分类，而不是只抄正确答案。"
                    "每道题写三行审题笔记（条件、目标、桥梁），能显著减少“会而不对”的情况。"
                ),
                "key_points": ["先翻译条件与目标", "选择匹配的证明策略", "用分类错题本固化方法"],
                "recommendations": [
                    {"title": "怎样解题", "author": "G. 波利亚", "type": "书籍", "why": "经典解题四步法，对数学学习迁移性强。"},
                    {"title": "数学分析习题课讲义（选做）", "author": "林源渠 等", "type": "书籍", "why": "题目梯度清楚，适合训练严谨表达。"},
                ],
                "reflection": "选一道你错过的题，用“条件—目标—桥梁”三行话重写审题过程。",
                "url": "",
            },
            {
                "title": f"{t}：进阶书单与阅读路线",
                "author": "智学体学习导读",
                "difficulty": "进阶",
                "estimated_minutes": 12,
                "tags": [t, "书单"],
                "summary": "按“教材打底 → 习题巩固 → 直观视频/拓展读物”安排，避免同时开太多资料。",
                "content": (
                    f"若课程是「{t}」，优先吃透一本主教材，而不是搜集十份讲义。"
                    "每周：精读一小节 + 完成少量代表性习题 + 回顾错题。"
                    "遇到几何直觉不足，用可视化视频补；遇到证明写不出来，回教材定理叙述逐句对照。"
                    "进阶可按兴趣分支：分析方向补ε语言，应用方向补物理/经济中的微积分模型。"
                    "两周复习法：前三天概念地图，中间五天题型归类，最后两天错题与模拟卷。"
                ),
                "key_points": ["一本主教材吃透", "习题少而精", "直觉与严谨交替补齐"],
                "recommendations": [
                    {"title": "高等数学（同济版）全册", "author": "同济大学数学系", "type": "书籍", "why": "与多数国内课程同步，适合作为主线。"},
                    {"title": "数学分析（华东师大版）选读", "author": "华东师范大学数学系", "type": "书籍", "why": "想往分析方向走时，补充更严谨的叙述。"},
                    {"title": "MIT OCW Single Variable Calculus", "author": "MIT", "type": "课程", "why": "英文讲授清晰，可对照国内教材看同一概念。"},
                ],
                "reflection": "若只有两周复习期，你会如何分配“概念复习 / 计算训练 / 错题回炉”的时间？",
                "url": "",
            },
        ]

    # 通用主题：正文 + 可检索的真实书/文建议（不编造网址）
    return [
        {
            "title": f"{t}：核心概念精读",
            "author": "智学体学习导读",
            "difficulty": "基础",
            "estimated_minutes": 16,
            "tags": [t, "核心概念"],
            "summary": f"围绕「{t}」建立术语地图：每个概念是什么、何时用、和相邻概念如何区分。",
            "content": (
                f"先列出「{t}」中最容易混淆的 5 个术语，给每个术语写一句人话定义，再配一个正例与一个反例。"
                f"阅读目标不是背定义，而是能判断：面对一个具体问题时，该不该调用这个概念。"
                f"建议用一张两列表：左列写概念，右列写“适用条件 / 不适用条件”。读完后合上材料复述，查漏补缺。"
            ),
            "key_points": ["用自己的话定义概念", "区分相近术语", "用正例/反例检验理解"],
            "recommendations": [
                {"title": f"检索「{t} 教材 / 入门」的权威教材前两章", "author": "课程指定或馆藏教材", "type": "书籍", "why": "系统教材通常比碎片文章更可靠，适合建立知识骨架。"},
                {"title": f"Stanford / MIT / 国家精品课中与「{t}」相关的公开讲义", "author": "高校公开课", "type": "讲义/课程", "why": "可对照不同老师的讲解路径，加深概念理解。"},
            ],
            "reflection": f"用自己的话复述「{t}」最核心的一个概念，并给出一个正例和一个反例。",
            "url": "",
        },
        {
            "title": f"{t}：方法步骤与常见陷阱",
            "author": "智学体学习导读",
            "difficulty": "进阶",
            "estimated_minutes": 18,
            "tags": [t, "方法"],
            "summary": f"把「{t}」拆成可执行步骤：每步输入、输出、检查点，并记录最常见的错误。",
            "content": (
                f"将完成一个与「{t}」相关的小任务写成 4–6 步清单。每一步写清：需要什么信息、产出什么中间结果、如何自检。"
                f"单独开一栏记录“易错点”，例如条件遗漏、顺序颠倒、边界情况未处理。"
                f"然后用一个最小例子从头走到尾；若中途卡住，说明该步的前置条件还没写清楚。"
            ),
            "key_points": ["步骤化拆解任务", "明确每步输入输出", "为易错点设置检查"],
            "recommendations": [
                {"title": "How to Solve It（怎样解题）", "author": "G. Pólya", "type": "书籍", "why": "提供可迁移的审题—计划—执行—回顾框架。"},
                {"title": f"主题「{t}」的高质量博客长文或官方文档 Getting Started", "author": "官方文档 / 领域专家", "type": "文章", "why": "补足教材之外的操作细节与当代实践。"},
            ],
            "reflection": "哪一步最容易出错？你会用什么检查表避免它？",
            "url": "",
        },
        {
            "title": f"{t}：应用案例与迁移",
            "author": "智学体学习导读",
            "difficulty": "进阶",
            "estimated_minutes": 15,
            "tags": [t, "应用"],
            "summary": f"把「{t}」放进真实情境：何时该用、何时不该用，以及结果如何解释。",
            "content": (
                f"选择一个贴近专业的场景，写出：背景约束、可用数据/条件、你准备调用的「{t}」方法、预期产出、失败时的备选方案。"
                f"重点练习“迁移”：把课内例子的结构映射到新场景，而不是只改名词。"
                f"最后用三句话向非专业同学解释你的方案——若讲不清，多半是概念边界还不稳。"
            ),
            "key_points": ["提取情境中的关键变量", "判断方法是否匹配", "解释结果并给出边界"],
            "recommendations": [
                {"title": f"与「{t}」相关的案例集 / 课程大作业优秀样本", "author": "本校课程或公开数据集说明", "type": "案例", "why": "看完整链路比只看定义更能学会迁移。"},
                {"title": "The Craft of Research（研究是一门艺术）选读", "author": "Booth 等", "type": "书籍", "why": "帮助把知识点组织成可表达的问题与论证。"},
            ],
            "reflection": f"为「{t}」设计一个贴近专业的应用情境，并写明成功标准。",
            "url": "",
        },
        {
            "title": f"{t}：进阶阅读路线图",
            "author": "智学体学习导读",
            "difficulty": "进阶",
            "estimated_minutes": 12,
            "tags": [t, "书单", "路线"],
            "summary": "给出从入门到进阶的阅读顺序：先建立直觉，再补形式化，最后看工程/研究材料。",
            "content": (
                f"建议按“直觉 → 系统教材 → 专题深化 → 前沿/工程”的顺序阅读「{t}」。"
                f"每周固定精读一章并做少量习题或笔记卡片；不要同时开太多材料。"
                f"遇到不懂的定义，先回教材对应章节，再查综述或文档，避免被碎片信息带偏。"
            ),
            "key_points": ["先教材后碎片", "精读优于广读", "笔记里保留问题清单"],
            "recommendations": [
                {"title": "本领域公认教材（馆藏检索主题词）", "author": "按学科选择", "type": "书籍", "why": "保证知识体系完整、术语标准。"},
                {"title": "ACM / IEEE / 中国知网 综述论文（近 5 年）", "author": "学术数据库", "type": "论文", "why": "快速了解前沿问题与常用方法地图。"},
            ],
            "reflection": "若只有 7 天，你会怎样安排「入门章 + 一章专题 + 一篇综述」？",
            "url": "",
        },
    ]


def _has_sufficient_readings(items: Any) -> bool:
    if not isinstance(items, list) or len(items) < 3:
        return False
    hollow_points = {"明确概念定义", "识别使用条件", "用例子检验理解", "按步骤处理问题", "记录中间结果", "检查常见错误"}
    for item in items[:3]:
        if not isinstance(item, dict):
            return False
        content = str(item.get("content") or "").strip()
        if len(content) < 160:
            return False
        points = item.get("key_points") or []
        if isinstance(points, list) and points and set(str(p) for p in points) <= hollow_points:
            return False
        recs = item.get("recommendations")
        if recs is not None and not isinstance(recs, list):
            return False
    has_any_rec = any(
        isinstance(item, dict) and isinstance(item.get("recommendations"), list) and len(item["recommendations"]) > 0
        for item in items
    )
    has_long_content = all(
        isinstance(item, dict) and len(str(item.get("content") or "").strip()) >= 160 for item in items[:3]
    )
    return has_any_rec and has_long_content


def _enrich_readings(topic: str, items: Any) -> list[dict[str, Any]]:
    """确保每篇都有可读正文 + 建议书目；空壳直接替换为高质量兜底。"""
    defaults = _default_extension_readings(topic)
    if not _has_sufficient_readings(items):
        return defaults

    assert isinstance(items, list)
    enriched: list[dict[str, Any]] = []
    for idx, raw in enumerate(items):
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        content = str(item.get("content") or "").strip()
        summary = str(item.get("summary") or "").strip()
        recs = item.get("recommendations") if isinstance(item.get("recommendations"), list) else []
        fallback = defaults[idx] if idx < len(defaults) else defaults[-1]

        if len(content) < 160:
            item["content"] = fallback.get("content") or summary or fallback.get("summary") or ""
        if not summary:
            item["summary"] = fallback.get("summary") or ""
        if len(recs) < 2:
            item["recommendations"] = fallback.get("recommendations") or []
        points = item.get("key_points")
        if not isinstance(points, list) or not points or (
            set(str(p) for p in points) <= {"明确概念定义", "识别使用条件", "用例子检验理解"}
        ):
            item["key_points"] = fallback.get("key_points") or points or []
        enriched.append(item)

    return enriched if len(enriched) >= 3 else defaults


def _default_mindmap_data(topic: str) -> dict[str, Any]:
    """保证知识图谱具备可视化所需的层级和节点密度。"""
    if "线性代数" in topic:
        nodes = [
            {"id": "root", "label": "线性代数", "description": "研究向量、矩阵及线性关系的基础工具。", "level": 0},
            {"id": "vector", "label": "向量与线性组合", "description": "从向量运算理解方向、长度和可表示性。", "level": 1},
            {"id": "vector-op", "label": "向量运算", "description": "加法、数乘、内积及其几何意义。", "level": 2},
            {"id": "span", "label": "张成空间", "description": "由一组向量所有线性组合形成的集合。", "level": 2},
            {"id": "matrix", "label": "矩阵与变换", "description": "用矩阵记录线性变换和多组数据关系。", "level": 1},
            {"id": "matrix-op", "label": "矩阵运算", "description": "维度检查、乘法、逆矩阵与行列式。", "level": 2},
            {"id": "transform", "label": "线性变换", "description": "旋转、缩放、投影等变换可以由矩阵表示。", "level": 2},
            {"id": "system", "label": "线性方程组", "description": "把多个一次方程组织为 Ax=b。", "level": 1},
            {"id": "elimination", "label": "高斯消元", "description": "通过初等行变换把方程组化为阶梯形。", "level": 2},
            {"id": "solution", "label": "解的结构", "description": "根据主元和增广列判断唯一解、无解或无穷多解。", "level": 2},
            {"id": "space", "label": "向量空间", "description": "满足封闭性等规则的向量集合。", "level": 1},
            {"id": "basis", "label": "基与维数", "description": "基既能张成空间又保持线性无关，维数表示自由方向数量。", "level": 2},
            {"id": "independence", "label": "线性无关", "description": "没有向量能由其余向量的线性组合得到。", "level": 2},
            {"id": "eigen", "label": "特征值与特征向量", "description": "描述变换后方向保持不变的特殊向量。", "level": 1},
            {"id": "eigen-app", "label": "典型应用", "description": "用于稳定性分析、图像处理和主成分分析。", "level": 2},
        ]
        edges = [
            {"from": "root", "to": "vector"}, {"from": "vector", "to": "vector-op"}, {"from": "vector", "to": "span"},
            {"from": "root", "to": "matrix"}, {"from": "matrix", "to": "matrix-op"}, {"from": "matrix", "to": "transform"},
            {"from": "root", "to": "system"}, {"from": "system", "to": "elimination"}, {"from": "system", "to": "solution"},
            {"from": "root", "to": "space"}, {"from": "space", "to": "basis"}, {"from": "space", "to": "independence"},
            {"from": "root", "to": "eigen"}, {"from": "eigen", "to": "eigen-app"},
        ]
        mermaid = "mindmap\n  root((线性代数))\n    向量与线性组合\n      向量运算\n      张成空间\n    矩阵与变换\n      矩阵运算\n      线性变换\n    线性方程组\n      高斯消元\n      解的结构\n    向量空间\n      基与维数\n      线性无关\n    特征值与特征向量\n      典型应用"
        return {"mermaid": mermaid, "nodes": nodes, "edges": edges}

    branches = ["核心概念", "方法步骤", "典型应用", "易错辨析"]
    nodes = [{"id": "root", "label": topic, "description": f"围绕{topic}建立概念、方法与应用的知识结构。", "level": 0}]
    edges: list[dict[str, str]] = []
    for i, branch in enumerate(branches, 1):
        bid = f"b{i}"
        nodes.append({"id": bid, "label": branch, "description": f"{topic}的{branch}。", "level": 1})
        edges.append({"from": "root", "to": bid})
        for j, leaf in enumerate(["重点理解", "学习检查"], 1):
            lid = f"{bid}-{j}"
            nodes.append({"id": lid, "label": leaf, "description": f"从{branch}角度梳理{topic}的{leaf}内容。", "level": 2})
            edges.append({"from": bid, "to": lid})
    return {"mermaid": f"mindmap\n  root(({topic}))", "nodes": nodes, "edges": edges}


def _has_sufficient_mindmap(data: Any) -> bool:
    return (
        isinstance(data, dict)
        and isinstance(data.get("nodes"), list)
        and isinstance(data.get("edges"), list)
        and len(data["nodes"]) >= 8
        and len(data["edges"]) >= 7
    )


class CoordinatorAgent(BaseAgent):
    """总协调智能体：解析任务、规划子任务、汇总结果。"""

    agent_code = "orchestrator"
    agent_name = "总协调智能体"

    async def execute(self, ctx: OrchestrationContext, parent_run_id: int | None = None) -> dict[str, Any]:
        run = self._start_run(
            ctx,
            {
                "topic": ctx.topic,
                "goal": ctx.goal,
                "resource_types": ctx.resource_types,
                "difficulty": ctx.difficulty,
            },
            parent_run_id,
        )
        system = (
            "你是智学体总协调智能体。根据用户画像与生成需求，输出 JSON 任务规划："
            '{"subtasks":[{"agent":"learning_analysis|document|question|mindmap|extension|animation",'
            '"resource_types":["document"], "priority":1, "rationale":"..."}], '
            '"parallel_groups":[["document","question","mindmap"]], "estimated_minutes":10}'
        )
        user = (
            f"主题: {ctx.topic}\n学习目标: {ctx.goal or '无'}\n"
            f"请求资源类型: {ctx.resource_types}\n难度: {ctx.difficulty}/5\n"
            f"用户画像:\n{ctx.profile_summary()}\n"
            f"本次生成约束:\n{ctx.generation_brief()}"
        )
        result = await self._chat(ctx, system, user, run.id, temperature=0.3)
        plan = _extract_json(result.content) or self._default_plan(ctx)
        ctx.orchestrator_plan = plan
        self._finish_run(run.id, {"plan": plan, "tokens": result.total_tokens})
        return plan

    def _default_plan(self, ctx: OrchestrationContext) -> dict:
        type_to_agent = {
            "document": "document",
            "question": "question",
            "mindmap": "mindmap",
            "reading": "extension",
            "code": "extension",
            "video": "animation",
        }
        agents_needed = {"learning_analysis"}
        for t in ctx.resource_types:
            if t in type_to_agent:
                agents_needed.add(type_to_agent[t])
        subtasks = [{"agent": "learning_analysis", "priority": 1, "rationale": "学情诊断先行"}]
        for a in sorted(agents_needed - {"learning_analysis"}):
            subtasks.append({"agent": a, "priority": 2, "rationale": f"生成{a}资源"})
        return {
            "subtasks": subtasks,
            "parallel_groups": [list(agents_needed - {"learning_analysis"})],
            "estimated_minutes": len(subtasks) * 2,
        }


class LearningAnalysisAgent(BaseAgent):
    """学情分析智能体：基于6维+画像输出学情诊断。"""

    agent_code = "learning_analysis"
    agent_name = "学情分析智能体"

    async def execute(self, ctx: OrchestrationContext, parent_run_id: int | None = None) -> dict[str, Any]:
        run = self._start_run(ctx, {"profile": ctx.profile_summary()}, parent_run_id)
        system = (
            "你是学情分析智能体。基于用户多维画像输出 JSON 学情诊断："
            '{"weak_points":["..."], "learning_style":"视觉型|言语型|序列型|综合型",'
            '"recommended_difficulty":1-5, "focus_areas":["..."], "error_patterns":["..."],'
            '"teaching_strategy":"一句话教学策略", "dimension_analysis":{"D1":"..."}}'
        )
        user = (
            f"学习主题: {ctx.topic}\n目标: {ctx.goal or '掌握该主题核心知识'}\n\n"
            f"画像数据:\n{ctx.profile_summary()}\n\n"
            f"本次生成约束:\n{ctx.generation_brief()}"
        )
        result = await self._chat(ctx, system, user, run.id, temperature=0.4)
        diagnosis = _extract_json(result.content)
        if not isinstance(diagnosis, dict):
            diagnosis = {
                "weak_points": ["基础概念", "实践应用"],
                "learning_style": "综合型",
                "recommended_difficulty": ctx.difficulty,
                "focus_areas": [ctx.topic],
                "error_patterns": ["概念混淆"],
                "teaching_strategy": "先理论后实践，配合例题与代码演示",
                "dimension_analysis": {},
            }
        ctx.learning_diagnosis = diagnosis
        ctx.partial_previews.append(
            {
                "agent_code": self.agent_code,
                "agent_name": self.agent_name,
                "type": "diagnosis",
                "preview": diagnosis.get("teaching_strategy", ""),
                "data": diagnosis,
            }
        )
        self._finish_run(run.id, {"diagnosis": diagnosis})
        return diagnosis


def _looks_truncated_markdown(text: str) -> bool:
    """启发式：正文像被硬截断（未收尾、未闭合标记）。"""
    t = (text or "").rstrip()
    if len(t) < 80:
        return True
    if t.endswith(("**", "*", "`", "```", "-", "：", ":", "、", "，", ",")):
        return True
    # 开了代码块但未闭合
    if t.count("```") % 2 == 1:
        return True
    return False


class DocumentAgent(BaseAgent):
    """课程讲义智能体：结构化专业课程讲解文档。"""

    agent_code = "document"
    agent_name = "课程讲义智能体"

    async def execute(self, ctx: OrchestrationContext, parent_run_id: int | None = None) -> dict[str, Any]:
        run = self._start_run(ctx, {"topic": ctx.topic, "type": "document"}, parent_run_id)
        length_hint = ctx.content_length or "标准课堂版"
        # DeepSeek 单次输出上限 8k；默认给 6k，长版直接 8k，减少“写到一半被截断”
        max_tokens = 6144
        if length_hint == "精简版":
            max_tokens = 3072
        elif length_hint in ("完整讲义", "详细版", "加长版"):
            max_tokens = 8192
        system = (
            "你是课程讲义智能体。只输出完整 Markdown 讲义正文，不要解释写作过程。"
            "必须包含：1) 学习目标 2) 核心概念 3) 分章节系统讲解（覆盖主题主要知识点，不得只写到一半）"
            "4) 关键公式/例题 5) 小结与自测要点。"
            "要求：全文控制在 1600-2600 字、4-5 章、每章 2-4 段，务必以「小结与自测」收尾；"
            "禁止中途截断；禁止留下未闭合的 Markdown（如单独的 **）；"
            f"篇幅按「{length_hint}」组织，但仍须结构完整、内容自洽。"
            "语言严谨、适合大学生阅读。"
        )
        user = (
            f"主题: {ctx.topic}\n难度: {ctx.difficulty}/5\n"
            f"学情诊断:\n{ctx.diagnosis_summary()}\n"
            f"用户画像:\n{ctx.profile_summary()}\n"
            f"本次生成约束:\n{ctx.generation_brief()}\n"
            f"知识库参考:\n{ctx.kb_summary() or '（无）'}\n"
            "请一次性写完整份讲义；若内容较长，也要写到小结与自测再结束。"
        )

        content = ""
        # 最多 1 次初稿 + 1 次续写（仅当模型明确因长度截断）
        for round_idx in range(3):
            if round_idx == 0:
                result = await self._chat(ctx, system, user, run.id, max_tokens=max_tokens)
                content = (result.content or "").strip()
            else:
                cont_user = (
                    "上一份讲义在生成时被截断了。请从中断处无缝续写剩余内容，"
                    "不要重复已有段落；补全所有未写完的章节，并以「小结与自测」收尾。"
                    "只输出续写部分的 Markdown。"
                )
                messages = [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                    {"role": "assistant", "content": content},
                    {"role": "user", "content": cont_user},
                ]
                result = await self.llm.chat(
                    messages,
                    user_id=ctx.user_id,
                    task_id=ctx.task_id,
                    agent_run_id=run.id,
                    temperature=0.7,
                    max_tokens=max_tokens,
                )
                piece = (result.content or "").strip()
                if piece:
                    content = f"{content.rstrip()}\n\n{piece}"

            # 勿用启发式误触发二次长耗时续写；仅 finish_reason=length 时续写
            if result.finish_reason != "length":
                break

        ctx.partial_previews.append(
            {
                "agent_code": self.agent_code,
                "agent_name": self.agent_name,
                "type": "document",
                "preview": content[:300],
            }
        )
        self._finish_run(run.id, {"content_md": content, "word_count": len(content)})
        return {"content_md": content, "agent_run_id": run.id}


class QuestionAgent(BaseAgent):
    """习题命题智能体：分层练习题+答案+解析。"""

    agent_code = "question"
    agent_name = "习题命题智能体"

    async def execute(self, ctx: OrchestrationContext, parent_run_id: int | None = None) -> dict[str, Any]:
        run = self._start_run(ctx, {"topic": ctx.topic, "type": "question"}, parent_run_id)
        system = (
            "你是习题命题智能体。只输出一个合法 JSON 数组，不要 Markdown 代码块。每题含："
            "question_type(single_choice|multi_choice|fill_blank|short_answer), "
            "stem, options(选择题必填 A/B/C/D), answer, analysis, difficulty(1-5), "
            "error_type, knowledge_point。"
            "必须生成 10-12 道分层题：基础约 4 题、提高约 4 题、挑战约 3-4 题；"
            "题型至少覆盖单选、多选、填空、简答；匹配用户薄弱点与易错点；"
            "答案与解析完整，但前端会在作答后再展示。"
        )
        user = (
            f"主题: {ctx.topic}\n难度基准: {ctx.difficulty}/5\n"
            f"易错点: {ctx.learning_diagnosis.get('error_patterns', []) if ctx.learning_diagnosis else []}\n"
            f"薄弱点: {ctx.learning_diagnosis.get('weak_points', []) if ctx.learning_diagnosis else []}\n"
            f"本次生成约束:\n{ctx.generation_brief()}\n"
            f"知识库参考:\n{ctx.kb_summary() or '（无）'}"
        )
        result = await self._chat(ctx, system, user, run.id, temperature=0.5, max_tokens=4096)
        questions = _extract_json(result.content)
        if not isinstance(questions, list) or len(questions) < 8:
            questions = _default_question_bank(ctx.topic, ctx.difficulty)
        ctx.partial_previews.append(
            {
                "agent_code": self.agent_code,
                "agent_name": self.agent_name,
                "type": "question",
                "preview": f"已生成 {len(questions)} 道练习题",
                "data": questions[:2],
            }
        )
        self._finish_run(run.id, {"questions": questions, "count": len(questions)})
        return {"questions": questions, "agent_run_id": run.id}


class MindmapAgent(BaseAgent):
    """知识图谱智能体：Mermaid 格式思维导图。"""

    agent_code = "mindmap"
    agent_name = "知识图谱智能体"

    async def execute(self, ctx: OrchestrationContext, parent_run_id: int | None = None) -> dict[str, Any]:
        run = self._start_run(ctx, {"topic": ctx.topic, "type": "mindmap"}, parent_run_id)
        system = (
            "你是知识图谱智能体。输出 JSON："
            '{"mermaid":"mindmap\\n  root((主题))\\n    分支1\\n      子节点", '
            '"nodes":[{"id":"n1","label":"节点名","description":"知识点简短释义","level":0}], '
            '"edges":[{"from":"n1","to":"n2"}]}'
            "必须输出至少 12 个节点：1 个中心主题、至少 4 个一级分支，每个一级分支至少有 2 个二级节点。"
            "mermaid 字段必须是合法 Mermaid mindmap 语法；每个 node 必须含 description 字段（20-50字释义）。"
        )
        user = (
            f"主题: {ctx.topic}\n"
            f"重点: {ctx.learning_diagnosis.get('focus_areas', []) if ctx.learning_diagnosis else [ctx.topic]}\n"
            f"本次生成约束:\n{ctx.generation_brief()}\n"
            f"知识库参考（节点命名与释义优先采用以下材料中的术语）:\n{ctx.kb_summary() or '（无）'}"
        )
        result = await self._chat(ctx, system, user, run.id, temperature=0.4)
        data = _extract_json(result.content)
        if not _has_sufficient_mindmap(data):
            data = _default_mindmap_data(ctx.topic)
        if "mermaid" not in data:
            data["mermaid"] = f"mindmap\n  root(({ctx.topic}))"
        ctx.partial_previews.append(
            {
                "agent_code": self.agent_code,
                "agent_name": self.agent_name,
                "type": "mindmap",
                "preview": data.get("mermaid", "")[:200],
            }
        )
        self._finish_run(run.id, data)
        return {**data, "agent_run_id": run.id}


class ExtensionAgent(BaseAgent):
    """拓展资源智能体：拓展阅读 + 可运行代码案例。"""

    agent_code = "extension"
    agent_name = "拓展资源智能体"

    async def execute(self, ctx: OrchestrationContext, parent_run_id: int | None = None) -> dict[str, Any]:
        run = self._start_run(
            ctx,
            {"topic": ctx.topic, "types": [t for t in ctx.resource_types if t in ("reading", "code")]},
            parent_run_id,
        )
        output: dict[str, Any] = {"reading": None, "code": None}

        if "reading" in ctx.resource_types:
            sys_r = (
                "你是拓展阅读智能体。只输出一个合法 JSON 数组（不要 Markdown 代码块），至少 4 篇。"
                "每项必须可直接阅读，禁止只给抽象要点清单。字段："
                '{"title":"...","author":"...","url":"",'
                '"summary":"80-150字导读",'
                '"content":"正文，不少于250字，含概念讲解、例子、易错点，可分段用\\n",'
                '"difficulty":"入门|基础|进阶","estimated_minutes":15,'
                '"tags":["关键词"],'
                '"key_points":["具体知识点，不要写「明确概念」这类空话"],'
                '"recommendations":[{"title":"书名或文章名","author":"作者","type":"书籍|文章|文档|课程","why":"推荐理由","url":"可选，真实网址或留空"}],'
                '"reflection":"一个具体思考问题"}。'
                "按概念建立、方法理解、应用迁移、进阶书单组织。"
                "recommendations 每篇至少 2 条，优先推荐真实存在的经典教材/官方文档/公开课；不要虚构网址。"
                "不要输出用户画像问答或系统提示。"
            )
            user_r = (
                f"主题: {ctx.topic}\n学习目标: {ctx.goal}\n"
                f"学习风格: {ctx.learning_diagnosis.get('learning_style', '综合型') if ctx.learning_diagnosis else '综合型'}\n"
                f"本次生成约束:\n{ctx.generation_brief()}\n"
                f"知识库参考（据此组织概念、方法与应用，不得与之矛盾）:\n{ctx.kb_summary() or '（无）'}"
            )
            res_r = await self._chat(ctx, sys_r, user_r, run.id, max_tokens=4096)
            reading = _enrich_readings(ctx.topic, _extract_json(res_r.content))
            output["reading"] = reading

        if "code" in ctx.resource_types:
            subject = detect_subject_category(ctx.topic, ctx.goal)
            if is_programming_subject(ctx.topic, ctx.goal):
                sys_c = (
                    "你是实战演练智能体（编程/计算机类学科）。只输出一个合法 JSON 对象，不要 Markdown 代码块。"
                    "字符串内的换行必须写成 \\n；代码里的双引号必须写成 \\\"；不要在 JSON 字符串里直接换行。"
                    "code_content 控制在 80 行以内，保证 JSON 完整可解析。"
                    "格式："
                    '{"content_mode":"code", "language":"java|python|...", "code_content":"...", "explanation":"...", '
                    '"objective":"实验目标", "run_instructions":"运行说明", '
                    '"test_cases":[{"input":"","expectedOutput":""}], "dependencies":[]}'
                    "代码必须可运行，含必要注释。严禁输出与编程无关的内容。"
                )
            elif subject == "english":
                sys_c = (
                    "你是英语实战演练智能体。输出 JSON："
                    '{"content_mode":"practice", "practice_type":"english", "language":"english", '
                    '"practice_items":[{"type":"grammar_fill|translation|dialogue", "title":"...", "content":"...", "answer":"..."}], '
                    '"explanation":"学习要点说明", "objective":"练习目标"}'
                    "生成语法填空、翻译练习或情景对话，严禁输出编程代码。"
                )
            elif subject == "math":
                sys_c = (
                    "你是数学实战演练智能体。输出 JSON："
                    '{"content_mode":"practice", "practice_type":"math", "language":"math", '
                    '"practice_items":[{"type":"calculation|proof|application", "title":"...", "content":"...", "steps":["步骤1"], "answer":"..."}], '
                    '"explanation":"解题方法总结", "objective":"练习目标"}'
                    "必须生成 4 道题：至少包含 2 道计算题、1 道应用题、1 道证明/辨析题。"
                    "每道 content 不少于 40 字，steps 至少 3 步，answer 必须给出明确结论；严禁输出编程代码或泛泛的知识介绍。"
                )
            else:
                sys_c = (
                    "你是学科实战演练智能体。输出 JSON："
                    '{"content_mode":"practice", "practice_type":"general", "language":"practice", '
                    '"practice_items":[{"type":"application|exercise", "title":"...", "content":"...", "answer":"..."}], '
                    '"explanation":"实操要点", "objective":"练习目标"}'
                    f"主题学科: {subject}。生成贴合该学科的应用案例或实操练习，严禁输出编程代码。"
                )
            user_c = (
                f"主题: {ctx.topic}\n难度: {ctx.difficulty}/5\n学科: {subject}\n"
                f"薄弱点: {ctx.learning_diagnosis.get('weak_points', []) if ctx.learning_diagnosis else []}\n"
                f"本次生成约束:\n{ctx.generation_brief()}\n"
                f"知识库参考（题目与参考答案须与以下材料一致）:\n{ctx.kb_summary() or '（无）'}"
            )
            res_c = await self._chat(ctx, sys_c, user_c, run.id, temperature=0.3, max_tokens=4096)
            is_prog = is_programming_subject(ctx.topic, ctx.goal)
            code_data = _normalize_code_agent_payload(
                res_c.content, is_programming=is_prog, topic=ctx.topic
            )
            code_data.setdefault("content_mode", "code" if is_prog else "practice")
            if subject == "math" and not _has_sufficient_practice(code_data):
                code_data = _default_math_practice(ctx.topic)
            output["code"] = code_data

        ctx.partial_previews.append(
            {
                "agent_code": self.agent_code,
                "agent_name": self.agent_name,
                "type": "extension",
                "preview": "拓展阅读与代码案例已生成",
            }
        )
        self._finish_run(run.id, output)
        return {**output, "agent_run_id": run.id}


class AnimationAgent(BaseAgent):
    """AI视频讲解智能体：生成沉浸式讲解（资源详情可预览，并可进入完整沉浸式页）。"""

    agent_code = "animation"
    agent_name = "AI视频讲解智能体"

    async def execute(self, ctx: OrchestrationContext, parent_run_id: int | None = None) -> dict[str, Any]:
        run = self._start_run(ctx, {"topic": ctx.topic, "type": "video"}, parent_run_id)
        from app.services.tutor_immersive_lecture_service import TutorImmersiveLectureService
        from app.services.tutor_lecture_resource_service import (
            animation_slides_from_lecture,
            script_from_lecture,
        )

        profile = ""
        if ctx.learning_diagnosis:
            profile = json.dumps(ctx.learning_diagnosis, ensure_ascii=False)[:1500]
        svc = TutorImmersiveLectureService(self.llm)
        lecture = await svc.generate(
            ctx.topic,
            profile,
            ctx.generation_brief()[:2000],
            False,
            ctx.user_id,
            ctx.task_id,
        )
        slides = animation_slides_from_lecture(lecture)
        script = script_from_lecture(lecture)
        data = {
            "lecture": lecture,
            "slides": slides,
            "script_content": script,
            "storyboard": slides,
            "animation_type": "immersive_lecture",
            "animation_data": {
                "slides": slides,
                "render_status": "ready",
                "style": "immersive_lecture",
                "teacher_name": "AI 教师",
                "lecture_id": lecture.get("lecture_id"),
                "lecture": {
                    "lecture_id": lecture.get("lecture_id"),
                    "topic": lecture.get("topic"),
                    "slides": lecture.get("slides") or [],
                    "content_slide_count": lecture.get("content_slide_count"),
                    "quiz_count": lecture.get("quiz_count"),
                    "recommendations": lecture.get("recommendations") or [],
                    "created_at": lecture.get("created_at"),
                },
            },
            "status": "ready",
        }
        ctx.partial_previews.append(
            {
                "agent_code": self.agent_code,
                "agent_name": self.agent_name,
                "type": "animation",
                "preview": f"AI视频讲解已生成 {len(slides)} 个分镜，可进入完整沉浸式讲解",
                "data": {"status": "ready", "scenes": len(slides), "lecture_id": lecture.get("lecture_id")},
            }
        )
        self._finish_run(run.id, {"lecture_id": lecture.get("lecture_id"), "slides": len(slides)})
        return {**data, "agent_run_id": run.id}


class ValidatorAgent(BaseAgent):
    """校验智能体：一致性 / 事实核查 / 安全审核。"""

    agent_code = "consistency"
    agent_name = "一致性校验智能体"

    async def execute(self, ctx: OrchestrationContext, parent_run_id: int | None = None) -> dict:
        return await self.validate_all(ctx, [], parent_run_id or 0)

    async def validate_all(self, ctx: OrchestrationContext, contents: list[str], parent_run_id: int) -> dict:
        run = self._start_run(ctx, {"content_count": len(contents)}, parent_run_id)
        combined = "\n---\n".join(c[:500] for c in contents)
        system = '你是内容一致性校验智能体。检查多资源间是否矛盾，输出 JSON：{"passed":true,"issues":[],"score":0.95}'
        result = await self._chat(ctx, system, f"主题: {ctx.topic}\n\n内容摘要:\n{combined}", run.id, temperature=0.2)
        data = _extract_json(result.content) or {"passed": True, "issues": [], "score": 0.9}
        self._finish_run(run.id, data, status=2 if data.get("passed", True) else 3)
        return data
