"""Tutor service — multimodal Q&A, document RAG, web search, lecture flow."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.agents.tutor_agent import (
    build_tutor_system_prompt,
    detect_message_type,
    is_exercise_question,
    profile_summary_text,
    resolve_is_exercise,
    wants_full_answer,
)
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppException
from app.core.exceptions import NotFoundException, ValidationException
from app.llm.gateway import LLMGateway
from app.models.sys import SysUser
from app.models.tutor import TutTutorMessage
from app.repositories.agent_repository import AgentRepository
from app.repositories.path_repository import PathRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.resource_repository import ResourceRepository
from app.repositories.tutor_repository import TutorRepository
from app.schemas.tutor import (
    DocCitation,
    KnowledgePointItem,
    RelatedResourceItem,
    TutorMessageItem,
    TutorMessageMeta,
    TutorMessageRequest,
    TutorMessageResponse,
    TutorSessionCreateRequest,
    TutorSessionResponse,
    WebSearchSource,
)
from app.services.path_planner import build_profile_context
from app.services.tutor_document_service import TutorDocumentService
from app.services.tutor_immersive_lecture_service import TutorImmersiveLectureService
from app.services.tutor_lecture_resource_service import TutorLectureResourceService
from app.services.tutor_lecture_service import TutorLectureService
from app.services.tutor_multimodal_service import TutorMultimodalService
from app.services.tutor_web_search_service import TutorWebSearchService
from app.services.vector_kb_service import get_vector_kb_service
from app.utils.async_timeout import async_timeout
from app.utils.tutor_context_utils import trim_messages, trim_text

from app.security.fact_validator import FactValidatorAgent

logger = logging.getLogger(__name__)

_THINK_TAG_RE = re.compile(
    r"<(think|thinking|redacted_reasoning)>[\s\S]*?</\1>",
    re.IGNORECASE,
)


def _strip_think_tags(text: str) -> str:
    cleaned = _THINK_TAG_RE.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


_AI_DISCLAIMER_RE = re.compile(
    r"\n*(?:\*\*)?AI 生成仅供参考(?:\*\*)?[。\.]?\s*",
    re.IGNORECASE,
)


def _student_visible_content(text: str) -> str:
    """Strip internal markers before persisting or returning tutor answers to students."""
    cleaned = FactValidatorAgent.strip_validation_notice(_strip_think_tags(text))
    return _AI_DISCLAIMER_RE.sub("", cleaned).rstrip()


def _friendly_llm_error(exc: BaseException) -> str:
    """Map upstream LLM failures to actionable student-facing copy."""
    text = str(exc) or ""
    low = text.lower()
    if "401" in text or "authorization required" in low or "invalid api key" in low or "incorrect api key" in low:
        return (
            "大模型 API 密钥无效或已失效（DeepSeek 返回 401）。"
            "请在 backend/.env 更新 DEEPSEEK_API_KEY 后重启智学体后端。"
        )
    if "402" in text or "insufficient" in low or "balance" in low or "quota" in low:
        return "大模型账户余额不足或配额已用尽，请充值或更换密钥后重试。"
    if "429" in text or "rate limit" in low:
        return "大模型请求过于频繁，请稍后再试。"
    if "timeout" in low or "timed out" in low:
        return "响应超时，请重试。"
    return "回答生成失败，请重试。"


LLM_STREAM_TIMEOUT_SEC = 30
LLM_STREAM_TIMEOUT_DEEP_SEC = 60
LLM_STREAM_TIMEOUT_WEB_SEC = 40
LLM_STREAM_TIMEOUT_DETAILED_SEC = 55


def _resolve_max_tokens(deep_mode: bool, answer_detail: str, cap: int = 4096) -> int:
    """Map answer_detail to completion budget (Chinese ~1–1.5 chars/token)."""
    if deep_mode:
        base = {"brief": 1000, "normal": 1600, "detailed": 2400}.get(answer_detail, 1600)
    else:
        base = {"brief": 384, "normal": 768, "detailed": 1800}.get(answer_detail, 768)
    return min(base, cap)


def _resolve_stream_timeout(deep_mode: bool, answer_detail: str, web_enabled: bool) -> float:
    if deep_mode:
        return LLM_STREAM_TIMEOUT_DEEP_SEC
    if answer_detail == "detailed":
        return LLM_STREAM_TIMEOUT_DETAILED_SEC
    if web_enabled:
        return LLM_STREAM_TIMEOUT_WEB_SEC
    return LLM_STREAM_TIMEOUT_SEC


class TutorService:
    MAX_ROUNDS = 20

    def __init__(self, db: Session) -> None:
        self.db = db
        self.tutor_repo = TutorRepository(db)
        self.profile_repo = ProfileRepository(db)
        self.path_repo = PathRepository(db)
        self.resource_repo = ResourceRepository(db)
        self.agent_repo = AgentRepository(db)
        self.llm = LLMGateway(db)
        self.doc_service = TutorDocumentService()
        self.web_search = TutorWebSearchService(self.llm)
        self.lecture_service = TutorLectureService(self.llm)
        self.multimodal_service = TutorMultimodalService(self.llm)
        self.immersive_service = TutorImmersiveLectureService(self.llm)
        self.lecture_resource_service = TutorLectureResourceService(db)
        self.vector_kb = get_vector_kb_service()

    def _build_profile_snapshot(self, user: SysUser) -> dict:
        profile = self.profile_repo.get_by_user_id(user.id)
        if not profile:
            return {"major": user.major, "grade": user.grade, "dimensions": {}}
        return build_profile_context(self.profile_repo, profile.id, user)

    def _detect_knowledge_points(self, text: str, domain: str = "machine_learning") -> list[KnowledgePointItem]:
        kps = self.path_repo.get_knowledge_points(domain)
        matched: list[KnowledgePointItem] = []
        seen: set[str] = set()
        for kp in kps:
            if kp.point_code in seen:
                continue
            if kp.point_name in text:
                matched.append(
                    KnowledgePointItem(
                        point_code=kp.point_code,
                        point_name=kp.point_name,
                        domain=kp.domain,
                        difficulty=kp.difficulty,
                    )
                )
                seen.add(kp.point_code)
                continue
            keywords = re.split(r"[/\s、，]", kp.point_name)
            if any(kw and len(kw) >= 2 and kw in text for kw in keywords):
                matched.append(
                    KnowledgePointItem(
                        point_code=kp.point_code,
                        point_name=kp.point_name,
                        domain=kp.domain,
                        difficulty=kp.difficulty,
                    )
                )
                seen.add(kp.point_code)
        return matched[:3]

    def _find_related_resources(self, user_id: int, topic: str) -> list[RelatedResourceItem]:
        items: list[RelatedResourceItem] = []
        for type_code in ("document", "question", "mindmap", "code"):
            matches = self.path_repo.find_matching_resources(user_id, topic, [type_code], limit=1)
            for res, tc, tn in matches:
                items.append(
                    RelatedResourceItem(
                        resource_id=res.id,
                        title=res.title,
                        type_code=tc,
                        type_name=tn,
                        topic=res.topic,
                    )
                )
        return items[:6]

    def _load_exercise_context(self, resource_id: int | None, question_id: int | None) -> str:
        if not resource_id:
            return ""
        resource = self.resource_repo.get_by_id(resource_id)
        if not resource:
            return ""
        ext = self.resource_repo.get_extension(resource)
        if not ext:
            return ""
        if ext.get("type_code") == "question":
            questions = ext.get("questions") or []
            q = questions[0] if questions else None
            if isinstance(q, dict):
                return (
                    f"\n## 关联习题（勿在 hint_level<2 时泄露答案）\n"
                    f"题干: {q.get('stem','')}\n"
                    f"题型: {q.get('question_type','')}\n"
                    f"选项: {q.get('options','')}\n"
                )
        return ""

    def _session_ext(self, session) -> dict:
        return dict(session.ext_json or {})

    def _store_message_meta(self, session, round_no: int, meta: TutorMessageMeta) -> None:
        """将消息 meta（含 slides/multimodal）存入 session.ext_json，兼容历史会话回放。"""
        ext = self._session_ext(session)
        store = dict(ext.get("message_store") or {})
        store[str(round_no)] = meta.model_dump()
        ext["message_store"] = store
        session.ext_json = ext

    def _load_message_meta(self, session, round_no: int, role: str, message_type: str, strategy: str | None) -> TutorMessageMeta | None:
        if role != "assistant":
            return None
        ext = self._session_ext(session)
        raw = (ext.get("message_store") or {}).get(str(round_no))
        if raw and isinstance(raw, dict):
            try:
                meta = TutorMessageMeta.model_validate(raw)
                meta.disclaimer = None
                return meta
            except Exception:
                pass
        return TutorMessageMeta(
            knowledge_points=[],
            related_resources=[],
            message_type=message_type or "text",
            strategy_used=strategy,
            hint_level=int(ext.get("hint_level", 0)),
            is_exercise=bool(ext.get("is_exercise")),
        )

    def _session_to_response(self, session, user: SysUser) -> TutorSessionResponse:
        msgs = self.tutor_repo.get_messages(session.id)
        ext = self._session_ext(session)
        profile_snap = session.profile_snapshot if ext.get("profile_adapt_enabled", True) else None
        return TutorSessionResponse(
            session_no=session.session_no,
            topic=session.topic,
            tutor_mode=session.tutor_mode,
            zpd_level=session.zpd_level,
            status=session.status,
            total_rounds=session.total_rounds,
            profile_summary=profile_summary_text(profile_snap if ext.get("profile_adapt_enabled", True) else None),
            messages=[
                TutorMessageItem(
                    id=m.id,
                    round_no=m.round_no,
                    role=m.role,
                    content=_student_visible_content(m.content) if m.role == "assistant" else m.content,
                    message_type=m.message_type,
                    strategy_used=m.strategy_used,
                    meta=self._load_message_meta(session, m.round_no, m.role, m.message_type, m.strategy_used),
                    created_at=m.created_at,
                )
                for m in msgs
            ],
            created_at=session.created_at,
            updated_at=session.updated_at,
            profile_adapt_enabled=bool(ext.get("profile_adapt_enabled", True)),
            answer_detail=str(ext.get("answer_detail", "normal")),
            show_steps=bool(ext.get("show_steps", True)),
            deep_mode=bool(ext.get("deep_mode", False)),
            web_search_enabled=bool(ext.get("web_search_enabled", False)),
            document_ids=list(ext.get("document_ids") or []),
        )

    async def create_session(self, user: SysUser, req: TutorSessionCreateRequest) -> TutorSessionResponse:
        profile_snapshot = self._build_profile_snapshot(user) if req.profile_adapt_enabled else {}
        task = self.agent_repo.create_task(user.id, "tutor", f"智能答疑: {req.topic[:30]}", {"topic": req.topic})

        ext = {
            "hint_level": 0,
            "is_exercise": is_exercise_question(req.topic),
            "profile_adapt_enabled": req.profile_adapt_enabled,
            "answer_detail": req.answer_detail,
            "show_steps": req.show_steps,
            "deep_mode": req.deep_mode,
            "web_search_enabled": req.web_search_enabled,
            "document_ids": req.document_ids or [],
        }
        if req.resource_id:
            ext["resource_id"] = req.resource_id
            ext["question_id"] = req.question_id

        session = self.tutor_repo.create_session(
            user_id=user.id,
            path_id=req.path_id,
            node_id=req.node_id,
            resource_id=req.resource_id,
            tutor_mode=req.tutor_mode,
            topic=req.topic,
            agent_task_id=task.id,
            profile_snapshot=profile_snapshot,
            ext_json=ext,
        )
        return self._session_to_response(session, user)

    def get_session(self, user: SysUser, session_no: str) -> TutorSessionResponse:
        session = self.tutor_repo.get_session(session_no)
        if not session or session.user_id != user.id:
            raise NotFoundException(ErrorCode.NOT_FOUND, "辅导会话不存在")
        return self._session_to_response(session, user)

    def list_sessions(self, user: SysUser) -> list[TutorSessionResponse]:
        return [self._session_to_response(s, user) for s in self.tutor_repo.list_user_sessions(user.id)]

    def delete_session(self, user: SysUser, session_no: str) -> None:
        session = self.tutor_repo.get_session(session_no)
        if not session or session.user_id != user.id:
            raise NotFoundException(ErrorCode.NOT_FOUND, "辅导会话不存在")
        self.tutor_repo.delete_session(session)

    def update_session_settings(
        self,
        user: SysUser,
        session_no: str,
        document_ids: list[str] | None = None,
        deep_mode: bool | None = None,
        web_search_enabled: bool | None = None,
        answer_detail: str | None = None,
        show_steps: bool | None = None,
        profile_adapt_enabled: bool | None = None,
        tutor_mode: str | None = None,
    ) -> TutorSessionResponse:
        session = self.tutor_repo.get_session(session_no)
        if not session or session.user_id != user.id:
            raise NotFoundException(ErrorCode.NOT_FOUND, "辅导会话不存在")
        ext = self._session_ext(session)
        if document_ids is not None:
            ext["document_ids"] = document_ids
        if deep_mode is not None:
            ext["deep_mode"] = deep_mode
        if web_search_enabled is not None:
            ext["web_search_enabled"] = web_search_enabled
        if answer_detail is not None:
            ext["answer_detail"] = answer_detail
        if show_steps is not None:
            ext["show_steps"] = show_steps
        if profile_adapt_enabled is not None:
            ext["profile_adapt_enabled"] = profile_adapt_enabled
        if tutor_mode is not None:
            session.tutor_mode = tutor_mode
        session.ext_json = ext
        self.tutor_repo.save_session(session)
        return self._session_to_response(session, user)

    def _compute_hint_level(self, session, content: str, request_full: bool, is_exercise: bool) -> int:
        if not is_exercise:
            return 0
        ext = session.ext_json or {}
        level = int(ext.get("hint_level", 0)) if ext.get("is_exercise") else 0
        if wants_full_answer(content, request_full):
            return max(level + 1, 2)
        if session.total_rounds > 0:
            return min(level + 1, 2)
        return level

    async def _search_external_knowledge(
        self,
        query: str,
        *,
        web_enabled: bool,
        user_id: int | None = None,
        task_id: int | None = None,
    ) -> tuple[str, list[WebSearchSource], bool]:
        """联网检索，作为辅导上下文补充。"""
        if not web_enabled:
            return "", [], False
        return await self.web_search.search(query, user_id=user_id, task_id=task_id)

    async def _build_contexts(
        self, user: SysUser, session, session_no: str, content: str, web_enabled: bool
    ) -> tuple[str, str, list[WebSearchSource], list[DocCitation], bool]:
        ext = self._session_ext(session)
        doc_ids = list(ext.get("document_ids") or [])
        doc_ctx, raw_citations = self.doc_service.build_rag_context(
            user.id, session_no, doc_ids, content
        )
        kb_ctx, kb_citations = "", []
        if self.vector_kb.enabled:
            kb_ctx, kb_citations = await self.vector_kb.search(content or session.topic)
        if kb_ctx:
            doc_ctx = "\n\n---\n\n".join([p for p in (doc_ctx, kb_ctx) if p])
        for c in kb_citations:
            raw_citations.append(c)
        doc_ctx = trim_text(doc_ctx, 3500 if web_enabled else 6000)
        citations = [DocCitation(**c) for c in raw_citations]

        web_ctx = ""
        web_sources: list[WebSearchSource] = []
        web_timed_out = False
        if web_enabled:
            web_ctx, web_sources, web_timed_out = await self._search_external_knowledge(
                content or session.topic,
                web_enabled=web_enabled,
                user_id=user.id,
                task_id=session.agent_task_id,
            )

        return doc_ctx, web_ctx, web_sources, citations, web_timed_out

    async def _prepare_chat(
        self,
        user: SysUser,
        session_no: str,
        req: TutorMessageRequest,
        *,
        web_ctx_override: str | None = None,
        web_sources_override: list[WebSearchSource] | None = None,
        web_timed_out_override: bool | None = None,
    ) -> tuple:
        session = self.tutor_repo.get_session(session_no)
        if not session or session.user_id != user.id:
            raise NotFoundException(ErrorCode.NOT_FOUND, "辅导会话不存在")
        if session.status != 0:
            raise ValidationException("辅导会话已结束")
        if session.total_rounds >= self.MAX_ROUNDS:
            raise ValidationException(f"已达最大对话轮次（{self.MAX_ROUNDS}）")

        ext = dict(session.ext_json or {})
        prev_exercise = bool(ext.get("is_exercise"))
        is_exercise = resolve_is_exercise(req.content, prev_exercise, req.request_full_answer)
        ext["is_exercise"] = is_exercise
        hint_level = self._compute_hint_level(session, req.content, req.request_full_answer, is_exercise)
        ext["hint_level"] = hint_level
        session.ext_json = ext

        round_no = session.total_rounds + 1
        if req.retry_assistant:
            history = self.tutor_repo.get_messages(session.id)
            last_user = next((m for m in reversed(history) if m.role == "user"), None)
            if not last_user or last_user.content != req.content:
                raise ValidationException("无法重试：找不到匹配的用户消息")
            round_no = last_user.round_no
        elif req.confirmed_outline:
            # 大纲确认阶段不重复插入用户消息
            round_no = session.total_rounds + 1
        else:
            self.tutor_repo.add_message(
                TutTutorMessage(session_id=session.id, round_no=round_no, role="user", content=req.content)
            )

        kps = self._detect_knowledge_points(req.content + " " + session.topic)
        related = self._find_related_resources(user.id, kps[0].point_name if kps else session.topic)
        kp_text = "\n".join(f"- {k.point_code} {k.point_name}" for k in kps) if kps else "未匹配到具体知识点"
        exercise_ctx = self._load_exercise_context(session.resource_id, ext.get("question_id"))

        use_profile = bool(ext.get("profile_adapt_enabled", True))
        profile_snap = session.profile_snapshot if use_profile else None
        deep_mode = (
            req.deep_mode
            if req.deep_mode is not None
            else bool(ext.get("deep_mode", False))
        )
        web_enabled = req.web_search_enabled if req.web_search_enabled is not None else bool(ext.get("web_search_enabled", False))

        if web_ctx_override is not None:
            web_ctx = web_ctx_override
            web_sources = web_sources_override or []
            web_timed_out = bool(web_timed_out_override)
            doc_ctx, raw_citations = self.doc_service.build_rag_context(
                user.id, session_no, list(ext.get("document_ids") or []), req.content
            )
            if self.vector_kb.enabled:
                kb_ctx, kb_citations = await self.vector_kb.search(req.content or session.topic)
                if kb_ctx:
                    doc_ctx = "\n\n---\n\n".join([p for p in (doc_ctx, kb_ctx) if p])
                raw_citations.extend(kb_citations)
            doc_ctx = trim_text(doc_ctx, 3500 if web_enabled else 6000)
            citations = [DocCitation(**c) for c in raw_citations]
        else:
            doc_ctx, web_ctx, web_sources, citations, web_timed_out = await self._build_contexts(
                user, session, session_no, req.content, web_enabled
            )

        system_prompt = build_tutor_system_prompt(
            mode=session.tutor_mode,
            profile_snapshot=profile_snap,
            hint_level=hint_level,
            is_exercise=is_exercise,
            exercise_context=exercise_ctx,
            knowledge_context=f"识别知识点:\n{kp_text}",
            profile_adapt_enabled=use_profile,
            answer_detail=str(ext.get("answer_detail", "normal")),
            show_steps=bool(ext.get("show_steps", True)),
            deep_mode=deep_mode,
            doc_context=doc_ctx or None,
            web_context=web_ctx or None,
            web_sources=[s.model_dump() for s in web_sources],
        )

        history = self.tutor_repo.get_messages(session.id)
        messages = [{"role": "system", "content": system_prompt}]
        for m in history[-16:]:
            if m.role in ("user", "assistant"):
                messages.append({"role": m.role, "content": m.content})

        meta = TutorMessageMeta(
            knowledge_points=kps,
            related_resources=related,
            hint_level=hint_level,
            is_exercise=is_exercise,
            web_sources=web_sources,
            doc_citations=citations,
            web_search_timeout=web_timed_out,
        )
        messages = trim_messages(messages)
        return session, round_no, messages, meta, doc_ctx, web_ctx, deep_mode

    async def send_message(
        self, user: SysUser, session_no: str, req: TutorMessageRequest
    ) -> TutorMessageResponse:
        session, round_no, messages, meta, *_ = await self._prepare_chat(user, session_no, req)
        ext = self._session_ext(session)
        web_enabled = req.web_search_enabled if req.web_search_enabled is not None else bool(
            ext.get("web_search_enabled", False)
        )
        from app.security.context import SecurityContext

        ctx = SecurityContext(
            target_type="tutor",
            target_id=session.id,
            topic=session.topic,
            source_module="tutor",
            allow_off_topic=True,
        )
        result = await self.llm.chat(
            messages,
            user_id=user.id,
            task_id=session.agent_task_id,
            temperature=0.6,
            max_tokens=_resolve_max_tokens(
                bool(ext.get("deep_mode", False)),
                str(ext.get("answer_detail", "normal")),
            ),
            context=ctx,
        )
        content = _student_visible_content(result.content)

        msg_type, strategy = detect_message_type(content, meta.is_exercise, meta.hint_level)
        meta.message_type = msg_type
        meta.strategy_used = strategy

        self.tutor_repo.add_message(
            TutTutorMessage(
                session_id=session.id,
                round_no=round_no,
                role="assistant",
                content=content,
                message_type=msg_type,
                strategy_used=strategy,
            )
        )
        self._store_message_meta(session, round_no, meta)
        session.total_rounds = round_no
        self.tutor_repo.save_session(session)

        return TutorMessageResponse(session_no=session_no, round_no=round_no, assistant_message=content, meta=meta)

    async def stream_message(self, user: SysUser, session_no: str, req: TutorMessageRequest):
        """Async generator yielding (event_type, payload) tuples."""
        session = self.tutor_repo.get_session(session_no)
        if not session or session.user_id != user.id:
            raise NotFoundException(ErrorCode.NOT_FOUND, "辅导会话不存在")
        if session.status != 0:
            raise ValidationException("辅导会话已结束")

        use_lecture = req.force_lecture or req.confirmed_outline is not None

        # ── 普通对话：先推送进度与联网检索，再 prepare（避免长时间无输出）──
        if not use_lecture and not req.confirmed_outline:
            yield ("progress", {"phase": "prepare", "message": "正在准备回答…"})
            web_enabled = req.web_search_enabled if req.web_search_enabled is not None else bool(
                (session.ext_json or {}).get("web_search_enabled")
            )
            web_ctx_pre, web_sources_pre, web_timed_out_pre = "", [], False
            if self.vector_kb.enabled:
                yield ("progress", {"phase": "vector_kb", "message": "正在检索本地向量知识库…"})
            if web_enabled:
                yield ("progress", {"phase": "web_search", "message": "正在检索相关资料…"})
                web_ctx_pre, web_sources_pre, web_timed_out_pre = await self._search_external_knowledge(
                    req.content or session.topic,
                    web_enabled=web_enabled,
                    user_id=user.id,
                    task_id=session.agent_task_id,
                )
                logger.info(
                    "tutor web_search session=%s timed_out=%s sources=%d",
                    session_no,
                    web_timed_out_pre,
                    len(web_sources_pre),
                )

            session, round_no, messages, meta, doc_ctx, web_ctx, deep_mode = await self._prepare_chat(
                user,
                session_no,
                req,
                web_ctx_override=web_ctx_pre if web_enabled else None,
                web_sources_override=web_sources_pre if web_enabled else None,
                web_timed_out_override=web_timed_out_pre if web_enabled else None,
            )

            yield ("meta", meta.model_dump())

            timeout_notice = ""
            if web_timed_out_pre and not meta.web_sources:
                timeout_notice = "\n\n> ⚠️ 未能获取网络资料，已为您生成通用解答\n\n"
            elif web_enabled and not meta.web_sources:
                timeout_notice = "\n\n> ℹ️ 本次未检索到相关资料，已为您生成通用解答\n\n"

            full_content = timeout_notice
            full_thinking = ""
            if timeout_notice:
                yield ("chunk", {"content": timeout_notice})

            from app.security.context import SecurityContext

            ctx = SecurityContext(
                target_type="tutor",
                target_id=session.id,
                topic=session.topic,
                source_module="tutor",
                allow_off_topic=True,
            )
            chat_temp = 0.55 if deep_mode else 0.5
            ext = self._session_ext(session)
            answer_detail = str(ext.get("answer_detail", "normal"))
            cap = 4096
            if self.db:
                from app.services.config_service import ConfigService, TUTOR_MAX_TOKENS

                cap = ConfigService(self.db).get_int(TUTOR_MAX_TOKENS, 4096)
            max_tokens = _resolve_max_tokens(deep_mode, answer_detail, cap)
            stream_timeout = _resolve_stream_timeout(deep_mode, answer_detail, web_enabled)
            got_chunk = False
            _THINK_MARK = "\x01T\x01"
            _CONTENT_MARK = "\x01C\x01"

            try:
                async with async_timeout(stream_timeout):
                    async for chunk in self.llm.stream_chat(
                        messages,
                        temperature=chat_temp,
                        max_tokens=max_tokens,
                        user_id=user.id,
                        task_id=session.agent_task_id,
                        context=ctx,
                    ):
                        got_chunk = True
                        from app.llm.stream_markers import peel_stream_chunk

                        kind, text = peel_stream_chunk(chunk or "")
                        if kind == "think":
                            full_thinking += text
                            if text:
                                yield ("think_chunk", {"content": text})
                        else:
                            full_content += text
                            if text:
                                yield ("chunk", {"content": text})
            except TimeoutError:
                logger.warning(
                    "tutor stream timeout session=%s deep=%s detail=%s max_tokens=%s",
                    session_no,
                    deep_mode,
                    answer_detail,
                    max_tokens,
                )
                if not got_chunk:
                    err = "响应超时，请重试。"
                    full_content += err
                    yield ("chunk", {"content": err})
                elif full_content.strip() and not full_content.rstrip().endswith(("。", "！", "？", ".", "!", "?", "」", "）", "`")):
                    notice = "\n\n> ⚠️ 回答因超时未完整生成，可点击「继续讲解」或重新提问。"
                    full_content += notice
                    yield ("chunk", {"content": notice})
            except AppException as exc:
                logger.warning("tutor stream blocked session=%s: %s", session_no, exc.message)
                if not got_chunk:
                    err = exc.message
                    full_content += err
                    yield ("chunk", {"content": err})
            except Exception as exc:
                logger.exception("tutor stream error session=%s: %s", session_no, exc)
                if not got_chunk:
                    err = _friendly_llm_error(exc)
                    full_content += err
                    yield ("chunk", {"content": err})

            stored_content = _student_visible_content(full_content)
            msg_type, strategy = detect_message_type(stored_content, meta.is_exercise, meta.hint_level)
            meta.message_type = msg_type
            meta.strategy_used = strategy

            self.tutor_repo.add_message(
                TutTutorMessage(
                    session_id=session.id,
                    round_no=round_no,
                    role="assistant",
                    content=stored_content,
                    message_type=msg_type,
                    strategy_used=strategy,
                )
            )
            self._store_message_meta(session, round_no, meta)
            session.total_rounds = round_no
            self.tutor_repo.save_session(session)
            yield ("done", {"round_no": round_no, "meta": meta.model_dump(), "content": stored_content})
            return

        session, round_no, messages, meta, doc_ctx, web_ctx, deep_mode = await self._prepare_chat(
            user, session_no, req
        )

        use_lecture = req.force_lecture or req.confirmed_outline is not None

        # ── 讲解流程：大纲 → 确认 → 分模块生成 ──
        if use_lecture and not req.confirmed_outline:
            yield ("progress", {"phase": "outline", "message": "正在生成课程大纲…"})
            profile_text = profile_summary_text(session.profile_snapshot)
            outline = await self.lecture_service.generate_outline(
                req.content,
                profile_text,
                doc_ctx,
                web_ctx,
                user.id,
                session.agent_task_id,
            )
            ext = self._session_ext(session)
            ext["pending_outline"] = outline
            session.ext_json = ext
            self.tutor_repo.save_session(session)
            yield ("outline", {"outline": outline, "topic": req.content})
            outline_meta = TutorMessageMeta(
                **{**meta.model_dump(), "message_type": "outline", "strategy_used": "lecture_outline"}
            )
            self._store_message_meta(session, round_no, outline_meta)
            yield ("done", {
                "round_no": round_no,
                "meta": outline_meta.model_dump(),
            })
            return

        if req.confirmed_outline:
            outline = req.confirmed_outline
            profile_text = profile_summary_text(session.profile_snapshot)
            full_parts: list[str] = []
            all_slides: list[dict] = []

            async for event_type, payload in self.lecture_service.stream_modules(
                outline,
                session.topic,
                profile_text,
                doc_ctx,
                deep_mode,
                user.id,
                session.agent_task_id,
            ):
                yield (event_type, payload)
                if event_type == "slides":
                    all_slides.extend(payload.get("slides") or [])
                if event_type == "module_chunk":
                    full_parts.append(payload.get("content") or "")

            full_content = f"## 📚 结构化讲解：{session.topic}\n\n" + "\n\n".join(full_parts)
            meta.slides = all_slides
            meta.message_type = "lecture"
            meta.strategy_used = "lecture_slides"

            self.tutor_repo.add_message(
                TutTutorMessage(
                    session_id=session.id,
                    round_no=round_no,
                    role="assistant",
                    content=full_content,
                    message_type="lecture",
                    strategy_used="lecture_slides",
                )
            )
            self._store_message_meta(session, round_no, meta)
            session.total_rounds = round_no
            ext = self._session_ext(session)
            ext.pop("pending_outline", None)
            session.ext_json = ext
            self.tutor_repo.save_session(session)
            yield ("done", {"round_no": round_no, "meta": meta.model_dump()})
            return

    async def generate_multimodal(
        self, user: SysUser, session_no: str, action: str, prompt: str, source_text: str | None
    ) -> dict:
        session = self.tutor_repo.get_session(session_no)
        if not session or session.user_id != user.id:
            raise NotFoundException(ErrorCode.NOT_FOUND, "辅导会话不存在")

        if action == "image":
            payload = await self.multimodal_service.generate_image(prompt, user.id, session.agent_task_id)
        elif action == "video":
            payload = await self.multimodal_service.generate_video_script(prompt, user.id, session.agent_task_id)
        elif action == "tts":
            payload = await self.multimodal_service.prepare_tts(source_text or prompt)
        else:
            raise ValidationException(f"不支持的多模态操作: {action}")
        return payload

    def list_session_documents(self, user: SysUser, session_no: str) -> list[dict]:
        session = self.tutor_repo.get_session(session_no)
        if not session or session.user_id != user.id:
            raise NotFoundException(ErrorCode.NOT_FOUND, "辅导会话不存在")
        ext = self._session_ext(session)
        return self.doc_service.list_session_docs(user.id, session_no, list(ext.get("document_ids") or []))

    def upload_session_document(
        self, user: SysUser, session_no: str, filename: str, data: bytes
    ) -> dict:
        session = self.tutor_repo.get_session(session_no)
        if not session or session.user_id != user.id:
            raise NotFoundException(ErrorCode.NOT_FOUND, "辅导会话不存在")
        result = self.doc_service.upload(user.id, session_no, filename, data)
        ext = self._session_ext(session)
        ids = list(ext.get("document_ids") or [])
        if result["doc_id"] not in ids:
            ids.append(result["doc_id"])
        ext["document_ids"] = ids
        session.ext_json = ext
        self.tutor_repo.save_session(session)
        return result

    def delete_session_document(self, user: SysUser, session_no: str, doc_id: str) -> TutorSessionResponse:
        session = self.tutor_repo.get_session(session_no)
        if not session or session.user_id != user.id:
            raise NotFoundException(ErrorCode.NOT_FOUND, "辅导会话不存在")
        self.doc_service.delete(user.id, session_no, doc_id)
        ext = self._session_ext(session)
        ext["document_ids"] = [d for d in (ext.get("document_ids") or []) if d != doc_id]
        session.ext_json = ext
        self.tutor_repo.save_session(session)
        return self._session_to_response(session, user)

    def _persist_lecture_resource(
        self, user: SysUser, session_no: str, lecture: dict, ext: dict
    ) -> int | None:
        try:
            return self.lecture_resource_service.save_lecture_as_resource(
                user, session_no, lecture, ext
            )
        except Exception as exc:
            logger.exception("Failed to sync lecture to resource center: %s", exc)
            self.db.rollback()
            return None

    async def generate_immersive_lecture(
        self, user: SysUser, session_no: str, topic: str, source_text: str | None = None
    ) -> dict:
        session = self.tutor_repo.get_session(session_no)
        if not session or session.user_id != user.id:
            raise NotFoundException(ErrorCode.NOT_FOUND, "辅导会话不存在")
        ext = self._session_ext(session)
        deep_mode = bool(ext.get("deep_mode", False))
        profile_text = profile_summary_text(session.profile_snapshot)
        doc_ids = list(ext.get("document_ids") or [])
        doc_ctx, _ = self.doc_service.build_rag_context(user.id, session_no, doc_ids, topic)
        lecture_topic = topic
        if source_text:
            lecture_topic = f"{topic}\n\n参考内容：\n{source_text[:2000]}"
        lecture = await self.immersive_service.generate(
            lecture_topic, profile_text, doc_ctx, deep_mode, user.id, session.agent_task_id
        )
        ext = self.immersive_service.store_in_session(ext, lecture)
        resource_id = self._persist_lecture_resource(user, session_no, lecture, ext)
        session.ext_json = ext
        self.tutor_repo.save_session(session)
        if resource_id:
            lecture["resource_id"] = resource_id
        return lecture

    async def stream_generate_immersive_lecture(
        self, user: SysUser, session_no: str, topic: str, source_text: str | None = None
    ):
        """SSE 分步生成沉浸式讲解。"""
        session = self.tutor_repo.get_session(session_no)
        if not session or session.user_id != user.id:
            raise NotFoundException(ErrorCode.NOT_FOUND, "辅导会话不存在")

        steps = [
            ("parse", "解析知识点…"),
            ("outline", "生成 PPT 大纲…"),
            ("slides", "生成逐页内容…"),
            ("narration", "合成讲解语音脚本…"),
        ]
        for phase, msg in steps:
            yield ("progress", {"phase": phase, "message": msg})
            await asyncio.sleep(0.05)

        ext = self._session_ext(session)
        deep_mode = bool(ext.get("deep_mode", False))
        profile_text = profile_summary_text(session.profile_snapshot)
        doc_ids = list(ext.get("document_ids") or [])
        doc_ctx, _ = self.doc_service.build_rag_context(user.id, session_no, doc_ids, topic)
        doc_ctx = trim_text(doc_ctx, 3000)
        lecture_topic = topic
        if source_text:
            lecture_topic = f"{topic}\n\n参考内容：\n{source_text[:2000]}"

        try:
            async with async_timeout(120):
                lecture = await self.immersive_service.generate(
                    lecture_topic, profile_text, doc_ctx, deep_mode, user.id, session.agent_task_id
                )
        except TimeoutError as exc:
            yield ("error", {"message": "讲解生成超时，请重试"})
            return
        except Exception as exc:
            logger.exception("immersive lecture generate failed session=%s: %s", session_no, exc)
            yield ("error", {"message": str(exc) or "讲解生成失败，请重试"})
            return

        yield ("progress", {"phase": "done", "message": "生成完成"})

        ext = self.immersive_service.store_in_session(ext, lecture)
        ext["lecture_jobs"] = ext.get("lecture_jobs") or {}
        ext["lecture_jobs"][lecture["lecture_id"]] = {
            "status": "done",
            "topic": topic,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        resource_id = self._persist_lecture_resource(user, session_no, lecture, ext)
        session.ext_json = ext
        self.tutor_repo.save_session(session)
        done_payload: dict = {"lecture": lecture}
        if resource_id:
            done_payload["resource_id"] = resource_id
            lecture["resource_id"] = resource_id
        yield ("done", done_payload)

    def get_immersive_lecture(self, user: SysUser, session_no: str, lecture_id: str) -> dict:
        session = self.tutor_repo.get_session(session_no)
        if not session or session.user_id != user.id:
            raise NotFoundException(ErrorCode.NOT_FOUND, "辅导会话不存在")
        ext = self._session_ext(session)
        lecture = self.immersive_service.get_from_session(ext, lecture_id)
        if not lecture:
            raise NotFoundException(message="讲解不存在或已过期")
        return lecture

    def export_lecture_pptx(self, user: SysUser, session_no: str, lecture_id: str) -> tuple[bytes, str]:
        lecture = self.get_immersive_lecture(user, session_no, lecture_id)
        data = self.immersive_service.export_pptx(lecture)
        safe_name = re.sub(r'[\\/*?:"<>|]', "_", lecture.get("topic") or "lecture")[:40]
        return data, f"{safe_name}.pptx"

    async def lecture_side_ask(
        self, user: SysUser, session_no: str, lecture_id: str, question: str, slide_index: int, history: list
    ) -> str:
        session = self.tutor_repo.get_session(session_no)
        if not session or session.user_id != user.id:
            raise NotFoundException(ErrorCode.NOT_FOUND, "辅导会话不存在")
        lecture = self.get_immersive_lecture(user, session_no, lecture_id)
        slides = lecture.get("slides") or []
        current = slides[slide_index] if 0 <= slide_index < len(slides) else None
        return await self.immersive_service.side_qa(
            lecture.get("topic") or session.topic,
            current,
            question,
            history,
            user.id,
            session.agent_task_id,
        )

    def submit_lecture_quiz(
        self, user: SysUser, session_no: str, lecture_id: str, slide_index: int, answers: list[str]
    ) -> dict:
        lecture = self.get_immersive_lecture(user, session_no, lecture_id)
        slides = lecture.get("slides") or []
        if slide_index < 0 or slide_index >= len(slides):
            raise ValidationException("无效的题目索引")
        slide = slides[slide_index]
        if slide.get("type") != "quiz":
            raise ValidationException("该页不是测验题")
        correct_ans = str(slide.get("answer") or "").upper()
        user_ans = ",".join(sorted(a.upper() for a in answers))
        if slide.get("multi"):
            correct_set = set(x.strip().upper() for x in correct_ans.replace(",", " ").split())
            user_set = set(a.upper() for a in answers)
            is_correct = correct_set == user_set
        else:
            is_correct = answers[0].upper().startswith(correct_ans[:1]) if answers else False
        ext = self._session_ext(self.tutor_repo.get_session(session_no))
        quiz_results = dict(ext.get("lecture_quiz_results") or {})
        key = f"{lecture_id}:{slide_index}"
        quiz_results[key] = {"correct": is_correct, "answers": answers}
        ext["lecture_quiz_results"] = quiz_results
        session = self.tutor_repo.get_session(session_no)
        session.ext_json = ext
        self.tutor_repo.save_session(session)
        return {
            "correct": is_correct,
            "analysis": slide.get("analysis") or "",
            "answer": correct_ans,
        }

    def get_lecture_summary(self, user: SysUser, session_no: str, lecture_id: str) -> dict:
        lecture = self.get_immersive_lecture(user, session_no, lecture_id)
        session = self.tutor_repo.get_session(session_no)
        ext = self._session_ext(session)
        quiz_results = ext.get("lecture_quiz_results") or {}
        slides = lecture.get("slides") or []
        quiz_indices = [i for i, s in enumerate(slides) if s.get("type") == "quiz"]
        correct = sum(
            1 for i in quiz_indices if quiz_results.get(f"{lecture_id}:{i}", {}).get("correct")
        )
        total = len(quiz_indices)
        accuracy = round(correct / total * 100, 1) if total else 100.0
        if accuracy >= 80:
            mastery = "掌握良好"
        elif accuracy >= 50:
            mastery = "基本掌握"
        else:
            mastery = "需加强复习"
        return {
            "topic": lecture.get("topic") or "",
            "knowledge_point_count": lecture.get("content_slide_count") or sum(
                1 for s in slides if s.get("type") == "content"
            ),
            "quiz_count": total,
            "correct_count": correct,
            "total_quizzes": total,
            "accuracy": accuracy,
            "mastery": mastery,
            "recommendations": lecture.get("recommendations") or [],
        }
