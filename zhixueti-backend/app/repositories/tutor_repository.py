"""Tutor repository."""

import uuid

from sqlalchemy.orm import Session

from app.models.tutor import TutTutorMessage, TutTutorSession


class TutorRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_session(self, session_no: str) -> TutTutorSession | None:
        return self.db.query(TutTutorSession).filter(TutTutorSession.session_no == session_no).first()

    def list_user_sessions(self, user_id: int, limit: int = 50) -> list[TutTutorSession]:
        return (
            self.db.query(TutTutorSession)
            .filter(TutTutorSession.user_id == user_id)
            .order_by(TutTutorSession.updated_at.desc())
            .limit(limit)
            .all()
        )

    def count_user_sessions(self, user_id: int) -> int:
        return self.db.query(TutTutorSession).filter(TutTutorSession.user_id == user_id).count()

    def delete_session(self, session: TutTutorSession) -> None:
        self.db.query(TutTutorMessage).filter(TutTutorMessage.session_id == session.id).delete()
        self.db.delete(session)
        self.db.commit()

    def create_session(self, **kwargs) -> TutTutorSession:
        session = TutTutorSession(session_no=str(uuid.uuid4()), **kwargs)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def save_session(self, session: TutTutorSession) -> TutTutorSession:
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_messages(self, session_id: int) -> list[TutTutorMessage]:
        return (
            self.db.query(TutTutorMessage)
            .filter(TutTutorMessage.session_id == session_id)
            .order_by(TutTutorMessage.round_no)
            .all()
        )

    def add_message(self, msg: TutTutorMessage) -> TutTutorMessage:
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg
