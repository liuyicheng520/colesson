"""Personalized 3-phase learning path planner based on 6-dimension profile."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.models.path import PthKnowledgePoint
from app.models.sys import SysUser
from app.profile_dimensions import CORE_DIMENSION_CODES
from app.repositories.profile_repository import ProfileRepository

PHASE_DEFS: list[dict[str, str]] = [
    {"phase": "intro", "phase_name": "入门", "description": "夯实基础概念，建立知识框架"},
    {"phase": "intermediate", "phase_name": "进阶", "description": "深入核心方法，强化实践能力"},
    {"phase": "advanced", "phase_name": "提升", "description": "综合应用与拓展，达成学习目标"},
]

EXPECTED_RESOURCE_TYPES = ["document", "question", "mindmap", "code"]


@dataclass
class PlannedNode:
    name: str
    description: str
    phase: str
    phase_name: str
    node_type: str = "learn"
    difficulty: int = 3
    estimated_min: int = 45
    knowledge_point_id: int | None = None
    expected_resource_types: list[str] = field(default_factory=lambda: list(EXPECTED_RESOURCE_TYPES))
    is_weak: bool = False
    is_adaptive: bool = False


@dataclass
class PathPlanResult:
    phases: list[dict[str, Any]]
    nodes: list[PlannedNode]
    profile_context: dict[str, Any]


def _parse_llm_json(raw: str) -> dict | None:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return None
    return None


def build_profile_context(profile_repo: ProfileRepository, profile_id: int, user: SysUser) -> dict[str, Any]:
    defs = {d.dimension_code: d for d in profile_repo.get_dimension_defs()}
    values = profile_repo.get_dimension_values(profile_id)
    dims: dict[str, Any] = {}
    for v in values:
        for code, d in defs.items():
            if d.id == v.dimension_id and code in CORE_DIMENSION_CODES:
                dims[code] = v.dimension_value
                break
    d1 = dims.get("D1") or {}
    d3 = dims.get("D3") or {}
    d5 = dims.get("D5") or {}
    return {
        "major": user.major,
        "grade": user.grade,
        "knowledge_domain": d1.get("domain") or user.major or "general",
        "knowledge_level": d1.get("level", 2),
        "knowledge_gaps": d1.get("gaps") or [],
        "learning_goal": d3.get("goal"),
        "goal_deadline": d3.get("deadline"),
        "goal_priority": d3.get("priority"),
        "weak_points": d5.get("weakPoints") or [],
        "dimensions": dims,
    }


def _fallback_plan(
    kps: list[PthKnowledgePoint],
    profile_ctx: dict[str, Any],
    goal: str,
) -> PathPlanResult:
    level = int(profile_ctx.get("knowledge_level") or 2)
    if not kps:
        kps = []

    intro = [kp for kp in kps if kp.difficulty <= max(1, level)]
    intermediate = [kp for kp in kps if level < kp.difficulty <= level + 2]
    advanced = [kp for kp in kps if kp.difficulty > level + 1]

    if not intro and kps:
        intro = kps[:3]
    if not intermediate and kps:
        intermediate = kps[3:6] if len(kps) > 3 else kps[2:4]
    if not advanced and kps:
        advanced = kps[6:] if len(kps) > 6 else kps[-2:]

    for bucket, default_names in (
        (intro, ["基础概念入门", "核心术语理解"]),
        (intermediate, ["方法原理深入", "典型算法实践"]),
        (advanced, ["综合项目应用", "拓展提升"]),
    ):
        while len(bucket) < 2:
            idx = len(bucket)
            bucket.append(
                type("KP", (), {
                    "id": None,
                    "point_name": default_names[idx] if idx < len(default_names) else f"知识点{idx+1}",
                    "difficulty": 2 + idx,
                    "estimated_min": 45,
                    "description": f"围绕「{goal}」的学习节点",
                })()
            )

    nodes: list[PlannedNode] = []
    phases_out: list[dict[str, Any]] = []
    for phase_def, bucket in zip(PHASE_DEFS, [intro[:3], intermediate[:3], advanced[:3]]):
        phase_nodes: list[PlannedNode] = []
        for kp in bucket[:3]:
            pn = PlannedNode(
                name=kp.point_name,
                description=getattr(kp, "description", None) or f"{phase_def['phase_name']}阶段：{kp.point_name}",
                phase=phase_def["phase"],
                phase_name=phase_def["phase_name"],
                node_type="learn" if phase_def["phase"] != "advanced" else "practice",
                difficulty=int(getattr(kp, "difficulty", 3)),
                estimated_min=int(getattr(kp, "estimated_min", 45)),
                knowledge_point_id=getattr(kp, "id", None),
            )
            phase_nodes.append(pn)
            nodes.append(pn)
        phases_out.append({**phase_def, "nodes": [n.name for n in phase_nodes]})
    return PathPlanResult(phases=phases_out, nodes=nodes, profile_context=profile_ctx)


def parse_llm_plan(raw: str, kps: list[PthKnowledgePoint], profile_ctx: dict, goal: str) -> PathPlanResult:
    data = _parse_llm_json(raw)
    if not data or "phases" not in data:
        return _fallback_plan(kps, profile_ctx, goal)

    kp_by_code = {kp.point_code: kp for kp in kps}
    kp_by_name = {kp.point_name: kp for kp in kps}
    nodes: list[PlannedNode] = []
    phases_out: list[dict[str, Any]] = []

    for phase_def in PHASE_DEFS:
        phase_data = next((p for p in data["phases"] if p.get("phase") == phase_def["phase"]), None)
        if not phase_data:
            continue
        phase_nodes: list[PlannedNode] = []
        for item in phase_data.get("nodes", [])[:4]:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("node_name") or "未命名节点")
            kp = None
            code = item.get("knowledge_point_code")
            if code and code in kp_by_code:
                kp = kp_by_code[code]
            elif name in kp_by_name:
                kp = kp_by_name[name]
            pn = PlannedNode(
                name=name,
                description=str(item.get("description") or f"{phase_def['phase_name']}：{name}"),
                phase=phase_def["phase"],
                phase_name=phase_def["phase_name"],
                node_type=str(item.get("node_type") or "learn"),
                difficulty=int(item.get("difficulty") or (kp.difficulty if kp else 3)),
                estimated_min=int(item.get("estimated_min") or (kp.estimated_min if kp else 45)),
                knowledge_point_id=kp.id if kp else None,
                is_weak=bool(item.get("is_weak")),
                is_adaptive=bool(item.get("is_adaptive") or item.get("node_type") == "remedial"),
            )
            phase_nodes.append(pn)
            nodes.append(pn)
        if phase_nodes:
            phases_out.append({**phase_def, "nodes": [n.name for n in phase_nodes]})

    if len(nodes) < 4:
        return _fallback_plan(kps, profile_ctx, goal)
    return PathPlanResult(phases=phases_out, nodes=nodes, profile_context=profile_ctx)


def build_plan_prompt(
    goal: str,
    domain: str,
    profile_ctx: dict,
    kps: list[PthKnowledgePoint],
    *,
    ignore_profile: bool = False,
    supplement: str | None = None,
    adaptive: bool = False,
) -> list[dict]:
    kp_list = [{"code": kp.point_code, "name": kp.point_name, "difficulty": kp.difficulty} for kp in kps[:12]]
    mode = "通用标准路径（忽略个人画像）" if ignore_profile else "画像定制路径"
    if adaptive:
        mode += " · 自适应重规划"
    system = (
        "你是个性化学习路径规划专家。生成「入门→进阶→提升」三阶段学习路径。\n"
        "返回JSON格式：\n"
        '{"phases":[{"phase":"intro","phase_name":"入门","nodes":[{"name":"节点名","description":"描述",'
        '"node_type":"learn|practice|remedial","difficulty":1-5,"estimated_min":30,'
        '"knowledge_point_code":"ML_001","is_weak":false,"is_adaptive":false}]},'
        '{"phase":"intermediate",...},{"phase":"advanced",...}]}\n'
        "要求：每阶段2-4个节点，共6-10个节点；薄弱相关节点标记 is_weak=true；"
        "自适应新增巩固节点标记 is_adaptive=true 且 node_type=remedial；"
        "优先从知识点列表选取；仅返回JSON。"
    )
    user = (
        f"路径模式: {mode}\n"
        f"学习目标: {goal}\n"
        f"领域: {domain}\n"
        f"补充需求: {supplement or '无'}\n"
    )
    if ignore_profile:
        user += "请按通用课程标准生成标准路径，不要针对个人薄弱点过度定制。\n"
    else:
        user += (
            f"专业: {profile_ctx.get('major')}\n"
            f"知识水平(1-5): {profile_ctx.get('knowledge_level')}\n"
            f"知识缺口: {profile_ctx.get('knowledge_gaps')}\n"
            f"薄弱点: {profile_ctx.get('weak_points')}\n"
            "请围绕薄弱点在入门阶段增加巩固节点。\n"
        )
    if adaptive:
        user += "这是自适应重规划：请根据薄弱点额外插入 1-3 个巩固节点（is_adaptive=true）。\n"
    user += f"知识点库: {json.dumps(kp_list, ensure_ascii=False)}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
