"""Profile repository."""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.profile import (
    UsrProfile,
    UsrProfileDialogueMessage,
    UsrProfileDialogueSession,
    UsrProfileDimensionDef,
    UsrProfileDimensionValue,
    UsrProfileEvolutionLog,
)


class ProfileRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_user_id(self, user_id: int) -> UsrProfile | None:
        return self.db.query(UsrProfile).filter(UsrProfile.user_id == user_id).first()

    def get_dimension_defs(self) -> list[UsrProfileDimensionDef]:
        return (
            self.db.query(UsrProfileDimensionDef)
            .filter(UsrProfileDimensionDef.status == 1)
            .order_by(UsrProfileDimensionDef.sort_order)
            .all()
        )

    def list_all_dimension_defs(self) -> list[UsrProfileDimensionDef]:
        return (
            self.db.query(UsrProfileDimensionDef)
            .order_by(UsrProfileDimensionDef.sort_order)
            .all()
        )

    def get_dimension_def_by_id(self, dim_id: int) -> UsrProfileDimensionDef | None:
        return self.db.query(UsrProfileDimensionDef).filter(UsrProfileDimensionDef.id == dim_id).first()

    def save_dimension_def(self, dim: UsrProfileDimensionDef) -> UsrProfileDimensionDef:
        self.db.add(dim)
        self.db.commit()
        self.db.refresh(dim)
        return dim

    def get_dimension_values(self, profile_id: int) -> list[UsrProfileDimensionValue]:
        return (
            self.db.query(UsrProfileDimensionValue)
            .filter(UsrProfileDimensionValue.profile_id == profile_id)
            .all()
        )

    def get_dimension_def_by_code(self, code: str) -> UsrProfileDimensionDef | None:
        return (
            self.db.query(UsrProfileDimensionDef)
            .filter(UsrProfileDimensionDef.dimension_code == code)
            .first()
        )

    def get_dialogue_session(self, session_no: str) -> UsrProfileDialogueSession | None:
        return (
            self.db.query(UsrProfileDialogueSession)
            .filter(UsrProfileDialogueSession.session_no == session_no)
            .first()
        )

    def get_active_dialogue_session(self, user_id: int, profile_id: int) -> UsrProfileDialogueSession | None:
        """获取用户未结束的对话会话，用于断点续答。"""
        return (
            self.db.query(UsrProfileDialogueSession)
            .filter(
                UsrProfileDialogueSession.user_id == user_id,
                UsrProfileDialogueSession.profile_id == profile_id,
                UsrProfileDialogueSession.status == 0,
            )
            .order_by(UsrProfileDialogueSession.id.desc())
            .first()
        )

    def get_latest_dialogue_session(self, user_id: int, profile_id: int) -> UsrProfileDialogueSession | None:
        """最近一次画像对话会话（含已结束），用于回看历史。"""
        return (
            self.db.query(UsrProfileDialogueSession)
            .filter(
                UsrProfileDialogueSession.user_id == user_id,
                UsrProfileDialogueSession.profile_id == profile_id,
            )
            .order_by(UsrProfileDialogueSession.id.desc())
            .first()
        )

    def get_dialogue_session_for_restore(
        self, user_id: int, profile_id: int
    ) -> UsrProfileDialogueSession | None:
        """在最近会话中选消息最多的一条，避免完成后新开会话丢掉历史。"""
        recent = (
            self.db.query(UsrProfileDialogueSession)
            .filter(
                UsrProfileDialogueSession.user_id == user_id,
                UsrProfileDialogueSession.profile_id == profile_id,
            )
            .order_by(UsrProfileDialogueSession.id.desc())
            .limit(8)
            .all()
        )
        best: UsrProfileDialogueSession | None = None
        best_count = -1
        best_active = False
        for s in recent:
            count = (
                self.db.query(UsrProfileDialogueMessage)
                .filter(UsrProfileDialogueMessage.session_id == s.id)
                .count()
            )
            is_active = s.status == 0
            if count > best_count or (count == best_count and is_active and not best_active):
                best = s
                best_count = count
                best_active = is_active
        return best if best_count > 0 else None

    def close_active_dialogue_sessions(self, user_id: int, profile_id: int) -> int:
        """关闭未结束的对话会话（切换模式后重新开始提问）。"""
        from datetime import datetime, timezone

        sessions = (
            self.db.query(UsrProfileDialogueSession)
            .filter(
                UsrProfileDialogueSession.user_id == user_id,
                UsrProfileDialogueSession.profile_id == profile_id,
                UsrProfileDialogueSession.status == 0,
            )
            .all()
        )
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for s in sessions:
            s.status = 1
            s.ended_at = now
        if sessions:
            self.db.commit()
        return len(sessions)

    def get_dialogue_messages(self, session_id: int) -> list[UsrProfileDialogueMessage]:
        return (
            self.db.query(UsrProfileDialogueMessage)
            .filter(UsrProfileDialogueMessage.session_id == session_id)
            .order_by(UsrProfileDialogueMessage.round_no, UsrProfileDialogueMessage.id)
            .all()
        )

    def save_profile(self, profile: UsrProfile) -> UsrProfile:
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def upsert_dimension_value(
        self,
        profile_id: int,
        dimension_id: int,
        value: dict,
        confidence: Decimal,
        source_type: str,
        source_ref_id: int | None = None,
    ) -> UsrProfileDimensionValue:
        existing = (
            self.db.query(UsrProfileDimensionValue)
            .filter(
                UsrProfileDimensionValue.profile_id == profile_id,
                UsrProfileDimensionValue.dimension_id == dimension_id,
            )
            .first()
        )
        if existing:
            existing.dimension_value = value
            existing.confidence = confidence
            existing.source_type = source_type
            existing.source_ref_id = source_ref_id
            self.db.commit()
            self.db.refresh(existing)
            return existing
        dim_value = UsrProfileDimensionValue(
            profile_id=profile_id,
            dimension_id=dimension_id,
            dimension_value=value,
            confidence=confidence,
            source_type=source_type,
            source_ref_id=source_ref_id,
        )
        self.db.add(dim_value)
        self.db.commit()
        self.db.refresh(dim_value)
        return dim_value

    def add_evolution_log(self, log: UsrProfileEvolutionLog) -> None:
        self.db.add(log)
        self.db.commit()

    def recalc_completeness(self, profile_id: int) -> tuple[Decimal, Decimal]:
        defs = self.get_dimension_defs()
        required = [d for d in defs if d.is_required == 1]
        values = self.get_dimension_values(profile_id)
        value_map = {v.dimension_id: v for v in values}
        filled = sum(1 for d in required if d.id in value_map)
        completeness = Decimal(str(round(filled / len(required), 4))) if required else Decimal("0")
        confidences = [value_map[d.id].confidence for d in required if d.id in value_map]
        avg_conf = (
            sum(confidences) / len(confidences) if confidences else Decimal("0")
        )
        profile = self.db.query(UsrProfile).filter(UsrProfile.id == profile_id).first()
        if profile:
            profile.completeness = completeness
            profile.avg_confidence = avg_conf
            self.db.commit()
        return completeness, avg_conf
