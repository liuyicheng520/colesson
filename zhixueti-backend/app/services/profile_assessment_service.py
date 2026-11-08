"""自适应测评服务 — 接收前端 IRT 计算结果，生成知识基础精准画像。"""

import math
from decimal import Decimal

from app.core.exceptions import ValidationException
from app.profile_assessment_bank import ASSESSMENT_DEFAULT_DIMENSIONS, ASSESSMENT_QUESTIONS
from app.profile_dimensions import CORE_DIMENSION_CODES
from app.repositories.profile_repository import ProfileRepository
from app.schemas.profile import AssessmentSubmitRequest, ProfileResponse
from app.services.profile_dimension_utils import QUESTIONS_PER_DIMENSION, get_dimension_answers, get_question_progress, recalc_core_completeness, set_question_progress
from app.services.profile_fusion import SOURCE_ACCURACY_WEIGHT, append_fusion_history, fusion_contribute_dimension
from app.services.profile_service import ProfileService

QUESTION_BY_ID = {q["id"]: q for q in ASSESSMENT_QUESTIONS}


def theta_to_level(theta: float) -> int:
    """能力值 θ 映射到 1~5 级知识水平。"""
    if theta < -1.0:
        return 1
    if theta < -0.3:
        return 2
    if theta < 0.5:
        return 3
    if theta < 1.2:
        return 4
    return 5


def build_knowledge_profile(theta: float, topic_stats: dict[str, dict]) -> dict:
    """根据 θ 与知识点统计生成 D1 画像。"""
    level = theta_to_level(theta)
    weak_topics = [t for t, s in topic_stats.items() if s.get("accuracy", 1) < 0.5]
    strong_topics = [t for t, s in topic_stats.items() if s.get("accuracy", 0) >= 0.8]
    gaps = weak_topics[:5] if weak_topics else (["进阶专题"] if level < 4 else [])
    return {
        "domain": "计算机基础",
        "level": level,
        "gaps": gaps,
        "theta": round(theta, 3),
        "strongTopics": strong_topics[:5],
        "topicMastery": {k: round(v.get("accuracy", 0) * 100, 1) for k, v in topic_stats.items()},
    }


class ProfileAssessmentService:
    def __init__(self, db) -> None:
        self.db = db
        self.profile_repo = ProfileRepository(db)
        self.profile_service = ProfileService(db)

    def get_bank(self) -> list[dict]:
        """返回题库（不含答案），供前端自适应选题。"""
        return [
            {
                "id": q["id"],
                "topic": q["topic"],
                "stem": q["stem"],
                "options": q["options"],
                "difficulty": q["difficulty"],
                "discrimination": q["discrimination"],
            }
            for q in ASSESSMENT_QUESTIONS
        ]

    def submit(self, user, req: AssessmentSubmitRequest) -> ProfileResponse:
        if not req.answers:
            raise ValidationException("测评答案不能为空")

        topic_stats: dict[str, dict] = {}
        for ans in req.answers:
            q = QUESTION_BY_ID.get(ans.question_id)
            if not q:
                continue
            topic = q["topic"]
            if topic not in topic_stats:
                topic_stats[topic] = {"correct": 0, "total": 0}
            topic_stats[topic]["total"] += 1
            if ans.selected_index == q["answer"]:
                topic_stats[topic]["correct"] += 1

        for t, s in topic_stats.items():
            s["accuracy"] = s["correct"] / s["total"] if s["total"] else 0

        theta = req.theta if req.theta is not None else self._estimate_theta(req.answers)
        d1_value = build_knowledge_profile(theta, topic_stats)

        profile = self.profile_service.get_or_create_profile(user)
        updated: list[str] = []

        dim_def = self.profile_repo.get_dimension_def_by_code("D1")
        if dim_def and fusion_contribute_dimension(
            self.profile_repo,
            profile.id,
            dim_def.id,
            "D1",
            d1_value,
            "assessment",
            SOURCE_ACCURACY_WEIGHT["assessment"],
        ):
            updated.append("D1")

        q_progress = get_question_progress(profile.ext_json)
        answers = get_dimension_answers(profile.ext_json)
        q_progress["D1"] = max(q_progress.get("D1", 0), QUESTIONS_PER_DIMENSION)
        answers["D1"] = [f"自适应测评 θ={theta:.2f}, 答题{len(req.answers)}题"]

        # D2~D6 仅极低权重占位，不覆盖问卷/对话成果
        ASSESSMENT_SUPPLEMENT_WEIGHT = 0.12
        for code in CORE_DIMENSION_CODES:
            if code == "D1":
                continue
            default_val = ASSESSMENT_DEFAULT_DIMENSIONS.get(code)
            if not default_val:
                continue
            ddef = self.profile_repo.get_dimension_def_by_code(code)
            if not ddef:
                continue
            fusion_contribute_dimension(
                self.profile_repo,
                profile.id,
                ddef.id,
                code,
                default_val,
                "assessment",
                ASSESSMENT_SUPPLEMENT_WEIGHT,
            )

        set_question_progress(self.profile_repo, profile.id, q_progress, answers)
        self.db.refresh(profile)
        recalc_core_completeness(self.profile_repo, profile.id)

        append_fusion_history(
            self.profile_repo,
            profile.id,
            {
                "mode": "assessment",
                "theta": theta,
                "question_count": len(req.answers),
                "updated_dimensions": updated,
            },
        )
        profile.profile_version += 1
        self.db.commit()
        return self.profile_service.get_profile_detail(user)

    def _estimate_theta(self, answers) -> float:
        """服务端兜底：简化 MLE 能力估计。"""
        theta = 0.0
        for ans in answers:
            q = QUESTION_BY_ID.get(ans.question_id)
            if not q:
                continue
            a, b = q["discrimination"], q["difficulty"]
            correct = 1.0 if ans.selected_index == q["answer"] else 0.0
            p = 1.0 / (1.0 + math.exp(-a * (theta - b)))
            theta += a * (correct - p)
        return max(-2.5, min(2.5, theta))
