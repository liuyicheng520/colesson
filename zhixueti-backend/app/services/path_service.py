"""Learning path service — 3-phase personalized path with resource linking."""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundException, ValidationException
from app.llm.gateway import LLMGateway
from app.models.path import PthNodeProgress, PthPathNode, PthPathNodeEdge
from app.models.sys import SysUser
from app.repositories.agent_repository import AgentRepository
from app.repositories.path_repository import PathRepository
from app.repositories.profile_repository import ProfileRepository
from app.schemas.path import (
    NodeResourceItem,
    PathEdgeResponse,
    PathNodeResponse,
    PathPhaseResponse,
    PathPlanRequest,
    PathReplanRequest,
    PathResponse,
)
from app.services.path_planner import (
    EXPECTED_RESOURCE_TYPES,
    PHASE_DEFS,
    build_plan_prompt,
    build_profile_context,
    parse_llm_plan,
)


class PathService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.path_repo = PathRepository(db)
        self.profile_repo = ProfileRepository(db)
        self.agent_repo = AgentRepository(db)
        self.llm = LLMGateway(db)

    def _load_resource_items(
        self,
        node_id: int,
        learned_ids: set[int] | None = None,
        *,
        items_by_node: dict[int, list[NodeResourceItem]] | None = None,
    ) -> tuple[list[int], list[NodeResourceItem]]:
        if items_by_node is not None:
            items = items_by_node.get(node_id, [])
            if learned_ids:
                items = [
                    NodeResourceItem(
                        resource_id=it.resource_id,
                        title=it.title,
                        type_code=it.type_code,
                        type_name=it.type_name,
                        resource_role=it.resource_role,
                        is_learned=it.resource_id in learned_ids,
                    )
                    for it in items
                ]
            return [it.resource_id for it in items], items

        from app.models.resource import ResResource, ResResourceTypeDef

        learned = learned_ids or set()
        bindings = self.path_repo.get_node_resources(node_id)
        ids: list[int] = []
        items: list[NodeResourceItem] = []
        for b in bindings:
            res = self.db.query(ResResource).filter(ResResource.id == b.resource_id).first()
            if not res:
                continue
            type_def = self.db.query(ResResourceTypeDef).filter(ResResourceTypeDef.id == res.type_id).first()
            ids.append(res.id)
            items.append(
                NodeResourceItem(
                    resource_id=res.id,
                    title=res.title,
                    type_code=type_def.type_code if type_def else "document",
                    type_name=type_def.type_name if type_def else "文档",
                    resource_role=b.resource_role,
                    is_learned=res.id in learned,
                )
            )
        return ids, items

    def _batch_resource_items(self, node_ids: list[int]) -> dict[int, list[NodeResourceItem]]:
        """一次查出多节点绑定资源，消除 N+1。"""
        from app.models.resource import ResResource, ResResourceTypeDef

        result: dict[int, list[NodeResourceItem]] = {nid: [] for nid in node_ids}
        if not node_ids:
            return result

        bindings = self.path_repo.get_nodes_resources(node_ids)
        if not bindings:
            return result

        resource_ids = list({b.resource_id for b in bindings})
        resources = (
            self.db.query(ResResource).filter(ResResource.id.in_(resource_ids)).all()
            if resource_ids
            else []
        )
        res_map = {r.id: r for r in resources}
        type_ids = list({r.type_id for r in resources})
        types = (
            self.db.query(ResResourceTypeDef).filter(ResResourceTypeDef.id.in_(type_ids)).all()
            if type_ids
            else []
        )
        type_map = {t.id: t for t in types}

        for b in bindings:
            res = res_map.get(b.resource_id)
            if not res:
                continue
            type_def = type_map.get(res.type_id)
            result.setdefault(b.node_id, []).append(
                NodeResourceItem(
                    resource_id=res.id,
                    title=res.title,
                    type_code=type_def.type_code if type_def else "document",
                    type_name=type_def.type_name if type_def else "文档",
                    resource_role=b.resource_role,
                    is_learned=False,
                )
            )
        return result

    def _learned_resource_ids(self, prog: PthNodeProgress | None) -> set[int]:
        if not prog or not prog.ext_json:
            return set()
        raw = prog.ext_json.get("completed_resource_ids") or []
        out: set[int] = set()
        for x in raw:
            try:
                out.add(int(x))
            except (TypeError, ValueError):
                continue
        return out

    def _node_to_response(
        self,
        n: PthPathNode,
        progress_map: dict,
        name_by_id: dict[int, str] | None = None,
        *,
        items_by_node: dict[int, list[NodeResourceItem]] | None = None,
    ) -> PathNodeResponse:
        prog = progress_map.get(n.id)
        ext = n.ext_json or {}
        learned = self._learned_resource_ids(prog)
        resource_ids, resource_items = self._load_resource_items(
            n.id, learned, items_by_node=items_by_node
        )
        status = prog.status if prog else 0
        # 旧数据：误把单资源完成当成整节完成 → 有资源但无一标记已学时，展示为学习中
        if status == 3 and resource_items and not learned:
            status = 2
        elif status == 3 and resource_items and not all(it.is_learned for it in resource_items):
            status = 2
        prereq_names: list[str] = []
        if name_by_id is not None:
            pass
        return PathNodeResponse(
            id=n.id,
            node_code=n.node_code,
            node_name=n.node_name,
            node_type=n.node_type,
            phase=ext.get("phase", ""),
            phase_name=ext.get("phase_name", ""),
            description=n.description,
            sort_order=n.sort_order,
            difficulty=n.difficulty,
            estimated_min=n.estimated_min,
            status=status,
            mastery_score=prog.mastery_score if prog else None,
            resources=resource_ids,
            resource_items=resource_items,
            expected_resource_types=ext.get("expected_resource_types") or list(EXPECTED_RESOURCE_TYPES),
            is_weak=bool(ext.get("is_weak")),
            is_adaptive=bool(ext.get("is_adaptive")),
            prereq_names=prereq_names,
            learned_resource_count=sum(1 for it in resource_items if it.is_learned),
            total_resource_count=len(resource_items),
        )

    def _build_phases(self, nodes: list[PathNodeResponse]) -> list[PathPhaseResponse]:
        phases: list[PathPhaseResponse] = []
        for phase_def in PHASE_DEFS:
            phase_nodes = [n for n in nodes if n.phase == phase_def["phase"]]
            if not phase_nodes:
                continue
            phases.append(
                PathPhaseResponse(
                    phase=phase_def["phase"],
                    phase_name=phase_def["phase_name"],
                    description=phase_def["description"],
                    node_ids=[n.id for n in phase_nodes],
                    completed_count=sum(1 for n in phase_nodes if n.status == 3),
                    total_count=len(phase_nodes),
                )
            )
        return phases

    def _normalize_weak_labels(self, path) -> list[str]:
        ext = path.ext_json or {}
        snap = path.profile_snapshot or {}
        weak = list(snap.get("weak_points") or ext.get("weak_focus") or [])
        weak_labels: list[str] = []
        for w in weak:
            if isinstance(w, dict):
                label = str(w.get("topic") or w.get("name") or w.get("point") or "").strip()
            else:
                label = str(w).strip()
            if label and label not in weak_labels:
                weak_labels.append(label)
            if len(weak_labels) >= 6:
                break
        return weak_labels

    def _build_path_response(self, path, user_id: int) -> PathResponse:
        nodes = self.path_repo.get_nodes(path.id)
        edges = self.path_repo.get_edges(path.id)
        progress_list = self.path_repo.get_node_progress(user_id, path.id)
        progress_map = {p.node_id: p for p in progress_list}

        from app.models.learning import LrnUserProgressSummary

        summary = (
            self.db.query(LrnUserProgressSummary)
            .filter(LrnUserProgressSummary.user_id == user_id, LrnUserProgressSummary.path_id == path.id)
            .first()
        )

        name_by_id = {n.id: n.node_name for n in nodes}
        prereq_map: dict[int, list[str]] = {n.id: [] for n in nodes}
        for e in edges:
            if e.edge_type in ("prerequisite", "phase_gate") and e.to_node_id in prereq_map:
                prereq_map[e.to_node_id].append(name_by_id.get(e.from_node_id, "前置节点"))

        items_by_node = self._batch_resource_items([n.id for n in nodes])
        node_responses: list[PathNodeResponse] = []
        for n in nodes:
            resp = self._node_to_response(n, progress_map, items_by_node=items_by_node)
            resp.prereq_names = prereq_map.get(n.id, [])
            node_responses.append(resp)

        ext = path.ext_json or {}
        weak_labels = self._normalize_weak_labels(path)
        return PathResponse(
            id=path.id,
            path_no=path.path_no,
            title=path.title,
            goal=path.goal,
            path_version=path.path_version,
            total_nodes=path.total_nodes,
            estimated_hours=path.estimated_hours,
            status=path.status,
            progress_rate=summary.progress_rate if summary else Decimal("0"),
            path_mode=ext.get("path_mode") or ("standard" if ext.get("ignore_profile") else "profile"),
            nodes=node_responses,
            phases=self._build_phases(node_responses),
            edges=[
                PathEdgeResponse(from_node_id=e.from_node_id, to_node_id=e.to_node_id, edge_type=e.edge_type)
                for e in edges
            ],
            profile_snapshot=path.profile_snapshot,
            weak_focus=weak_labels,
            adaptive_node_count=sum(1 for n in node_responses if n.is_adaptive),
            created_at=path.created_at,
        )

    def _path_to_summary(self, path, user_id: int, progress_rate: Decimal | None = None) -> "PathSummaryResponse":
        from app.schemas.path import PathSummaryResponse

        ext = path.ext_json or {}
        rate = progress_rate
        if rate is None:
            from app.models.learning import LrnUserProgressSummary

            summary = (
                self.db.query(LrnUserProgressSummary)
                .filter(LrnUserProgressSummary.user_id == user_id, LrnUserProgressSummary.path_id == path.id)
                .first()
            )
            rate = summary.progress_rate if summary else Decimal("0")
        return PathSummaryResponse(
            id=path.id,
            path_no=path.path_no,
            title=path.title,
            goal=path.goal,
            path_version=path.path_version,
            total_nodes=path.total_nodes or 0,
            estimated_hours=path.estimated_hours,
            status=path.status,
            progress_rate=rate or Decimal("0"),
            path_mode=ext.get("path_mode") or ("standard" if ext.get("ignore_profile") else "profile"),
            weak_focus=self._normalize_weak_labels(path),
            adaptive_node_count=int(ext.get("adaptive_node_count") or 0),
            created_at=path.created_at,
            nodes=[],
        )

    def _auto_match_resources(self, user_id: int, node: PthPathNode) -> None:
        """将用户已有、主题相近的资源绑定到节点（路径创建或打开详情时补绑）。"""
        from app.models.resource import ResResource, ResResourceTypeDef

        existing = self.path_repo.get_node_resources(node.id)
        bound_ids = {b.resource_id for b in existing}
        bound_types: set[str] = set()
        if bound_ids:
            rows = (
                self.db.query(ResResourceTypeDef.type_code)
                .join(ResResource, ResResource.type_id == ResResourceTypeDef.id)
                .filter(ResResource.id.in_(bound_ids))
                .all()
            )
            bound_types = {r[0] for r in rows if r[0]}

        expected = [
            "document",
            "question",
            "mindmap",
            "reading",
            "code",
            "video",
        ]
        need_types = [t for t in expected if t not in bound_types]
        if not need_types:
            return

        matches = self.path_repo.find_matching_resources(user_id, node.node_name, need_types, limit=6)
        if not matches and len(node.node_name) >= 2:
            topic_word = node.node_name[:6]
            matches = self.path_repo.find_matching_resources(user_id, topic_word, need_types, limit=6)
        role_map = {
            "document": "primary",
            "question": "primary",
            "mindmap": "supplementary",
            "code": "supplementary",
            "reading": "supplementary",
            "video": "supplementary",
        }
        for res, type_code, _ in matches:
            if res.id in bound_ids or type_code in bound_types:
                continue
            role = role_map.get(type_code, "supplementary")
            self.path_repo.bind_node_resources(node.id, [res.id], role)
            bound_ids.add(res.id)
            bound_types.add(type_code)

    def _refresh_progress_summary(self, user_id: int, path_id: int) -> None:
        nodes = self.path_repo.get_nodes(path_id)
        progress_list = self.path_repo.get_node_progress(user_id, path_id)
        completed = sum(1 for p in progress_list if p.status == 3)
        self.path_repo.upsert_progress_summary(user_id, path_id, len(nodes), completed)

        path = self.path_repo.get_path_by_id(path_id)
        if path and len(nodes) > 0 and completed >= len(nodes):
            path.status = 2
            path.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            self.db.commit()

    async def plan_path(self, user: SysUser, req: PathPlanRequest) -> PathResponse:
        from app.services.config_service import ConfigService, PROFILE_MIN_COMPLETENESS

        profile = self.profile_repo.get_by_user_id(user.id)
        ignore_profile = bool(req.ignore_profile)
        path_mode = "standard" if ignore_profile else "profile"

        if not profile:
            raise ValidationException("请先初始化学习画像后再规划路径")

        if ignore_profile:
            profile_ctx = build_profile_context(self.profile_repo, profile.id, user)
        else:
            min_completeness = Decimal(str(ConfigService(self.db).get_float(PROFILE_MIN_COMPLETENESS, 0.8)))
            if profile.completeness < min_completeness:
                raise ValidationException(
                    f"请先完成用户画像构建（完整度≥{int(min_completeness * 100)}%）"
                )
            profile_ctx = build_profile_context(self.profile_repo, profile.id, user)
        profile_id = profile.id

        # 画像路径：薄弱点写入节点启发式标记
        weak_points = [str(w) for w in (profile_ctx.get("weak_points") or [])] if not ignore_profile else []
        kps = self.path_repo.get_knowledge_points(req.domain)

        task = self.agent_repo.create_task(
            user.id,
            "path_plan",
            f"{'标准' if ignore_profile else '画像'}路径: {req.goal[:30]}",
            {
                "goal": req.goal,
                "domain": req.domain,
                "ignore_profile": ignore_profile,
                "supplement": req.supplement,
                "adaptive": req.adaptive,
                "profile": profile_ctx,
            },
        )

        result = await self.llm.chat(
            build_plan_prompt(
                req.goal,
                req.domain,
                profile_ctx,
                kps,
                ignore_profile=ignore_profile,
                supplement=req.supplement,
                adaptive=req.adaptive,
            ),
            user_id=user.id,
            task_id=task.id,
            temperature=0.3,
            max_tokens=4096,
        )
        plan = parse_llm_plan(result.content, kps, profile_ctx, req.goal)

        # 启发式补齐 weak / adaptive 标记
        for pn in plan.nodes:
            blob = f"{pn.name} {pn.description}".lower()
            if not pn.is_weak and any(str(w).lower() in blob for w in weak_points):
                pn.is_weak = True
            if req.adaptive and pn.node_type == "remedial":
                pn.is_adaptive = True

        mode_label = "通用标准路径" if ignore_profile else "画像定制路径"
        if req.adaptive:
            mode_label = f"自适应·{mode_label}"
        total_min = sum(n.estimated_min for n in plan.nodes)
        path = self.path_repo.create_path_with_no(
            user_id=user.id,
            profile_id=profile_id,
            title=req.title or f"{req.goal[:20]} · {mode_label}",
            goal=req.goal,
            total_nodes=len(plan.nodes),
            estimated_hours=Decimal(str(round(total_min / 60, 1))),
            status=1,
            agent_task_id=task.id,
            profile_snapshot=None if ignore_profile else profile_ctx,
            ext_json={
                "phases": plan.phases,
                "planner": "3-phase-v2",
                "path_mode": path_mode,
                "ignore_profile": ignore_profile,
                "supplement": req.supplement,
                "adaptive": req.adaptive,
                "weak_focus": weak_points,
                "adaptive_node_count": sum(1 for pn in plan.nodes if pn.is_adaptive),
            },
            started_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )

        created_nodes: list[PthPathNode] = []

        for idx, pn in enumerate(plan.nodes):
            node = PthPathNode(
                path_id=path.id,
                node_code=f"{pn.phase.upper()[:3]}{idx+1:02d}",
                node_name=pn.name,
                node_type=pn.node_type,
                knowledge_point_id=pn.knowledge_point_id,
                sort_order=idx,
                difficulty=pn.difficulty,
                estimated_min=pn.estimated_min,
                description=pn.description,
                ext_json={
                    "phase": pn.phase,
                    "phase_name": pn.phase_name,
                    "expected_resource_types": pn.expected_resource_types,
                    "is_weak": pn.is_weak,
                    "is_adaptive": pn.is_adaptive,
                },
                unlock_condition={"phase": pn.phase},
            )
            node = self.path_repo.add_node(node)
            created_nodes.append(node)

            status = 1 if idx == 0 else 0
            self.path_repo.upsert_node_progress(
                PthNodeProgress(user_id=user.id, path_id=path.id, node_id=node.id, status=status)
            )
            self._auto_match_resources(user.id, node)

        for i in range(1, len(created_nodes)):
            self.path_repo.add_edge(
                PthPathNodeEdge(
                    path_id=path.id,
                    from_node_id=created_nodes[i - 1].id,
                    to_node_id=created_nodes[i].id,
                    edge_type="prerequisite",
                )
            )

        self._refresh_progress_summary(user.id, path.id)
        self.agent_repo.update_task(
            task.id,
            status=2,
            output_result={"path_id": path.id, "phases": plan.phases, "node_count": len(plan.nodes), "path_mode": path_mode},
        )
        return self._build_path_response(path, user.id)

    async def request_replan(self, user: SysUser, path_id: int, req: PathReplanRequest) -> PathResponse:
        """基于现有路径与学情触发自适应重规划，生成新版本路径。"""
        path = self.path_repo.get_path_by_id(path_id)
        if not path or path.user_id != user.id:
            raise NotFoundException(ErrorCode.PATH_NOT_FOUND)
        ext = path.ext_json or {}
        plan_req = PathPlanRequest(
            goal=path.goal,
            domain="machine_learning",
            title=f"{path.goal[:16]} · 自适应重规划",
            ignore_profile=bool(ext.get("ignore_profile")),
            supplement=(req.reason or ext.get("supplement") or "根据学习完成度与薄弱点动态调整节点"),
            adaptive=True,
        )
        return await self.plan_path(user, plan_req)

    def list_paths(self, user: SysUser) -> list:
        """列表仅返回轻量摘要，详情走 get_path。"""
        from app.models.learning import LrnUserProgressSummary

        paths = self.path_repo.list_user_paths(user.id)
        if not paths:
            return []
        path_ids = [p.id for p in paths]
        rate_rows = (
            self.db.query(LrnUserProgressSummary.path_id, LrnUserProgressSummary.progress_rate)
            .filter(
                LrnUserProgressSummary.user_id == user.id,
                LrnUserProgressSummary.path_id.in_(path_ids),
            )
            .all()
        )
        rate_map = {pid: rate for pid, rate in rate_rows}
        return [self._path_to_summary(p, user.id, rate_map.get(p.id)) for p in paths]

    def get_path(self, user: SysUser, path_id: int) -> PathResponse:
        path = self.path_repo.get_path_by_id(path_id)
        if not path or path.user_id != user.id:
            raise NotFoundException(ErrorCode.PATH_NOT_FOUND)
        # 打开路径时为空节点补绑主题匹配资源（修复「已生成但不展示」）
        for node in self.path_repo.get_nodes(path.id):
            self._auto_match_resources(user.id, node)
        return self._build_path_response(path, user.id)

    def update_node_progress(
        self,
        user: SysUser,
        node_id: int,
        status: int,
        study_duration_sec: int | None,
        mastery_score: Decimal | None,
        resource_id: int | None = None,
        mark_resource_done: bool = False,
    ) -> PathResponse:
        node = self.path_repo.get_node_by_id(node_id)
        if not node:
            raise NotFoundException(ErrorCode.PATH_NOT_FOUND)
        path = self.path_repo.get_path_by_id(node.path_id)
        if not path or path.user_id != user.id:
            raise NotFoundException(ErrorCode.PATH_NOT_FOUND)

        if status >= 2:
            self._ensure_prerequisites_met(user.id, path.id, node_id)

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        existing = next(
            (p for p in self.path_repo.get_node_progress(user.id, path.id) if p.node_id == node_id),
            None,
        )
        ext = dict(existing.ext_json or {}) if existing else {}
        completed_ids: list[int] = []
        for x in ext.get("completed_resource_ids") or []:
            try:
                completed_ids.append(int(x))
            except (TypeError, ValueError):
                continue

        if mark_resource_done and resource_id:
            if int(resource_id) not in completed_ids:
                completed_ids.append(int(resource_id))
            ext["completed_resource_ids"] = completed_ids

        resource_ids, _ = self._load_resource_items(node_id)
        # 学完单个资源：默认进入「学习中」；全部资源都学过才自动「已完成」
        effective_status = status
        if mark_resource_done and resource_id:
            if resource_ids and all(rid in completed_ids for rid in resource_ids):
                effective_status = 3
                if mastery_score is None:
                    mastery_score = Decimal("0.85")
            else:
                effective_status = 2 if status >= 2 else status

        progress = PthNodeProgress(
            user_id=user.id,
            path_id=path.id,
            node_id=node_id,
            status=effective_status,
            study_duration_sec=(existing.study_duration_sec if existing else 0) + (study_duration_sec or 0),
            mastery_score=mastery_score if mastery_score is not None else (existing.mastery_score if existing else None),
            last_study_at=now,
            ext_json=ext or None,
        )
        if effective_status == 2 and not (existing and existing.first_started_at):
            progress.first_started_at = now
        if existing and existing.first_started_at:
            progress.first_started_at = existing.first_started_at
        if effective_status == 3:
            progress.completed_at = now
        self.path_repo.upsert_node_progress(progress)

        if effective_status == 3:
            self._unlock_successors(user.id, path.id, node_id)
        self._refresh_progress_summary(user.id, path.id)
        return self._build_path_response(path, user.id)

    def _unlock_successors(self, user_id: int, path_id: int, node_id: int) -> None:
        edges = self.path_repo.get_edges(path_id)
        for edge in edges:
            if edge.from_node_id == node_id:
                self.path_repo.upsert_node_progress(
                    PthNodeProgress(user_id=user_id, path_id=path_id, node_id=edge.to_node_id, status=1)
                )

    def _ensure_prerequisites_met(self, user_id: int, path_id: int, node_id: int) -> None:
        edges = self.path_repo.get_edges(path_id)
        prereq_ids = [
            e.from_node_id
            for e in edges
            if e.to_node_id == node_id and e.edge_type in ("prerequisite", "phase_gate")
        ]
        if not prereq_ids:
            return
        progress_map = {p.node_id: p for p in self.path_repo.get_node_progress(user_id, path_id)}
        for pid in prereq_ids:
            prog = progress_map.get(pid)
            if not prog or prog.status < 3:
                raise ValidationException("请先完成前置节点", detail={"locked_node_id": node_id})

    def push_resources_to_node(self, user: SysUser, node_id: int, resource_ids: list[int], role: str) -> None:
        node = self.path_repo.get_node_by_id(node_id)
        if not node:
            raise NotFoundException(ErrorCode.PATH_NOT_FOUND)
        path = self.path_repo.get_path_by_id(node.path_id)
        if not path or path.user_id != user.id:
            raise NotFoundException(ErrorCode.PATH_NOT_FOUND)
        self.path_repo.bind_node_resources(node_id, resource_ids, role)
