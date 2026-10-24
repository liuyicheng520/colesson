"""学科分类工具 — 判断编程类 vs 非编程类主题。"""

from __future__ import annotations

import re

# 编程 / 计算机类关键词
PROGRAMMING_KEYWORDS = [
    "python", "java", "c++", "c语言", "javascript", "typescript", "go语言", "rust",
    "编程", "代码", "算法", "数据结构", "计算机", "软件工程", "前端", "后端",
    "机器学习", "深度学习", "神经网络", "人工智能", "ai", "sql", "数据库",
    "html", "css", "react", "vue", "spring", "docker", "linux", "api",
    "函数式编程", "面向对象", "编译", "调试", "git",
]

# 非编程类学科关键词（用于强化判断）
NON_PROGRAMMING_SUBJECTS = {
    "english": ["英语", "英文", "语法", "词汇", "翻译", "听力", "口语", "写作", "reading", "grammar"],
    "math": ["数学", "微积分", "线性代数", "概率", "统计", "几何", "方程", "证明", "函数"],
    "physics": ["物理", "力学", "电磁", "光学", "量子"],
    "chemistry": ["化学", "有机", "无机", "分子"],
    "biology": ["生物", "细胞", "遗传"],
    "history": ["历史", "朝代", "文明"],
    "literature": ["语文", "文学", "诗词", "古文"],
}


def detect_subject_category(topic: str, goal: str | None = None) -> str:
    """
    返回学科类别：
    - programming: 编程/计算机类 → 实战演练（代码）
    - english / math / physics / ... : 非编程类 → 实战演练
    - general: 通用（默认非编程）
    """
    text = f"{topic} {goal or ''}".lower()

    prog_score = sum(1 for kw in PROGRAMMING_KEYWORDS if kw.lower() in text)
    if prog_score >= 1:
        return "programming"

    for subject, keywords in NON_PROGRAMMING_SUBJECTS.items():
        if any(kw.lower() in text for kw in keywords):
            return subject

    # 含代码相关符号但非明确编程主题 → 仍归 general
    if re.search(r"\b(def |class |import |function |void |int main)", text):
        return "programming"

    return "general"


def is_programming_subject(topic: str, goal: str | None = None) -> bool:
    return detect_subject_category(topic, goal) == "programming"


def code_module_label(topic: str, goal: str | None = None) -> str:
    return "实战演练"
