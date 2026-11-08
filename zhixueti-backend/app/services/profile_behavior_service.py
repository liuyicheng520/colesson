"""
行为静默画像生成 — 基于学习行为数据自动推断 6 维画像。
数据来源：学习会话、行为事件、路径进度、资源交互。
"""

from decimal import Decimal

from app.models.learning import LrnBehaviorEvent, LrnLearningSession
from app.models.sys import SysUser
from app.profile_dimensions import CORE_DIMENSION_CODES
from app.repositories.profile_repository import ProfileRepository
from app.schemas.profile import BehaviorGenerateResponse, ProfileResponse
from app.services.learning_stats_service import LearningStatsService
from app.services.profile_dimension_utils import QUESTIONS_PER_DIMENSION, get_dimension_answers, get_question_progress, recalc_core_completeness, set_question_progress
from app.services.profile_fusion import (
    SOURCE_ACCURACY_WEIGHT,
    append_fusion_history,
    fused_confidence,
    fusion_contribute_dimension,
    get_dimension_contributions,
    list_refinement_dimensions,
)

# 兼容旧名
SOURCE_CONFIDENCE = SOURCE_ACCURACY_WEIGHT
from app.services.profile_service import ProfileService
from sqlalchemy import func


class ProfileBehaviorService:
    def __init__(self, db) -> None:
        self.db = db
        self.profile_repo = ProfileRepository(db)
        self.profile_service = ProfileService(db)
        self.stats_service = LearningStatsService(db)

    def check_availability(self, user: SysUser) -> dict:
        stats = self.stats_service.get_stats(user)
        return {"has_data": stats.has_data, "resources_learned": stats.resources_learned}

    def generate(self, user: SysUser) -> BehaviorGenerateResponse:
        stats = self.stats_service.get_stats(user)
        if not stats.has_data:
            from app.core.exceptions import ValidationException
            raise ValidationException("暂无学习数据，无法生成行为画像")

        features = self._extract_features(user.id, stats)
        dimensions = self._map_features_to_dimensions(features, user)

        profile = self.profile_service.get_or_create_profile(user)
        updated: list[str] = []
        q_progress = get_question_progress(profile.ext_json)
        answers = get_dimension_answers(profile.ext_json)

        for code in CORE_DIMENSION_CODES:
            val = dimensions.get(code)
            if not val:
                continue
            dim_def = self.profile_repo.get_dimension_def_by_code(code)
            if not dim_def:
                continue
            if fusion_contribute_dimension(
                self.profile_repo,
                profile.id,
                dim_def.id,
                code,
                val,
                "behavior",
                SOURCE_ACCURACY_WEIGHT["behavior"],
            ):
                updated.append(code)

        set_question_progress(self.profile_repo, profile.id, q_progress, answers)
        self.db.refresh(profile)
        ext = dict(profile.ext_json or {})
        from datetime import datetime, timezone
        ext["behavior_refresh_at"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        profile.ext_json = ext
        self.db.commit()
        recalc_core_completeness(self.profile_repo, profile.id)

        append_fusion_history(
            self.profile_repo,
            profile.id,
            {"mode": "behavior", "features": features, "updated_dimensions": updated},
        )
        profile.profile_version += 1
        self.db.commit()

        detail = self.profile_service.get_profile_detail(user)
        return BehaviorGenerateResponse(profile=detail, features_used=features, updated_dimensions=updated)

    def refresh_from_behavior(self, user: SysUser, *, force: bool = False) -> dict:
        """
        静默刷新行为画像 — 根据最新学习数据动态调整（替换同 source 贡献后重新融合）。
        默认 6 小时内不重复刷新，避免频繁写入。
        """
        from datetime import datetime, timedelta, timezone

        stats = self.stats_service.get_stats(user)
        if not stats.has_data:
            return {"refreshed": False, "reason": "no_data"}

        profile = self.profile_service.get_or_create_profile(user)
        ext = profile.ext_json or {}
        last = ext.get("behavior_refresh_at")
        if not force and last:
            try:
                last_dt = datetime.fromisoformat(str(last))
                if datetime.now(timezone.utc).replace(tzinfo=None) - last_dt < timedelta(hours=6):
                    return {"refreshed": False, "reason": "throttled"}
            except ValueError:
                pass

        features = self._extract_features(user.id, stats)
        dimensions = self._map_features_to_dimensions(features, user)
        updated: list[str] = []

        for code in CORE_DIMENSION_CODES:
            val = dimensions.get(code)
            if not val:
                continue
            dim_def = self.profile_repo.get_dimension_def_by_code(code)
            if not dim_def:
                continue
            if fusion_contribute_dimension(
                self.profile_repo,
                profile.id,
                dim_def.id,
                code,
                val,
                "behavior",
                SOURCE_ACCURACY_WEIGHT["behavior"],
            ):
                updated.append(code)

        ext = dict(profile.ext_json or {})
        ext["behavior_refresh_at"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        profile.ext_json = ext
        recalc_core_completeness(self.profile_repo, profile.id)
        append_fusion_history(
            self.profile_repo,
            profile.id,
            {"mode": "behavior_refresh", "updated_dimensions": updated, "features": features},
        )
        profile.profile_version += 1
        self.db.commit()
        return {"refreshed": True, "updated_dimensions": updated}

    def _extract_features(self, user_id: int, stats) -> dict:
        """提取 12 类核心行为特征。"""
        session_count = (
            self.db.query(func.count(LrnLearningSession.id))
            .filter(LrnLearningSession.user_id == user_id)
            .scalar()
            or 0
        )
        avg_duration = (
            self.db.query(func.avg(LrnLearningSession.duration_sec))
            .filter(LrnLearningSession.user_id == user_id, LrnLearningSession.duration_sec.isnot(None))
            .scalar()
            or 0
        )
        events = (
            self.db.query(LrnBehaviorEvent)
            .filter(LrnBehaviorEvent.user_id == user_id)
            .all()
        )
        event_types: dict[str, int] = {}
        for ev in events:
            event_types[ev.event_type] = event_types.get(ev.event_type, 0) + 1

        trend_minutes = sum(p.minutes for p in stats.trend_7d) if stats.trend_7d else 0

        return {
            "login_frequency_7d": len([p for p in stats.trend_7d if p.minutes > 0]),
            "avg_session_minutes": round(float(avg_duration) / 60, 1) if avg_duration else 0,
            "total_study_hours": stats.total_study_hours,
            "resources_learned": stats.resources_learned,
            "avg_accuracy": stats.avg_accuracy,
            "path_progress_rate": stats.path_progress_rate,
            "weekly_study_minutes": trend_minutes,
            "session_count": int(session_count),
            "resource_view_events": event_types.get("resource_view", 0),
            "quiz_submit_events": event_types.get("quiz_submit", 0),
            "tutor_ask_events": event_types.get("tutor_ask", 0),
            "video_complete_rate": min(stats.resources_learned / max(session_count, 1), 1.0),
        }

    def _map_features_to_dimensions(self, f: dict, user: SysUser) -> dict:
        """特征 → 6 维标签映射规则。"""
        # D1 知识基础：由正确率与路径进度推断
        accuracy = (f.get("avg_accuracy") or 0) / 100.0
        level = max(1, min(5, int(accuracy * 5) + (1 if f.get("path_progress_rate", 0) > 0.5 else 0)))
        weak = []
        if accuracy < 0.6:
            weak.append("基础巩固")
        if f.get("quiz_submit_events", 0) > 0 and accuracy < 0.75:
            weak.append("答题准确率提升")

        # D2 认知风格：由资源交互推断
        style = "visual" if f.get("resource_view_events", 0) > f.get("quiz_submit_events", 0) else "sequential"

        # D3 学习目标
        goal = "系统提升学习能力"
        priority = "high" if f.get("path_progress_rate", 0) > 0.3 else "mid"

        # D4 学习历史
        courses = []
        if f.get("resources_learned", 0) > 0:
            courses.append(f"已学习 {f['resources_learned']} 个资源")
        total_hours = f.get("total_study_hours", 0)

        # D5 易错点
        weak_points = []
        if accuracy < 0.7:
            weak_points.append({"topic": "综合答题", "errorType": "accuracy", "frequency": f.get("quiz_submit_events", 0)})

        # D6 学习节奏
        avg_min = f.get("avg_session_minutes", 30)
        if avg_min < 25:
            pace = "fast"
        elif avg_min > 50:
            pace = "slow"
        else:
            pace = "medium"

        return {
            "D1": {"domain": user.major or "通用", "level": level, "gaps": weak, "source": "behavior"},
            "D2": {"style": style, "score": 0.8},
            "D3": {"goal": goal, "deadline": None, "priority": priority},
            "D4": {"courses": courses, "completedTopics": courses, "totalHours": int(total_hours)},
            "D5": {"weakPoints": weak_points},
            "D6": {"pace": pace, "sessionMinutes": int(avg_min) or 30},
        }
