"""
画像多源加权融合层 — 持续测量、持续理解

各采集方式的「准确度权重」（非互斥覆盖，而是加权累积）:
  manual(1.00) > assessment(0.92) > dialogue(0.82) > behavior(0.55) > questionnaire(0.30)

同一维度多次采集时，按权重混合数值型字段，分类型字段取权重最高来源。
融合置信度 = 1 - ∏(1 - w_i)，多源互补提升整体可信度。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from decimal import Decimal

from app.profile_dimensions import CORE_DIMENSION_CODES
from app.repositories.profile_repository import ProfileRepository

# 准确度权重 — 问卷题少且为选择题，权重最低；对话三轮深挖次之；测评对知识维度最准
SOURCE_ACCURACY_WEIGHT: dict[str, float] = {
    "manual": 1.00,
    "assessment": 0.92,
    "dialogue": 0.82,
    "behavior": 0.55,
    "questionnaire": 0.30,
}

SOURCE_PRIORITY: list[str] = ["manual", "assessment", "dialogue", "behavior", "questionnaire"]

# 兼容旧引用
SOURCE_CONFIDENCE = SOURCE_ACCURACY_WEIGHT


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def get_dimension_contributions(ext_json: dict | None) -> dict[str, list[dict[str, Any]]]:
    raw = (ext_json or {}).get("dimension_contributions") or {}
    result: dict[str, list[dict[str, Any]]] = {}
    for code in CORE_DIMENSION_CODES:
        items = raw.get(code)
        result[code] = list(items) if isinstance(items, list) else []
    return result


def _save_contributions(profile_repo: ProfileRepository, profile_id: int, contributions: dict[str, list]) -> None:
    from app.models.profile import UsrProfile

    profile = profile_repo.db.query(UsrProfile).filter(UsrProfile.id == profile_id).first()
    if not profile:
        return
    ext = dict(profile.ext_json or {})
    ext["dimension_contributions"] = contributions
    profile.ext_json = ext
    profile_repo.db.commit()


def get_dimension_sources(ext_json: dict | None) -> dict[str, dict[str, Any]]:
    """各维度融合后的主来源摘要（兼容旧字段）。"""
    contribs = get_dimension_contributions(ext_json)
    result: dict[str, dict[str, Any]] = {}
    for code in CORE_DIMENSION_CODES:
        items = contribs.get(code) or []
        if not items:
            continue
        primary = max(items, key=lambda x: float(x.get("weight", 0)))
        fused_conf = fused_confidence(items)
        result[code] = {
            "source": primary.get("source"),
            "confidence": fused_conf,
            "sources": [{"source": i.get("source"), "weight": i.get("weight")} for i in items],
        }
    return result


def fused_confidence(contributions: list[dict[str, Any]]) -> float:
    """多源独立证据融合置信度: 1 - ∏(1 - w)"""
    if not contributions:
        return 0.0
    product = 1.0
    for c in contributions:
        w = min(max(float(c.get("weight", 0)), 0), 1)
        product *= 1.0 - w
    return round(min(0.99, 1.0 - product), 4)


def _weighted_pick(contributions: list[dict], field: str, default: Any = None) -> Any:
    """分类型字段：取权重最高来源的值。"""
    best = default
    best_w = -1.0
    for c in contributions:
        val = (c.get("value") or {}).get(field)
        w = float(c.get("weight", 0))
        if val is not None and val != "" and w > best_w:
            best = val
            best_w = w
    return best


def _weighted_avg(contributions: list[dict], field: str, default: float = 0.0) -> float:
    total_w = 0.0
    acc = 0.0
    for c in contributions:
        val = (c.get("value") or {}).get(field)
        w = float(c.get("weight", 0))
        if val is None or w <= 0:
            continue
        try:
            acc += float(val) * w
            total_w += w
        except (TypeError, ValueError):
            continue
    return acc / total_w if total_w > 0 else default


def _merge_list_field(contributions: list[dict], field: str) -> list:
    seen: set[str] = set()
    merged: list = []
    for c in sorted(contributions, key=lambda x: -float(x.get("weight", 0))):
        items = (c.get("value") or {}).get(field) or []
        if not isinstance(items, list):
            continue
        for item in items:
            key = str(item)
            if key not in seen:
                seen.add(key)
                merged.append(item)
    return merged


def blend_dimension_value(code: str, contributions: list[dict[str, Any]]) -> dict[str, Any] | None:
    """按维度 schema 加权混合多源贡献值。"""
    if not contributions:
        return None
    if code == "D1":
        gaps = _merge_list_field(contributions, "gaps")
        strong = _merge_list_field(contributions, "strongTopics")
        level = round(_weighted_avg(contributions, "level", 3))
        domain = _weighted_pick(contributions, "domain", "通用")
        theta = _weighted_avg(contributions, "theta", 0) if any((c.get("value") or {}).get("theta") for c in contributions) else None
        result: dict[str, Any] = {"domain": domain, "level": max(1, min(5, int(level))), "gaps": gaps[:8]}
        if strong:
            result["strongTopics"] = strong[:8]
        if theta:
            result["theta"] = round(theta, 3)
        topic_m = {}
        for c in contributions:
            tm = (c.get("value") or {}).get("topicMastery")
            if isinstance(tm, dict):
                topic_m.update(tm)
        if topic_m:
            result["topicMastery"] = topic_m
        return result
    if code == "D2":
        return {"style": _weighted_pick(contributions, "style", "sequential"), "score": round(_weighted_avg(contributions, "score", 0.7), 2)}
    if code == "D3":
        return {
            "goal": _weighted_pick(contributions, "goal", ""),
            "deadline": _weighted_pick(contributions, "deadline"),
            "priority": _weighted_pick(contributions, "priority", "mid"),
        }
    if code == "D4":
        return {
            "courses": _merge_list_field(contributions, "courses"),
            "completedTopics": _merge_list_field(contributions, "completedTopics"),
            "totalHours": int(_weighted_avg(contributions, "totalHours", 0)),
        }
    if code == "D5":
        weak: list[dict] = []
        seen: set[str] = set()
        for c in sorted(contributions, key=lambda x: -float(x.get("weight", 0))):
            for wp in (c.get("value") or {}).get("weakPoints") or []:
                if isinstance(wp, dict) and wp.get("topic") and wp["topic"] not in seen:
                    seen.add(wp["topic"])
                    weak.append(wp)
        return {"weakPoints": weak[:6]}
    if code == "D6":
        pace = _weighted_pick(contributions, "pace", "medium")
        mins = int(_weighted_avg(contributions, "sessionMinutes", 30))
        return {"pace": pace, "sessionMinutes": max(10, mins)}
    # fallback: highest weight wins
    primary = max(contributions, key=lambda x: float(x.get("weight", 0)))
    return dict(primary.get("value") or {})


def fusion_contribute_dimension(
    profile_repo: ProfileRepository,
    profile_id: int,
    dimension_id: int,
    dimension_code: str,
    value: dict[str, Any],
    source_type: str,
    weight: float | None = None,
    source_ref_id: int | None = None,
    *,
    force: bool = False,
) -> bool:
    """
    向维度贡献一条采集记录并重新计算加权融合结果。
    同 source 再次贡献时替换该来源的旧记录（支持测评复测、行为动态刷新）。
    """
    if dimension_code not in CORE_DIMENSION_CODES or not value:
        return False

    w = float(weight if weight is not None else SOURCE_ACCURACY_WEIGHT.get(source_type, 0.5))
    if force:
        w = 1.0

    from app.models.profile import UsrProfile

    profile = profile_repo.db.query(UsrProfile).filter(UsrProfile.id == profile_id).first()
    if not profile:
        return False

    all_contribs = get_dimension_contributions(profile.ext_json)
    items = [c for c in all_contribs.get(dimension_code, []) if c.get("source") != source_type]
    items.append({
        "source": source_type,
        "weight": w,
        "value": value,
        "at": _now_iso(),
        "ref_id": source_ref_id,
    })
    all_contribs[dimension_code] = items
    _save_contributions(profile_repo, profile_id, all_contribs)

    blended = blend_dimension_value(dimension_code, items)
    if not blended:
        return False

    conf = Decimal(str(fused_confidence(items)))
    primary_source = max(items, key=lambda x: float(x.get("weight", 0))).get("source", source_type)
    profile_repo.upsert_dimension_value(profile_id, dimension_id, blended, conf, str(primary_source), source_ref_id)

    # 同步 dimension_sources 摘要
    ext = dict(profile.ext_json or {})
    sources_summary = dict(ext.get("dimension_sources") or {})
    sources_summary[dimension_code] = {
        "source": primary_source,
        "confidence": float(conf),
        "sources": [{"source": i["source"], "weight": i["weight"]} for i in items],
    }
    ext["dimension_sources"] = sources_summary
    profile.ext_json = ext
    profile_repo.db.commit()
    return True


# 兼容旧函数名
def fusion_upsert_dimension(
    profile_repo: ProfileRepository,
    profile_id: int,
    dimension_id: int,
    dimension_code: str,
    value: dict[str, Any],
    source_type: str,
    confidence: Decimal | None = None,
    source_ref_id: int | None = None,
    *,
    force: bool = False,
) -> bool:
    w = float(confidence) if confidence is not None else None
    return fusion_contribute_dimension(
        profile_repo, profile_id, dimension_id, dimension_code, value, source_type, w, source_ref_id, force=force
    )


def append_fusion_history(profile_repo: ProfileRepository, profile_id: int, entry: dict[str, Any]) -> None:
    from app.models.profile import UsrProfile

    profile = profile_repo.db.query(UsrProfile).filter(UsrProfile.id == profile_id).first()
    if not profile:
        return
    ext = dict(profile.ext_json or {})
    history = list(ext.get("fusion_history") or [])
    entry["at"] = _now_iso()
    history.append(entry)
    ext["fusion_history"] = history[-80:]
    profile.ext_json = ext
    profile_repo.db.commit()


def get_refinement_priority(code: str, contributions: list[dict]) -> float:
    """维度待深化优先级：融合置信度越低、对话贡献越少，越优先。"""
    if not contributions:
        return 1.0
    conf = fused_confidence(contributions)
    dialogue_w = sum(float(c.get("weight", 0)) for c in contributions if c.get("source") == "dialogue")
    return (1.0 - conf) * 0.6 + (1.0 - min(dialogue_w, 1.0)) * 0.4


def list_refinement_dimensions(ext_json: dict | None) -> list[str]:
    """返回建议优先用对话/测评深化的维度列表。"""
    contribs = get_dimension_contributions(ext_json)
    scored = [(code, get_refinement_priority(code, contribs.get(code) or [])) for code in CORE_DIMENSION_CODES]
    scored.sort(key=lambda x: -x[1])
    return [code for code, _ in scored]
