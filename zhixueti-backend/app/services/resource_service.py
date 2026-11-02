"""Resource center service — delegates generation to multi-agent orchestrator."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundException
from app.models.resource import ResResource
from app.models.sys import SysUser
from app.repositories.resource_repository import ResourceRepository
from app.schemas.resource import ResourceGenerateRequest, ResourceResponse
from app.services.resource_orchestrator import ResourceOrchestrator, schedule_resource_generation


def _lecture_from_animation_slides(
    topic: str,
    slides: list[dict[str, Any]],
    *,
    lecture_id: str | None = None,
    resource_id: int | None = None,
) -> dict[str, Any]:
    """将旧版分镜动画转为图二 TutorLecture 所需的讲义结构。"""
    out_slides: list[dict[str, Any]] = []
    for i, s in enumerate(slides or []):
        visual = str(s.get("visual") or "").strip()
        bullets = [ln.lstrip("•★ ").strip() for ln in visual.splitlines() if ln.strip()]
        highlight = None
        if bullets and str(s.get("visual") or "").find("★") >= 0:
            for ln in visual.splitlines():
                if "★" in ln:
                    highlight = ln.replace("★", "").strip()
                    bullets = [b for b in bullets if b != highlight]
                    break
        title = str(s.get("title") or f"第{i + 1}页")
        narration = str(s.get("narration") or "")
        if title == "随堂测验" or (s.get("emoji") == "❓"):
            opts = [ln.strip() for ln in visual.splitlines() if ln.strip()]
            out_slides.append(
                {
                    "id": i + 1,
                    "type": "quiz",
                    "title": title,
                    "question": narration or title,
                    "options": opts or ["A", "B", "C", "D"],
                    "answer": "A",
                    "narration": narration,
                    "analysis": "",
                }
            )
        else:
            out_slides.append(
                {
                    "id": i + 1,
                    "type": "content",
                    "title": title,
                    "bullets": bullets or ([narration[:80]] if narration else ["请听讲解"]),
                    "highlight": highlight,
                    "narration": narration,
                }
            )
    lid = lecture_id or (f"resource-{resource_id}" if resource_id else "resource-lecture")
    return {
        "lecture_id": str(lid),
        "topic": topic or "AI视频讲解",
        "slides": out_slides,
        "content_slide_count": sum(1 for x in out_slides if x.get("type") == "content"),
        "quiz_count": sum(1 for x in out_slides if x.get("type") == "quiz"),
        "recommendations": [],
        "resource_id": resource_id,
    }


class ResourceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.resource_repo = ResourceRepository(db)
        self.orchestrator = ResourceOrchestrator(db)

    def _to_response(
        self,
        resource: ResResource,
        author_name: str | None = None,
        *,
        include_detail: bool = True,
        types_map: dict | None = None,
    ) -> ResourceResponse:
        types = types_map if types_map is not None else {t.id: t for t in self.resource_repo.get_types()}
        t = types.get(resource.type_id)
        detail = None
        if include_detail:
            ext = self.resource_repo.get_extension(resource)
            if ext and ext["data"]:
                obj = ext["data"]
                tc = ext["type_code"]
                if tc == "document":
                    detail = {"content_md": obj.content_md, "word_count": obj.word_count}
                elif tc == "mindmap":
                    map_data = obj.map_data or {}
                    detail = {
                        "map_data": map_data,
                        "mermaid": map_data.get("mermaid") if map_data else "",
                        "nodes": map_data.get("nodes", []),
                        "edges": map_data.get("edges", []),
                    }
                elif tc == "reading":
                    from app.agents.specialists import _enrich_readings

                    detail = {"reading_list": _enrich_readings(resource.topic or "", obj.reading_list)}
                elif tc == "video":
                    anim = obj.animation_data or {}
                    extj = obj.ext_json or {}
                    slides = anim.get("slides") or extj.get("slides") or obj.storyboard or []
                    if not isinstance(slides, list):
                        slides = []
                    lecture = anim.get("lecture") or extj.get("lecture")
                    session_no = anim.get("session_no") or extj.get("session_no")
                    lecture_id = (
                        (lecture or {}).get("lecture_id")
                        if isinstance(lecture, dict)
                        else None
                    ) or anim.get("lecture_id") or extj.get("lecture_id")
                    # 旧资源只有分镜：合成图二讲义，避免永远停在动画预览
                    if (not isinstance(lecture, dict) or not lecture.get("slides")) and slides:
                        lecture = _lecture_from_animation_slides(
                            resource.title or resource.topic or "AI视频讲解",
                            slides,
                            lecture_id=str(lecture_id) if lecture_id else None,
                            resource_id=resource.id,
                        )
                        lecture_id = lecture.get("lecture_id")
                    style = (
                        anim.get("style")
                        or obj.animation_type
                        or ("immersive_lecture" if lecture else None)
                    )
                    detail = {
                        "script_content": obj.script_content,
                        "storyboard": obj.storyboard,
                        "slides": slides,
                        "animation_type": style,
                        "animation_data": {
                            **anim,
                            "session_no": session_no,
                            "lecture_id": lecture_id,
                            "style": style or "immersive_lecture",
                            "lecture": lecture,
                        },
                        "video_url": obj.video_url,
                        "render_status": anim.get("render_status", "ready"),
                        "session_no": session_no,
                        "lecture_id": lecture_id,
                        "lecture": lecture,
                    }
                elif tc == "code":
                    ext_json = obj.ext_json or {}
                    code_content = obj.code_content
                    explanation = obj.explanation
                    # 兼容历史坏数据：整段 JSON 被写入 explanation / code_content
                    blob = None
                    for candidate in (explanation, code_content):
                        if isinstance(candidate, str) and candidate.strip().startswith("{") and "content_mode" in candidate:
                            try:
                                import json as _json
                                parsed = _json.loads(candidate)
                                if isinstance(parsed, dict) and (
                                    parsed.get("code_content") or parsed.get("practice_items")
                                ):
                                    blob = parsed
                                    break
                            except Exception:
                                pass
                    if blob:
                        code_content = blob.get("code_content") or code_content
                        if isinstance(explanation, str) and explanation.strip().startswith("{"):
                            explanation = blob.get("explanation") or ""
                        ext_json = {
                            **ext_json,
                            "practice_items": blob.get("practice_items", ext_json.get("practice_items")),
                            "practice_type": blob.get("practice_type", ext_json.get("practice_type")),
                            "objective": blob.get("objective", ext_json.get("objective")),
                        }
                    module_label = ext_json.get("module_label") or "实战演练"
                    if module_label == "代码实操":
                        module_label = "实战演练"
                    detail = {
                        "code_content": code_content,
                        "language": blob.get("language", obj.language) if blob else obj.language,
                        "explanation": explanation,
                        "test_cases": obj.test_cases,
                        "is_programming": ext_json.get("is_programming", obj.language not in ("practice", "english", "math")),
                        "module_label": module_label,
                        "practice_type": ext_json.get("practice_type"),
                        "practice_items": ext_json.get("practice_items"),
                        "objective": ext_json.get("objective"),
                        "subject_category": ext_json.get("subject_category"),
                    }
                elif tc == "question":
                    detail = {"questions": ext.get("questions", [])}
        return ResourceResponse(
            id=resource.id,
            resource_no=resource.resource_no,
            type_code=t.type_code if t else "",
            type_name=(
                "实战演练" if t and t.type_code == "code"
                else ("AI视频讲解" if t and t.type_code == "video"
                      else (t.type_name if t else ""))
            ),
            title=(
                resource.title.replace(" - 代码实操", " - 实战演练")
                .replace(" - 教学动画", " - AI视频讲解")
                .replace(" - 视频讲解", " - AI视频讲解")
                if (t and t.type_code in ("code", "video"))
                else resource.title
            ),
            summary=(
                (f"{resource.topic} · 实战演练" if resource.topic else "实战演练")
                if (
                    t
                    and t.type_code == "code"
                    and isinstance(resource.summary, str)
                    and resource.summary.strip().startswith("{")
                    and "content_mode" in resource.summary
                )
                else resource.summary
            ),
            topic=resource.topic,
            difficulty=resource.difficulty,
            status=resource.status,
            audit_status=resource.audit_status,
            fact_check_status=resource.fact_check_status,
            citation_count=resource.citation_count,
            agent_task_id=resource.agent_task_id,
            created_at=resource.created_at,
            published_at=resource.published_at,
            detail=detail,
            author_name=author_name,
        )

    def _username_map(self, user_ids: set[int]) -> dict[int, str]:
        if not user_ids:
            return {}
        rows = (
            self.db.query(SysUser.id, SysUser.nickname, SysUser.username)
            .filter(SysUser.id.in_(user_ids), SysUser.deleted_at.is_(None))
            .all()
        )
        return {r[0]: (r[1] or r[2]) for r in rows}

    def list_resources(self, user: SysUser, type_code: str | None, topic: str | None, status: int | None, page: int, page_size: int):
        """个人资源中心：严格限定当前登录用户。列表不带正文详情，加快加载。"""
        items, total = self.resource_repo.list_by_user(user.id, type_code, topic, status, page, page_size)
        types = {t.id: t for t in self.resource_repo.get_types()}
        return [self._to_response(r, include_detail=False, types_map=types) for r in items], total

    def list_public_resources(
        self,
        type_code: str | None,
        topic: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[ResourceResponse], int]:
        """资源广场：仅 status=2 已发布资源，所有人可见。"""
        items, total = self.resource_repo.list_published(
            type_code=type_code, topic=topic, page=page, page_size=page_size
        )
        names = self._username_map({r.user_id for r in items})
        types = {t.id: t for t in self.resource_repo.get_types()}
        return [
            self._to_response(r, author_name=names.get(r.user_id), include_detail=False, types_map=types)
            for r in items
        ], total

    def get_resource(self, user: SysUser, resource_id: int) -> ResourceResponse:
        resource = self.resource_repo.get_by_id(resource_id)
        if not resource or resource.user_id != user.id:
            raise NotFoundException(ErrorCode.RESOURCE_NOT_FOUND)
        return self._to_response(resource, include_detail=True)

    def get_public_resource(self, resource_id: int) -> ResourceResponse:
        """广场预览：仅允许访问已发布资源，返回完整 detail。"""
        resource = self.resource_repo.get_by_id(resource_id)
        if not resource or resource.status != 2:
            raise NotFoundException(ErrorCode.RESOURCE_NOT_FOUND)
        names = self._username_map({resource.user_id})
        return self._to_response(resource, author_name=names.get(resource.user_id), include_detail=True)

    async def start_generation(self, user: SysUser, req: ResourceGenerateRequest) -> dict:
        """Create task and schedule multi-agent pipeline in background."""
        task = self.orchestrator.create_task(user, req)
        schedule_resource_generation(user.id, task.task_no, req)
        return {
            "task_no": task.task_no,
            "resource_ids": [],
            "message": "多智能体协同生成已启动，请通过 SSE/轮询追踪进度",
        }
