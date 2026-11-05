"""Input-side guard: sensitive words + relevance filter."""

import re

from sqlalchemy.orm import Session

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppException
from app.models.path import SecSensitiveWord

DEFAULT_BLOCK_WORDS = ["暴力恐怖", "色情", "赌博", "毒品", "反动", "制毒", "枪支"]

EDUCATION_HINTS = [
    "学习", "课程", "知识", "题", "算法", "编程", "数学", "物理", "化学", "英语",
    "机器学习", "深度学习", "梯度", "模型", "考试", "作业", "理解", "解释", "为什么",
    "如何", "什么", "原理", "概念", "错题", "辅导", "路径", "资源", "画像",
]

WEB_SEARCH_HINTS = [
    "联网", "搜索", "检索", "查一下", "帮我查", "帮我搜", "新闻", "最新", "资料",
    "百科", "查询", "google", "bing", "百度",
]

OFF_TOPIC_PATTERNS = [
    r"写一封.*信",
    r"帮我黑",
    r"破解.*密码",
    r"生成.*色情|制作.*色情|写.*黄文",
    r"政治.*立场",
    r"制毒|贩毒|枪支|爆炸物",
    r"赌博|六合彩|网赌|菠菜",
    r"色情|淫秽|裸体",
]


class InputGuard:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _load_words(self) -> list[SecSensitiveWord]:
        return self.db.query(SecSensitiveWord).filter(SecSensitiveWord.status == 1).all()

    def filter_text(self, text: str) -> tuple[str, list[str]]:
        matched: list[str] = []
        filtered = text
        words = self._load_words()
        word_list = [w.word for w in words] if words else DEFAULT_BLOCK_WORDS

        for w in words:
            if w.word in text:
                matched.append(w.category)
                if w.word_type == "block":
                    raise AppException(
                        ErrorCode.LLM_CONTENT_FILTERED,
                        f"输入包含违规内容，已被拦截",
                        detail={"word": w.word, "category": w.category},
                        http_status=400,
                    )
                if w.word_type == "replace" and w.replacement:
                    filtered = filtered.replace(w.word, w.replacement)
                if w.word_type == "warn":
                    matched.append(f"warn:{w.word}")

        for w in word_list:
            if isinstance(w, str) and w in text:
                raise AppException(
                    ErrorCode.LLM_CONTENT_FILTERED,
                    "输入包含违规内容，已被拦截",
                    detail={"word": w},
                    http_status=400,
                )
        return filtered, matched

    def check_relevance(self, text: str, allow_off_topic: bool = False) -> None:
        """仅拦截明确违法/恶意请求；日常闲聊与非学习话题均放行。"""
        stripped = text.strip()
        if not stripped or len(stripped) < 2:
            return
        if any(re.search(p, text, re.I) for p in OFF_TOPIC_PATTERNS):
            raise AppException(
                ErrorCode.LLM_CONTENT_FILTERED,
                "提问包含违法或不当内容，已被拦截",
                http_status=400,
            )

    def guard_messages(
        self, messages: list[dict[str, str]], allow_off_topic: bool = False
    ) -> list[dict[str, str]]:
        guarded: list[dict[str, str]] = []
        for msg in messages:
            content = msg.get("content") or ""
            if msg.get("role") == "user" and content.strip():
                self.check_relevance(content, allow_off_topic)
                filtered, _ = self.filter_text(content)
                guarded.append({**msg, "content": filtered})
            else:
                guarded.append(msg)
        return guarded
