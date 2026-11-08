"""Learning behavior service."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException, ValidationException
from app.models.learning import LrnBehaviorEvent, LrnLearningSession
from app.models.sys import SysUser


class BehaviorService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def start_session(self, user: SysUser, path_id: int | None, node_id: int | None, session_type: str, device_type: str | None, ip: str | None) -> LrnLearningSession:
        session = LrnLearningSession(
            user_id=user.id,
            path_id=path_id,
            node_id=node_id,
            session_type=session_type,
            device_type=device_type,
            ip_address=ip,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def end_session(self, session_id: int, user_id: int) -> None:
        session = self.db.query(LrnLearningSession).filter(
            LrnLearningSession.id == session_id, LrnLearningSession.user_id == user_id
        ).first()
        if not session:
            raise NotFoundException(message="学习会话不存在")
        if session.ended_at:
            raise ValidationException("会话已结束")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        session.ended_at = now
        session.duration_sec = int((now - session.started_at).total_seconds())
        self.db.commit()

    def batch_track(self, user: SysUser, session_id: int | None, events: list) -> int:
        if session_id is not None:
            session = self.db.query(LrnLearningSession).filter(
                LrnLearningSession.id == session_id,
                LrnLearningSession.user_id == user.id,
            ).first()
            if not session:
                raise NotFoundException(message="学习会话不存在")
            if session.ended_at:
                raise ValidationException("会话已结束，无法上报事件")
        count = 0
        for e in events:
            self.db.add(
                LrnBehaviorEvent(
                    user_id=user.id,
                    session_id=session_id,
                    event_type=e.event_type,
                    event_target=e.event_target,
                    target_id=e.target_id,
                    event_data=e.event_data,
                    page_url=e.page_url,
                    client_ts=e.client_ts,
                )
            )
            count += 1
        self.db.commit()
        return count
