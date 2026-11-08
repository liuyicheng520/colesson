"""Resolve profile dimension metadata — DB ext_json overrides code constants."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.profile_dimensions import CORE_PROFILE_DIMENSIONS, DIMENSION_BY_CODE
from app.repositories.profile_repository import ProfileRepository


@dataclass
class DimensionMeta:
    code: str
    name: str
    description: str
    guide_questions: tuple[str, ...]
    extract_hint: str = ""


def _from_constant(code: str) -> DimensionMeta | None:
    c = DIMENSION_BY_CODE.get(code)
    if not c:
        return None
    return DimensionMeta(
        code=c.code,
        name=c.name,
        description=c.description,
        guide_questions=c.guide_questions,
        extract_hint=c.extract_hint,
    )


def get_dimension_meta(db: Session, code: str) -> DimensionMeta | None:
    repo = ProfileRepository(db)
    db_def = repo.get_dimension_def_by_code(code)
    if db_def:
        ext = db_def.ext_json or {}
        questions = ext.get("guide_questions")
        if questions and isinstance(questions, list) and len(questions) >= 1:
            return DimensionMeta(
                code=db_def.dimension_code,
                name=db_def.dimension_name,
                description=db_def.dimension_desc or "",
                guide_questions=tuple(str(q) for q in questions[:10]),
                extract_hint=str(ext.get("extract_hint") or ""),
            )
        return DimensionMeta(
            code=db_def.dimension_code,
            name=db_def.dimension_name,
            description=db_def.dimension_desc or "",
            guide_questions=_from_constant(code).guide_questions if _from_constant(code) else ("请描述该维度的关键学习情况。",),
            extract_hint=str(ext.get("extract_hint") or ""),
        )
    return _from_constant(code)


def get_core_dimension_codes(db: Session) -> list[str]:
    repo = ProfileRepository(db)
    defs = repo.get_dimension_defs()
    codes = [d.dimension_code for d in defs if d.dimension_code.startswith("D")]
    if codes:
        return sorted(codes, key=lambda c: next((d.sort_order for d in defs if d.dimension_code == c), 99))
    return [d.code for d in CORE_PROFILE_DIMENSIONS]
