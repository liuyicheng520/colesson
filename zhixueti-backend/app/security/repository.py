"""Security audit repository."""

import uuid

from sqlalchemy.orm import Session

from app.models.path import SecContentAudit, SecSensitiveWord
from app.models.resource import ResResource


class SecurityRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_audits(
        self,
        audit_result: int | None = None,
        target_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SecContentAudit], int]:
        q = self.db.query(SecContentAudit)
        if audit_result is not None:
            q = q.filter(SecContentAudit.audit_result == audit_result)
        if target_type:
            q = q.filter(SecContentAudit.target_type == target_type)
        total = q.count()
        items = (
            q.order_by(SecContentAudit.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def get_audit(self, audit_id: int) -> SecContentAudit | None:
        return self.db.query(SecContentAudit).filter(SecContentAudit.id == audit_id).first()

    def list_sensitive_words(self) -> list[SecSensitiveWord]:
        return self.db.query(SecSensitiveWord).order_by(SecSensitiveWord.id).all()

    def add_sensitive_word(self, word: SecSensitiveWord) -> SecSensitiveWord:
        self.db.add(word)
        self.db.commit()
        self.db.refresh(word)
        return word

    def takedown_resource(self, resource_id: int, auditor_id: int, note: str) -> bool:
        res = self.db.query(ResResource).filter(ResResource.id == resource_id).first()
        if not res:
            return False
        res.status = 0
        res.audit_status = 0
        audit = SecContentAudit(
            audit_no=str(uuid.uuid4()),
            target_type="resource",
            target_id=resource_id,
            content_snapshot=res.title,
            audit_type="manual",
            audit_provider="admin",
            audit_result=0,
            risk_level=3,
            risk_labels=["admin_takedown"],
            auditor_id=auditor_id,
            audit_note=note,
        )
        self.db.add(audit)
        self.db.commit()
        return True
