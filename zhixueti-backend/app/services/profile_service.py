"""User profile service — 6-dimension × 1-question guided dialogue."""

import asyncio
import json
import logging
import re
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundException, ValidationException
from app.llm.gateway import LLMGateway
from app.models.profile import UsrProfile, UsrProfileDialogueMessage, UsrProfileDialogueSession, UsrProfileEvolutionLog
from app.models.sys import SysUser
from app.profile_dimensions import (
    CORE_DIMENSION_CODES,
    CORE_DIMENSION_COUNT,
    DIMENSION_BY_CODE,
    QUESTIONS_PER_DIMENSION,
    TOTAL_PROFILE_QUESTIONS,
)
from app.repositories.agent_repository import AgentRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.profile_dimension_meta import get_dimension_meta
from app.security.context import SecurityContext

logger = logging.getLogger(__name__)
from app.schemas.profile import (
    DialogueHistoryMessage,
    DialogueMessageRequest,
    DialogueMessageResponse,
    DialogueStartResponse,
    DimensionProgressItem,
    DimensionValueResponse,
    ProfileDimensionUpdateRequest,
    ProfileResponse,
)
from app.services.profile_fusion import SOURCE_ACCURACY_WEIGHT, fusion_contribute_dimension, get_dimension_contributions, list_refinement_dimensions
from app.services.profile_dimension_utils import (
    BUILT_SOURCE_TYPES,
    build_dimension_progress,
    completed_question_count,
    dimension_display_score,
    get_active_question_index,
    get_dimension_answers,
    get_next_dimension_code,
    get_question_progress,
    is_dialogue_flow_complete,
    is_profile_built,
    merge_dimension_answers,
    recalc_core_completeness,
    set_question_progress,
)

# 画像对话为受控教育场景，用户以陈述句回答，不应走通用「提问相关性」拦截
_PROFILE_LLM_CTX = SecurityContext(
    target_type="profile_dialogue",
    allow_off_topic=True,
    require_citation=False,
    source_module="profile",
)


class ProfileService:
    EXTRACT_SYSTEM = (
        "你是画像特征提取引擎。根据同一维度下多轮用户回答，综合提取6维画像数据，仅返回JSON对象。"
        "键必须是 D1~D6 的子集，不可编造用户未提及的内容。\n"
        "D1知识基础: {domain, level:1-5, gaps:[]}\n"
        "D2认知风格: {style:visual|verbal|sequential|global, score:0-1}\n"
        "D3学习目标: {goal, deadline, priority:high|mid|low}\n"
        "D4学习历史: {courses:[], completedTopics:[], totalHours}\n"
        "D5易错点: {weakPoints:[{topic, errorType, frequency}]}\n"
        "D6学习节奏: {pace:fast|medium|slow, sessionMinutes}\n"
        "只返回JSON，无其他文字。"
    )

    SYNTHESIS_SYSTEM = (
        "你是学习画像分析师。根据用户在某一维度下的多轮回答，综合提炼该维度的结构化画像标签。"
        "必须忠实于用户原话，不可编造。只返回该维度对应的 JSON 对象（单个键值对，键为维度编码）。"
    )

    def __init__(self, db: Session) -> None:
        self.db = db
        self.profile_repo = ProfileRepository(db)
        self.agent_repo = AgentRepository(db)
        self.llm = LLMGateway(db)
        self.settings = get_settings()

    def _assert_profile_owner(self, profile: UsrProfile | None, user: SysUser) -> UsrProfile:
        if not profile or profile.user_id != user.id:
            raise NotFoundException(ErrorCode.PROFILE_NOT_FOUND, "画像不存在或无权访问")
        return profile

    def get_or_create_profile(self, user: SysUser) -> UsrProfile:
        profile = self.profile_repo.get_by_user_id(user.id)
        if profile:
            return profile
        profile = UsrProfile(user_id=user.id, status=0)
        return self.profile_repo.save_profile(profile)

    def get_profile_detail(self, user: SysUser) -> ProfileResponse:
        profile = self.get_or_create_profile(user)
        # 强制校验：画像必须属于当前登录用户
        self._assert_profile_owner(profile, user)

        built = is_profile_built(self.profile_repo, profile.id, profile.status)
        defs = {d.id: d for d in self.profile_repo.get_dimension_defs()}
        values = self.profile_repo.get_dimension_values(profile.id)
        dimensions = []
        if built:
            for v in values:
                if v.dimension_id not in defs:
                    continue
                d = defs[v.dimension_id]
                if d.dimension_code not in CORE_DIMENSION_CODES:
                    continue
                if v.source_type not in BUILT_SOURCE_TYPES:
                    continue
                dimensions.append(
                    DimensionValueResponse(
                        dimension_code=d.dimension_code,
                        dimension_name=d.dimension_name,
                        dimension_value=v.dimension_value,
                        confidence=v.confidence,
                        source_type=v.source_type,
                        updated_at=v.updated_at,
                        display_score=dimension_display_score(d.dimension_code, v.dimension_value, float(v.confidence)),
                    )
                )

        recalc_core_completeness(self.profile_repo, profile.id)
        self.db.refresh(profile)
        progress = build_dimension_progress(self.profile_repo, profile.id)
        q_progress = get_question_progress(profile.ext_json)
        answered = completed_question_count(q_progress)
        _, completed_dims = recalc_core_completeness(self.profile_repo, profile.id)

        return ProfileResponse(
            id=profile.id,
            user_id=profile.user_id,
            profile_version=profile.profile_version,
            completeness=profile.completeness if built or answered > 0 else Decimal("0"),
            avg_confidence=profile.avg_confidence if built else Decimal("0"),
            learning_goal=profile.learning_goal if built else None,
            status=profile.status,
            confirmed_at=profile.confirmed_at,
            dimensions=dimensions,
            dimension_progress=[DimensionProgressItem.model_validate(p) for p in progress],
            core_dimension_count=CORE_DIMENSION_COUNT,
            completed_dimension_count=len(completed_dims),
            total_question_count=TOTAL_PROFILE_QUESTIONS,
            completed_question_count=answered,
            is_profile_built=built or answered > 0,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )

    def update_dimension(self, user: SysUser, req: ProfileDimensionUpdateRequest) -> ProfileResponse:
        if req.dimension_code not in CORE_DIMENSION_CODES:
            raise ValidationException(f"仅支持核心6维: {', '.join(CORE_DIMENSION_CODES)}")
        profile = self.get_or_create_profile(user)
        self._assert_profile_owner(profile, user)
        dim_def = self.profile_repo.get_dimension_def_by_code(req.dimension_code)
        if not dim_def:
            raise ValidationException(f"未知维度: {req.dimension_code}")
        old_values = self.profile_repo.get_dimension_values(profile.id)
        old = next((v for v in old_values if v.dimension_id == dim_def.id), None)
        fusion_contribute_dimension(
            self.profile_repo,
            profile.id,
            dim_def.id,
            req.dimension_code,
            req.dimension_value,
            "manual",
            force=True,
        )
        profile.profile_version += 1
        self.db.commit()
        self.profile_repo.add_evolution_log(
            UsrProfileEvolutionLog(
                profile_id=profile.id,
                dimension_id=dim_def.id,
                old_version=profile.profile_version - 1,
                new_version=profile.profile_version,
                old_value=old.dimension_value if old else None,
                new_value=req.dimension_value,
                trigger_type=req.source_type,
                change_reason="manual update",
            )
        )
        # 手动编辑视为该维度 3 问已完成
        q_progress = get_question_progress(profile.ext_json)
        answers = get_dimension_answers(profile.ext_json)
        q_progress[req.dimension_code] = QUESTIONS_PER_DIMENSION
        set_question_progress(self.profile_repo, profile.id, q_progress, answers)
        recalc_core_completeness(self.profile_repo, profile.id)
        return self.get_profile_detail(user)

    def _looks_like_profile_json(self, text: str) -> bool:
        """检测误将画像 JSON 当作对话回复展示给用户。"""
        t = text.strip()
        if not t.startswith("{"):
            return False
        try:
            data = json.loads(t)
        except json.JSONDecodeError:
            return bool(re.search(r'"D[1-6]"\s*:', t))
        if not isinstance(data, dict):
            return False
        return any(k.startswith("D") and isinstance(v, dict) for k, v in data.items())

    def _spoken_question(self, code: str, *, salt: str = "") -> str:
        alts = {
            "D1": (
                "你有没有学过数据结构，或者别的专业课？学到哪一步了，哪一块还不太会？",
                "最近哪一门课或者哪个知识点让你觉得最头疼？",
                "要是用一句话说，你现在最熟的是什么、最虚的是什么？",
            ),
            "D2": (
                "你学新东西时，更想先看图、看例子，还是自己上手试？",
                "你更吃「先给大框架」还是「一步一步带着做」这种讲法？",
                "回想上次学得比较顺的一次，那次你主要是看的、听的，还是自己练的？",
            ),
            "D3": (
                "你接下来最想搞懂的是什么？大概想在多久之内学会？",
                "如果这周只能抓一件事，你会先抓哪一件？",
                "你学这个，是为了考试、项目，还是纯兴趣？",
            ),
            "D4": (
                "跟这个有关的课，你上过哪些？自己额外学过吗？",
                "你以前为这个主题大概花过多少时间？",
                "有没有哪本书、哪门网课、哪次作业让你印象特别深？",
            ),
            "D5": (
                "哪一类题你老是错？想多练几道，还是先把原理听明白？",
                "你一碰到哪种题就容易懵？",
                "错的时候，你更常卡在「不会下手」还是「算到一半乱了」？",
            ),
            "D6": (
                "你一次大概能坐住学多久？一周里通常什么时候学？",
                "你更喜欢短时间多几次，还是一口气学很长？",
                "晚上学、周末学，还是碎片时间学，哪种对你更现实？",
            ),
        }
        options = alts.get(code) or (
            DIMENSION_BY_CODE[code].spoken_question
            if code in DIMENSION_BY_CODE and DIMENSION_BY_CODE[code].spoken_question
            else "你最近在学什么？哪一块还不太熟？",
        )
        if isinstance(options, str):
            return options
        idx = abs(hash((code, salt or ""))) % len(options)
        return options[idx]

    @staticmethod
    def _user_turn_kind(user_text: str) -> str:
        compact = re.sub(r"\s+", "", user_text or "")
        bare = re.sub(r"[！!。.~～,，呀啊哦呢吧吗？?]", "", compact).lower()
        if not compact:
            return "empty"
        if bare in {"你好", "您好", "嗨", "哈喽", "hi", "hello", "在吗", "早", "晚上好", "你好呀", "嗨呀"}:
            return "greeting"
        if bare in {"你是啥", "你是谁", "你叫啥", "你叫什么", "你是什么"} or compact.startswith(("你是", "你叫")):
            return "identity"
        if any(k in compact for k in ("别说了", "不要说了", "闭嘴", "停", "停止", "不聊了", "结束")):
            return "stop"
        if any(k in compact for k in ("不想回答", "不想说", "不告诉你", "不告诉", "保密", "无可奉告")):
            return "refuse"
        if any(k in compact for k in ("聊一会儿", "聊会", "闲聊", "随便聊聊", "陪我聊", "说点别的")):
            return "chat"
        if "不是学生" in compact:
            return "not_student"
        if any(k in compact for k in ("不知道", "不清楚", "随便", "忘了", "不记得")):
            return "unsure"
        if compact.endswith(("？", "?")) or re.match(
            r"^(什么|为什么|为啥|怎么|如何|能不能|请问|帮我)", compact
        ):
            return "question"
        return "talk"

    def _human_turn(self, user_text: str, code: str) -> str:
        """模型失败时的兜底：按用户意图接话，拒绝时不强塞同一句采集题。"""
        kind = self._user_turn_kind(user_text)
        q = self._spoken_question(code, salt=user_text or "")
        soft = {
            "D1": "那先不急。你愿不愿意随口说一个最近接触过的知识点？",
            "D2": "那换个轻松的：你平时刷短视频学东西，还是更爱自己翻文档？",
            "D3": "没事。你要是愿意，就随便说一个「最近想弄明白的小事」。",
            "D4": "行。那有没有哪次作业或小项目你还记得一点？",
            "D5": "好。那有没有哪道题让你印象很深，哪怕只记得个大概？",
            "D6": "可以。那你一般是晚上有空，还是周末才有整块时间？",
        }.get(code, "那你想聊点什么都行，我听着。")

        if kind == "empty":
            return f"你好呀。我在这儿陪你聊学习，你怎么说都行。\n\n{q}"
        if kind == "greeting":
            return f"你好呀。我在呢，想先闲聊两句也行，想直接说学习也行。\n\n{q}"
        if kind == "identity":
            return f"我是陪你聊学习的伙伴。你怎么称呼我都行，主要想听听你平时怎么学。\n\n{q}"
        if kind == "not_student":
            return f"没关系，不一定非要是学生。我们按你平时怎么学、怎么记来聊就行。\n\n{soft}"
        if kind == "stop":
            return "好，我先停。你想歇会儿就歇，想继续的时候叫我就行。"
        if kind == "refuse":
            return f"可以，不想说就不说，我不追着问。\n\n{soft}"
        if kind == "chat":
            return "行啊，那我们先随便聊。你最近有啥开心的、烦的，或者想吐槽的？"
        if kind == "unsure":
            return f"没关系，不确定就不确定。想到多少说多少，一个词也行。\n\n{soft}"
        if kind == "question":
            return (
                f"你这个问题我接住了。我按大白话说：学习这件事没有标准答案，"
                f"你怎么感受怎么讲都行。\n\n那我反问你一句——{q}"
            )
        # talk: 对具体内容做一点变化，避免永远同一句
        seed = abs(hash(user_text)) % 3
        leads = (
            "收到。你这句我记住了。",
            "嗯，我懂你的意思。",
            "好，我跟着你的节奏。",
        )
        return f"{leads[seed]}\n\n{q}"

    @staticmethod
    def _looks_robotic(text: str) -> bool:
        return bool(
            re.search(
                r"问题指引|不会计入|有效画像依据|这一维度我记下了|请继续聊聊|请继续告诉我|"
                r"第\s*\d+\s*/\s*\d+\s*维|维\s*[·•]\s*|吸收方式|点名引用|"
                r"Hello 智学体|Hello EduNexus|示例代码|```python|def hello\(|"
                r"你刚才说的|我听到了|先把这一句回应完|有用就顺着追问|"
                r"嗯，我在听。你接着说就行",
                text or "",
            )
        )

    def _fallback_guide_reply(
        self,
        target_code: str,
        q_progress: dict[str, int],
        *,
        transition: bool = False,
        next_code: str | None = None,
        user_text: str = "",
    ) -> str:
        """模型失败或说出套话时，改成先接话、再提问。"""
        _ = q_progress
        code = next_code if transition and next_code else target_code
        return self._human_turn(user_text, code)

    def _sanitize_assistant_message(
        self,
        msg: str,
        *,
        target_code: str,
        q_progress: dict[str, int],
        transition: bool = False,
        next_code: str | None = None,
        user_text: str = "",
    ) -> str:
        from app.llm.stream_markers import strip_stream_markers

        msg = strip_stream_markers(msg or "")
        ask_code = next_code if transition and next_code else target_code
        if self._looks_like_profile_json(msg) or self._looks_robotic(msg):
            return self._fallback_guide_reply(
                target_code,
                q_progress,
                transition=transition,
                next_code=next_code,
                user_text=user_text,
            )
        if "请继续告诉我你的学习目标和基础情况" in msg:
            return self._fallback_guide_reply(
                target_code,
                q_progress,
                transition=transition,
                next_code=next_code,
                user_text=user_text,
            )
        text = msg.strip()
        if text and "？" not in text and "?" not in text:
            if re.search(r"先停|不想说|不想答|随便聊|想歇|叫我就行", text):
                return text
            return f"{text}\n\n{self._spoken_question(ask_code, salt=user_text)}"
        return msg

    async def _stream_llm_text(
        self,
        messages: list[dict[str, str]],
        *,
        user_id: int,
        task_id: int | None,
    ):
        from app.llm.stream_markers import peel_stream_chunk

        async for chunk in self.llm.stream_chat(
            messages,
            user_id=user_id,
            task_id=task_id,
            context=_PROFILE_LLM_CTX,
        ):
            if not chunk:
                continue
            kind, text = peel_stream_chunk(chunk)
            # 画像对话不展示 reasoning，只推正文
            if kind == "think" or not text:
                continue
            yield text

    _FILLER_ANSWERS = {
        "1", "2", "3", "4", "5",
        "嗯", "哦", "啊", "呃", "ok", "yes", "no",
        "好", "好的", "行", "可以", "不知道", "不清楚",
        "随便", "无", "忘了", "不记得",
        "你好", "您好", "嗨", "哈喽", "在吗", "hi", "hello", "你好呀", "嗨呀",
        "你是啥", "你是谁", "你叫啥", "你叫什么", "你是什么",
    }

    @staticmethod
    def _counts_toward_profile(content: str) -> bool:
        """寒暄、纯拒答、向助手提问不计入进度；其余任何长度都算学生在回答。"""
        compact = re.sub(r"\s+", "", content or "").strip()
        if not compact:
            return False
        bare = re.sub(r"[！!。.~～,，呀啊哦呢吧吗？?]", "", compact).lower()
        if compact.lower() in ProfileService._FILLER_ANSWERS or bare in ProfileService._FILLER_ANSWERS:
            return False
        if ProfileService._user_turn_kind(content) in {
            "greeting", "identity", "stop", "refuse", "chat", "unsure", "question", "empty",
        }:
            return False
        if compact.endswith(("？", "?")):
            return False
        if re.match(
            r"^(什么|为什么|为啥|怎么|如何|能不能|请问|帮我|你是|你叫|你谁)",
            compact,
        ):
            return False
        return True

    @staticmethod
    def _is_substantive_profile_answer(content: str) -> bool:
        return ProfileService._counts_toward_profile(content)

    def _parse_extracted(self, raw: str) -> dict:
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        return {}

    async def _synthesize_dimension(self, user: SysUser, code: str, answers: list[str], task_id: int | None) -> dict:
        meta = DIMENSION_BY_CODE.get(code)
        if not meta or not answers:
            return {}
        joined = "\n".join(f"第{i + 1}轮回答：{a}" for i, a in enumerate(answers))
        result = await self.llm.chat(
            [
                {"role": "system", "content": self.SYNTHESIS_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"维度: {code} {meta.name}\n"
                        f"提取提示: {meta.extract_hint}\n"
                        f"用户多轮回答:\n{joined}\n"
                        f"请返回形如 {{\"{code}\": {{...}} }} 的 JSON。"
                    ),
                },
            ],
            user_id=user.id,
            task_id=task_id,
            temperature=0.2,
            context=_PROFILE_LLM_CTX,
        )
        parsed = self._parse_extracted(result.content)
        if code in parsed:
            return {code: parsed[code]}
        return parsed

    def _apply_extracted(self, profile: UsrProfile, session_id: int, extracted: dict) -> list[str]:
        defs = {d.dimension_code: d for d in self.profile_repo.get_dimension_defs()}
        updated: list[str] = []
        for code in CORE_DIMENSION_CODES:
            if code not in extracted or code not in defs:
                continue
            value = extracted[code]
            if not isinstance(value, dict) or not value:
                continue
            if fusion_contribute_dimension(
                self.profile_repo,
                profile.id,
                defs[code].id,
                code,
                value,
                "dialogue",
                SOURCE_ACCURACY_WEIGHT["dialogue"],
                session_id,
            ):
                updated.append(code)
        if updated:
            profile.profile_version += 1
            self.db.commit()
        return updated

    def _profile_context_snippet(self, profile_id: int) -> str:
        """已有画像摘要，供对话开场引用。"""
        values = self.profile_repo.get_dimension_values(profile_id)
        defs = {d.id: d.dimension_code for d in self.profile_repo.get_dimension_defs()}
        parts: list[str] = []
        for v in values:
            code = defs.get(v.dimension_id)
            if not code or not v.dimension_value:
                continue
            val = v.dimension_value
            if code == "D1":
                parts.append(f"知识基础 Lv.{val.get('level', '?')}")
            elif code == "D3" and val.get("goal"):
                parts.append(f"学习目标：{val.get('goal')}")
            elif code == "D2" and val.get("style"):
                parts.append(f"认知风格：{val.get('style')}")
        return "；".join(parts[:4]) if parts else ""

    def _is_continue_build_intent(self, text: str) -> bool:
        t = text.strip()
        keys = ("继续", "构建", "补充", "完善", "深化", "再问", "接着", "画像", "开始问", "从头")
        return any(k in t for k in keys)

    def _pick_supplement_dimension(self, profile_ext: dict | None) -> str:
        order = list_refinement_dimensions(profile_ext)
        return order[0] if order else "D1"

    def _prior_answers_snippet(self, profile_ext: dict | None) -> str:
        """已采集的维度回答摘要，供下一问结合上文。"""
        answers = get_dimension_answers(profile_ext)
        parts: list[str] = []
        for code in CORE_DIMENSION_CODES:
            items = answers.get(code) or []
            if not items:
                continue
            name = DIMENSION_BY_CODE[code].name
            parts.append(f"「{name}」用户已说：{'；'.join(items)}")
        return "\n".join(parts) if parts else ""

    def _dimension_guide(self, code: str) -> str:
        """本维问题指引（采集目标），非既定问句。"""
        meta_db = get_dimension_meta(self.db, code)
        if meta_db:
            questions = list(meta_db.guide_questions)
            name = meta_db.name
        else:
            meta = DIMENSION_BY_CODE[code]
            questions = list(meta.guide_questions)
            name = meta.name
        cleaned = [q.strip() for q in questions if q and str(q).strip()]
        if not cleaned:
            return f"了解用户在「{name}」方面的关键学习情况"
        if len(cleaned) == 1:
            return cleaned[0]
        return f"本维「{name}」需覆盖：" + "；".join(cleaned)

    def _hint_question(self, code: str, q_idx: int) -> str:
        _ = q_idx
        return self._spoken_question(code)

    def _coach_rules(self) -> str:
        return (
            "你是一位有情商的学习伙伴，说话像豆包，像坐在旁边的学长学姐。"
            "不像客服，不像在填表，也不要自称系统。"
            "用户说什么都先接住，再在全文最后留下一个口语问题。"
            "打招呼，就回问候，再自然聊一句。"
            "用户向你提问，就先把问题用大白话讲明白，不要躲。"
            "用户说不知道、不会、随便、嗯，就先说没关系，把压力放下来，再把问题问得更小。"
            "用户已经在回答，就点出他刚才说的具体内容，让他感到被听懂，不要复读他的原句。"
            "禁止出现这些说法：维度、画像、问题指引、第几问、第几维、进度、采集、JSON、代码块、"
            "结合刚才的情况、我记下了、为了更准确地了解你、请继续聊聊。"
            "回复分成两段，中间空一行。第一段 2 到 4 句，只回应用户。第二段只留一个问句，放在全文最后。"
            "最后要问的那一句可以稍微改得更顺口，但意思不要换，也不要一次问两件无关的事。"
        )

    def _next_question_system(
        self,
        *,
        meta_name: str,
        hint: str,
        prior: str,
        mode: str,
        from_name: str = "",
        dim_ordinal: int = 1,
    ) -> str:
        _ = meta_name, from_name, dim_ordinal
        prior_block = (
            f"你已经知道这些，接话时可以自然用上，但不要逐条复述：\n{prior}\n"
            if prior
            else "你目前还没什么可引用的旧回答。\n"
        )
        task = f"最后要问：{hint}"
        if mode == "opening":
            extra = "这是开场。先说你好，再用一两句说明你在陪他聊学习，然后留下最后那个问题。"
        elif mode == "switch":
            extra = "用户刚换了个话题方向。先接住他刚才的话，不要宣布切换，再留下最后那个问题。"
        elif mode == "transition":
            extra = "用户上一句已经把眼前这件事说清楚了。先就那一句做具体回应，再自然落到最后那个问题上，不要说进入下一部分。"
        else:
            extra = "用户这一句可能是寒暄、提问，或还没说清。先回应这一句本身，不要跳过，再留下最后那个问题。"
        return f"{self._coach_rules()}{prior_block}{extra}{task}"

    async def _llm_text(
        self,
        messages: list[dict[str, str]],
        *,
        user_id: int,
        task_id: int | None,
    ) -> str:
        result = await self.llm.chat(
            messages,
            user_id=user_id,
            task_id=task_id,
            context=_PROFILE_LLM_CTX,
        )
        return result.content

    async def _build_dialogue_opening(
        self,
        user: SysUser,
        profile: UsrProfile,
        task_id: int,
        next_code: str,
        q_idx: int,
        *,
        dialogue_answered: int,
        has_other_sources: bool,
    ) -> str:
        """生成对话开场/第一问（LLM 按指引自由组织；结合已有信息）。"""
        meta = DIMENSION_BY_CODE[next_code]
        q_progress = get_question_progress(profile.ext_json)
        hint = self._hint_question(next_code, q_idx)
        ctx = self._profile_context_snippet(profile.id)
        prior = self._prior_answers_snippet(profile.ext_json)
        dim_ordinal = CORE_DIMENSION_CODES.index(next_code) + 1 if next_code in CORE_DIMENSION_CODES else 1

        extra = ""
        if has_other_sources and ctx:
            extra = f"可以自然用上这些旧信息，但不要向用户宣布进度或条目：{ctx}。"

        system = (
            self._next_question_system(
                meta_name=meta.name,
                hint=hint,
                prior=prior or ctx,
                mode="opening",
                dim_ordinal=dim_ordinal,
            )
            + extra
        )

        try:
            text = await self._llm_text(
                [{"role": "system", "content": system}],
                user_id=user.id,
                task_id=task_id,
            )
            return self._sanitize_assistant_message(
                text, target_code=next_code, q_progress=q_progress
            )
        except Exception:
            return self._build_guide_message(next_code, q_idx, [])

    async def _supplement_dialogue_reply(
        self,
        user: SysUser,
        session: UsrProfileDialogueSession,
        profile: UsrProfile,
        user_text: str,
        history: list,
    ) -> str:
        """标准 6 问完成后的自由补充：根据用户意图与上文提出新问题。"""
        dim_code = self._pick_supplement_dimension(profile.ext_json)
        ctx = self._profile_context_snippet(profile.id)
        prior = self._prior_answers_snippet(profile.ext_json)
        continue_intent = self._is_continue_build_intent(user_text)
        hint = self._spoken_question(dim_code)

        prior_block = f"此前他说过：\n{prior}" if prior else ""
        system = (
            f"{self._coach_rules()}"
            f"标准问题已经问完，现在是顺着他的话再聊深一点。"
            f"已知情况：{ctx or '还不多'}。\n"
            f"{prior_block}"
            f"最后要问：{hint}\n"
        )
        if continue_intent:
            system += "他想继续聊。先接住这一句，再把最后那个问题问得更具体，不要和上一轮用同一套说法。"
        else:
            system += "先把这一句回应完。有用就顺着追问一个细节；没用也要温柔地落到最后那个问题上。"

        chat_history = [{"role": m.role, "content": m.content} for m in history[-8:]]
        chat_history.append({"role": "user", "content": user_text})
        try:
            text = await self._llm_text(
                [{"role": "system", "content": system}, *chat_history],
                user_id=user.id,
                task_id=session.agent_task_id,
            )
            return self._sanitize_assistant_message(
                text,
                target_code=dim_code,
                q_progress=get_question_progress(profile.ext_json),
                user_text=user_text,
            )
        except Exception:
            return self._human_turn(user_text, dim_code)

    def _build_guide_message(self, dimension_code: str, question_index: int, completed_dims: list[str]) -> str:
        _ = question_index, completed_dims
        return self._human_turn("", dimension_code)

    async def _compose_assistant_after_answer(
        self,
        *,
        user: SysUser,
        session: UsrProfileDialogueSession,
        profile: UsrProfile,
        user_text: str,
        history: list,
        supplement_mode: bool,
        dialogue_done: bool,
        dialogue_done_before: bool,
        target_code: str,
        next_code: str,
        q_progress: dict[str, int],
        completed: list[str],
    ) -> str:
        """根据状态机生成下一轮助手回复（LLM 优先，预设仅兜底）。"""
        if supplement_mode:
            if self._is_continue_build_intent(user_text):
                dim_code = self._pick_supplement_dimension(profile.ext_json)
                try:
                    return await self._supplement_dialogue_reply(
                        user, session, profile, user_text, history
                    )
                except Exception:
                    qp = get_question_progress(profile.ext_json)
                    return self._build_guide_message(
                        dim_code, min(qp.get(dim_code, 0) + 1, QUESTIONS_PER_DIMENSION), completed
                    )
            return await self._supplement_dialogue_reply(
                user, session, profile, user_text, history
            )

        if dialogue_done and not dialogue_done_before:
            return (
                "🎉 **6维画像构建完成！**（6 轮问答全部完成）\n\n"
                "右侧已生成你的完整画像卡片与雷达图。这些画像数据将自动用于：\n"
                "- 多智能体个性化资源生成\n"
                "- AI 学习路径规划\n\n"
                "你随时可以继续补充或调整任一维度的信息。"
            )

        chat_history = [{"role": m.role, "content": m.content} for m in history[-8:]]
        chat_history.append({"role": "user", "content": user_text})
        prior = self._prior_answers_snippet(profile.ext_json)

        if q_progress[target_code] < QUESTIONS_PER_DIMENSION:
            meta = DIMENSION_BY_CODE[target_code]
            next_q = q_progress[target_code] + 1
            hint = self._hint_question(target_code, next_q)
            messages = [
                {
                    "role": "system",
                    "content": self._next_question_system(
                        meta_name=meta.name,
                        hint=hint,
                        prior=prior,
                        mode="same_dim",
                    ),
                },
                *chat_history,
            ]
            try:
                text = await self._llm_text(
                    messages, user_id=user.id, task_id=session.agent_task_id
                )
                return self._sanitize_assistant_message(
                    text, target_code=target_code, q_progress=q_progress
                )
            except Exception:
                return self._fallback_guide_reply(target_code, q_progress)

        meta = DIMENSION_BY_CODE[next_code]
        hint = self._hint_question(next_code, 1)
        messages = [
            {
                "role": "system",
                "content": self._next_question_system(
                    meta_name=meta.name,
                    hint=hint,
                    prior=prior,
                    mode="transition",
                    from_name=DIMENSION_BY_CODE[target_code].name,
                    dim_ordinal=len(completed) + 1,
                ),
            },
            *chat_history,
        ]
        try:
            text = await self._llm_text(
                messages, user_id=user.id, task_id=session.agent_task_id
            )
            return self._sanitize_assistant_message(
                text,
                target_code=target_code,
                q_progress=q_progress,
                transition=True,
                next_code=next_code,
            )
        except Exception:
            return self._fallback_guide_reply(
                target_code, q_progress, transition=True, next_code=next_code
            )

    async def _iter_assistant_after_answer(
        self,
        *,
        user: SysUser,
        session: UsrProfileDialogueSession,
        profile: UsrProfile,
        user_text: str,
        history: list,
        supplement_mode: bool,
        dialogue_done: bool,
        dialogue_done_before: bool,
        target_code: str,
        next_code: str,
        q_progress: dict[str, int],
        completed: list[str],
    ):
        """流式产出助手回复文本块；非 LLM 路径一次性 yield。"""
        if supplement_mode or (dialogue_done and not dialogue_done_before):
            text = await self._compose_assistant_after_answer(
                user=user,
                session=session,
                profile=profile,
                user_text=user_text,
                history=history,
                supplement_mode=supplement_mode,
                dialogue_done=dialogue_done,
                dialogue_done_before=dialogue_done_before,
                target_code=target_code,
                next_code=next_code,
                q_progress=q_progress,
                completed=completed,
            )
            yield text
            return

        chat_history = [{"role": m.role, "content": m.content} for m in history[-8:]]
        chat_history.append({"role": "user", "content": user_text})
        prior = self._prior_answers_snippet(profile.ext_json)

        if q_progress[target_code] < QUESTIONS_PER_DIMENSION:
            meta = DIMENSION_BY_CODE[target_code]
            next_q = q_progress[target_code] + 1
            hint = self._hint_question(target_code, next_q)
            messages = [
                {
                    "role": "system",
                    "content": self._next_question_system(
                        meta_name=meta.name,
                        hint=hint,
                        prior=prior,
                        mode="same_dim",
                    ),
                },
                *chat_history,
            ]
            sanitize_kwargs = dict(target_code=target_code, q_progress=q_progress, user_text=user_text)
        else:
            meta = DIMENSION_BY_CODE[next_code]
            hint = self._hint_question(next_code, 1)
            messages = [
                {
                    "role": "system",
                    "content": self._next_question_system(
                        meta_name=meta.name,
                        hint=hint,
                        prior=prior,
                        mode="transition",
                        from_name=DIMENSION_BY_CODE[target_code].name,
                        dim_ordinal=len(completed) + 1,
                    ),
                },
                *chat_history,
            ]
            sanitize_kwargs = dict(
                target_code=target_code,
                q_progress=q_progress,
                transition=True,
                next_code=next_code,
                user_text=user_text,
            )

        buf: list[str] = []
        try:
            async for chunk in self._stream_llm_text(
                messages, user_id=user.id, task_id=session.agent_task_id
            ):
                buf.append(chunk)
                yield chunk
        except Exception:
            yield self._fallback_guide_reply(**sanitize_kwargs)  # type: ignore[arg-type]
            return

        full = "".join(buf)
        cleaned = self._sanitize_assistant_message(full, **sanitize_kwargs)  # type: ignore[arg-type]
        if not (dialogue_done and not dialogue_done_before):
            cleaned = self._sanitize_assistant_message(
                cleaned, target_code=next_code, q_progress=q_progress, user_text=user_text
            )
        if cleaned != full:
            yield "\0REPLACE:" + cleaned

    def _dialogue_history_items(
        self,
        messages: list[UsrProfileDialogueMessage],
        *,
        target_code: str,
        q_progress: dict,
    ) -> list[DialogueHistoryMessage]:
        items: list[DialogueHistoryMessage] = []
        for m in messages:
            content = m.content
            if m.role == "assistant":
                content = self._sanitize_assistant_message(
                    content,
                    target_code=target_code,
                    q_progress=q_progress,
                )
            role = "assistant" if m.role == "assistant" else "user"
            items.append(DialogueHistoryMessage(role=role, content=content))
        return items

    def _build_dialogue_start_from_session(
        self,
        user: SysUser,
        profile: UsrProfile,
        session: UsrProfileDialogueSession,
        *,
        q_progress: dict,
        completed: list[str],
        answered_total: int,
        dialogue_done: bool,
    ) -> DialogueStartResponse:
        if session.status != 0:
            session.status = 0
            session.ended_at = None
            self.db.commit()

        # 关闭其它未结束会话，统一续聊到本会话
        from datetime import datetime, timezone

        others = (
            self.db.query(UsrProfileDialogueSession)
            .filter(
                UsrProfileDialogueSession.user_id == user.id,
                UsrProfileDialogueSession.profile_id == profile.id,
                UsrProfileDialogueSession.status == 0,
                UsrProfileDialogueSession.id != session.id,
            )
            .all()
        )
        if others:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            for s in others:
                s.status = 1
                s.ended_at = now
            self.db.commit()

        messages = self.profile_repo.get_dialogue_messages(session.id)
        progress = build_dimension_progress(self.profile_repo, profile.id)
        completeness, _ = recalc_core_completeness(self.profile_repo, profile.id)
        focus_code = (profile.ext_json or {}).get("dialogue_focus_dimension")
        next_code, q_idx = get_active_question_index(q_progress, completed)
        if focus_code and focus_code in CORE_DIMENSION_CODES and not dialogue_done:
            next_code = focus_code
            q_idx = min(q_progress.get(focus_code, 0) + 1, QUESTIONS_PER_DIMENSION)
        next_code = next_code or "D1"
        meta = DIMENSION_BY_CODE[next_code]
        history = self._dialogue_history_items(
            messages, target_code=next_code, q_progress=q_progress
        )
        last_assistant = next(
            (h.content for h in reversed(history) if h.role == "assistant"),
            "",
        )
        task_no = ""
        if session.agent_task_id:
            task = self.agent_repo.get_task_by_id(session.agent_task_id)
            task_no = task.task_no if task else ""
        return DialogueStartResponse(
            session_no=session.session_no,
            profile_id=profile.id,
            task_no=task_no,
            message=last_assistant or self._build_guide_message(next_code, q_idx or 1, completed),
            messages=history,
            current_dimension_code=next_code,
            current_dimension_name=meta.name,
            current_question_index=q_idx if not dialogue_done else QUESTIONS_PER_DIMENSION,
            completeness=completeness,
            dimension_progress=[DimensionProgressItem.model_validate(p) for p in progress],
            completed_question_count=answered_total,
            total_question_count=TOTAL_PROFILE_QUESTIONS,
        )

    async def start_dialogue(self, user: SysUser) -> DialogueStartResponse:
        profile = self.get_or_create_profile(user)
        self._assert_profile_owner(profile, user)
        _, completed = recalc_core_completeness(self.profile_repo, profile.id)
        q_progress = get_question_progress(profile.ext_json)
        answered_total = completed_question_count(q_progress)
        dialogue_done = is_dialogue_flow_complete(q_progress)

        contribs = get_dimension_contributions(profile.ext_json)
        has_other_sources = any(
            c.get("source") in {"questionnaire", "assessment", "behavior"}
            for items in contribs.values()
            for c in items
        )

        # 复用最近会话并回传完整历史（含已完成会话，便于回看与补充）
        existing = self.profile_repo.get_dialogue_session_for_restore(user.id, profile.id)
        if existing:
            return self._build_dialogue_start_from_session(
                user,
                profile,
                existing,
                q_progress=q_progress,
                completed=completed,
                answered_total=answered_total,
                dialogue_done=dialogue_done,
            )

        self.profile_repo.close_active_dialogue_sessions(user.id, profile.id)

        task = self.agent_repo.create_task(
            user.id, "profile_build", "6维×3问对话式画像构建", {"profile_id": profile.id}
        )
        session = UsrProfileDialogueSession(
            user_id=user.id,
            profile_id=profile.id,
            session_no=str(uuid.uuid4()),
            status=0,
            current_round=0,
            agent_task_id=task.id,
            target_dimensions=CORE_DIMENSION_CODES,
            completed_dimensions=completed,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        next_code, q_idx = get_active_question_index(q_progress, [])
        next_code = next_code or "D1"
        q_idx = q_idx or 1

        if dialogue_done:
            guide = (
                f"你已完成 **6 维 × 每维 1 问**（共 {TOTAL_PROFILE_QUESTIONS} 问）对话式画像！\n\n"
                "若想继续深化，可直接告诉我你想补充的维度或新情况；"
                "我会针对具体维度追问，而不会重复空泛提示。\n\n"
                "例如：「我想补充学习节奏」或「继续完善知识基础」。"
            )
        else:
            guide = await self._build_dialogue_opening(
                user,
                profile,
                task.id,
                next_code,
                q_idx,
                dialogue_answered=answered_total,
                has_other_sources=has_other_sources,
            )
            guide = self._sanitize_assistant_message(
                guide,
                target_code=next_code,
                q_progress=q_progress,
            )

        session.current_round = 1
        self.db.add(
            UsrProfileDialogueMessage(
                session_id=session.id,
                round_no=1,
                role="assistant",
                content=guide,
            )
        )
        self.db.commit()

        progress = build_dimension_progress(self.profile_repo, profile.id)
        completeness, _ = recalc_core_completeness(self.profile_repo, profile.id)
        meta = DIMENSION_BY_CODE.get(next_code) or DIMENSION_BY_CODE["D1"]
        history = [DialogueHistoryMessage(role="assistant", content=guide)]

        return DialogueStartResponse(
            session_no=session.session_no,
            profile_id=profile.id,
            task_no=task.task_no,
            message=guide,
            messages=history,
            current_dimension_code=next_code,
            current_dimension_name=meta.name,
            current_question_index=q_idx if not dialogue_done else QUESTIONS_PER_DIMENSION,
            completeness=completeness,
            dimension_progress=[DimensionProgressItem.model_validate(p) for p in progress],
            completed_question_count=answered_total,
            total_question_count=TOTAL_PROFILE_QUESTIONS,
        )

    async def send_dialogue_message(
        self, user: SysUser, session_no: str, req: DialogueMessageRequest
    ) -> DialogueMessageResponse:
        session = self.profile_repo.get_dialogue_session(session_no)
        if not session or session.user_id != user.id:
            raise NotFoundException(ErrorCode.NOT_FOUND, "会话不存在")

        profile = self.profile_repo.get_by_user_id(user.id)
        self._assert_profile_owner(profile, user)

        q_progress = get_question_progress(profile.ext_json)
        dialogue_done_before = is_dialogue_flow_complete(q_progress)
        # 仅当标准问已走完才进入补充模式；旧会话误标完成则恢复
        if session.status == 1 and not dialogue_done_before:
            session.status = 0
            self.db.commit()
        supplement_mode = dialogue_done_before

        _, completed_before = recalc_core_completeness(self.profile_repo, profile.id)
        q_progress = get_question_progress(profile.ext_json)
        dim_answers = get_dimension_answers(profile.ext_json)

        focus_code = (profile.ext_json or {}).get("dialogue_focus_dimension")
        target_code, question_idx = get_active_question_index(q_progress, completed_before)
        if focus_code and focus_code in CORE_DIMENSION_CODES and not supplement_mode:
            target_code = focus_code
            question_idx = min(q_progress.get(focus_code, 0) + 1, QUESTIONS_PER_DIMENSION)
        if not target_code:
            target_code = completed_before[-1] if completed_before else "D1"
            question_idx = QUESTIONS_PER_DIMENSION

        round_no = session.current_round + 1
        self.db.add(
            UsrProfileDialogueMessage(
                session_id=session.id,
                round_no=round_no,
                role="user",
                content=req.content,
            )
        )
        self.db.commit()

        # 记录本轮回答（补充模式不递增进度，仅更新对话）
        if not supplement_mode and self._counts_toward_profile(req.content):
            dim_answers = merge_dimension_answers(dim_answers, target_code, req.content)
            q_progress[target_code] = min(q_progress.get(target_code, 0) + 1, QUESTIONS_PER_DIMENSION)
            set_question_progress(self.profile_repo, profile.id, q_progress, dim_answers)
            self.db.refresh(profile)

        extracted: dict = {}
        updated_dims: list[str] = []

        completeness, completed = recalc_core_completeness(self.profile_repo, profile.id)
        session.completed_dimensions = completed
        dialogue_done = is_dialogue_flow_complete(q_progress)
        is_completed = dialogue_done

        next_code, next_q_idx = get_active_question_index(q_progress, [])
        if not next_code:
            next_code = CORE_DIMENSION_CODES[-1]
            next_q_idx = QUESTIONS_PER_DIMENSION

        history = self.profile_repo.get_dialogue_messages(session.id)

        need_synthesis = (
            not supplement_mode and q_progress[target_code] >= QUESTIONS_PER_DIMENSION
        )
        compose_coro = self._compose_assistant_after_answer(
            user=user,
            session=session,
            profile=profile,
            user_text=req.content,
            history=history,
            supplement_mode=supplement_mode,
            dialogue_done=dialogue_done,
            dialogue_done_before=dialogue_done_before,
            target_code=target_code,
            next_code=next_code,
            q_progress=q_progress,
            completed=completed,
        )
        if need_synthesis:
            synth_coro = self._synthesize_dimension(
                user, target_code, dim_answers.get(target_code, []), session.agent_task_id
            )
            extracted, assistant_msg = await asyncio.gather(synth_coro, compose_coro)
            updated_dims = self._apply_extracted(profile, session.id, extracted)
            completeness, completed = recalc_core_completeness(self.profile_repo, profile.id)
            session.completed_dimensions = completed
        else:
            assistant_msg = await compose_coro

        # 最后一道防线：绝不把画像 JSON 写入对话气泡
        if not (dialogue_done and not dialogue_done_before):
            assistant_msg = self._sanitize_assistant_message(
                assistant_msg,
                target_code=next_code,
                q_progress=q_progress,
            )

        self.db.add(
            UsrProfileDialogueMessage(
                session_id=session.id,
                round_no=round_no,
                role="assistant",
                content=assistant_msg,
                extracted_dims=extracted or None,
            )
        )
        session.current_round = round_no

        if is_completed and not supplement_mode:
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            session.status = 1
            session.ended_at = now
            if profile.status != 1:
                profile.status = 1
                profile.confirmed_at = now

        self.db.commit()

        progress = build_dimension_progress(self.profile_repo, profile.id)
        answered_total = completed_question_count(get_question_progress(profile.ext_json))

        return DialogueMessageResponse(
            session_no=session_no,
            round_no=round_no,
            assistant_message=assistant_msg,
            extracted_dims=extracted or None,
            updated_dimensions=updated_dims,
            completeness=completeness,
            is_completed=is_completed,
            current_dimension_code=next_code,
            current_dimension_name=DIMENSION_BY_CODE[next_code].name if next_code else None,
            current_question_index=next_q_idx if next_code else QUESTIONS_PER_DIMENSION,
            dimension_progress=[DimensionProgressItem.model_validate(p) for p in progress],
            completed_count=len(completed),
            total_count=CORE_DIMENSION_COUNT,
            completed_question_count=answered_total,
            total_question_count=TOTAL_PROFILE_QUESTIONS,
        )

    async def stream_dialogue_message(
        self, user: SysUser, session_no: str, req: DialogueMessageRequest
    ):
        """SSE：先推送 token，最后推 done 元数据。打断时未完成则不落库助手消息。"""
        # 短答快速路径：整段返回
        session = self.profile_repo.get_dialogue_session(session_no)
        if not session or session.user_id != user.id:
            raise NotFoundException(ErrorCode.NOT_FOUND, "会话不存在")

        profile = self.profile_repo.get_by_user_id(user.id)
        self._assert_profile_owner(profile, user)

        q_progress = get_question_progress(profile.ext_json)
        dialogue_done_before = is_dialogue_flow_complete(q_progress)
        if session.status == 1 and not dialogue_done_before:
            session.status = 0
            self.db.commit()
        supplement_mode = dialogue_done_before

        _, completed_before = recalc_core_completeness(self.profile_repo, profile.id)
        q_progress = get_question_progress(profile.ext_json)
        dim_answers = get_dimension_answers(profile.ext_json)

        focus_code = (profile.ext_json or {}).get("dialogue_focus_dimension")
        target_code, question_idx = get_active_question_index(q_progress, completed_before)
        if focus_code and focus_code in CORE_DIMENSION_CODES and not supplement_mode:
            target_code = focus_code
            question_idx = min(q_progress.get(focus_code, 0) + 1, QUESTIONS_PER_DIMENSION)
        if not target_code:
            target_code = completed_before[-1] if completed_before else "D1"
            question_idx = QUESTIONS_PER_DIMENSION

        round_no = session.current_round + 1
        self.db.add(
            UsrProfileDialogueMessage(
                session_id=session.id,
                round_no=round_no,
                role="user",
                content=req.content,
            )
        )
        self.db.commit()

        if not supplement_mode and self._counts_toward_profile(req.content):
            dim_answers = merge_dimension_answers(dim_answers, target_code, req.content)
            q_progress[target_code] = min(q_progress.get(target_code, 0) + 1, QUESTIONS_PER_DIMENSION)
            set_question_progress(self.profile_repo, profile.id, q_progress, dim_answers)
            self.db.refresh(profile)

        extracted: dict = {}
        updated_dims: list[str] = []
        synthesis_task: asyncio.Task | None = None
        need_synthesis = (
            not supplement_mode and q_progress[target_code] >= QUESTIONS_PER_DIMENSION
        )
        if need_synthesis:
            synthesis_task = asyncio.create_task(
                self._synthesize_dimension(
                    user, target_code, dim_answers.get(target_code, []), session.agent_task_id
                )
            )

        completeness, completed = recalc_core_completeness(self.profile_repo, profile.id)
        session.completed_dimensions = completed
        dialogue_done = is_dialogue_flow_complete(q_progress)
        is_completed = dialogue_done

        next_code, next_q_idx = get_active_question_index(q_progress, [])
        if not next_code:
            next_code = CORE_DIMENSION_CODES[-1]
            next_q_idx = QUESTIONS_PER_DIMENSION

        history = self.profile_repo.get_dialogue_messages(session.id)
        parts: list[str] = []
        replaced: str | None = None
        try:
            async for piece in self._iter_assistant_after_answer(
                user=user,
                session=session,
                profile=profile,
                user_text=req.content,
                history=history,
                supplement_mode=supplement_mode,
                dialogue_done=dialogue_done,
                dialogue_done_before=dialogue_done_before,
                target_code=target_code,
                next_code=next_code,
                q_progress=q_progress,
                completed=completed,
            ):
                if piece.startswith("\0REPLACE:"):
                    replaced = piece[len("\0REPLACE:") :]
                    continue
                parts.append(piece)
                yield ("chunk", {"content": piece})
        except asyncio.CancelledError:
            if synthesis_task and not synthesis_task.done():
                synthesis_task.cancel()
            raise

        if synthesis_task:
            try:
                extracted = await synthesis_task
                if extracted:
                    updated_dims = self._apply_extracted(profile, session.id, extracted)
                    completeness, completed = recalc_core_completeness(self.profile_repo, profile.id)
                    session.completed_dimensions = completed
            except Exception:
                logger.exception("Dimension synthesis failed during stream")
                extracted = {}

        assistant_msg = replaced if replaced is not None else "".join(parts)
        if not (dialogue_done and not dialogue_done_before):
            assistant_msg = self._sanitize_assistant_message(
                assistant_msg, target_code=next_code, q_progress=q_progress
            )

        self.db.add(
            UsrProfileDialogueMessage(
                session_id=session.id,
                round_no=round_no,
                role="assistant",
                content=assistant_msg,
                extracted_dims=extracted or None,
            )
        )
        session.current_round = round_no
        if is_completed and not supplement_mode:
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            session.status = 1
            session.ended_at = now
            if profile.status != 1:
                profile.status = 1
                profile.confirmed_at = now
        self.db.commit()

        progress = build_dimension_progress(self.profile_repo, profile.id)
        answered_total = completed_question_count(get_question_progress(profile.ext_json))
        resp = DialogueMessageResponse(
            session_no=session_no,
            round_no=round_no,
            assistant_message=assistant_msg,
            extracted_dims=extracted or None,
            updated_dimensions=updated_dims,
            completeness=completeness,
            is_completed=is_completed,
            current_dimension_code=next_code,
            current_dimension_name=DIMENSION_BY_CODE[next_code].name if next_code else None,
            current_question_index=next_q_idx if next_code else QUESTIONS_PER_DIMENSION,
            dimension_progress=[DimensionProgressItem.model_validate(p) for p in progress],
            completed_count=len(completed),
            total_count=CORE_DIMENSION_COUNT,
            completed_question_count=answered_total,
            total_question_count=TOTAL_PROFILE_QUESTIONS,
        )
        if replaced is not None:
            yield ("replace", {"content": assistant_msg})
        yield ("done", resp.model_dump(mode="json"))

    def _set_dialogue_focus(self, profile_id: int, dimension_code: str | None) -> None:
        from app.models.profile import UsrProfile

        profile = self.profile_repo.db.query(UsrProfile).filter(UsrProfile.id == profile_id).first()
        if not profile:
            return
        ext = dict(profile.ext_json or {})
        if dimension_code:
            ext["dialogue_focus_dimension"] = dimension_code
        else:
            ext.pop("dialogue_focus_dimension", None)
        profile.ext_json = ext
        self.profile_repo.db.commit()

    async def switch_dialogue_dimension(self, user: SysUser, session_no: str, dimension_code: str) -> DialogueStartResponse:
        """维度跳转：用户主动切换采集维度。"""
        if dimension_code not in CORE_DIMENSION_CODES:
            raise ValidationException(f"无效维度: {dimension_code}")

        session = self.profile_repo.get_dialogue_session(session_no)
        if not session or session.user_id != user.id:
            raise NotFoundException(ErrorCode.NOT_FOUND, "会话不存在")

        profile = self.profile_repo.get_by_user_id(user.id)
        self._assert_profile_owner(profile, user)
        self._set_dialogue_focus(profile.id, dimension_code)

        q_progress = get_question_progress(profile.ext_json)
        _, completed = recalc_core_completeness(self.profile_repo, profile.id)
        q_idx = min(q_progress.get(dimension_code, 0) + 1, QUESTIONS_PER_DIMENSION)
        meta = DIMENSION_BY_CODE[dimension_code]
        hint = self._hint_question(dimension_code, q_idx)
        prior = self._prior_answers_snippet(profile.ext_json)
        try:
            guide = await self._llm_text(
                [
                    {
                        "role": "system",
                        "content": self._next_question_system(
                            meta_name=meta.name,
                            hint=hint,
                            prior=prior,
                            mode="switch",
                        ),
                    }
                ],
                user_id=user.id,
                task_id=session.agent_task_id,
            )
            guide = self._sanitize_assistant_message(
                guide, target_code=dimension_code, q_progress=q_progress
            )
        except Exception:
            guide = (
                f"已切换到 **{meta.name}** 维度。\n\n"
                + self._build_guide_message(dimension_code, q_idx, completed)
            )

        round_no = session.current_round + 1
        self.db.add(
            UsrProfileDialogueMessage(
                session_id=session.id,
                round_no=round_no,
                role="assistant",
                content=guide,
            )
        )
        session.current_round = round_no
        self.db.commit()

        progress = build_dimension_progress(self.profile_repo, profile.id)
        completeness, _ = recalc_core_completeness(self.profile_repo, profile.id)
        answered_total = completed_question_count(q_progress)

        task_no = ""
        if session.agent_task_id:
            task = self.agent_repo.get_task_by_id(session.agent_task_id)
            task_no = task.task_no if task else ""

        history = self._dialogue_history_items(
            self.profile_repo.get_dialogue_messages(session.id),
            target_code=dimension_code,
            q_progress=q_progress,
        )

        return DialogueStartResponse(
            session_no=session.session_no,
            profile_id=profile.id,
            task_no=task_no,
            message=guide,
            messages=history,
            current_dimension_code=dimension_code,
            current_dimension_name=meta.name,
            current_question_index=q_idx,
            completeness=completeness,
            dimension_progress=[DimensionProgressItem.model_validate(p) for p in progress],
            completed_question_count=answered_total,
            total_question_count=TOTAL_PROFILE_QUESTIONS,
        )
