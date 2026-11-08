"""Admin content management services — resources, profile, paths, generated content, documents."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenException, NotFoundException, ValidationException
from app.models.path import PthKnowledgePoint
from app.models.profile import UsrProfileDimensionDef
from app.models.sys import SysUser
from app.models.tutor import TutTutorSession
from app.profile_dimensions import CORE_PROFILE_DIMENSIONS, DIMENSION_BY_CODE
from app.repositories.config_repository import ConfigRepository
from app.repositories.path_repository import PathRepository
from app.repositories.permission_repository import PermissionRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.resource_repository import ResourceRepository
from app.repositories.tutor_repository import TutorRepository
from app.repositories.user_repository import UserRepository
from app.schemas.admin_content import (
    AdminDocumentListItem,
    AdminDocumentPreviewResponse,
    AdminDocumentSettingsRequest,
    AdminDocumentSettingsResponse,
    AdminImageListItem,
    AdminImagePreviewResponse,
    AdminKnowledgePointCreateRequest,
    AdminKnowledgePointItem,
    AdminKnowledgePointUpdateRequest,
    AdminLectureListItem,
    AdminLecturePreviewResponse,
    AdminPathDetailResponse,
    AdminPathListItem,
    AdminProfileDimensionCreateRequest,
    AdminProfileDimensionItem,
    AdminProfileDimensionUpdateRequest,
    AdminProfileTagItem,
    AdminProfileTagUpsertRequest,
    AdminResourceListItem,
    AdminResourceListResponse,
    AdminResourcePreviewResponse,
)
from app.services.config_service import (
    DOCUMENT_ALLOWED_EXTENSIONS,
    DOCUMENT_AUDIT_ENABLED,
    DOCUMENT_MAX_FILE_MB,
    PROFILE_TAG_LIBRARY,
    ConfigService,
)


class _AdminPermMixin:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.perm_repo = PermissionRepository(db)

    def _assert_perm(self, operator_id: int, perm_code: str) -> None:
        if perm_code not in self.perm_repo.get_user_permission_codes(operator_id):
            raise ForbiddenException(f"缺少权限: {perm_code}")

    def _username_map(self, user_ids: set[int]) -> dict[int, str]:
        if not user_ids:
            return {}
        rows = (
            self.db.query(SysUser.id, SysUser.username)
            .filter(SysUser.id.in_(user_ids), SysUser.deleted_at.is_(None))
            .all()
        )
        return {r[0]: r[1] for r in rows}


class AdminResourceService(_AdminPermMixin):
    def __init__(self, db: Session) -> None:
        super().__init__(db)
        self.repo = ResourceRepository(db)

    def list_resources(
        self,
        operator_id: int,
        *,
        keyword: str | None = None,
        type_code: str | None = None,
        status: int | None = None,
        user_id: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> AdminResourceListResponse:
        self._assert_perm(operator_id, "menu:resources")
        items, total = self.repo.list_all(
            keyword=keyword,
            type_code=type_code,
            status=status,
            user_id=user_id,
            page=page,
            page_size=page_size,
        )
        type_map = {t.id: t for t in self.repo.get_types()}
        users = self._username_map({r.user_id for r in items})
        result: list[AdminResourceListItem] = []
        for r in items:
            tdef = type_map.get(r.type_id)
            result.append(
                AdminResourceListItem(
                    id=r.id,
                    resource_no=r.resource_no,
                    user_id=r.user_id,
                    username=users.get(r.user_id),
                    type_code=tdef.type_code if tdef else "",
                    type_name=tdef.type_name if tdef else "",
                    title=r.title,
                    topic=r.topic,
                    difficulty=r.difficulty,
                    status=r.status,
                    fact_check_status=r.fact_check_status,
                    created_at=r.created_at,
                    published_at=r.published_at,
                )
            )
        return AdminResourceListResponse(items=result, total=total, page=page, page_size=page_size)

    def set_status(self, operator_id: int, resource_id: int, status: int) -> None:
        self._assert_perm(operator_id, "btn:resource:publish")
        res = self.repo.get_by_id(resource_id)
        if not res:
            raise NotFoundException(message="资源不存在")
        self.repo.update_status(res, status)

    def batch_status(self, operator_id: int, ids: list[int], status: int) -> int:
        self._assert_perm(operator_id, "btn:resource:publish")
        return self.repo.batch_update_status(ids, status)

    def delete(self, operator_id: int, resource_id: int) -> None:
        self._assert_perm(operator_id, "btn:resource:delete")
        res = self.repo.get_by_id(resource_id)
        if not res:
            raise NotFoundException(message="资源不存在")
        self.repo.soft_delete(res)

    def export_json(self, operator_id: int, limit: int = 200) -> list[dict[str, Any]]:
        self._assert_perm(operator_id, "menu:resources")
        items, _ = self.repo.list_all(page=1, page_size=min(limit, 500))
        type_map = {t.id: t for t in self.repo.get_types()}
        out: list[dict[str, Any]] = []
        for r in items:
            tdef = type_map.get(r.type_id)
            out.append(
                {
                    "resource_no": r.resource_no,
                    "title": r.title,
                    "topic": r.topic,
                    "type_code": tdef.type_code if tdef else "",
                    "difficulty": r.difficulty,
                    "status": r.status,
                    "summary": r.summary,
                }
            )
        return out

    def get_preview(self, operator_id: int, resource_id: int) -> AdminResourcePreviewResponse:
        """管理员预览资源完整内容，按类型返回结构化数据。"""
        self._assert_perm(operator_id, "menu:resources")
        res = self.repo.get_by_id(resource_id)
        if not res:
            raise NotFoundException(message="资源不存在")
        types = {t.id: t for t in self.repo.get_types()}
        tdef = types.get(res.type_id)
        type_code = tdef.type_code if tdef else "unknown"
        type_name = tdef.type_name if tdef else ""
        ext = self.repo.get_extension(res)
        content: dict[str, Any] = {"summary": res.summary}
        preview_type = type_code

        if ext and ext.get("data"):
            obj = ext["data"]
            tc = ext["type_code"]
            if tc == "document":
                content = {"content_md": obj.content_md, "word_count": obj.word_count}
            elif tc == "mindmap":
                map_data = obj.map_data or {}
                content = {
                    "mermaid": map_data.get("mermaid", ""),
                    "map_data": map_data,
                    "nodes": map_data.get("nodes", []),
                    "edges": map_data.get("edges", []),
                }
            elif tc == "reading":
                content = {"reading_list": obj.reading_list or []}
            elif tc == "video":
                slides = (obj.animation_data or {}).get("slides") or (obj.ext_json or {}).get("slides") or []
                content = {
                    "script_content": obj.script_content,
                    "storyboard": obj.storyboard,
                    "slides": slides,
                    "video_url": obj.video_url,
                    "animation_type": obj.animation_type,
                }
                preview_type = "video"
            elif tc == "code":
                ext_json = obj.ext_json or {}
                content = {
                    "code_content": obj.code_content,
                    "language": obj.language,
                    "explanation": obj.explanation,
                    "test_cases": obj.test_cases,
                    "practice_items": ext_json.get("practice_items"),
                }
            elif tc == "question":
                content = {"questions": ext.get("questions", [])}
        elif res.summary:
            content = {"text": res.summary}
            preview_type = "text"

        return AdminResourcePreviewResponse(
            id=res.id,
            title=res.title,
            type_code=type_code,
            type_name=type_name,
            status=res.status,
            topic=res.topic,
            summary=res.summary,
            preview_type=preview_type,
            content=content,
        )


class AdminProfileConfigService(_AdminPermMixin):
    def __init__(self, db: Session) -> None:
        super().__init__(db)
        self.repo = ProfileRepository(db)
        self.config = ConfigService(db)

    def _dim_to_item(self, d: UsrProfileDimensionDef) -> AdminProfileDimensionItem:
        ext = d.ext_json or {}
        questions = ext.get("guide_questions")
        if not questions:
            meta = DIMENSION_BY_CODE.get(d.dimension_code)
            questions = list(meta.guide_questions) if meta else []
        return AdminProfileDimensionItem(
            id=d.id,
            dimension_code=d.dimension_code,
            dimension_name=d.dimension_name,
            dimension_desc=d.dimension_desc,
            collect_method=d.collect_method,
            weight=float(d.weight),
            sort_order=d.sort_order,
            is_required=d.is_required,
            status=d.status,
            guide_questions=[str(q) for q in questions],
            tags=[str(t) for t in (ext.get("tags") or [])],
        )

    def list_dimensions(self, operator_id: int) -> list[AdminProfileDimensionItem]:
        self._assert_perm(operator_id, "menu:profile-config")
        return [self._dim_to_item(d) for d in self.repo.list_all_dimension_defs()]

    def create_dimension(self, operator_id: int, req: AdminProfileDimensionCreateRequest) -> AdminProfileDimensionItem:
        self._assert_perm(operator_id, "btn:profile-config:edit")
        if self.repo.get_dimension_def_by_code(req.dimension_code):
            raise ValidationException("维度编码已存在")
        ext: dict[str, Any] = {}
        if req.guide_questions:
            ext["guide_questions"] = req.guide_questions
        dim = UsrProfileDimensionDef(
            dimension_code=req.dimension_code,
            dimension_name=req.dimension_name,
            dimension_desc=req.dimension_desc,
            value_schema={"type": "object"},
            collect_method=req.collect_method,
            weight=req.weight,
            sort_order=req.sort_order,
            is_required=req.is_required,
            status=1,
            ext_json=ext or None,
        )
        return self._dim_to_item(self.repo.save_dimension_def(dim))

    def update_dimension(
        self, operator_id: int, dim_id: int, req: AdminProfileDimensionUpdateRequest
    ) -> AdminProfileDimensionItem:
        self._assert_perm(operator_id, "btn:profile-config:edit")
        dim = self.repo.get_dimension_def_by_id(dim_id)
        if not dim:
            raise NotFoundException(message="维度不存在")
        if req.dimension_name is not None:
            dim.dimension_name = req.dimension_name
        if req.dimension_desc is not None:
            dim.dimension_desc = req.dimension_desc
        if req.collect_method is not None:
            dim.collect_method = req.collect_method
        if req.weight is not None:
            dim.weight = req.weight
        if req.sort_order is not None:
            dim.sort_order = req.sort_order
        if req.is_required is not None:
            dim.is_required = req.is_required
        if req.status is not None:
            dim.status = req.status
        if req.guide_questions is not None:
            ext = dict(dim.ext_json or {})
            ext["guide_questions"] = req.guide_questions
            dim.ext_json = ext
        self.db.commit()
        self.db.refresh(dim)
        return self._dim_to_item(dim)

    def delete_dimension(self, operator_id: int, dim_id: int) -> None:
        self._assert_perm(operator_id, "btn:profile-config:edit")
        dim = self.repo.get_dimension_def_by_id(dim_id)
        if not dim:
            raise NotFoundException(message="维度不存在")
        dim.status = 0
        self.db.commit()

    def list_tags(self, operator_id: int) -> list[AdminProfileTagItem]:
        self._assert_perm(operator_id, "menu:profile-config")
        raw = self.config.get_json(PROFILE_TAG_LIBRARY, [])
        return [AdminProfileTagItem(**t) for t in raw if isinstance(t, dict) and t.get("code")]

    def upsert_tag(self, operator_id: int, req: AdminProfileTagUpsertRequest) -> list[AdminProfileTagItem]:
        self._assert_perm(operator_id, "btn:profile-config:edit")
        tags = self.config.get_json(PROFILE_TAG_LIBRARY, [])
        found = False
        for t in tags:
            if t.get("code") == req.code:
                t.update(req.model_dump())
                found = True
                break
        if not found:
            tags.append(req.model_dump())
        self.config.set_value(PROFILE_TAG_LIBRARY, json.dumps(tags, ensure_ascii=False), config_type="json")
        return self.list_tags(operator_id)

    def delete_tag(self, operator_id: int, code: str) -> list[AdminProfileTagItem]:
        self._assert_perm(operator_id, "btn:profile-config:edit")
        tags = [t for t in self.config.get_json(PROFILE_TAG_LIBRARY, []) if t.get("code") != code]
        self.config.set_value(PROFILE_TAG_LIBRARY, json.dumps(tags, ensure_ascii=False), config_type="json")
        return self.list_tags(operator_id)

    def seed_guide_questions(self) -> None:
        """Sync default question guides into dimension ext_json (idempotent)."""
        from app.profile_dimensions import QUESTIONS_PER_DIMENSION

        for c in CORE_PROFILE_DIMENSIONS:
            dim = self.repo.get_dimension_def_by_code(c.code)
            if not dim:
                continue
            ext = dict(dim.ext_json or {})
            existing = ext.get("guide_questions") or []
            # 旧版每维多问 → 同步为每维 1 条指引；空值也写入默认
            if not existing or len(existing) > QUESTIONS_PER_DIMENSION:
                ext["guide_questions"] = list(c.guide_questions)
                ext.setdefault("extract_hint", c.extract_hint)
                dim.ext_json = ext
        self.db.commit()


class AdminPathService(_AdminPermMixin):
    def __init__(self, db: Session) -> None:
        super().__init__(db)
        self.repo = PathRepository(db)

    def list_paths(
        self,
        operator_id: int,
        *,
        keyword: str | None = None,
        user_id: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AdminPathListItem], int]:
        self._assert_perm(operator_id, "menu:learning-paths")
        items, total = self.repo.list_all_paths(keyword=keyword, user_id=user_id, page=page, page_size=page_size)
        users = self._username_map({p.user_id for p in items})
        return (
            [
                AdminPathListItem(
                    id=p.id,
                    path_no=p.path_no,
                    user_id=p.user_id,
                    username=users.get(p.user_id),
                    title=p.title,
                    goal=p.goal,
                    total_nodes=p.total_nodes,
                    status=p.status,
                    created_at=p.created_at,
                )
                for p in items
            ],
            total,
        )

    def get_path_detail(self, operator_id: int, path_id: int) -> AdminPathDetailResponse:
        self._assert_perm(operator_id, "menu:learning-paths")
        path = self.repo.get_path_by_id(path_id)
        if not path:
            raise NotFoundException(message="学习路径不存在")
        users = self._username_map({path.user_id})
        nodes = self.repo.get_nodes(path_id)
        edges = self.repo.get_edges(path_id)
        return AdminPathDetailResponse(
            id=path.id,
            path_no=path.path_no,
            user_id=path.user_id,
            username=users.get(path.user_id),
            title=path.title,
            goal=path.goal,
            total_nodes=path.total_nodes,
            status=path.status,
            nodes=[
                {
                    "id": n.id,
                    "node_code": n.node_code,
                    "node_name": n.node_name,
                    "node_type": n.node_type,
                    "sort_order": n.sort_order,
                    "difficulty": n.difficulty,
                    "estimated_min": n.estimated_min,
                    "knowledge_point_id": n.knowledge_point_id,
                    "ext_json": n.ext_json,
                }
                for n in nodes
            ],
            edges=[
                {"id": e.id, "from_node_id": e.from_node_id, "to_node_id": e.to_node_id, "edge_type": e.edge_type}
                for e in edges
            ],
        )

    def list_knowledge_points(self, operator_id: int) -> list[AdminKnowledgePointItem]:
        self._assert_perm(operator_id, "menu:learning-paths")
        return [
            AdminKnowledgePointItem(
                id=p.id,
                point_code=p.point_code,
                point_name=p.point_name,
                domain=p.domain,
                difficulty=p.difficulty,
                estimated_min=p.estimated_min,
                description=p.description,
                prerequisite_ids=p.prerequisite_ids,
                status=p.status,
            )
            for p in self.repo.list_all_knowledge_points()
        ]

    def create_knowledge_point(
        self, operator_id: int, req: AdminKnowledgePointCreateRequest
    ) -> AdminKnowledgePointItem:
        self._assert_perm(operator_id, "btn:path:edit")
        if self.repo.get_knowledge_point_by_code(req.point_code):
            raise ValidationException("知识点编码已存在")
        point = PthKnowledgePoint(
            point_code=req.point_code,
            point_name=req.point_name,
            domain=req.domain,
            difficulty=req.difficulty,
            estimated_min=req.estimated_min,
            description=req.description,
            prerequisite_ids=req.prerequisite_ids,
            status=1,
        )
        saved = self.repo.save_knowledge_point(point)
        return AdminKnowledgePointItem(
            id=saved.id,
            point_code=saved.point_code,
            point_name=saved.point_name,
            domain=saved.domain,
            difficulty=saved.difficulty,
            estimated_min=saved.estimated_min,
            description=saved.description,
            prerequisite_ids=saved.prerequisite_ids,
            status=saved.status,
        )

    def update_knowledge_point(
        self, operator_id: int, point_id: int, req: AdminKnowledgePointUpdateRequest
    ) -> AdminKnowledgePointItem:
        self._assert_perm(operator_id, "btn:path:edit")
        point = self.repo.get_knowledge_point_by_id(point_id)
        if not point:
            raise NotFoundException(message="知识点不存在")
        for field in ("point_name", "domain", "difficulty", "estimated_min", "description", "prerequisite_ids", "status"):
            val = getattr(req, field, None)
            if val is not None:
                setattr(point, field, val)
        self.db.commit()
        self.db.refresh(point)
        return AdminKnowledgePointItem(
            id=point.id,
            point_code=point.point_code,
            point_name=point.point_name,
            domain=point.domain,
            difficulty=point.difficulty,
            estimated_min=point.estimated_min,
            description=point.description,
            prerequisite_ids=point.prerequisite_ids,
            status=point.status,
        )

    def delete_knowledge_point(self, operator_id: int, point_id: int) -> None:
        self._assert_perm(operator_id, "btn:path:edit")
        point = self.repo.get_knowledge_point_by_id(point_id)
        if not point:
            raise NotFoundException(message="知识点不存在")
        point.status = 0
        self.db.commit()


class AdminGeneratedContentService(_AdminPermMixin):
    def __init__(self, db: Session) -> None:
        super().__init__(db)
        self.tutor_repo = TutorRepository(db)

    def list_lectures(
        self,
        operator_id: int,
        *,
        keyword: str | None = None,
        user_id: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AdminLectureListItem], int]:
        self._assert_perm(operator_id, "menu:generated-content")
        sessions = self.db.query(TutTutorSession).order_by(TutTutorSession.updated_at.desc()).all()
        rows: list[AdminLectureListItem] = []
        for s in sessions:
            if user_id and s.user_id != user_id:
                continue
            ext = s.ext_json or {}
            lectures = ext.get("lectures") or {}
            for lid, lec in lectures.items():
                if not isinstance(lec, dict):
                    continue
                title = str(lec.get("title") or lec.get("topic") or lid)
                if keyword and keyword not in title and keyword not in str(lec.get("topic") or ""):
                    continue
                slides = lec.get("slides") or []
                rows.append(
                    AdminLectureListItem(
                        session_id=s.id,
                        session_no=s.session_no,
                        user_id=s.user_id,
                        lecture_id=str(lid),
                        title=title,
                        topic=lec.get("topic"),
                        slide_count=len(slides) if isinstance(slides, list) else 0,
                        created_at=lec.get("created_at") or (s.updated_at.isoformat() if s.updated_at else None),
                    )
                )
        users = self._username_map({r.user_id for r in rows})
        for r in rows:
            r.username = users.get(r.user_id)
        total = len(rows)
        start = (page - 1) * page_size
        return rows[start : start + page_size], total

    def list_images(
        self,
        operator_id: int,
        *,
        keyword: str | None = None,
        user_id: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AdminImageListItem], int]:
        self._assert_perm(operator_id, "menu:generated-content")
        sessions = self.db.query(TutTutorSession).order_by(TutTutorSession.updated_at.desc()).all()
        rows: list[AdminImageListItem] = []
        for s in sessions:
            if user_id and s.user_id != user_id:
                continue
            store = (s.ext_json or {}).get("message_store") or {}
            for round_no, meta in store.items():
                if not isinstance(meta, dict):
                    continue
                mm = meta.get("multimodal") or meta
                if mm.get("type") != "image":
                    continue
                title = str(mm.get("title") or "知识点示意图")
                if keyword and keyword not in title and keyword not in str(mm.get("caption") or ""):
                    continue
                rows.append(
                    AdminImageListItem(
                        session_id=s.id,
                        session_no=s.session_no,
                        user_id=s.user_id,
                        round_no=str(round_no),
                        title=title,
                        caption=mm.get("caption"),
                        created_at=s.updated_at.isoformat() if s.updated_at else None,
                    )
                )
        users = self._username_map({r.user_id for r in rows})
        for r in rows:
            r.username = users.get(r.user_id)
        total = len(rows)
        start = (page - 1) * page_size
        return rows[start : start + page_size], total

    def delete_lecture(self, operator_id: int, session_id: int, lecture_id: str) -> None:
        self._assert_perm(operator_id, "btn:content:delete")
        session = self.db.query(TutTutorSession).filter(TutTutorSession.id == session_id).first()
        if not session:
            raise NotFoundException(message="会话不存在")
        ext = dict(session.ext_json or {})
        lectures = dict(ext.get("lectures") or {})
        if lecture_id not in lectures:
            raise NotFoundException(message="讲解不存在")
        del lectures[lecture_id]
        ext["lectures"] = lectures
        session.ext_json = ext
        self.db.commit()

    def delete_image(self, operator_id: int, session_id: int, round_no: str) -> None:
        self._assert_perm(operator_id, "btn:content:delete")
        session = self.db.query(TutTutorSession).filter(TutTutorSession.id == session_id).first()
        if not session:
            raise NotFoundException(message="会话不存在")
        ext = dict(session.ext_json or {})
        store = dict(ext.get("message_store") or {})
        if round_no not in store:
            raise NotFoundException(message="生成内容不存在")
        del store[round_no]
        ext["message_store"] = store
        session.ext_json = ext
        self.db.commit()

    def get_lecture_preview(
        self, operator_id: int, session_id: int, lecture_id: str
    ) -> AdminLecturePreviewResponse:
        """获取讲解完整内容供管理员预览。"""
        self._assert_perm(operator_id, "menu:generated-content")
        session = self.db.query(TutTutorSession).filter(TutTutorSession.id == session_id).first()
        if not session:
            raise NotFoundException(message="会话不存在")
        ext = session.ext_json or {}
        lec = (ext.get("lectures") or {}).get(lecture_id)
        if not lec or not isinstance(lec, dict):
            raise NotFoundException(message="讲解不存在")
        slides = lec.get("slides") or []
        if not isinstance(slides, list):
            slides = []
        title = str(lec.get("title") or lec.get("topic") or lecture_id)
        return AdminLecturePreviewResponse(
            session_id=session_id,
            lecture_id=lecture_id,
            title=title,
            topic=lec.get("topic"),
            slides=slides,
            video_url=lec.get("video_url"),
            recommendations=lec.get("recommendations") or [],
        )

    def get_image_preview(
        self, operator_id: int, session_id: int, round_no: str
    ) -> AdminImagePreviewResponse:
        """获取图像生成内容供管理员预览。"""
        self._assert_perm(operator_id, "menu:generated-content")
        session = self.db.query(TutTutorSession).filter(TutTutorSession.id == session_id).first()
        if not session:
            raise NotFoundException(message="会话不存在")
        store = (session.ext_json or {}).get("message_store") or {}
        meta = store.get(round_no)
        if not meta or not isinstance(meta, dict):
            raise NotFoundException(message="生成内容不存在")
        mm = meta.get("multimodal") or meta
        return AdminImagePreviewResponse(
            session_id=session_id,
            round_no=round_no,
            title=str(mm.get("title") or "知识点示意图"),
            caption=mm.get("caption"),
            mermaid=mm.get("mermaid"),
            image_url=mm.get("image_url") or mm.get("url"),
        )


class AdminDocumentService(_AdminPermMixin):
    def __init__(self, db: Session) -> None:
        super().__init__(db)
        self.config = ConfigService(db)
        from app.core.config import get_settings

        self.base_dir = Path(get_settings().upload_dir) / "tutor_docs"

    def _iter_docs(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        if not self.base_dir.exists():
            return items
        for user_dir in self.base_dir.iterdir():
            if not user_dir.is_dir():
                continue
            try:
                user_id = int(user_dir.name)
            except ValueError:
                continue
            for fp in user_dir.glob("*.json"):
                try:
                    record = json.loads(fp.read_text(encoding="utf-8"))
                    record["_file_size"] = fp.stat().st_size
                    record["_path"] = str(fp)
                    record.setdefault("user_id", user_id)
                    record.setdefault("audit_status", 1 if not self.config.document_audit_enabled() else 0)
                    items.append(record)
                except (json.JSONDecodeError, OSError):
                    continue
        items.sort(key=lambda x: x.get("uploaded_at") or x.get("doc_id") or "", reverse=True)
        return items

    def list_documents(
        self,
        operator_id: int,
        *,
        keyword: str | None = None,
        audit_status: int | None = None,
        user_id: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AdminDocumentListItem], int]:
        self._assert_perm(operator_id, "menu:documents")
        rows: list[AdminDocumentListItem] = []
        for rec in self._iter_docs():
            if user_id and rec.get("user_id") != user_id:
                continue
            st = int(rec.get("audit_status", 1))
            if audit_status is not None and st != audit_status:
                continue
            fname = str(rec.get("filename") or "")
            if keyword and keyword not in fname:
                continue
            rows.append(
                AdminDocumentListItem(
                    doc_id=str(rec.get("doc_id")),
                    user_id=int(rec.get("user_id")),
                    session_no=rec.get("session_no"),
                    filename=fname,
                    page_count=int(rec.get("page_count") or 0),
                    audit_status=st,
                    file_size=rec.get("_file_size"),
                    uploaded_at=rec.get("uploaded_at"),
                )
            )
        users = self._username_map({r.user_id for r in rows})
        for r in rows:
            r.username = users.get(r.user_id)
        total = len(rows)
        start = (page - 1) * page_size
        return rows[start : start + page_size], total

    def audit_document(self, operator_id: int, user_id: int, doc_id: str, audit_status: int, reason: str | None) -> None:
        self._assert_perm(operator_id, "btn:document:audit")
        fp = self.base_dir / str(user_id) / f"{doc_id}.json"
        if not fp.exists():
            raise NotFoundException(message="文档不存在")
        record = json.loads(fp.read_text(encoding="utf-8"))
        record["audit_status"] = audit_status
        if reason:
            record["audit_reason"] = reason
        fp.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    def batch_audit_documents(
        self, operator_id: int, items: list, audit_status: int, reason: str | None
    ) -> int:
        self._assert_perm(operator_id, "btn:document:audit")
        count = 0
        for item in items:
            fp = self.base_dir / str(item.user_id) / f"{item.doc_id}.json"
            if not fp.exists():
                continue
            record = json.loads(fp.read_text(encoding="utf-8"))
            record["audit_status"] = audit_status
            if reason:
                record["audit_reason"] = reason
            fp.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            count += 1
        return count

    def delete_document(self, operator_id: int, user_id: int, doc_id: str) -> None:
        self._assert_perm(operator_id, "btn:content:delete")
        fp = self.base_dir / str(user_id) / f"{doc_id}.json"
        if fp.exists():
            fp.unlink()

    def get_settings(self, operator_id: int) -> AdminDocumentSettingsResponse:
        self._assert_perm(operator_id, "menu:documents")
        return AdminDocumentSettingsResponse(
            audit_enabled=self.config.document_audit_enabled(),
            max_file_mb=self.config.get_int(DOCUMENT_MAX_FILE_MB, 100),
            allowed_extensions=sorted(self.config.document_allowed_extensions()),
        )

    def update_settings(self, operator_id: int, req: AdminDocumentSettingsRequest) -> AdminDocumentSettingsResponse:
        self._assert_perm(operator_id, "btn:document:audit")
        if req.audit_enabled is not None:
            self.config.set_value(DOCUMENT_AUDIT_ENABLED, str(req.audit_enabled).lower(), config_type="boolean")
        if req.max_file_mb is not None:
            self.config.set_value(DOCUMENT_MAX_FILE_MB, str(req.max_file_mb), config_type="number")
        if req.allowed_extensions is not None:
            self.config.set_value(
                DOCUMENT_ALLOWED_EXTENSIONS,
                json.dumps(req.allowed_extensions, ensure_ascii=False),
                config_type="json",
            )
        ConfigService.clear_cache()
        return self.get_settings(operator_id)

    def get_document_preview(
        self, operator_id: int, user_id: int, doc_id: str
    ) -> AdminDocumentPreviewResponse:
        """获取用户上传文档完整内容供审核预览。"""
        self._assert_perm(operator_id, "menu:documents")
        fp = self.base_dir / str(user_id) / f"{doc_id}.json"
        if not fp.exists():
            raise NotFoundException(message="文档不存在")
        try:
            record = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            raise ValidationException("文档数据损坏，无法预览") from e
        pages = record.get("pages") or []
        if not isinstance(pages, list):
            pages = []
        return AdminDocumentPreviewResponse(
            doc_id=str(record.get("doc_id") or doc_id),
            user_id=int(record.get("user_id") or user_id),
            filename=str(record.get("filename") or ""),
            page_count=int(record.get("page_count") or len(pages)),
            pages=pages,
            full_text=str(record.get("full_text") or ""),
            truncated=bool(record.get("truncated", False)),
        )
