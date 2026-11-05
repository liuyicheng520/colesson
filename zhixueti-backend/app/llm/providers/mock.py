"""Mock LLM provider for local development without API keys."""

import asyncio
import json
import re
import time
from collections.abc import AsyncIterator

from app.llm.base import BaseLLMProvider, LLMResult


def _is_profile_json_extract(messages: list[dict[str, str]]) -> bool:
    """仅画像结构化提取/合成走 JSON，对话引导绝不走此分支。"""
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    last = messages[-1]["content"] if messages else ""

    if "画像特征提取引擎" in system:
        return True
    if "画像分析师" in system and "只返回" in system and "JSON" in system:
        return True
    if "只返回JSON" in system or "只返回该维度" in system:
        return True
    if "请返回形如" in last and "维度:" in last:
        return True
    return False


def _is_profile_dialogue(messages: list[dict[str, str]]) -> bool:
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    return (
        "学习画像顾问" in system
        or "画像顾问" in system
        or "有情商的学习伙伴" in system
        or "最后要问：" in system
        or "说话像豆包" in system
    )


def _is_tutor_chat(messages: list[dict[str, str]]) -> bool:
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    return "智学体多模态智能辅导助手" in system or "EduNexus 多模态智能辅导助手" in system or "智能辅导助手" in system


def _is_lecture_outline(messages: list[dict[str, str]]) -> bool:
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    return "课程设计专家" in system and "讲解大纲" in system


def _is_lecture_module(messages: list[dict[str, str]]) -> bool:
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    return "专业讲师" in system and "lecture_slides" in system


def _is_mindmap_visual(messages: list[dict[str, str]]) -> bool:
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    return "思维导图设计师" in system or "教育可视化" in system


def _is_animation_agent(messages: list[dict[str, str]]) -> bool:
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    return "教学动画智能体" in system


def _mindmap_visual_mock(prompt: str) -> str:
    topic = (prompt or "知识点").strip()
    for sep in ("主题：", "主题:"):
        if sep in topic:
            topic = topic.split(sep, 1)[-1].split("\n", 1)[0].strip()
            break
    topic = re.sub(r"(的)?(思维导图|知识图谱).*$", "", topic).strip()[:24] or "知识点"
    return json.dumps(
        {
            "title": f"{topic} · 思维导图",
            "caption": f"「{topic}」结构化知识脉络",
            "branches": [
                {"name": "核心概念", "children": ["基本定义", "关键术语", "适用范围"]},
                {"name": "结构组成", "children": ["组成部分", "相互关系", "约束条件"]},
                {"name": "方法步骤", "children": ["基本流程", "操作要点", "常见错误"]},
                {"name": "应用场景", "children": ["典型例子", "实践建议", "迁移练习"]},
            ],
        },
        ensure_ascii=False,
    )


def _animation_mock(topic: str) -> str:
    t = (topic or "本主题").strip()[:40] or "本主题"
    slides = [
        {
            "step": 1,
            "title": f"认识{t}",
            "narration": (
                f"同学们好，今天系统学习「{t}」。先建立整体地图：要解决什么问题、"
                f"关键概念有哪些、学完后能独立完成什么。请带着这三个问题听完整节。"
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
                f"「{t}」先用一句话定义，再划清边界：包含什么、不包含什么。"
                f"请对照一个生活或工程小例子，确认定义说得通。"
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
                f"把「{t}」拆成 3～4 个积木块，说明各块职责与衔接，"
                f"以及常见漏掉哪一块会出错。"
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
                f"走一遍「{t}」标准流程：每步做什么、为何必要、输出是什么。"
                f"强调中间结果如何被下一步消费。"
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
                f"拖动滑块改变参数，观察「{t}」结果如何变化。"
                f"请总结：哪个参数影响最大？何时出现异常？"
            ),
            "visual": "参数驱动示意：调节—观察—总结",
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
                f"回顾「{t}」：定义与边界、结构、流程、参数直觉。"
                f"用自己的话复述三点，并留下一个还能继续追问的问题。"
            ),
            "visual": "四要点清单 + 自测复述",
            "emoji": "✅",
            "duration_sec": 18,
            "scene_type": "concept",
            "nodes": ["定义", "结构", "流程", "下一步"],
        },
    ]
    script = "\n\n".join(f"## {s['title']}\n{s['narration']}" for s in slides)
    return json.dumps(
        {
            "script_content": script,
            "slides": slides,
            "storyboard": [
                {
                    "scene": s["step"],
                    "duration_sec": s["duration_sec"],
                    "narration": s["narration"],
                    "visual": s["visual"],
                }
                for s in slides
            ],
            "animation_type": "interactive_scene_animation",
            "animation_data": {
                "style": "interactive_lab",
                "teacher_name": "小智老师",
                "interaction_enabled": True,
            },
            "status": "ready",
        },
        ensure_ascii=False,
    )


def _tutor_mock_reply(messages: list[dict[str, str]]) -> str:
    last = messages[-1]["content"] if messages else ""
    topic = (last or "你的问题").strip()[:120]
    return (
        f"## 关于「{topic}」\n\n"
        f"你好！针对你提到的内容，我先从几个方面说明：\n\n"
        f"### 核心概念\n"
        f"- **定义**：这是该主题最基础的理解框架。\n"
        f"- **原理**：关键机制通常由若干步骤或因果关系构成。\n\n"
        f"### 应用场景\n"
        f"- 在学习和实践中，可以结合具体例题或案例加深理解。\n"
        f"- 若你有更具体的背景（专业、基础、目标），我可以进一步细化讲解。\n\n"
        f"### 小结\n"
        f"你刚才说的是：{last[:80] or '（等待你的补充）'}。\n\n"
        f"> 当前为 **Mock 演示模式**（未接入真实大模型）。"
        f"如需更智能的回答，请在 `backend/.env` 配置 DeepSeek API Key 并将 "
        f"`LLM_DEFAULT_PROVIDER=deepseek`。\n\n"
        f"AI 生成仅供参考"
    )


def _lecture_outline_mock(topic: str) -> str:
    title = topic[:40] or "知识点"
    return json.dumps(
        [
            {"title": f"{title} 概述", "objectives": ["理解核心概念"], "duration_min": 5},
            {"title": f"{title} 原理拆解", "objectives": ["掌握关键原理"], "duration_min": 8},
            {"title": f"{title} 应用与练习", "objectives": ["能够举一反三"], "duration_min": 7},
        ],
        ensure_ascii=False,
    )


def _lecture_module_mock(section: str) -> str:
    return json.dumps(
        {
            "lecture_slides": [
                {"title": section, "bullets": ["核心定义", "关键步骤", "常见易错点"], "highlight": "先理解再应用", "mermaid": None},
                {"title": "示例说明", "bullets": ["结合例题理解", "对照步骤练习"], "highlight": "多练多思考", "mermaid": None},
            ],
            "quiz": {
                "question": f"关于「{section}」，以下哪项最符合核心概念？",
                "options": ["A. 选项一", "B. 选项二", "C. 选项三", "D. 选项四"],
                "answer": "A",
                "analysis": "Mock 模式下为示例题目，接入真实模型后将生成更精准测验。",
            },
            "extension": {"title": "拓展思考", "content": f"## {section} 拓展\n\n可进一步查阅教材或相关论文加深理解。"},
        },
        ensure_ascii=False,
    )


def _dialogue_mock_reply(messages: list[dict[str, str]]) -> str:
    """模型不可用时的兜底。按用户意图接话，拒绝或闲聊时不强塞同一句。"""
    from app.services.profile_service import ProfileService

    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    last_user = ""
    for message in reversed(messages):
        if message.get("role") == "user":
            last_user = (message.get("content") or "").strip()
            break
    match = re.search(r"最后要问：([^\n]+)", system)
    question = match.group(1).strip() if match else ""
    stub = ProfileService.__new__(ProfileService)
    text = stub._human_turn(last_user, "D2")
    if question and question not in text and "？" not in text and "?" not in text:
        if not re.search(r"先停|不想说|不想答|随便聊|想歇", text):
            text = f"{text}\n\n{question}"
    return text


class MockProvider(BaseLLMProvider):
    provider_name = "mock"

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResult:
        start = time.perf_counter()
        await asyncio.sleep(0.1)
        last = messages[-1]["content"] if messages else ""
        system = next((m["content"] for m in messages if m["role"] == "system"), "")

        # 对话引导优先于 JSON 提取，避免 system 含「维度」等词时误返回画像 JSON
        if _is_profile_dialogue(messages):
            content = _dialogue_mock_reply(messages)
        elif _is_lecture_outline(messages):
            last = messages[-1]["content"] if messages else ""
            topic_match = re.search(r"主题[：:]\s*(.+)", last)
            topic = topic_match.group(1).split("\n")[0].strip() if topic_match else last[:60]
            content = _lecture_outline_mock(topic)
        elif _is_lecture_module(messages):
            section_match = re.search(r"当前小节[：:]\s*(.+)", messages[-1]["content"] if messages else "")
            section = section_match.group(1).split("\n")[0].strip() if section_match else "本节内容"
            content = _lecture_module_mock(section)
        elif _is_animation_agent(messages):
            topic_match = re.search(r"主题[：:]\s*(.+)", last)
            topic = topic_match.group(1).split("\n")[0].strip() if topic_match else last[:60]
            content = _animation_mock(topic)
        elif _is_mindmap_visual(messages):
            content = _mindmap_visual_mock(last)
        elif _is_tutor_chat(messages):
            content = _tutor_mock_reply(messages)
        elif _is_profile_json_extract(messages):
            content = json.dumps(
                {
                    "D1": {"domain": "machine_learning", "level": 2, "gaps": ["线性代数"]},
                    "D3": {"goal": last[:100] or "学习机器学习", "priority": "high"},
                },
                ensure_ascii=False,
            )
        elif "内容校验智能体" in system or "教育内容校验智能体" in system:
            content = json.dumps(
                {"passed": True, "risk_level": 0, "issues": [], "suspicious_segments": [], "needs_regenerate": False},
                ensure_ascii=False,
            )
        elif "审核" in system or "安全" in system:
            content = json.dumps({"safe": True, "risk_level": 0, "labels": []}, ensure_ascii=False)
        elif "路径" in system or "path" in system.lower():
            content = json.dumps(
                {"nodes": ["概述", "线性回归", "逻辑回归", "模型评估", "项目实战"]},
                ensure_ascii=False,
            )
        elif "文档" in system or "讲义" in system or "document" in system.lower():
            content = (
                "⚠️ 演示模式：以下内容由本地模板生成（未配置 AI Key），并非 AI 输出。\n\n"
                f"# {last}\n\n## 概述\n这是关于{last}的个性化学习文档。\n\n## 核心概念\n1. 基础定义\n2. 应用场景\n3. 实践要点"
            )
        elif "导图" in system or "mindmap" in system.lower():
            content = json.dumps(
                {
                    "nodes": [
                        {"id": "1", "label": last or "主题", "level": 0},
                        {"id": "2", "label": "核心概念", "level": 1},
                        {"id": "3", "label": "应用", "level": 1},
                    ],
                    "edges": [{"from": "1", "to": "2"}, {"from": "1", "to": "3"}],
                },
                ensure_ascii=False,
            )
        elif ("写代码" in system or "编程题" in system) and ("code" in system.lower() or "代码" in system):
            content = "```python\n# 示例代码\ndef hello():\n    return 'Hello 智学体'\n\nprint(hello())\n```"
        elif "实战演练" in system or "practice_items" in system:
            # 非编程学科的实战演练：返回可解析的练习 JSON（带答案与步骤），避免生成空壳资源。
            topic_match = re.search(r"主题[：:]\s*(.+)", str(last))
            last = topic_match.group(1).split("\n")[0].strip() if topic_match else str(last)[:40]
            last = last[:40] or "本主题"
            if "数学" in system or '"math"' in system or "math" in system.lower():
                ptype, lang = "math", "math"
                items = [
                    {"type": "calculation", "title": f"{last}·基础计算", "content": f"围绕「{last}」给出一道基础计算题，先列式再逐步求解，写出每一步依据。", "steps": ["审题并明确已知量与目标量", "列出计算式并代入数值", "求出结果并检查量纲与合理性"], "answer": "按步骤求解，结果与教材公式一致即可（演示参考答案）"},
                    {"type": "calculation", "title": f"{last}·综合计算", "content": f"给出「{last}」的变式条件，综合运用两个公式完成求解。", "steps": ["拆解复合条件", "分别应用对应公式", "合并结果并验算"], "answer": "两步公式结果合并后即为最终解（演示参考答案）"},
                    {"type": "application", "title": f"{last}·实际应用", "content": f"举出一个生活中可用「{last}」解决的实例，建立模型并求解。", "steps": ["抽象实际问题为数学模型", "代入数据求解", "解释结果的实际意义"], "answer": "建模正确、解释合理即可（演示参考答案）"},
                    {"type": "proof", "title": f"{last}·证明/辨析", "content": f"证明或辨析「{last}」中的一个关键结论，写出完整论证链条。", "steps": ["明确结论与已知", "寻找可用定理/性质", "组织论证并得出结论"], "answer": "论证链条完整、结论成立（演示参考答案）"},
                ]
            elif "英语" in system or '"english"' in system or "english" in system.lower():
                ptype, lang = "english", "english"
                items = [
                    {"type": "grammar_fill", "title": "语法填空", "content": f"用「{last}」相关句型完成填空：She ____ (go) to school every day.", "answer": "goes（一般现在时第三人称单数）"},
                    {"type": "translation", "title": "翻译练习", "content": f"把句子翻译成英文：请围绕「{last}」写一句完整的英文表达。", "answer": "示例：This topic is very important in our daily life.（演示参考答案）"},
                    {"type": "dialogue", "title": "情景对话", "content": f"以「{last}」为话题，与同伴完成一段 4 轮对话。", "answer": "参考：A: What do you think of this topic? B: I think it is useful because...（演示参考答案）"},
                ]
            else:
                ptype, lang = "general", "practice"
                items = [
                    {"type": "application", "title": f"{last}·核心应用", "content": f"结合「{last}」的核心概念，说明它解决什么问题、适用场景是什么，并给出一个具体例子（不少于 80 字）。", "answer": f"「{last}」的核心价值在于其解决问题的思路与适用边界；示例应包含场景、做法与结果三要素（演示参考答案）"},
                    {"type": "exercise", "title": f"{last}·流程实操", "content": f"按步骤完成一次与「{last}」相关的实操任务，记录每一步的关键动作与结果。", "steps": ["明确任务目标与输入", "按标准流程逐步执行", "核对结果并总结要点"], "answer": "流程完整、记录清晰即可（演示参考答案）"},
                    {"type": "application", "title": f"{last}·对比分析", "content": f"找出「{last}」中两个容易混淆的概念或方案，从 2-3 个维度对比分析。", "answer": "对比维度选择合理、结论明确即可（演示参考答案）"},
                ]
            content = json.dumps(
                {
                    "content_mode": "practice",
                    "practice_type": ptype,
                    "language": lang,
                    "practice_items": items,
                    "explanation": "⚠️ 演示模式：练习内容由本地模板生成（未配置 AI Key），并非 AI 输出。",
                    "objective": f"围绕「{last}」完成实战自测",
                },
                ensure_ascii=False,
            )
        else:
            # 通用兜底：未识别的 Agent 一律返回结构化演示文档（带水印）。
            # 历史 bug：课程讲义 Agent 的 system 不含「文档」关键词，曾落到这里，
            # 导致生成的讲义正文变成 210 字的画像对话文本。
            topic = last[:60] or "本主题"
            content = (
                "⚠️ 演示模式：以下内容由本地模板生成（未配置 AI Key），并非 AI 输出。\n\n"
                f"# {topic}\n\n## 概述\n这是关于{topic}的结构化演示文档。\n\n"
                "## 核心概念\n1. 基础定义\n2. 应用场景\n3. 实践要点\n\n"
                "## 小结\n配置 AI 服务密钥后，此处将输出真实生成内容。"
            )

        latency = int((time.perf_counter() - start) * 1000)
        return LLMResult(
            content=content,
            provider="mock",
            model=model or "mock-v1",
            prompt_tokens=len(str(messages)) // 4,
            completion_tokens=len(content) // 4,
            total_tokens=len(str(messages)) // 4 + len(content) // 4,
            latency_ms=latency,
        )

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        result = await self.chat(messages, model, temperature, max_tokens)
        for char in result.content:
            yield char
            await asyncio.sleep(0.005)
