"""Profile dimension progress helpers — 6维 × 每维1问 = 6题进度。"""

from decimal import Decimal
from typing import Any

from app.profile_dimensions import (
    CORE_DIMENSION_CODES,
    CORE_DIMENSION_COUNT,
    DIMENSION_BY_CODE,
    QUESTIONS_PER_DIMENSION,
    TOTAL_PROFILE_QUESTIONS,
)
from app.repositories.profile_repository import ProfileRepository
from app.services.profile_fusion import fused_confidence, get_dimension_contributions

# 视为「已构建画像」的来源类型（不含注册预填 import）
# 融合优先级见 profile_fusion.SOURCE_PRIORITY
BUILT_SOURCE_TYPES = frozenset({"dialogue", "manual", "questionnaire", "assessment", "behavior"})


def _is_dimension_filled(value: dict | None) -> bool:
    if not value or not isinstance(value, dict):
        return False
    return any(v is not None and v != "" and v != [] for v in value.values())


def get_question_progress(profile_ext: dict | None) -> dict[str, int]:
    """从 profile.ext_json 读取各维度已答问题数 (0~QUESTIONS_PER_DIMENSION)。"""
    raw = (profile_ext or {}).get("question_progress") or {}
    progress: dict[str, int] = {}
    for code in CORE_DIMENSION_CODES:
        try:
            progress[code] = min(max(int(raw.get(code, 0)), 0), QUESTIONS_PER_DIMENSION)
        except (TypeError, ValueError):
            progress[code] = 0
    return progress


def get_dimension_answers(profile_ext: dict | None) -> dict[str, list[str]]:
    """从 profile.ext_json 读取各维度累积回答。"""
    raw = (profile_ext or {}).get("dimension_answers") or {}
    answers: dict[str, list[str]] = {}
    for code in CORE_DIMENSION_CODES:
        items = raw.get(code) or []
        answers[code] = [str(x) for x in items if x][:QUESTIONS_PER_DIMENSION]
    return answers


def set_question_progress(profile_repo: ProfileRepository, profile_id: int, progress: dict[str, int], answers: dict[str, list[str]]) -> None:
    from app.models.profile import UsrProfile

    profile = profile_repo.db.query(UsrProfile).filter(UsrProfile.id == profile_id).first()
    if not profile:
        return
    ext = dict(profile.ext_json or {})
    ext["question_progress"] = {code: min(max(progress.get(code, 0), 0), QUESTIONS_PER_DIMENSION) for code in CORE_DIMENSION_CODES}
    ext["dimension_answers"] = {code: (answers.get(code) or [])[:QUESTIONS_PER_DIMENSION] for code in CORE_DIMENSION_CODES}
    profile.ext_json = ext
    profile_repo.db.commit()


def completed_question_count(progress: dict[str, int]) -> int:
    return sum(min(progress.get(code, 0), QUESTIONS_PER_DIMENSION) for code in CORE_DIMENSION_CODES)


def is_dialogue_flow_complete(progress: dict[str, int]) -> bool:
    """对话式 6 维 × 每维 1 问是否全部完成（与融合画像是否丰富无关）。"""
    return completed_question_count(progress) >= TOTAL_PROFILE_QUESTIONS


def recalc_core_completeness(profile_repo: ProfileRepository, profile_id: int) -> tuple[Decimal, list[str]]:
    defs = {d.dimension_code: d for d in profile_repo.get_dimension_defs()}
    values = profile_repo.get_dimension_values(profile_id)
    value_by_code: dict = {}
    for v in values:
        for code, d in defs.items():
            if d.id == v.dimension_id:
                value_by_code[code] = v
                break

    from app.models.profile import UsrProfile

    profile = profile_repo.db.query(UsrProfile).filter(UsrProfile.id == profile_id).first()
    q_progress = get_question_progress(profile.ext_json if profile else None)

    # 维度完成：融合置信度达标，或该维对话问已完成
    FUSION_COMPLETE_THRESHOLD = 0.55
    DIALOGUE_COMPLETE_THRESHOLD = 0.72

    completed: list[str] = []
    for code in CORE_DIMENSION_CODES:
        val = value_by_code.get(code)
        contribs = get_dimension_contributions(profile.ext_json if profile else None).get(code) or []
        fconf = fused_confidence(contribs) if contribs else (float(val.confidence) if val else 0.0)
        q_done = q_progress.get(code, 0) >= QUESTIONS_PER_DIMENSION
        filled = val and val.source_type in BUILT_SOURCE_TYPES and _is_dimension_filled(val.dimension_value)
        has_dialogue = any(c.get("source") == "dialogue" for c in contribs)
        if filled and (q_done or fconf >= FUSION_COMPLETE_THRESHOLD or (has_dialogue and fconf >= DIALOGUE_COMPLETE_THRESHOLD)):
            completed.append(code)

    answered = completed_question_count(q_progress)
    # 与前端「x/6 问 / 已完成维度」进度对齐；融合质量体现在雷达轴与置信度，不掺进总百分比
    dialogue_ratio = answered / TOTAL_PROFILE_QUESTIONS if TOTAL_PROFILE_QUESTIONS else 0.0
    dim_ratio = len(completed) / CORE_DIMENSION_COUNT if CORE_DIMENSION_COUNT else 0.0
    completeness = Decimal(str(round(min(1.0, max(dialogue_ratio, dim_ratio)), 4)))

    confidences = [value_by_code[c].confidence for c in completed if c in value_by_code]
    avg_conf = sum(confidences) / len(confidences) if confidences else Decimal("0")

    if profile:
        profile.completeness = completeness
        profile.avg_confidence = avg_conf
        if "D3" in value_by_code:
            goal = value_by_code["D3"].dimension_value.get("goal")
            if goal:
                profile.learning_goal = str(goal)[:512]
        profile_repo.db.commit()

    return completeness, completed


def get_next_dimension_code(completed: list[str]) -> str | None:
    for code in CORE_DIMENSION_CODES:
        if code not in completed:
            return code
    return None


def get_active_question_index(progress: dict[str, int], completed: list[str]) -> tuple[str | None, int]:
    """返回当前维度编码与下一题序号 (1~QUESTIONS_PER_DIMENSION)。优先未完成对话进度的维度。"""
    for code in CORE_DIMENSION_CODES:
        if progress.get(code, 0) < QUESTIONS_PER_DIMENSION:
            answered = progress.get(code, 0)
            return code, min(answered + 1, QUESTIONS_PER_DIMENSION)
    return None, QUESTIONS_PER_DIMENSION


def is_profile_built(profile_repo: ProfileRepository, profile_id: int, profile_status: int) -> bool:
    """是否已通过对话/手动构建过画像（新用户应返回 False）。"""
    if profile_status == 1:
        return True
    values = profile_repo.get_dimension_values(profile_id)
    return any(v.source_type in BUILT_SOURCE_TYPES and _is_dimension_filled(v.dimension_value) for v in values)


def build_dimension_progress(profile_repo: ProfileRepository, profile_id: int) -> list[dict]:
    defs = {d.dimension_code: d for d in profile_repo.get_dimension_defs()}
    values = profile_repo.get_dimension_values(profile_id)
    value_by_dim_id = {v.dimension_id: v for v in values}

    from app.models.profile import UsrProfile

    profile = profile_repo.db.query(UsrProfile).filter(UsrProfile.id == profile_id).first()
    q_progress = get_question_progress(profile.ext_json if profile else None)
    all_contribs = get_dimension_contributions(profile.ext_json if profile else None)
    _, completed = recalc_core_completeness(profile_repo, profile_id)
    completed_set = set(completed)

    # 优先深化：融合置信度最低的维度
    from app.services.profile_fusion import list_refinement_dimensions
    refine_order = list_refinement_dimensions(profile.ext_json if profile else None)
    next_code = None
    for code in refine_order:
        if q_progress.get(code, 0) < QUESTIONS_PER_DIMENSION:
            next_code = code
            break
    if not next_code:
        next_code = get_next_dimension_code(completed)

    progress = []
    for code in CORE_DIMENSION_CODES:
        dim_def = defs.get(code)
        meta = DIMENSION_BY_CODE.get(code)
        val = value_by_dim_id.get(dim_def.id) if dim_def else None
        q_answered = q_progress.get(code, 0)
        contribs = all_contribs.get(code) or []
        fconf = fused_confidence(contribs) if contribs else (float(val.confidence) if val else 0.0)
        filled = code in completed_set
        if code == next_code and not filled:
            status = "active"
        elif filled:
            status = "completed"
        elif contribs:
            status = "active"
        else:
            status = "pending"
        source_summary = [{"source": c.get("source"), "weight": c.get("weight")} for c in contribs]
        progress.append(
            {
                "dimension_code": code,
                "dimension_name": meta.name if meta else (dim_def.dimension_name if dim_def else code),
                "description": meta.description if meta else "",
                "status": status,
                "confidence": fconf,
                "fusion_confidence": fconf,
                "source_contributions": source_summary,
                "dimension_value": val.dimension_value if val and val.source_type in BUILT_SOURCE_TYPES else None,
                "display_score": dimension_display_score(code, val.dimension_value if val else None, fconf),
                "updated_at": val.updated_at.isoformat() if val and val.updated_at else None,
                "questions_answered": q_answered,
                "questions_total": QUESTIONS_PER_DIMENSION,
            }
        )
    return progress


def dimension_display_score(code: str, value: dict | None, confidence: float) -> float:
    if not value:
        return 0.0
    if code == "D1":
        level = value.get("level")
        if isinstance(level, (int, float)):
            return min(max(float(level) / 5.0, 0), 1)
    if code == "D2":
        score = value.get("score")
        if isinstance(score, (int, float)):
            return min(max(float(score), 0), 1)
        return 0.75 if value.get("style") else 0.0
    if code == "D3":
        return 1.0 if value.get("goal") else 0.0
    if code == "D4":
        courses = value.get("courses") or value.get("completedTopics") or []
        return min(len(courses) / 3.0, 1.0) if courses else 0.0
    if code == "D5":
        weak = value.get("weakPoints") or []
        return min(len(weak) / 3.0, 1.0) if weak else 0.0
    if code == "D6":
        return 0.8 if value.get("pace") or value.get("sessionMinutes") else 0.0
    return confidence


def merge_dimension_answers(existing: dict[str, list[str]], code: str, answer: str) -> dict[str, list[str]]:
    merged = {k: list(v) for k, v in existing.items()}
    items = list(merged.get(code) or [])
    items.append(answer)
    merged[code] = items[:QUESTIONS_PER_DIMENSION]
    return merged
