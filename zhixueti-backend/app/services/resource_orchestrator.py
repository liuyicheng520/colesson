"""Multi-agent resource generation orchestrator."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.agents.context import OrchestrationContext
from app.agents.specialists import (
    AnimationAgent,
    CoordinatorAgent,
    DocumentAgent,
    ExtensionAgent,
    LearningAnalysisAgent,
    MindmapAgent,
    QuestionAgent,
    ValidatorAgent,
)
from app.db.session import SessionLocal
from app.core.exceptions import AppException
from app.llm.safety import ContentSafetyService
from app.models.agent import AgtAgentDefinition
from app.models.resource import (
    ResCodeCase,
    ResDocument,
    ResMindmap,
    ResQuestion,
    ResReading,
    ResResource,
    ResResourceCitation,
    ResVideo,
)
from app.models.sys import SysUser
from app.repositories.agent_repository import AgentRepository
from app.repositories.path_repository import PathRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.resource_repository import ResourceRepository
from app.schemas.resource import ResourceGenerateRequest
from app.utils.subject_utils import code_module_label, detect_subject_category, is_programming_subject

logger = logging.getLogger(__name__)

# In-memory task registry for cancellation (dev); production use Redis
_running_tasks: dict[str, asyncio.Task] = {}


class ResourceOrchestrator:
    """Coordinates 1 orchestrator + 5 specialist agents + validators."""

    AGENT_TYPE_MAP = {
        "document": "document",
        "question": "question",
        "mindmap": "mindmap",
        "reading": "extension",
        "code": "extension",
        "video": "animation",
    }

    def __init__(self, db: Session) -> None:
        self.db = db
        self.agent_repo = AgentRepository(db)
        self.resource_repo = ResourceRepository(db)
        self.profile_repo = ProfileRepository(db)
        self.path_repo = PathRepository(db)
        self.safety = ContentSafetyService(db)
        self.coordinator = CoordinatorAgent(db)
        self.learning_analysis = LearningAnalysisAgent(db)
        self.document_agent = DocumentAgent(db)
        self.question_agent = QuestionAgent(db)
        self.mindmap_agent = MindmapAgent(db)
        self.extension_agent = ExtensionAgent(db)
        self.animation_agent = AnimationAgent(db)
        self.validator = ValidatorAgent(db)

    AGENT_DEFINITIONS = [
        ("orchestrator", "总协调智能体", "orchestrator", "spark-pro"),
        ("learning_analysis", "学情分析智能体", "assessor", "spark-pro"),
        ("document", "课程讲义智能体", "generator", "spark-ultra"),
        ("question", "习题命题智能体", "generator", "spark-pro"),
        ("mindmap", "知识图谱智能体", "generator", "spark-pro"),
        ("extension", "拓展资源智能体", "generator", "spark-pro"),
        ("animation", "AI视频讲解智能体", "generator", "spark-pro"),
        ("consistency", "一致性校验智能体", "validator", "spark-pro"),
        ("fact_check", "事实核查智能体", "validator", "spark-pro"),
        ("safety", "安全审核智能体", "validator", "spark-pro"),
    ]

    def _ensure_agent_definitions(self) -> None:
        for code, name, atype, model in self.AGENT_DEFINITIONS:
            if not self.agent_repo.get_agent_by_code(code):
                self.db.add(
                    AgtAgentDefinition(
                        agent_code=code,
                        agent_name=name,
                        agent_type=atype,
                        default_model=model,
                        description=f"智学体 {name}",
                    )
                )
        self.db.commit()

    def create_task(self, user: SysUser, req: ResourceGenerateRequest):
        self._ensure_agent_definitions()
        return self.agent_repo.create_task(
            user.id,
            "resource_gen",
            f"多智能体生成: {req.topic}",
            req.model_dump(),
        )

    def _build_context(self, user: SysUser, req: ResourceGenerateRequest, task) -> OrchestrationContext:
        snapshot = None
        dimensions: list[dict] = []
        ignore_profile = bool(req.ignore_profile)
        if not ignore_profile:
            profile = self.profile_repo.get_by_user_id(user.id)
            if profile:
                defs = {d.id: d for d in self.profile_repo.get_dimension_defs()}
                values = self.profile_repo.get_dimension_values(profile.id)
                snapshot = {str(v.dimension_id): v.dimension_value for v in values}
                for v in values:
                    d = defs.get(v.dimension_id)
                    if d:
                        dimensions.append(
                            {
                                "dimension_code": d.dimension_code,
                                "dimension_name": d.dimension_name,
                                "dimension_value": v.dimension_value,
                                "confidence": float(v.confidence or 0),
                            }
                        )
        return OrchestrationContext(
            task_id=task.id,
            task_no=task.task_no,
            user_id=user.id,
            topic=req.topic,
            goal=req.goal,
            difficulty=req.difficulty,
            node_id=req.node_id,
            resource_types=req.resource_types,
            profile_snapshot=snapshot,
            profile_dimensions=dimensions,
            ignore_profile=ignore_profile,
            supplement=(req.supplement or "").strip() or None,
            use_scene=(req.use_scene or "").strip() or None,
            content_focus=[x for x in (req.content_focus or []) if x],
            content_length=(req.content_length or "").strip() or None,
            special_requirements=(req.special_requirements or "").strip() or None,
        )

    def _update_partial(self, ctx: OrchestrationContext) -> None:
        self.agent_repo.update_task(
            ctx.task_id,
            output_result={
                "resource_ids": ctx.resource_ids,
                "partial_previews": ctx.partial_previews,
                "learning_diagnosis": ctx.learning_diagnosis,
            },
        )

    async def execute(self, user_id: int, task_no: str, req: ResourceGenerateRequest) -> None:
        task = self.agent_repo.get_task_by_no(task_no)
        if not task:
            return
        user = self.db.query(SysUser).filter(SysUser.id == user_id).first()
        if not user:
            return

        ctx = self._build_context(user, req, task)
        self._ensure_agent_definitions()

        from app.services.vector_kb_service import get_vector_kb_service

        kb = get_vector_kb_service()
        if kb.enabled:
            kb_ctx, kb_cites = await kb.search(req.topic)
            ctx.kb_context = kb_ctx
            ctx.kb_citations = kb_cites

        coord_def = self.coordinator.get_definition()
        coordinator_run = self.agent_repo.create_agent_run(
            task.id,
            coord_def.id if coord_def else 1,
            {"phase": "orchestration"},
        )

        try:
            self.agent_repo.update_task(task.id, status=1)
            # Stage 1: parse
            self.agent_repo.update_task_stage(task.id, "parse", 1, 10, "总协调智能体解析参数...")
            await asyncio.sleep(0.1)
            self.agent_repo.update_task_stage(task.id, "parse", 2, 100, "参数解析完成")

            # Stage 2: plan
            self.agent_repo.update_task_stage(task.id, "plan", 1, 20, "总协调智能体规划子任务...")
            plan = await self.coordinator.execute(ctx, coordinator_run.id)
            agents_to_run = self._resolve_agents(req.resource_types, plan)
            self.agent_repo.update_task_stage(
                task.id, "plan", 2, 100, f"已规划 {len(agents_to_run)} 个子任务"
            )
            self._update_partial(ctx)

            # Stage 3: generate — learning analysis first, then parallel specialists
            self.agent_repo.update_task_stage(task.id, "generate", 1, 5, "学情分析智能体工作中...")
            await self.learning_analysis.execute(ctx, coordinator_run.id)
            self._update_partial(ctx)
            self.agent_repo.update_task_stage(task.id, "generate", 1, 25, "学情分析完成，并行生成资源...")

            agent_outputs = await self._run_specialists_parallel(ctx, agents_to_run, coordinator_run.id)
            self.agent_repo.update_task_stage(task.id, "generate", 2, 100, "内容生成完成")

            # Stage 4: validate
            self.agent_repo.update_task_stage(task.id, "validate", 1, 50, "一致性校验中...")
            contents = [str(v) for v in agent_outputs.values() if v]
            await self.validator.validate_all(ctx, contents, coordinator_run.id)
            self.agent_repo.update_task_stage(task.id, "validate", 2, 100, "校验通过")

            # Stage 5: audit + store
            self.agent_repo.update_task_stage(task.id, "audit", 1, 70, "安全审核与入库...")
            await self._persist_resources(ctx, user, req, agent_outputs)
            self.agent_repo.update_task_stage(task.id, "audit", 2, 100, "审核入库完成")
            self.agent_repo.update_task_stage(task.id, "store", 2, 100, "结构化存储完成")

            # Stage 6: push — 绑定到路径节点（显式 node_id，或按主题回填空节点）
            self.agent_repo.update_task_stage(task.id, "push", 1, 90, "推送结果...")
            bind_node_id = req.node_id
            if not bind_node_id and ctx.resource_ids and req.topic:
                topic = (req.topic or "").strip()
                for path in self.path_repo.list_user_paths(user.id):
                    for node in self.path_repo.get_nodes(path.id):
                        name = (node.node_name or "").strip()
                        if not name:
                            continue
                        if name != topic and topic not in name and name not in topic:
                            continue
                        if self.path_repo.get_node_resources(node.id):
                            continue
                        bind_node_id = node.id
                        break
                    if bind_node_id:
                        break
            if bind_node_id and ctx.resource_ids:
                self.path_repo.bind_node_resources(bind_node_id, ctx.resource_ids, "primary")
            self.agent_repo.update_task_stage(task.id, "push", 2, 100, "推送完成")

            status = 2 if not ctx.errors else (4 if ctx.resource_ids else 3)
            err_msg = "; ".join(ctx.errors) if ctx.errors else None
            self.agent_repo.update_task(
                task.id,
                status=status,
                error_message=err_msg,
                output_result={
                    "resource_ids": ctx.resource_ids,
                    "partial_previews": ctx.partial_previews,
                    "learning_diagnosis": ctx.learning_diagnosis,
                    "plan": plan,
                    "errors": ctx.errors,
                },
            )
            self.agent_repo.finish_agent_run(coordinator_run.id, {"resource_ids": ctx.resource_ids})

        except Exception as exc:
            logger.exception("Orchestration failed task=%s: %s", task_no, exc)
            self.agent_repo.update_task(task.id, status=3, error_message=str(exc))
            self.agent_repo.update_task_stage(task.id, "generate", 3, 0, str(exc))
            self.agent_repo.finish_agent_run(coordinator_run.id, {"error": str(exc)}, status=3)

    def _resolve_agents(self, resource_types: list[str], plan: dict) -> set[str]:
        agents = set()
        for t in resource_types:
            if t in self.AGENT_TYPE_MAP:
                agents.add(self.AGENT_TYPE_MAP[t])
        if plan.get("subtasks"):
            for st in plan["subtasks"]:
                if st.get("agent") and st["agent"] != "learning_analysis":
                    agents.add(st["agent"])
        return agents

    async def _run_specialists_parallel(
        self, ctx: OrchestrationContext, agents: set[str], parent_run_id: int
    ) -> dict[str, Any]:
        async def run_one(code: str):
            try:
                if code == "document" and "document" in ctx.resource_types:
                    return "document", await self.document_agent.execute(ctx, parent_run_id)
                if code == "question" and "question" in ctx.resource_types:
                    return "question", await self.question_agent.execute(ctx, parent_run_id)
                if code == "mindmap" and "mindmap" in ctx.resource_types:
                    return "mindmap", await self.mindmap_agent.execute(ctx, parent_run_id)
                if code == "extension" and any(t in ctx.resource_types for t in ("reading", "code")):
                    return "extension", await self.extension_agent.execute(ctx, parent_run_id)
                if code == "animation" and "video" in ctx.resource_types:
                    return "animation", await self.animation_agent.execute(ctx, parent_run_id)
                return code, None
            except Exception as e:
                ctx.errors.append(f"{code}: {e}")
                return code, None

        total = len(agents)
        results: dict[str, Any] = {}
        done = 0
        for coro in asyncio.as_completed([run_one(a) for a in agents]):
            code, output = await coro
            if output:
                results[code] = output
            done += 1
            pct = 25 + int(done / max(total, 1) * 55)
            self.agent_repo.update_task_stage(
                ctx.task_id, "generate", 1, pct, f"已完成 {done}/{total} 个智能体（讲义生成较慢，请稍候）"
            )
            self._update_partial(ctx)
        return results

    async def _persist_resources(
        self, ctx: OrchestrationContext, user: SysUser, req: ResourceGenerateRequest, outputs: dict
    ) -> None:
        """逐类入库，单类失败不阻断其他资源。"""
        savers = []
        if "document" in outputs and outputs["document"]:
            savers.append(("document", self._save_document(ctx, user, req, outputs["document"])))
        if "question" in outputs and outputs["question"]:
            savers.append(("question", self._save_questions(ctx, user, req, outputs["question"])))
        if "mindmap" in outputs and outputs["mindmap"]:
            savers.append(("mindmap", self._save_mindmap(ctx, user, req, outputs["mindmap"])))
        if "extension" in outputs and outputs["extension"]:
            ext = outputs["extension"]
            if ext.get("reading") and "reading" in req.resource_types:
                savers.append(("reading", self._save_reading(ctx, user, req, ext["reading"])))
            if ext.get("code") and "code" in req.resource_types:
                savers.append(("code", self._save_code(ctx, user, req, ext["code"])))
        if "animation" in outputs and outputs["animation"]:
            savers.append(("video", self._save_animation(ctx, user, req, outputs["animation"])))

        for name, coro in savers:
            try:
                await coro
            except Exception as exc:
                from app.core.exceptions import AppException
                msg = exc.message if isinstance(exc, AppException) else str(exc)
                ctx.errors.append(f"{name}: {msg}")
                logger.exception("Failed to persist %s: %s", name, exc)

    async def _save_resource_base(
        self,
        ctx: OrchestrationContext,
        user: SysUser,
        req: ResourceGenerateRequest,
        type_code: str,
        title: str,
        summary: str,
        content: str,
        *,
        retry_on_audit: bool = True,
        on_flushed=None,
    ) -> ResResource:
        """入库前两级安全审核；审核失败时自动重试一次（教育模式）。

        on_flushed: 在拿到 resource.id 后、最终 commit 前挂接扩展表（讲义正文等），
        保证主表与扩展表同事务落库，避免孤儿资源。
        """
        last_error: Exception | None = None
        for attempt in range(2 if retry_on_audit else 1):
            try:
                edu_retry = attempt > 0
                # 资源生成本身即教学材料：固定 educational_mode=True。
                # 敏感词/语义违规（tier=semantic）仍硬拦截；事实与完整性校验不通过时
                # 降级为「待人工复核」标记，不阻断入库——否则长讲义会因"表述不够严谨"永久无法生成。
                review_flag = False
                try:
                    await self.safety.validate_content(
                        content, topic=req.topic, content_type=type_code, educational_mode=True
                    )
                except AppException as audit_exc:
                    detail = audit_exc.detail if isinstance(audit_exc.detail, dict) else {}
                    if detail.get("tier") == "semantic" or detail.get("reasons"):
                        raise
                    review_flag = True
                    logger.warning("content fact-check flagged, keep with review mark: %s", str(audit_exc.message)[:160])
                type_def = self.resource_repo.get_type_by_code(type_code)
                if not type_def:
                    raise ValueError(f"Unknown type: {type_code}")
                # 纯文本摘要，避免 Markdown 原文塞进列表卡片
                clean_summary = summary.replace("#", "").replace("*", "").replace("---", " ").strip()
                clean_summary = " ".join(clean_summary.split())[:200]
                resource = ResResource(
                    resource_no=str(uuid.uuid4()),
                    user_id=user.id,
                    type_id=type_def.id,
                    title=title,
                    summary=clean_summary or f"{req.topic} 学习资源",
                    topic=req.topic,
                    difficulty=req.difficulty,
                    status=1,
                    audit_status=1,
                    fact_check_status=1,
                    agent_task_id=ctx.task_id,
                    content_hash=hashlib.sha256(content.encode()).hexdigest(),
                    profile_snapshot=ctx.profile_snapshot,
                    ext_json={"learning_diagnosis": ctx.learning_diagnosis},
                )
                self.db.add(resource)
                self.db.flush()
                if on_flushed is not None:
                    on_flushed(resource)
                try:
                    await self.safety.audit_and_persist(content, "resource", resource.id, topic=req.topic)
                except AppException as audit_exc:
                    detail = audit_exc.detail if isinstance(audit_exc.detail, dict) else {}
                    if detail.get("tier") == "semantic" or detail.get("reasons"):
                        raise
                    review_flag = True
                    logger.warning("persist audit flagged, keep with review mark: %s", str(audit_exc.message)[:160])
                citations = ContentSafetyService.extract_citations(content)
                for c in citations:
                    self.db.add(
                        ResResourceCitation(
                            resource_id=resource.id,
                            claim_text=c["claim_text"],
                            verify_status=c["verify_status"],
                            source_type="rag",
                        )
                    )
                # 知识库检索命中同样记为引用，保证「知识库依据」可追溯（此前只统计正文里的行内引用）
                kb_cites = getattr(ctx, "kb_citations", None) or []
                seen = {c.get("claim_text") for c in citations}
                kb_added = 0
                for kc in kb_cites[:6]:
                    snippet = (kc.get("snippet") or "").strip()
                    doc_id = kc.get("doc_id") or "知识库"
                    if not snippet or snippet in seen:
                        continue
                    seen.add(snippet)
                    self.db.add(
                        ResResourceCitation(
                            resource_id=resource.id,
                            claim_text=f"[{doc_id}] {snippet[:200]}",
                            verify_status=1,
                            source_type="vector_kb",
                        )
                    )
                    kb_added += 1
                resource.citation_count = len(citations) + kb_added
                if review_flag:
                    # 事实/完整性待人工复核（不影响学生可见与演示）
                    resource.fact_check_status = 2
                resource.status = 2
                resource.published_at = datetime.now(timezone.utc).replace(tzinfo=None)
                self.db.commit()
                ctx.resource_ids.append(resource.id)
                self._update_partial(ctx)
                return resource
            except Exception as exc:
                last_error = exc
                self.db.rollback()
                if attempt == 0 and retry_on_audit:
                    logger.warning("Audit failed for %s, retrying with educational mode: %s", type_code, exc)
                    continue
                raise last_error
        raise last_error  # type: ignore[misc]

    async def _save_document(self, ctx, user, req, data):
        content = data.get("content_md", "") or ""
        if not isinstance(content, str):
            content = str(content)

        def attach_document(resource: ResResource) -> None:
            chapters = content.count("\n## ")
            self.db.add(
                ResDocument(
                    resource_id=resource.id,
                    content_md=content,
                    word_count=len(content),
                    chapter_count=chapters,
                )
            )

        r = await self._save_resource_base(
            ctx,
            user,
            req,
            "document",
            f"{req.topic} - 课程讲义",
            content[:200],
            content,
            on_flushed=attach_document,
        )
        ctx.partial_previews.append({"agent_code": "document", "resource_id": r.id, "title": r.title})

    async def _save_questions(self, ctx, user, req, data):
        questions = data.get("questions", [])
        content = str(questions)

        def attach_questions(resource: ResResource) -> None:
            for i, q in enumerate(questions):
                self.db.add(
                    ResQuestion(
                        resource_id=resource.id,
                        question_no=f"{resource.resource_no}-{i+1}",
                        question_type=q.get("question_type", "single_choice"),
                        stem=q.get("stem", ""),
                        options=q.get("options"),
                        answer=q.get("answer", {}),
                        analysis=q.get("analysis"),
                        knowledge_point=req.topic,
                        difficulty=q.get("difficulty", req.difficulty),
                        error_type=q.get("error_type"),
                    )
                )

        r = await self._save_resource_base(
            ctx,
            user,
            req,
            "question",
            f"{req.topic} - 分层习题",
            f"共{len(questions)}道题",
            content,
            on_flushed=attach_questions,
        )
        ctx.partial_previews.append({"agent_code": "question", "resource_id": r.id, "title": r.title})

    async def _save_mindmap(self, ctx, user, req, data):
        mermaid = data.get("mermaid", "")
        map_data = {"mermaid": mermaid, "nodes": data.get("nodes", []), "edges": data.get("edges", [])}
        content = mermaid

        def attach_mindmap(resource: ResResource) -> None:
            self.db.add(
                ResMindmap(
                    resource_id=resource.id,
                    map_data=map_data,
                    node_count=len(map_data.get("nodes", [])),
                    render_config={"engine": "mermaid", "theme": "default"},
                )
            )

        r = await self._save_resource_base(
            ctx,
            user,
            req,
            "mindmap",
            f"{req.topic} - 知识图谱",
            "Mermaid思维导图",
            content,
            on_flushed=attach_mindmap,
        )
        ctx.partial_previews.append({"agent_code": "mindmap", "resource_id": r.id, "title": r.title})

    async def _save_reading(self, ctx, user, req, reading_list):
        content = str(reading_list)

        def attach_reading(resource: ResResource) -> None:
            self.db.add(ResReading(resource_id=resource.id, reading_list=reading_list, item_count=len(reading_list)))

        r = await self._save_resource_base(
            ctx,
            user,
            req,
            "reading",
            f"{req.topic} - 拓展阅读",
            f"{len(reading_list)} 篇结构化学习单元，覆盖概念、方法、应用与进阶思考",
            content,
            on_flushed=attach_reading,
        )
        ctx.partial_previews.append({"agent_code": "extension", "resource_id": r.id, "title": r.title, "subtype": "reading"})

    async def _save_code(self, ctx, user, req, code_data):
        label = code_module_label(req.topic, req.goal)
        is_prog = is_programming_subject(req.topic, req.goal)
        if is_prog:
            code = code_data.get("code_content", "")
            content = code if isinstance(code, str) else str(code or "")
        else:
            # 非编程类：结构化实战内容存入 code_content 供前端渲染
            import json
            code = json.dumps(code_data, ensure_ascii=False)
            content = (code_data.get("explanation") or "") + "\n" + code

        explanation = code_data.get("explanation") or ""
        if isinstance(explanation, str) and explanation.strip().startswith("{") and "content_mode" in explanation:
            # 历史坏数据形态：整段 JSON 被当成 explanation
            explanation = f"{req.topic} · {label}"
        summary = (explanation[:200] if explanation else f"{req.topic} · {label}")

        def attach_code(resource: ResResource) -> None:
            self.db.add(
                ResCodeCase(
                    resource_id=resource.id,
                    language=code_data.get("language", "practice" if not is_prog else "python"),
                    code_content=code if is_prog else (code_data.get("practice_content") or code),
                    explanation=explanation or None,
                    test_cases=code_data.get("test_cases"),
                    dependencies=code_data.get("dependencies"),
                    is_runnable=1 if is_prog else 0,
                    ext_json={
                        "is_programming": is_prog,
                        "subject_category": detect_subject_category(req.topic, req.goal),
                        "practice_type": code_data.get("practice_type"),
                        "practice_items": code_data.get("practice_items"),
                        "objective": code_data.get("objective"),
                        "module_label": label,
                    },
                )
            )

        r = await self._save_resource_base(
            ctx,
            user,
            req,
            "code",
            f"{req.topic} - {label}",
            summary,
            content,
            on_flushed=attach_code,
        )
        ctx.partial_previews.append({"agent_code": "extension", "resource_id": r.id, "title": r.title, "subtype": "code"})

    async def _save_animation(self, ctx, user, req, data):
        """入库 AI 视频讲解：绑定辅导会话中的沉浸式讲义，详情页可进完整沉浸式。"""
        from app.llm.gateway import LLMGateway
        from app.repositories.tutor_repository import TutorRepository
        from app.services.tutor_immersive_lecture_service import TutorImmersiveLectureService
        from app.services.tutor_lecture_resource_service import (
            TutorLectureResourceService,
            animation_slides_from_lecture,
            script_from_lecture,
        )

        lecture = data.get("lecture") if isinstance(data, dict) else None
        if isinstance(lecture, dict) and lecture.get("lecture_id"):
            tutor_repo = TutorRepository(self.db)
            session = tutor_repo.create_session(
                user_id=user.id,
                topic=(req.topic or "AI视频讲解")[:256],
                tutor_mode="socratic",
                agent_task_id=ctx.task_id,
                ext_json={"source": "resource_center"},
            )
            immersive = TutorImmersiveLectureService(LLMGateway(self.db))
            ext = immersive.store_in_session(dict(session.ext_json or {}), lecture)
            session.ext_json = ext
            tutor_repo.save_session(session)

            resource_id = TutorLectureResourceService(self.db).save_lecture_as_resource(
                user, session.session_no, lecture, ext
            )
            session.ext_json = ext
            tutor_repo.save_session(session)
            if resource_id:
                if resource_id not in ctx.resource_ids:
                    ctx.resource_ids.append(resource_id)
                self._update_partial(ctx)
                ctx.partial_previews.append(
                    {
                        "agent_code": "animation",
                        "resource_id": resource_id,
                        "title": f"{req.topic} - AI视频讲解",
                    }
                )
            return

        # 兼容旧版分镜动画数据
        script = data.get("script_content") or script_from_lecture({"slides": data.get("slides") or []})
        slides = data.get("slides") or animation_slides_from_lecture({"slides": []})

        def attach_video(resource: ResResource) -> None:
            anim_data = data.get("animation_data") or {}
            anim_data["slides"] = slides or anim_data.get("slides") or []
            anim_data["render_status"] = "ready"
            if not anim_data.get("teacher_name"):
                anim_data["teacher_name"] = "AI 教师"
            self.db.add(
                ResVideo(
                    resource_id=resource.id,
                    script_content=script,
                    storyboard=data.get("storyboard") or slides,
                    duration_sec=sum(int(s.get("duration_sec") or 10) for s in (slides or [])),
                    animation_type=data.get("animation_type", "slide_animation"),
                    animation_data=anim_data,
                    video_url=data.get("video_url"),
                    ext_json={"status": data.get("status", "ready"), "slides": slides},
                )
            )

        r = await self._save_resource_base(
            ctx,
            user,
            req,
            "video",
            f"{req.topic} - AI视频讲解",
            "AI 教师互动讲解，可进入完整沉浸式讲义",
            script,
            on_flushed=attach_video,
        )
        ctx.partial_previews.append({"agent_code": "animation", "resource_id": r.id, "title": r.title})


async def run_resource_generation_background(user_id: int, task_no: str, req_dict: dict) -> None:
    """Background entry point with isolated DB session."""
    db = SessionLocal()
    try:
        req = ResourceGenerateRequest(**req_dict)
        orchestrator = ResourceOrchestrator(db)
        await orchestrator.execute(user_id, task_no, req)
    finally:
        db.close()
        _running_tasks.pop(task_no, None)


def schedule_resource_generation(user_id: int, task_no: str, req: ResourceGenerateRequest) -> None:
    task = asyncio.create_task(
        run_resource_generation_background(user_id, task_no, req.model_dump())
    )
    _running_tasks[task_no] = task
