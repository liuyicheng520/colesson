"""结构化问卷提交服务 — 本地计算 <100ms，融合写入画像。"""

from decimal import Decimal

from app.core.exceptions import ValidationException
from app.profile_dimensions import CORE_DIMENSION_CODES
from app.profile_questionnaire_data import QUESTIONNAIRE_ITEMS
from app.repositories.profile_repository import ProfileRepository
from app.schemas.profile import ProfileResponse, QuestionnaireSubmitRequest
from app.services.profile_dimension_utils import QUESTIONS_PER_DIMENSION, set_question_progress, get_question_progress, get_dimension_answers, recalc_core_completeness
from app.services.profile_fusion import (
    SOURCE_ACCURACY_WEIGHT,
    append_fusion_history,
    fusion_contribute_dimension,
    list_refinement_dimensions,
)
from app.services.profile_service import ProfileService


class ProfileQuestionnaireService:
    def __init__(self, db) -> None:
        self.db = db
        self.profile_repo = ProfileRepository(db)
        self.profile_service = ProfileService(db)

    def get_items(self) -> list[dict]:
        return [
            {
                "dimension_code": item["dimension_code"],
                "question": item["question"],
                "options": [{"id": o["id"], "label": o["label"]} for o in item["options"]],
            }
            for item in QUESTIONNAIRE_ITEMS
        ]

    def submit(self, user, req: QuestionnaireSubmitRequest) -> ProfileResponse:
        if len(req.answers) != len(QUESTIONNAIRE_ITEMS):
            raise ValidationException("请完成全部 6 道问卷题目")

        option_map: dict[str, dict] = {}
        for item in QUESTIONNAIRE_ITEMS:
            for opt in item["options"]:
                option_map[opt["id"]] = {"dimension_code": item["dimension_code"], "value": opt["value"], "score": opt["score"]}

        profile = self.profile_service.get_or_create_profile(user)
        updated: list[str] = []
        q_progress = get_question_progress(profile.ext_json)
        answers = get_dimension_answers(profile.ext_json)

        for ans in req.answers:
            mapped = option_map.get(ans.option_id)
            if not mapped:
                raise ValidationException(f"无效选项: {ans.option_id}")
            code = mapped["dimension_code"]
            dim_def = self.profile_repo.get_dimension_def_by_code(code)
            if not dim_def:
                continue
            if fusion_contribute_dimension(
                self.profile_repo,
                profile.id,
                dim_def.id,
                code,
                mapped["value"],
                "questionnaire",
                SOURCE_ACCURACY_WEIGHT["questionnaire"],
            ):
                updated.append(code)
            # 问卷仅作基线，不占用对话 3 问进度，便于后续对话深化
            answers[code] = [f"问卷基线: {ans.option_id}"]

        set_question_progress(self.profile_repo, profile.id, q_progress, answers)
        self.db.refresh(profile)
        recalc_core_completeness(self.profile_repo, profile.id)

        append_fusion_history(
            self.profile_repo,
            profile.id,
            {
                "mode": "questionnaire",
                "updated_dimensions": updated,
                "answer_count": len(req.answers),
                "hint": "建议切换至对话引导式深化画像",
                "refinement_priority": list_refinement_dimensions(profile.ext_json),
            },
        )
        profile.profile_version += 1
        self.db.commit()
        return self.profile_service.get_profile_detail(user)
