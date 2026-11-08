"""Tutor multimodal generation — 思维导图/讲解动画脚本。"""

from __future__ import annotations

import json
import re
from typing import Any

from app.llm.gateway import LLMGateway
from app.security.context import SecurityContext

_MM_CTX = SecurityContext(target_type="tutor_multimodal", allow_off_topic=True, source_module="tutor")


def _topic_from_prompt(prompt: str) -> str:
    text = (prompt or "").strip()
    text = re.sub(r"^(请|帮我|给我|生成|画|绘制|做一[个张]|输出)", "", text).strip()
    text = re.sub(r"(的)?(思维导图|知识图谱|导图|结构图|脉络图|示意图).*$", "", text).strip(" ：:，,")
    return (text or prompt or "知识点")[:40]


def _safe_label(text: str, limit: int = 12) -> str:
    s = re.sub(r"[\[\]()（）{}<>\"'|\\/]", "", str(text or "").strip())
    s = re.sub(r"\s+", "", s)
    return (s or "节点")[:limit]


def _default_branches(topic: str) -> list[dict[str, Any]]:
    return [
        {"name": "核心概念", "children": ["基本定义", "关键术语", "适用范围"]},
        {"name": "结构组成", "children": ["主要组成部分", "相互关系", "约束条件"]},
        {"name": "方法步骤", "children": ["基本流程", "操作要点", "常见错误"]},
        {"name": "应用场景", "children": ["典型例子", "实践建议", "迁移练习"]},
    ]


def _normalize_branches(raw: Any, topic: str) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        return _default_branches(topic)
    branches: list[dict[str, Any]] = []
    for item in raw[:6]:
        if not isinstance(item, dict):
            continue
        name = _safe_label(item.get("name") or item.get("title") or "分支", 10)
        children_raw = item.get("children") or item.get("items") or []
        children: list[str] = []
        if isinstance(children_raw, list):
            for c in children_raw[:5]:
                if isinstance(c, str):
                    children.append(_safe_label(c, 12))
                elif isinstance(c, dict):
                    children.append(_safe_label(c.get("name") or c.get("title") or "子点", 12))
        if not children:
            children = ["要点一", "要点二"]
        branches.append({"name": name, "children": children})
    return branches if len(branches) >= 3 else _default_branches(topic)


def _build_graph(topic: str, branches: list[dict[str, Any]]) -> dict[str, Any]:
    """用结构化分支生成可渲染的 flowchart + nodes/edges（避免 LLM 手写 Mermaid 语法错误）。"""
    root_label = _safe_label(topic, 16)
    nodes: list[dict[str, Any]] = [
        {"id": "root", "label": root_label, "description": f"「{root_label}」知识结构中心", "level": 0},
    ]
    edges: list[dict[str, str]] = []
    lines = ["flowchart TD", f'  root["{root_label}"]']

    for bi, branch in enumerate(branches):
        bid = f"b{bi}"
        bname = _safe_label(branch["name"], 10)
        nodes.append({"id": bid, "label": bname, "description": f"{root_label} · {bname}", "level": 1})
        edges.append({"from": "root", "to": bid})
        lines.append(f'  {bid}["{bname}"]')
        lines.append(f"  root --> {bid}")
        for ci, child in enumerate(branch.get("children") or []):
            cid = f"b{bi}c{ci}"
            cname = _safe_label(str(child), 12)
            nodes.append({"id": cid, "label": cname, "description": f"{bname} · {cname}", "level": 2})
            edges.append({"from": bid, "to": cid})
            lines.append(f'  {cid}["{cname}"]')
            lines.append(f"  {bid} --> {cid}")

    return {
        "mermaid": "\n".join(lines),
        "nodes": nodes,
        "edges": edges,
    }


def _fallback_mindmap(prompt: str) -> dict[str, Any]:
    topic = _topic_from_prompt(prompt)
    branches = _default_branches(topic)
    graph = _build_graph(topic, branches)
    return {
        "type": "image",
        "title": f"{topic} · 思维导图",
        "mermaid": graph["mermaid"],
        "nodes": graph["nodes"],
        "edges": graph["edges"],
        "caption": f"围绕「{topic}」的结构化知识脉络。",
        "disclaimer": "AI 生成思维导图，仅供学习参考",
        "chart_kind": "mindmap",
    }


class TutorMultimodalService:
    def __init__(self, llm: LLMGateway) -> None:
        self.llm = llm

    async def generate_image(
        self, prompt: str, user_id: int, task_id: int | None
    ) -> dict[str, Any]:
        """生成知识点思维导图：LLM 只产出结构化分支，服务端拼装可渲染图。"""
        topic = _topic_from_prompt(prompt)
        result = await self.llm.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "你是教育思维导图设计师。只输出一个合法 JSON 对象，不要 Markdown 代码块。"
                        "格式严格为："
                        '{"title":"标题","caption":"一句话导读",'
                        '"branches":[{"name":"一级分支","children":["子点1","子点2","子点3"]}]}'
                        "要求：至少 4 个一级分支；每个分支 2~4 个具体子点；"
                        "名称简短（≤10字），必须贴合主题学科知识，禁止「内容/其他/总结」等空泛词。"
                    ),
                },
                {
                    "role": "user",
                    "content": f"主题：{topic}\n用户原话：{prompt}\n请给出「{topic}」的学习思维导图分支结构。",
                },
            ],
            user_id=user_id,
            task_id=task_id,
            temperature=0.35,
            max_tokens=2048,
            context=_MM_CTX,
        )
        data = self._parse_json(result.content)
        if not isinstance(data, dict) or not data:
            return _fallback_mindmap(prompt)

        branches = _normalize_branches(data.get("branches"), topic)
        graph = _build_graph(topic, branches)
        title = str(data.get("title") or "").strip() or f"{topic} · 思维导图"
        caption = str(data.get("caption") or "").strip() or f"「{topic}」知识结构思维导图"
        return {
            "type": "image",
            "title": title[:40],
            "mermaid": graph["mermaid"],
            "nodes": graph["nodes"],
            "edges": graph["edges"],
            "caption": caption[:120],
            "disclaimer": "AI 生成思维导图，仅供学习参考",
            "chart_kind": "mindmap",
        }

    async def generate_video_script(
        self, topic: str, user_id: int, task_id: int | None
    ) -> dict[str, Any]:
        """生成分步讲解动画脚本（前端 CSS 逐步展示）。"""
        result = await self.llm.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "你是微课脚本编剧。返回 JSON："
                        '{"title":"标题","steps":[{"label":"步骤名","content":"讲解文案","duration_sec":4}]}'
                        "4~6 步，由浅入深。只返回 JSON。"
                    ),
                },
                {"role": "user", "content": f"知识点：{topic}"},
            ],
            user_id=user_id,
            task_id=task_id,
            temperature=0.5,
            context=_MM_CTX,
        )
        data = self._parse_json(result.content)
        steps = data.get("steps") or [
            {"label": "引入", "content": f"我们来学习 {topic}", "duration_sec": 4},
            {"label": "核心", "content": topic, "duration_sec": 6},
        ]
        return {
            "type": "video",
            "title": data.get("title") or f"{topic} 讲解",
            "steps": steps,
            "disclaimer": "AI 生成讲解动画",
        }

    async def prepare_tts(self, text: str) -> dict[str, Any]:
        """TTS 由前端 Web Speech API 播放，后端返回清洗后文本。"""
        clean = re.sub(r"```[\s\S]*?```", "", text)
        clean = re.sub(r"\$\$[\s\S]*?\$\$", "", clean)
        clean = re.sub(r"\$[^$]+\$", "", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        return {"type": "tts", "text": clean[:3000], "disclaimer": "语音由浏览器合成"}

    def _parse_json(self, raw: str) -> dict:
        text = (raw or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
        try:
            return json.loads(text) if text else {}
        except json.JSONDecodeError:
            m = re.search(r"\{[\s\S]*\}", text)
            if m:
                try:
                    return json.loads(m.group())
                except json.JSONDecodeError:
                    pass
        return {}
