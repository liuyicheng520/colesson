"""将智能答疑沉浸式讲解同步为 video 资源（个人中心 + 资源广场）。"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.resource import ResResource, ResVideo
from app.models.sys import SysUser
from app.repositories.resource_repository import ResourceRepository

logger = logging.getLogger(__name__)


def animation_slides_from_lecture(lecture: dict[str, Any]) -> list[dict[str, Any]]:
    """转换为 TeachingAnimationPlayer 可播放的分镜。"""
    result: list[dict[str, Any]] = []
    for i, slide in enumerate(lecture.get("slides") or []):
        st = slide.get("type") or "content"
        if st == "quiz":
            opts = slide.get("options") or []
            result.append(
                {
                    "step": i + 1,
                    "title": "随堂测验",
                    "narration": slide.get("narration") or slide.get("question") or "",
                    "visual": "\n".join(str(o) for o in opts),
                    "emoji": "❓",
                    "duration_sec": 12,
                }
            )
            continue
        bullets = slide.get("bullets") or []
        visual_parts = [f"• {b}" for b in bullets]
        if slide.get("highlight"):
            visual_parts.append(f"★ {slide['highlight']}")
        narration = slide.get("narration") or ""
        result.append(
            {
                "step": i + 1,
                "title": slide.get("title") or f"第{i + 1}页",
                "narration": narration,
                "visual": "\n".join(visual_parts),
                "emoji": "📖",
                "duration_sec": max(8, min(28, len(narration) // 6 or 10)),
            }
        )
    return result


def script_from_lecture(lecture: dict[str, Any]) -> str:
    parts: list[str] = []
    for slide in lecture.get("slides") or []:
        title = slide.get("title") or slide.get("question") or ""
        narration = slide.get("narration") or ""
        if title:
            parts.append(f"## {title}")
        if narration:
            parts.append(str(narration))
    return "\n\n".join(parts) or str(lecture.get("topic") or "沉浸式讲解")


class TutorLectureResourceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.resource_repo = ResourceRepository(db)

    def save_lecture_as_resource(
        self,
        user: SysUser,
        session_no: str,
        lecture: dict[str, Any],
        ext: dict[str, Any],
    ) -> int | None:
        """入库 video 资源并发布（status=2）。返回 resource_id。"""
        lecture_id = lecture.get("lecture_id")
        if not lecture_id:
            return None

        mapping: dict[str, int] = dict(ext.get("lecture_resources") or {})
        existing_id = mapping.get(str(lecture_id))
        if existing_id and self.resource_repo.get_by_id(existing_id):
            return int(existing_id)

        type_def = self.resource_repo.get_type_by_code("video")
        if not type_def:
            logger.warning("video resource type not found, skip lecture resource sync")
            return None

        topic = str(lecture.get("topic") or "沉浸式讲解").strip()[:128] or "沉浸式讲解"
        slides = lecture.get("slides") or []
        slide_count = len(slides)
        title = f"{topic} - AI视频讲解"[:256]
        summary = f"智学体智能答疑生成的沉浸式视频讲解，共 {slide_count} 页"
        animation_slides = animation_slides_from_lecture(lecture)
        script = script_from_lecture(lecture)

        resource = ResResource(
            resource_no=str(uuid.uuid4()),
            user_id=user.id,
            type_id=type_def.id,
            title=title,
            summary=summary[:500],
            topic=topic,
            difficulty=3,
            status=2,
            audit_status=1,
            fact_check_status=0,
            content_hash=hashlib.sha256(script.encode()).hexdigest(),
            ext_json={
                "source": "tutor_immersive_lecture",
                "session_no": session_no,
                "lecture_id": str(lecture_id),
                "slide_count": slide_count,
            },
            published_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        self.db.add(resource)
        self.db.flush()

        duration = sum(int(s.get("duration_sec") or 10) for s in animation_slides)
        anim_data = {
            "slides": animation_slides,
            "render_status": "ready",
            "style": "immersive_lecture",
            "teacher_name": "AI 教师",
            "session_no": session_no,
            "lecture_id": str(lecture_id),
            # 完整讲义（图二 TutorLecture 页），避免只能看到动画预览
            "lecture": {
                "lecture_id": str(lecture_id),
                "topic": topic,
                "slides": slides,
                "content_slide_count": lecture.get("content_slide_count"),
                "quiz_count": lecture.get("quiz_count"),
                "recommendations": lecture.get("recommendations") or [],
                "created_at": lecture.get("created_at"),
            },
        }
        self.db.add(
            ResVideo(
                resource_id=resource.id,
                script_content=script,
                storyboard=animation_slides,
                duration_sec=duration,
                animation_type="immersive_lecture",
                animation_data=anim_data,
                ext_json={
                    "slides": animation_slides,
                    "status": "ready",
                    "session_no": session_no,
                    "lecture_id": str(lecture_id),
                    "lecture": anim_data["lecture"],
                },
            )
        )
        self.db.commit()

        mapping[str(lecture_id)] = resource.id
        ext["lecture_resources"] = mapping
        logger.info(
            "Synced tutor lecture %s to resource %s for user %s",
            lecture_id,
            resource.id,
            user.id,
        )
        return resource.id
