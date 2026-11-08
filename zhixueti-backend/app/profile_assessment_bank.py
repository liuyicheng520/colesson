"""
自适应测评题库 — 简化 IRT 参数
每题: difficulty b ∈ [-2,2], discrimination a ∈ [0.5,2], topic 知识点
"""

from typing import Any

ASSESSMENT_QUESTIONS: list[dict[str, Any]] = [
    {"id": "q01", "topic": "基础概念", "stem": "下列哪项最能体现「变量」在编程中的含义？", "options": ["存储数据的命名容器", "程序的输出结果", "用户界面元素", "网络协议"], "answer": 0, "difficulty": -1.5, "discrimination": 1.2},
    {"id": "q02", "topic": "基础概念", "stem": "算法的时间复杂度主要描述什么？", "options": ["代码行数", "执行时间随输入规模的增长趋势", "内存占用大小", "编译速度"], "answer": 1, "difficulty": -1.0, "discrimination": 1.0},
    {"id": "q03", "topic": "数据结构", "stem": "栈（Stack）的典型特点是？", "options": ["先进先出", "后进先出", "随机访问", "双向遍历"], "answer": 1, "difficulty": -0.5, "discrimination": 1.1},
    {"id": "q04", "topic": "数据结构", "stem": "二叉搜索树的中序遍历结果是？", "options": ["随机顺序", "升序排列", "降序排列", "层序排列"], "answer": 1, "difficulty": 0.0, "discrimination": 1.3},
    {"id": "q05", "topic": "算法", "stem": "快速排序的平均时间复杂度是？", "options": ["O(n)", "O(n log n)", "O(n²)", "O(log n)"], "answer": 1, "difficulty": 0.3, "discrimination": 1.2},
    {"id": "q06", "topic": "算法", "stem": "动态规划的核心思想是？", "options": ["贪心选择", "分而治之", "记忆化避免重复子问题", "随机搜索"], "answer": 2, "difficulty": 0.5, "discrimination": 1.4},
    {"id": "q07", "topic": "数据库", "stem": "关系型数据库中，主键的作用是？", "options": ["加密数据", "唯一标识每一行记录", "加速所有查询", "存储图片"], "answer": 1, "difficulty": -0.3, "discrimination": 0.9},
    {"id": "q08", "topic": "网络", "stem": "HTTP 协议默认使用的端口是？", "options": ["21", "25", "80", "443"], "answer": 2, "difficulty": -0.8, "discrimination": 0.8},
    {"id": "q09", "topic": "操作系统", "stem": "进程与线程的主要区别是？", "options": ["进程更轻量", "线程共享进程资源", "线程不能并发", "进程不能通信"], "answer": 1, "difficulty": 0.8, "discrimination": 1.3},
    {"id": "q10", "topic": "软件工程", "stem": "单元测试的主要目的是？", "options": ["测试整个系统", "验证最小代码单元的正确性", "压力测试", "用户验收"], "answer": 1, "difficulty": 0.2, "discrimination": 1.0},
    {"id": "q11", "topic": "机器学习", "stem": "过拟合（Overfitting）是指？", "options": ["模型在训练集和测试集都差", "模型在训练集好但泛化差", "模型训练太慢", "数据量太大"], "answer": 1, "difficulty": 1.0, "discrimination": 1.5},
    {"id": "q12", "topic": "机器学习", "stem": "梯度下降中，学习率过大可能导致？", "options": ["收敛更快", "震荡或不收敛", "过拟合消失", "无需迭代"], "answer": 1, "difficulty": 1.2, "discrimination": 1.4},
    {"id": "q13", "topic": "高级算法", "stem": "Dijkstra 算法不能处理哪种图？", "options": ["有向图", "无向图", "带负权边的图", "稀疏图"], "answer": 2, "difficulty": 1.5, "discrimination": 1.6},
    {"id": "q14", "topic": "高级数据结构", "stem": "红黑树保证的最坏查找复杂度是？", "options": ["O(1)", "O(log n)", "O(n)", "O(n log n)"], "answer": 1, "difficulty": 1.8, "discrimination": 1.5},
    {"id": "q15", "topic": "分布式", "stem": "CAP 定理中，分区容忍性（P）意味着？", "options": ["系统永不宕机", "网络分区时系统仍能运行", "强一致性", "无延迟"], "answer": 1, "difficulty": 2.0, "discrimination": 1.3},
]

# 默认维度标签（测评完成后补充 D2~D6）
ASSESSMENT_DEFAULT_DIMENSIONS: dict[str, dict] = {
    "D2": {"style": "sequential", "score": 0.7},
    "D3": {"goal": "知识水平提升", "deadline": None, "priority": "mid"},
    "D4": {"courses": [], "completedTopics": [], "totalHours": 0},
    "D5": {"weakPoints": []},
    "D6": {"pace": "medium", "sessionMinutes": 40},
}
