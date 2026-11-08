"""Learning statistics aggregation — 所有查询强制按 user_id 过滤。"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.learning import LrnBehaviorEvent, LrnLearningSession, LrnUserProgressSummary
from app.models.path import PthLearningPath, PthNodeProgress, PthPathNode
from app.models.resource import ResResource
from app.models.sys import SysUser
from app.repositories.path_repository import PathRepository
from app.schemas.learning import LearningStatsResponse, MasteryItem, RecentRecord, TrendPoint


class LearningStatsService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.path_repo = PathRepository(db)

    def get_stats(self, user: SysUser, *, include_trend_30d: bool = True) -> LearningStatsResponse:
        user_id = user.id
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        paths = self.path_repo.list_user_paths(user_id)
        primary_path = paths[0] if paths else None

        # 学习时长：优先 learning_session，其次节点进度累计
        total_sec = (
            self.db.query(func.coalesce(func.sum(LrnLearningSession.duration_sec), 0))
            .filter(LrnLearningSession.user_id == user_id, LrnLearningSession.duration_sec.isnot(None))
            .scalar()
            or 0
        )
        if total_sec == 0 and primary_path:
            node_progress = self.path_repo.get_node_progress(user_id, primary_path.id)
            total_sec = sum(p.study_duration_sec or 0 for p in node_progress)

        resources_learned = (
            self.db.query(func.count(ResResource.id))
            .filter(ResResource.user_id == user_id, ResResource.deleted_at.is_(None), ResResource.status.in_([1, 2]))
            .scalar()
            or 0
        )

        knowledge_completed = 0
        path_progress_rate = 0.0
        path_completed = 0
        path_total = 0
        path_title = None
        mastery_items: list[MasteryItem] = []

        if primary_path:
            path_title = primary_path.title
            nodes = self.path_repo.get_nodes(primary_path.id)
            path_total = len(nodes)
            progress_list = self.path_repo.get_node_progress(user_id, primary_path.id)
            progress_map = {p.node_id: p for p in progress_list}
            path_completed = sum(1 for p in progress_list if p.status == 3)
            knowledge_completed = path_completed
            summary = (
                self.db.query(LrnUserProgressSummary)
                .filter(LrnUserProgressSummary.user_id == user_id, LrnUserProgressSummary.path_id == primary_path.id)
                .first()
            )
            path_progress_rate = float(summary.progress_rate) if summary else (
                round(path_completed / path_total, 4) if path_total else 0
            )
            for node in nodes[:8]:
                prog = progress_map.get(node.id)
                score = float(prog.mastery_score) if prog and prog.mastery_score is not None else (
                    0.85 if prog and prog.status == 3 else 0.5 if prog and prog.status == 2 else 0
                )
                mastery_items.append(MasteryItem(name=node.node_name[:12], value=round(score * 100, 1)))

        # 正确率：来自 quiz_submit 事件
        quiz_events = (
            self.db.query(LrnBehaviorEvent)
            .filter(LrnBehaviorEvent.user_id == user_id, LrnBehaviorEvent.event_type == "quiz_submit")
            .all()
        )
        correct = 0
        total_quiz = 0
        for ev in quiz_events:
            data = ev.event_data or {}
            if "correct" in data:
                total_quiz += 1
                if data.get("correct"):
                    correct += 1
            elif "score" in data:
                total_quiz += 1
                try:
                    if float(data["score"]) >= 0.6:
                        correct += 1
                except (TypeError, ValueError):
                    pass
        # 无真实作答数据时返回 None（诚实空态），不再用路径完成率冒充正确率
        avg_accuracy = round(correct / total_quiz * 100, 1) if total_quiz else None

        trend_7d = self._build_trend(user_id, now, 7)
        # 30 日趋势按需计算；默认跳过以加速个人中心等轻量看板
        trend_30d = self._build_trend(user_id, now, 30) if include_trend_30d else []

        prev_7d_sec = self._period_study_sec(user_id, now - timedelta(days=14), now - timedelta(days=7))
        curr_7d_sec = self._period_study_sec(user_id, now - timedelta(days=7), now)
        study_hours_change = self._pct_change(prev_7d_sec, curr_7d_sec)

        recent_records = self._recent_records(user_id, primary_path.id if primary_path else None)

        has_data = bool(
            total_sec > 0 or resources_learned > 0 or path_completed > 0 or len(recent_records) > 0
        )

        return LearningStatsResponse(
            total_study_hours=round(total_sec / 3600, 2),
            resources_learned=int(resources_learned),
            knowledge_points_completed=knowledge_completed,
            avg_accuracy=avg_accuracy,
            study_hours_change_pct=study_hours_change,
            resources_change_pct=0,
            knowledge_change_pct=study_hours_change,
            accuracy_change_pct=0,
            trend_7d=trend_7d,
            trend_30d=trend_30d,
            mastery_items=mastery_items,
            path_progress_rate=path_progress_rate,
            path_completed_nodes=path_completed,
            path_total_nodes=path_total,
            path_title=path_title,
            recent_records=recent_records,
            has_data=has_data,
        )

    def _period_study_sec(self, user_id: int, start: datetime, end: datetime) -> int:
        return (
            self.db.query(func.coalesce(func.sum(LrnLearningSession.duration_sec), 0))
            .filter(
                LrnLearningSession.user_id == user_id,
                LrnLearningSession.started_at >= start,
                LrnLearningSession.started_at < end,
                LrnLearningSession.duration_sec.isnot(None),
            )
            .scalar()
            or 0
        )

    def _pct_change(self, prev: int | float, curr: int | float) -> float | None:
        # 基线为 0 时百分比无意义，返回 None（前端显示「—」）
        if prev <= 0:
            return None
        return round((curr - prev) / prev * 100, 1)

    def _build_trend(self, user_id: int, now: datetime, days: int) -> list[TrendPoint]:
        start = now - timedelta(days=days - 1)
        sessions = (
            self.db.query(LrnLearningSession)
            .filter(
                LrnLearningSession.user_id == user_id,
                LrnLearningSession.started_at >= start.replace(hour=0, minute=0, second=0),
            )
            .all()
        )
        by_date: dict[str, int] = {}
        for s in sessions:
            key = s.started_at.strftime("%Y-%m-%d")
            by_date[key] = by_date.get(key, 0) + (s.duration_sec or 0)

        # 补充节点进度时长（无 session 时）
        if not sessions:
            progress_rows = (
                self.db.query(PthNodeProgress)
                .filter(PthNodeProgress.user_id == user_id, PthNodeProgress.last_study_at.isnot(None))
                .all()
            )
            for p in progress_rows:
                if p.last_study_at and p.last_study_at >= start:
                    key = p.last_study_at.strftime("%Y-%m-%d")
                    by_date[key] = by_date.get(key, 0) + (p.study_duration_sec or 0)

        points: list[TrendPoint] = []
        for i in range(days):
            d = (start + timedelta(days=i)).strftime("%Y-%m-%d")
            points.append(TrendPoint(date=d, minutes=round(by_date.get(d, 0) / 60, 1)))
        return points

    def _recent_records(self, user_id: int, path_id: int | None) -> list[RecentRecord]:
        sessions = (
            self.db.query(LrnLearningSession)
            .filter(LrnLearningSession.user_id == user_id)
            .order_by(LrnLearningSession.started_at.desc())
            .limit(10)
            .all()
        )
        records: list[RecentRecord] = []
        for s in sessions:
            node_name = None
            resource_name = "学习会话"
            if s.node_id:
                node = self.db.query(PthPathNode).filter(PthPathNode.id == s.node_id).first()
                node_name = node.node_name if node else None
                resource_name = node_name or resource_name
            records.append(
                RecentRecord(
                    resource_name=resource_name,
                    study_time=s.started_at.strftime("%Y-%m-%d %H:%M") if s.started_at else "",
                    duration_minutes=round((s.duration_sec or 0) / 60, 1),
                    node_name=node_name,
                )
            )

        if not records and path_id:
            progress_list = (
                self.db.query(PthNodeProgress)
                .filter(PthNodeProgress.user_id == user_id, PthNodeProgress.path_id == path_id)
                .order_by(PthNodeProgress.last_study_at.desc().nullslast())
                .limit(8)
                .all()
            )
            for p in progress_list:
                node = self.db.query(PthPathNode).filter(PthPathNode.id == p.node_id).first()
                if not node:
                    continue
                records.append(
                    RecentRecord(
                        resource_name=node.node_name,
                        study_time=p.last_study_at.strftime("%Y-%m-%d %H:%M") if p.last_study_at else "",
                        duration_minutes=round((p.study_duration_sec or 0) / 60, 1),
                        node_name=node.node_name,
                    )
                )
        return records[:10]
