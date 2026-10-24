"""Resource repository."""

from sqlalchemy.orm import Session

from app.models.resource import (
    ResCodeCase,
    ResDocument,
    ResMindmap,
    ResQuestion,
    ResReading,
    ResResource,
    ResResourceTypeDef,
    ResVideo,
)


class ResourceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_type_by_code(self, type_code: str) -> ResResourceTypeDef | None:
        return (
            self.db.query(ResResourceTypeDef)
            .filter(ResResourceTypeDef.type_code == type_code)
            .first()
        )

    def get_types(self) -> list[ResResourceTypeDef]:
        return (
            self.db.query(ResResourceTypeDef)
            .filter(ResResourceTypeDef.status == 1)
            .order_by(ResResourceTypeDef.sort_order)
            .all()
        )

    def get_by_id(self, resource_id: int) -> ResResource | None:
        return (
            self.db.query(ResResource)
            .filter(ResResource.id == resource_id, ResResource.deleted_at.is_(None))
            .first()
        )

    def get_by_no(self, resource_no: str) -> ResResource | None:
        return (
            self.db.query(ResResource)
            .filter(ResResource.resource_no == resource_no, ResResource.deleted_at.is_(None))
            .first()
        )

    def list_by_user(
        self,
        user_id: int,
        type_code: str | None = None,
        topic: str | None = None,
        status: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ResResource], int]:
        q = self.db.query(ResResource).filter(
            ResResource.user_id == user_id,
            ResResource.deleted_at.is_(None),
        )
        if type_code:
            type_def = self.get_type_by_code(type_code)
            if type_def:
                q = q.filter(ResResource.type_id == type_def.id)
        if topic:
            q = q.filter(ResResource.topic.like(f"%{topic}%"))
        if status is not None:
            q = q.filter(ResResource.status == status)
        total = q.count()
        items = (
            q.order_by(ResResource.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def list_all(
        self,
        *,
        keyword: str | None = None,
        type_code: str | None = None,
        status: int | None = None,
        user_id: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ResResource], int]:
        q = self.db.query(ResResource).filter(ResResource.deleted_at.is_(None))
        if type_code:
            type_def = self.get_type_by_code(type_code)
            if type_def:
                q = q.filter(ResResource.type_id == type_def.id)
        if status is not None:
            q = q.filter(ResResource.status == status)
        if user_id is not None:
            q = q.filter(ResResource.user_id == user_id)
        if keyword:
            like = f"%{keyword}%"
            q = q.filter((ResResource.title.like(like)) | (ResResource.topic.like(like)))
        total = q.count()
        items = (
            q.order_by(ResResource.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def list_published(
        self,
        *,
        type_code: str | None = None,
        topic: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ResResource], int]:
        """资源广场：仅已发布(status=2)的公开资源，跨用户可见。"""
        q = self.db.query(ResResource).filter(
            ResResource.deleted_at.is_(None),
            ResResource.status == 2,
        )
        if type_code:
            type_def = self.get_type_by_code(type_code)
            if type_def:
                q = q.filter(ResResource.type_id == type_def.id)
        if topic:
            like = f"%{topic}%"
            q = q.filter((ResResource.title.like(like)) | (ResResource.topic.like(like)))
        total = q.count()
        items = (
            q.order_by(ResResource.published_at.desc(), ResResource.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def update_status(self, resource: ResResource, status: int) -> ResResource:
        from datetime import datetime, timezone

        resource.status = status
        if status == 2:
            resource.published_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.commit()
        self.db.refresh(resource)
        return resource

    def soft_delete(self, resource: ResResource) -> None:
        from datetime import datetime, timezone

        resource.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        resource.status = 3
        self.db.commit()

    def batch_update_status(self, ids: list[int], status: int) -> int:
        from datetime import datetime, timezone

        q = self.db.query(ResResource).filter(
            ResResource.id.in_(ids), ResResource.deleted_at.is_(None)
        )
        count = 0
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for res in q.all():
            res.status = status
            if status == 2:
                res.published_at = now
            count += 1
        self.db.commit()
        return count

    def save(self, resource: ResResource) -> ResResource:
        self.db.add(resource)
        self.db.commit()
        self.db.refresh(resource)
        return resource

    def get_extension(self, resource: ResResource) -> dict | None:
        type_def = self.db.query(ResResourceTypeDef).filter(ResResourceTypeDef.id == resource.type_id).first()
        if not type_def:
            return None
        mapping = {
            "document": ResDocument,
            "mindmap": ResMindmap,
            "reading": ResReading,
            "video": ResVideo,
            "code": ResCodeCase,
            "question": ResQuestion,
        }
        model = mapping.get(type_def.type_code)
        if type_def.type_code == "question":
            questions = self.db.query(ResQuestion).filter(ResQuestion.resource_id == resource.id).all()
            return {
                "type_code": "question",
                "data": questions[0] if questions else None,
                "questions": [
                    {
                        "question_type": q.question_type,
                        "stem": q.stem,
                        "options": q.options,
                        "answer": q.answer,
                        "analysis": q.analysis,
                        "difficulty": q.difficulty,
                        "error_type": q.error_type,
                    }
                    for q in questions
                ],
            }
        if not model:
            return None
        ext = self.db.query(model).filter(model.resource_id == resource.id).first()
        if not ext:
            return None
        return {"type_code": type_def.type_code, "data": ext}
