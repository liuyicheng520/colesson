"""Tutor lecture generation — 大纲预览 → 分模块流式 → 幻灯片结构化输出。"""

from __future__ import annotations

import json
import re
from typing import Any, AsyncIterator

from app.llm.gateway import LLMGateway
from app.security.context import SecurityContext

_LECTURE_CTX = SecurityContext(
    target_type="tutor_lecture",
    allow_off_topic=True,
    require_citation=False,
    source_module="tutor",
)

OUTLINE_SYSTEM = """你是课程设计专家。根据用户请求生成结构化讲解大纲。
仅返回 JSON 数组，每项格式：
{"title":"小节标题","objectives":["目标1"],"duration_min":5}
共 4~8 个小节，由浅入深。不要输出其他文字。"""

MODULE_SYSTEM = """你是专业讲师。根据大纲小节生成三部分内容，严格返回 JSON：
{
  "lecture_slides": [
    {"title":"页标题","bullets":["要点1","要点2"],"highlight":"关键句","mermaid":null}
  ],
  "quiz": {"question":"...","options":["A","B","C","D"],"answer":"A","analysis":"..."},
  "extension": {"title":"拓展","content":"markdown 拓展内容"}
}
lecture_slides 3~5 页，适合幻灯片展示。需要图解时在 mermaid 字段放 flowchart 代码。"""


def is_lecture_request(content: str) -> bool:
    patterns = [
        r"讲解|介绍|梳理|系统学习|课程|知识点|帮我学|教我",
        r"什么是|是什么|原理|概念",
    ]
    return any(re.search(p, content) for p in patterns)


def _parse_json_array(raw: str) -> list[dict]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    try:
        data = json.loads(text)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return []


def _parse_json_obj(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return {}


class TutorLectureService:
    def __init__(self, llm: LLMGateway) -> None:
        self.llm = llm

    async def generate_outline(
        self,
        topic: str,
        profile_text: str,
        doc_context: str,
        web_context: str,
        user_id: int,
        task_id: int | None,
    ) -> list[dict]:
        user_prompt = f"主题：{topic}\n\n用户画像：\n{profile_text}\n"
        if doc_context:
            user_prompt += f"\n参考文档：\n{doc_context[:6000]}\n"
        if web_context:
            user_prompt += f"\n联网资料：\n{web_context[:4000]}\n"

        result = await self.llm.chat(
            [{"role": "system", "content": OUTLINE_SYSTEM}, {"role": "user", "content": user_prompt}],
            user_id=user_id,
            task_id=task_id,
            temperature=0.4,
            context=_LECTURE_CTX,
        )
        outline = _parse_json_array(result.content)
        if not outline:
            outline = [
                {"title": f"{topic} 概述", "objectives": ["理解核心概念"], "duration_min": 5},
                {"title": f"{topic} 原理拆解", "objectives": ["掌握关键原理"], "duration_min": 8},
                {"title": f"{topic} 应用与练习", "objectives": ["能够应用"], "duration_min": 7},
            ]
        return outline

    async def stream_modules(
        self,
        outline: list[dict],
        topic: str,
        profile_text: str,
        doc_context: str,
        deep_mode: bool,
        user_id: int,
        task_id: int | None,
    ) -> AsyncIterator[tuple[str, Any]]:
        modules = [
            ("lecture", "知识点讲解"),
            ("quiz", "随堂测验"),
            ("extension", "拓展练习"),
        ]
        for idx, item in enumerate(outline):
            section_title = item.get("title") or f"第{idx+1}节"
            yield ("module_start", {"index": idx, "title": section_title, "phase": "lecture"})

            prompt = (
                f"课程主题：{topic}\n当前小节：{section_title}\n"
                f"目标：{item.get('objectives', [])}\n"
                f"用户画像：{profile_text}\n"
            )
            if doc_context:
                prompt += f"文档参考：\n{doc_context[:4000]}\n"
            if deep_mode:
                prompt += "\n深度模式：原理拆解、案例推导、易错点均需覆盖。\n"

            yield ("progress", {"message": f"正在生成「{section_title}」讲解内容…"})

            result = await self.llm.chat(
                [{"role": "system", "content": MODULE_SYSTEM}, {"role": "user", "content": prompt}],
                user_id=user_id,
                task_id=task_id,
                temperature=0.5,
                context=_LECTURE_CTX,
            )
            module_data = _parse_json_obj(result.content)
            slides = module_data.get("lecture_slides") or []
            if not slides:
                slides = [{"title": section_title, "bullets": [result.content[:500]], "highlight": "", "mermaid": None}]

            yield ("slides", {"index": idx, "slides": slides})
            yield ("module_chunk", {"index": idx, "module": "lecture", "content": json.dumps(slides, ensure_ascii=False)})

            quiz = module_data.get("quiz") or {}
            if quiz:
                yield ("module_start", {"index": idx, "title": section_title, "phase": "quiz"})
                yield ("module_chunk", {"index": idx, "module": "quiz", "content": json.dumps(quiz, ensure_ascii=False)})

            ext = module_data.get("extension") or {}
            if ext:
                yield ("module_start", {"index": idx, "title": section_title, "phase": "extension"})
                yield ("module_chunk", {"index": idx, "module": "extension", "content": json.dumps(ext, ensure_ascii=False)})

            yield ("module_done", {"index": idx, "title": section_title})

        yield ("lecture_done", {"sections": len(outline)})
