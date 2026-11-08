"""Core profile dimensions for dialogue-driven profile building (赛题6维 × 每维1问)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CoreDimension:
    code: str
    name: str
    description: str
    # 问题指引（非既定问句）：告诉模型本维要采到什么，由模型结合上文自由组织提问
    guide_questions: tuple[str, ...]
    extract_hint: str
    # 对学生说出口的那一句。内部 guide_questions 不要出现在回复里。
    spoken_question: str = ""

    @property
    def guide_question(self) -> str:
        """兼容旧逻辑：返回本维指引。"""
        return self.guide_questions[0] if self.guide_questions else ""


QUESTIONS_PER_DIMENSION = 1
CORE_DIMENSION_COUNT = 6
TOTAL_PROFILE_QUESTIONS = CORE_DIMENSION_COUNT * QUESTIONS_PER_DIMENSION  # 6


CORE_PROFILE_DIMENSIONS: list[CoreDimension] = [
    CoreDimension(
        code="D1",
        name="知识基础",
        description="各学科/领域的知识掌握水平",
        guide_questions=(
            "摸清用户的专业/工作领域、当前掌握水平（可引导自评），以及最想补强的薄弱点；"
            "若上文已提到其中任一项，只追问尚未清楚的部分，禁止在未知领域上假设。",
        ),
        extract_hint='{"domain":"领域","level":1-5,"gaps":["缺口1"]}',
        spoken_question="你有没有学过数据结构，或者别的专业课？学到哪一步了，哪一块还不太会？",
    ),
    CoreDimension(
        code="D2",
        name="认知风格",
        description="视觉型/言语型/序列型/整体型等认知偏好",
        guide_questions=(
            "结合用户已提到的领域或经历，了解其更有效的知识吸收方式"
            "（看图/读文/动手、整体框架 vs 逐步推进、材料偏好等），点名引用上文细节。",
        ),
        extract_hint='{"style":"visual|verbal|sequential|global","score":0.0-1.0}',
        spoken_question="你学一个新东西的时候，是更喜欢看图、看例子，还是自己动手试？一般是先看整体，还是一步一步来？",
    ),
    CoreDimension(
        code="D3",
        name="学习目标",
        description="当前学习的具体目标与期限",
        guide_questions=(
            "基于已了解的领域与基础，问清一个具体可衡量的学习目标、大致期限与优先级；"
            "目标表述应贴合用户前文，勿问与其领域无关的空泛目标。",
        ),
        extract_hint='{"goal":"目标描述","deadline":"YYYY-MM-DD或null","priority":"high|mid|low"}',
        spoken_question="你接下来最想搞懂的是什么？大概想在多久之内学会？",
    ),
    CoreDimension(
        code="D4",
        name="学习历史",
        description="已完成的课程与学习记录",
        guide_questions=(
            "围绕用户目标与领域，了解相关课程/自学经历、已完成主题与大致投入时间；"
            "优先追问与目标直接相关的经历。",
        ),
        extract_hint='{"courses":["课程名"],"completedTopics":["主题"],"totalHours":数字}',
        spoken_question="跟这个有关的课，你上过哪些？自己额外学过吗，大概花了多少时间？",
    ),
    CoreDimension(
        code="D5",
        name="易错点偏好",
        description="历史错题与薄弱知识点",
        guide_questions=(
            "结合其领域与薄弱点，了解反复出错的知识点/题型、错误类型，以及更希望反复练还是先搞懂原理。",
        ),
        extract_hint='{"weakPoints":[{"topic":"知识点","errorType":"错误类型","frequency":次数}]}',
        spoken_question="哪一类题你老是错？你是想多做几道，还是想先把原理听明白？",
    ),
    CoreDimension(
        code="D6",
        name="学习节奏",
        description="学习速度与单次学习时长偏好",
        guide_questions=(
            "了解学习节奏偏好（快/稳）、单次高效专注时长，以及每周可安排的次数或时段；"
            "可结合其目标期限给出贴合的追问。",
        ),
        extract_hint='{"pace":"fast|medium|slow","sessionMinutes":30}',
        spoken_question="你一次大概能坐住学多久？一周里通常什么时候学？",
    ),
]

CORE_DIMENSION_CODES: list[str] = [d.code for d in CORE_PROFILE_DIMENSIONS]
DIMENSION_BY_CODE = {d.code: d for d in CORE_PROFILE_DIMENSIONS}
