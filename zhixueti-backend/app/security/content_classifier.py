"""内容分类 — 区分正常学科内容与违规内容。"""

from __future__ import annotations

import re

# 正常学科学习内容的特征词（命中则视为教育内容，放宽审核）
EDUCATIONAL_MARKERS = [
    "学习", "知识", "概念", "定义", "公式", "定理", "例题", "习题", "练习",
    "讲解", "步骤", "分析", "解析", "目标", "章节", "课程", "教学", "考试",
    "算法", "模型", "函数", "方程", "证明", "应用", "原理", "方法", "总结",
    "选项", "答案", "难度", "知识点", "思维导图", "mindmap", "mermaid",
    "python", "java", "代码", "编程", "语法", "翻译", "阅读",
]

# 明确违规模式（二级语义校验硬拦截）
VIOLATION_PATTERNS = [
    (r"色情|裸体|淫秽", "包含低俗色情内容"),
    (r"制毒|贩毒|枪支|爆炸物制作", "包含违法危险内容"),
    (r"赌博|六合彩|网赌", "包含赌博相关内容"),
    (r"暴力恐怖|恐怖袭击", "包含暴力恐怖内容"),
    (r"反动|颠覆.*政权", "包含敏感政治内容"),
]


def is_educational_content(content: str, topic: str | None = None) -> bool:
    """判断是否为正常学科学习类内容。"""
    text = f"{content} {topic or ''}"
    if len(content.strip()) < 15:
        return True
    marker_hits = sum(1 for m in EDUCATIONAL_MARKERS if m in text)
    if marker_hits >= 2:
        return True
    # Markdown / 结构化教学内容
    if re.search(r"#{1,3}\s|```|\$\$|步骤\s*\d|选项[A-D]", content):
        return True
    return False


def check_semantic_violations(content: str) -> list[str]:
    """二级语义违规检测，返回具体原因列表。"""
    reasons: list[str] = []
    for pattern, reason in VIOLATION_PATTERNS:
        if re.search(pattern, content, re.I):
            reasons.append(reason)
    return reasons


def format_audit_failure_message(
    *,
    word_labels: list[str] | None = None,
    semantic_reasons: list[str] | None = None,
    fact_issues: list[str] | None = None,
    risk_level: int = 0,
) -> str:
    """生成面向用户的审核失败原因文案。"""
    parts: list[str] = []
    if word_labels:
        cats = [l for l in word_labels if not l.startswith("warn:")]
        if cats:
            parts.append(f"包含敏感词汇（{', '.join(set(cats))}）")
    if semantic_reasons:
        parts.extend(semantic_reasons)
    if fact_issues:
        for issue in fact_issues[:3]:
            if issue not in parts:
                parts.append(issue)
    if risk_level >= 3 and not parts:
        parts.append("内容存在严重事实错误或编造信息")
    elif risk_level == 2 and not parts:
        parts.append("内容存在中度存疑，需人工复核")
    if not parts:
        parts.append("内容偏离学习主题或不符合安全规范")
    return "；".join(parts)
