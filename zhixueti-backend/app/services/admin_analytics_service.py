"""Platform-wide analytics for admin dashboard."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.learning import LrnLearningSession
from app.models.sys import SysUser
from app.models.tutor import TutTutorMessage, TutTutorSession


class AdminAnalyticsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _now(self) -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    def _day_start(self, dt: datetime) -> datetime:
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)

    def get_overview(self) -> dict:
        now = self._now()
        today = self._day_start(now)
        student_q = self.db.query(SysUser).filter(SysUser.deleted_at.is_(None), SysUser.user_type == 1)

        total_users = student_q.count()
        dau = student_q.filter(SysUser.last_login_at >= today).count() if total_users else 0

        total_study_sec = (
            self.db.query(func.coalesce(func.sum(LrnLearningSession.duration_sec), 0)).scalar() or 0
        )

        qa_total = (
            self.db.query(func.count(TutTutorMessage.id)).filter(TutTutorMessage.role == "user").scalar() or 0
        )

        return {
            "total_users": total_users,
            "dau_users": dau,
            "total_study_hours": round(total_study_sec / 3600, 1),
            "qa_total": int(qa_total),
            "multimodal_total": self._count_multimodal_generations(),
        }

    def _count_multimodal_generations(self) -> int:
        count = 0
        sessions = self.db.query(TutTutorSession).filter(TutTutorSession.ext_json.isnot(None)).all()
        for s in sessions:
            ext = s.ext_json or {}
            count += len(ext.get("lectures") or {})
            store = ext.get("message_store") or {}
            for meta in store.values():
                if isinstance(meta, dict):
                    mm = meta.get("multimodal") or meta
                    if mm.get("type") in ("image", "video"):
                        count += 1
        return count

    def get_trends(self, days: int = 7) -> dict:
        now = self._now()
        start = self._day_start(now - timedelta(days=days - 1))
        dates = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]

        reg_map: dict[str, int] = {d: 0 for d in dates}
        for u in (
            self.db.query(SysUser)
            .filter(SysUser.deleted_at.is_(None), SysUser.user_type == 1, SysUser.created_at >= start)
            .all()
        ):
            key = u.created_at.strftime("%Y-%m-%d")
            if key in reg_map:
                reg_map[key] += 1

        qa_map: dict[str, int] = {d: 0 for d in dates}
        for m in (
            self.db.query(TutTutorMessage)
            .filter(TutTutorMessage.role == "user", TutTutorMessage.created_at >= start)
            .all()
        ):
            key = m.created_at.strftime("%Y-%m-%d")
            if key in qa_map:
                qa_map[key] += 1

        lecture_map: dict[str, int] = {d: 0 for d in dates}
        for s in self.db.query(TutTutorSession).filter(TutTutorSession.updated_at >= start).all():
            ext = s.ext_json or {}
            for lec in (ext.get("lectures") or {}).values():
                if not isinstance(lec, dict):
                    continue
                ts = lec.get("created_at") or (s.updated_at.isoformat() if s.updated_at else "")
                day = ts[:10] if ts else s.updated_at.strftime("%Y-%m-%d")
                if day in lecture_map:
                    lecture_map[day] += 1

        return {
            "days": days,
            "dates": dates,
            "registrations": [reg_map[d] for d in dates],
            "qa_counts": [qa_map[d] for d in dates],
            "lecture_counts": [lecture_map[d] for d in dates],
        }

    def get_feature_usage(self) -> list[dict]:
        sessions = self.db.query(TutTutorSession).all()
        counts = {
            "text_qa": 0,
            "document_qa": 0,
            "web_search": 0,
            "deep_mode": 0,
            "image_gen": 0,
            "video_lecture": 0,
        }
        for s in sessions:
            ext = s.ext_json or {}
            rounds = max(s.total_rounds, 0)
            if ext.get("document_ids"):
                counts["document_qa"] += rounds or 1
            elif ext.get("web_search_enabled"):
                counts["web_search"] += rounds or 1
            elif ext.get("deep_mode"):
                counts["deep_mode"] += rounds or 1
            else:
                counts["text_qa"] += rounds or 1
            store = ext.get("message_store") or {}
            for meta in store.values():
                if isinstance(meta, dict):
                    mm = meta.get("multimodal") or meta
                    if mm.get("type") == "image":
                        counts["image_gen"] += 1
            counts["video_lecture"] += len(ext.get("lectures") or {})

        labels = {
            "text_qa": "纯文字问答",
            "document_qa": "文档问答",
            "web_search": "联网搜索",
            "deep_mode": "深度模式",
            "image_gen": "图像生成",
            "video_lecture": "视频讲解",
        }
        return [{"name": labels[k], "value": v} for k, v in counts.items() if v > 0]

    def get_top_topics(self, limit: int = 10) -> list[dict]:
        rows = (
            self.db.query(TutTutorSession.topic, func.count(TutTutorSession.id).label("cnt"))
            .group_by(TutTutorSession.topic)
            .order_by(func.count(TutTutorSession.id).desc())
            .limit(limit)
            .all()
        )
        return [{"topic": r[0], "count": int(r[1])} for r in rows if r[0]]
