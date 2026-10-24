"""Learning path repository."""

import uuid

from sqlalchemy.orm import Session

from app.models.path import (
    PthKnowledgePoint,
    PthLearningPath,
    PthNodeProgress,
    PthNodeResource,
    PthPathNode,
    PthPathNodeEdge,
)
from app.models.learning import LrnUserProgressSummary


class PathRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_path_by_id(self, path_id: int) -> PthLearningPath | None:
        return self.db.query(PthLearningPath).filter(PthLearningPath.id == path_id).first()

    def get_path_by_no(self, path_no: str) -> PthLearningPath | None:
        return self.db.query(PthLearningPath).filter(PthLearningPath.path_no == path_no).first()

    def list_user_paths(self, user_id: int) -> list[PthLearningPath]:
        return (
            self.db.query(PthLearningPath)
            .filter(PthLearningPath.user_id == user_id)
            .order_by(PthLearningPath.created_at.desc())
            .all()
        )

    def list_all_paths(
        self,
        *,
        keyword: str | None = None,
        user_id: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[PthLearningPath], int]:
        q = self.db.query(PthLearningPath)
        if user_id is not None:
            q = q.filter(PthLearningPath.user_id == user_id)
        if keyword:
            like = f"%{keyword}%"
            q = q.filter((PthLearningPath.title.like(like)) | (PthLearningPath.goal.like(like)))
        total = q.count()
        items = (
            q.order_by(PthLearningPath.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def list_all_knowledge_points(self) -> list[PthKnowledgePoint]:
        return (
            self.db.query(PthKnowledgePoint)
            .order_by(PthKnowledgePoint.domain, PthKnowledgePoint.difficulty)
            .all()
        )

    def get_knowledge_point_by_id(self, point_id: int) -> PthKnowledgePoint | None:
        return self.db.query(PthKnowledgePoint).filter(PthKnowledgePoint.id == point_id).first()

    def get_knowledge_point_by_code(self, code: str) -> PthKnowledgePoint | None:
        return self.db.query(PthKnowledgePoint).filter(PthKnowledgePoint.point_code == code).first()

    def save_knowledge_point(self, point: PthKnowledgePoint) -> PthKnowledgePoint:
        self.db.add(point)
        self.db.commit()
        self.db.refresh(point)
        return point

    def get_nodes(self, path_id: int) -> list[PthPathNode]:
        return (
            self.db.query(PthPathNode)
            .filter(PthPathNode.path_id == path_id)
            .order_by(PthPathNode.sort_order)
            .all()
        )

    def get_edges(self, path_id: int) -> list[PthPathNodeEdge]:
        return self.db.query(PthPathNodeEdge).filter(PthPathNodeEdge.path_id == path_id).all()

    def get_node_progress(self, user_id: int, path_id: int) -> list[PthNodeProgress]:
        return (
            self.db.query(PthNodeProgress)
            .filter(PthNodeProgress.user_id == user_id, PthNodeProgress.path_id == path_id)
            .all()
        )

    def get_node_by_id(self, node_id: int) -> PthPathNode | None:
        return self.db.query(PthPathNode).filter(PthPathNode.id == node_id).first()

    def get_knowledge_points(self, domain: str) -> list[PthKnowledgePoint]:
        return (
            self.db.query(PthKnowledgePoint)
            .filter(PthKnowledgePoint.domain == domain, PthKnowledgePoint.status == 1)
            .order_by(PthKnowledgePoint.difficulty)
            .all()
        )

    def get_node_resources(self, node_id: int) -> list[PthNodeResource]:
        return (
            self.db.query(PthNodeResource)
            .filter(PthNodeResource.node_id == node_id)
            .order_by(PthNodeResource.sort_order)
            .all()
        )

    def get_nodes_resources(self, node_ids: list[int]) -> list[PthNodeResource]:
        if not node_ids:
            return []
        return (
            self.db.query(PthNodeResource)
            .filter(PthNodeResource.node_id.in_(node_ids))
            .order_by(PthNodeResource.node_id, PthNodeResource.sort_order)
            .all()
        )

    def save_path(self, path: PthLearningPath) -> PthLearningPath:
        self.db.add(path)
        self.db.commit()
        self.db.refresh(path)
        return path

    def add_node(self, node: PthPathNode) -> PthPathNode:
        self.db.add(node)
        self.db.commit()
        self.db.refresh(node)
        return node

    def add_edge(self, edge: PthPathNodeEdge) -> None:
        self.db.add(edge)
        self.db.commit()

    def upsert_node_progress(self, progress: PthNodeProgress) -> PthNodeProgress:
        existing = (
            self.db.query(PthNodeProgress)
            .filter(
                PthNodeProgress.user_id == progress.user_id,
                PthNodeProgress.node_id == progress.node_id,
            )
            .first()
        )
        if existing:
            for field in ("status", "mastery_score", "study_duration_sec", "visit_count", "last_study_at", "completed_at", "first_started_at", "ext_json"):
                val = getattr(progress, field, None)
                if val is not None:
                    setattr(existing, field, val)
            self.db.commit()
            self.db.refresh(existing)
            return existing
        self.db.add(progress)
        self.db.commit()
        self.db.refresh(progress)
        return progress

    def bind_node_resources(self, node_id: int, resource_ids: list[int], role: str) -> None:
        for idx, rid in enumerate(resource_ids):
            exists = (
                self.db.query(PthNodeResource)
                .filter(PthNodeResource.node_id == node_id, PthNodeResource.resource_id == rid)
                .first()
            )
            if not exists:
                self.db.add(
                    PthNodeResource(
                        node_id=node_id,
                        resource_id=rid,
                        resource_role=role,
                        sort_order=idx,
                    )
                )
        self.db.commit()

    def find_matching_resources(
        self, user_id: int, topic: str, type_codes: list[str] | None = None, limit: int = 4
    ) -> list[tuple]:
        """Return (ResResource, type_code, type_name) tuples matching topic."""
        from app.models.resource import ResResource, ResResourceTypeDef

        q = (
            self.db.query(ResResource, ResResourceTypeDef)
            .join(ResResourceTypeDef, ResResource.type_id == ResResourceTypeDef.id)
            .filter(
                ResResource.user_id == user_id,
                ResResource.deleted_at.is_(None),
                ResResource.status.in_([1, 2]),
            )
        )
        if topic:
            q = q.filter(
                (ResResource.topic.like(f"%{topic[:20]}%"))
                | (ResResource.title.like(f"%{topic[:20]}%"))
            )
        if type_codes:
            q = q.filter(ResResourceTypeDef.type_code.in_(type_codes))
        rows = q.order_by(ResResource.created_at.desc()).limit(limit * 3).all()
        seen_types: set[str] = set()
        result: list[tuple] = []
        for res, type_def in rows:
            if type_codes and type_def.type_code not in type_codes:
                continue
            if type_codes and type_def.type_code in seen_types:
                continue
            seen_types.add(type_def.type_code)
            result.append((res, type_def.type_code, type_def.type_name))
            if len(result) >= limit:
                break
        return result

    def upsert_progress_summary(self, user_id: int, path_id: int, total: int, completed: int) -> None:
        summary = (
            self.db.query(LrnUserProgressSummary)
            .filter(
                LrnUserProgressSummary.user_id == user_id,
                LrnUserProgressSummary.path_id == path_id,
            )
            .first()
        )
        rate = round(completed / total, 4) if total else 0
        if summary:
            summary.total_nodes = total
            summary.completed_nodes = completed
            summary.progress_rate = rate
        else:
            self.db.add(
                LrnUserProgressSummary(
                    user_id=user_id,
                    path_id=path_id,
                    total_nodes=total,
                    completed_nodes=completed,
                    progress_rate=rate,
                )
            )
        self.db.commit()

    def create_path_with_no(self, **kwargs) -> PthLearningPath:
        path = PthLearningPath(path_no=str(uuid.uuid4()), **kwargs)
        return self.save_path(path)
