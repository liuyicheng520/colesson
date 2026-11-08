"""Immersive lecture — 幻灯片 + 语音讲解 + 随堂测验 + PPTX 导出。"""

from __future__ import annotations

import json
import re
import uuid
import base64
import zlib
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

import httpx

from app.security.citation import strip_citation_block
from app.security.context import SecurityContext

_LECTURE_CTX = SecurityContext(
    target_type="tutor_immersive_lecture",
    allow_off_topic=True,
    require_citation=False,
    source_module="tutor",
)

GENERATE_SYSTEM = """你是专业 AI 讲师。根据知识点生成沉浸式讲解内容，严格返回 JSON：
{
  "topic": "主题",
  "slides": [
    {
      "type": "content",
      "title": "页标题",
      "bullets": ["要点1", "要点2"],
      "highlight": "本页核心句（用于聚焦高亮）",
      "mermaid": null,
      "narration": "本页语音讲解稿（150~250字，口语化）"
    },
    {
      "type": "quiz",
      "question": "题目",
      "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
      "answer": "A",
      "multi": false,
      "analysis": "解析",
      "narration": "引导作答的简短语音"
    }
  ],
  "recommendations": ["推荐学习1", "推荐学习2"]
}
要求：
- content 页 5~8 页，由浅入深
- 至少 2~3 页 content 必须包含 mermaid 流程图/结构图（不可全为 null）
- 插入 1~2 个 quiz 节点（单选或多选）
- narration 与 bullets 对应，适合 TTS 朗读
- 需要图解时在 mermaid 放 flowchart 代码
只返回 JSON。"""


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    return {}


class TutorImmersiveLectureService:
    def __init__(self, llm: LLMGateway) -> None:
        self.llm = llm

    async def generate(
        self,
        topic: str,
        profile_text: str,
        doc_ctx: str,
        deep_mode: bool,
        user_id: int,
        task_id: int | None,
    ) -> dict[str, Any]:
        depth_hint = "深度讲解，每页内容充实" if deep_mode else "简明扼要，突出核心"
        user_msg = f"主题：{topic}\n\n用户画像：\n{profile_text}\n\n深度：{depth_hint}"
        if doc_ctx:
            user_msg += f"\n\n参考文档：\n{doc_ctx[:4000]}"

        result = await self.llm.chat(
            [{"role": "system", "content": GENERATE_SYSTEM}, {"role": "user", "content": user_msg}],
            user_id=user_id,
            task_id=task_id,
            temperature=0.5,
            max_tokens=4096,
            context=_LECTURE_CTX,
        )
        data = _parse_json(result.content)
        slides = data.get("slides") or self._fallback_slides(topic)
        slides = self._normalize_slides(slides)
        lecture_id = str(uuid.uuid4())
        content_count = sum(1 for s in slides if s.get("type") == "content")
        return {
            "lecture_id": lecture_id,
            "topic": data.get("topic") or topic,
            "slides": slides,
            "content_slide_count": content_count,
            "quiz_count": sum(1 for s in slides if s.get("type") == "quiz"),
            "recommendations": data.get("recommendations") or [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def _fallback_slides(self, topic: str) -> list[dict]:
        return [
            {
                "type": "content",
                "title": f"{topic} — 概述",
                "bullets": [f"理解 {topic} 的基本定义", "掌握核心应用场景"],
                "highlight": topic,
                "mermaid": None,
                "narration": f"欢迎来到 {topic} 的讲解。本节课我们将从基础概念开始。",
            },
            {
                "type": "quiz",
                "question": f"关于 {topic}，以下哪项描述最准确？",
                "options": ["A. 仅用于考试", "B. 是核心基础概念", "C. 无需学习", "D. 与学科无关"],
                "answer": "B",
                "multi": False,
                "analysis": f"{topic} 是本领域的核心基础概念。",
                "narration": "请思考后选择你认为正确的答案。",
            },
        ]

    def _normalize_slides(self, slides: list) -> list[dict]:
        out: list[dict] = []
        for i, raw in enumerate(slides):
            if not isinstance(raw, dict):
                continue
            st = raw.get("type") or "content"
            if st == "quiz":
                out.append(
                    {
                        "id": i,
                        "type": "quiz",
                        "question": raw.get("question") or "随堂测验",
                        "options": raw.get("options") or ["A", "B", "C", "D"],
                        "answer": str(raw.get("answer") or "A").upper(),
                        "multi": bool(raw.get("multi", False)),
                        "analysis": raw.get("analysis") or "",
                        "narration": raw.get("narration") or "",
                    }
                )
            else:
                out.append(
                    {
                        "id": i,
                        "type": "content",
                        "title": raw.get("title") or f"第{i + 1}页",
                        "bullets": raw.get("bullets") or [],
                        "highlight": raw.get("highlight") or "",
                        "mermaid": raw.get("mermaid"),
                        "narration": raw.get("narration") or raw.get("title") or "",
                    }
                )
        return out or self._fallback_slides("知识点")

    def store_in_session(self, ext: dict, lecture: dict) -> dict:
        lectures = dict(ext.get("lectures") or {})
        lectures[lecture["lecture_id"]] = lecture
        ext["lectures"] = lectures
        return ext

    def get_from_session(self, ext: dict, lecture_id: str) -> dict | None:
        return (ext.get("lectures") or {}).get(lecture_id)

    @staticmethod
    def _encode_kroki(source: str) -> str:
        compressed = zlib.compress(source.encode("utf-8"), 9)
        return base64.urlsafe_b64encode(compressed).decode("ascii")

    def _mermaid_to_png(self, mermaid_code: str) -> bytes | None:
        code = (mermaid_code or "").strip()
        if not code:
            return None
        try:
            encoded = self._encode_kroki(code)
            url = f"https://kroki.io/mermaid/png/{encoded}"
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(url)
                if resp.status_code == 200 and resp.content:
                    return resp.content
        except Exception:
            pass
        return None

    def _add_content_slide(self, prs, blank, slide_data: dict) -> None:
        from pptx.util import Inches, Pt

        has_mermaid = bool((slide_data.get("mermaid") or "").strip())
        text_width = Inches(6.8) if has_mermaid else Inches(11.5)

        slide = prs.slides.add_slide(blank)
        box = slide.shapes.add_textbox(Inches(0.8), Inches(0.6), Inches(11.5 if not has_mermaid else 11.5), Inches(0.9))
        tf = box.text_frame
        tf.text = slide_data.get("title") or ""
        tf.paragraphs[0].font.size = Pt(32)
        tf.paragraphs[0].font.bold = True

        body = slide.shapes.add_textbox(Inches(0.8), Inches(1.5), text_width, Inches(5.2))
        body_tf = body.text_frame
        body_tf.clear()
        bullets = slide_data.get("bullets") or []
        if bullets:
            body_tf.text = f"• {bullets[0]}"
            body_tf.paragraphs[0].font.size = Pt(22)
            for bullet in bullets[1:]:
                p = body_tf.add_paragraph()
                p.text = f"• {bullet}"
                p.font.size = Pt(22)
        hl = slide_data.get("highlight")
        if hl:
            p = body_tf.add_paragraph()
            p.text = f"★ {hl}"
            p.font.size = Pt(20)

        if has_mermaid:
            png = self._mermaid_to_png(slide_data.get("mermaid") or "")
            if png:
                slide.shapes.add_picture(BytesIO(png), Inches(7.8), Inches(1.5), width=Inches(4.8))

        narration = slide_data.get("narration") or ""
        if narration:
            notes = slide.notes_slide.notes_text_frame
            notes.text = narration

    def export_pptx(self, lecture: dict) -> bytes:
        try:
            from pptx import Presentation
            from pptx.util import Inches, Pt
        except ImportError as e:
            raise RuntimeError("PPTX 导出依赖未安装，请执行: pip install python-pptx") from e

        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)
        blank = prs.slide_layouts[6]

        for slide_data in lecture.get("slides") or []:
            if slide_data.get("type") == "quiz":
                slide = prs.slides.add_slide(blank)
                box = slide.shapes.add_textbox(Inches(0.8), Inches(1), Inches(11.5), Inches(5))
                tf = box.text_frame
                tf.text = f"随堂测验：{slide_data.get('question', '')}"
                for opt in slide_data.get("options") or []:
                    p = tf.add_paragraph()
                    p.text = opt
                    p.font.size = Pt(18)
                narration = slide_data.get("narration") or ""
                if narration:
                    slide.notes_slide.notes_text_frame.text = narration
                continue

            self._add_content_slide(prs, blank, slide_data)

        buf = BytesIO()
        prs.save(buf)
        return buf.getvalue()

    async def side_qa(
        self,
        topic: str,
        current_slide: dict | None,
        question: str,
        history: list[dict],
        user_id: int,
        task_id: int | None,
    ) -> str:
        slide_ctx = ""
        if current_slide:
            slide_ctx = json.dumps(current_slide, ensure_ascii=False)[:1500]
        messages = [
            {
                "role": "system",
                "content": (
                    f"你是 AI 讲师助手。当前讲解主题：{topic}。"
                    f"当前幻灯片：{slide_ctx or '无'}。"
                    "结合讲解内容简洁回答侧边栏提问，不超过200字。"
                    "不要输出「知识依据」「参考范围」「溯源说明」等附录段落。"
                ),
            }
        ]
        for h in history[-6:]:
            messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
        messages.append({"role": "user", "content": question})
        result = await self.llm.chat(messages, user_id=user_id, task_id=task_id, temperature=0.5, context=_LECTURE_CTX)
        return strip_citation_block(result.content.strip())
