"""结构化问卷 — 6 题对应 6 维，选项预置标签与分值权重。"""

from typing import Any

QUESTIONNAIRE_ITEMS: list[dict[str, Any]] = [
    {
        "dimension_code": "D1",
        "question": "你目前在专业领域的知识掌握程度如何？",
        "options": [
            {"id": "d1_1", "label": "刚入门，需要系统学习基础", "value": {"domain": "通用", "level": 1, "gaps": ["基础概念"]}, "score": 20},
            {"id": "d1_2", "label": "了解基础，能完成简单任务", "value": {"domain": "通用", "level": 2, "gaps": ["实践应用"]}, "score": 40},
            {"id": "d1_3", "label": "掌握核心知识，能独立解决问题", "value": {"domain": "通用", "level": 3, "gaps": ["进阶专题"]}, "score": 60},
            {"id": "d1_4", "label": "较为熟练，能处理复杂问题", "value": {"domain": "通用", "level": 4, "gaps": ["前沿拓展"]}, "score": 80},
            {"id": "d1_5", "label": "精通该领域，可指导他人", "value": {"domain": "通用", "level": 5, "gaps": []}, "score": 100},
        ],
    },
    {
        "dimension_code": "D2",
        "question": "你更偏好的知识吸收方式是什么？",
        "options": [
            {"id": "d2_1", "label": "图表、视频等可视化材料", "value": {"style": "visual", "score": 0.85}, "score": 85},
            {"id": "d2_2", "label": "文字阅读与笔记整理", "value": {"style": "verbal", "score": 0.85}, "score": 85},
            {"id": "d2_3", "label": "按步骤循序渐进学习", "value": {"style": "sequential", "score": 0.85}, "score": 85},
            {"id": "d2_4", "label": "先把握整体框架再深入", "value": {"style": "global", "score": 0.85}, "score": 85},
        ],
    },
    {
        "dimension_code": "D3",
        "question": "你当前最主要的学习目标类型是？",
        "options": [
            {"id": "d3_1", "label": "通过考试/认证（高优先级）", "value": {"goal": "考试认证", "deadline": None, "priority": "high"}, "score": 90},
            {"id": "d3_2", "label": "完成课程/项目作业", "value": {"goal": "课程项目", "deadline": None, "priority": "mid"}, "score": 70},
            {"id": "d3_3", "label": "提升职业技能", "value": {"goal": "职业提升", "deadline": None, "priority": "high"}, "score": 85},
            {"id": "d3_4", "label": "兴趣拓展，无硬性期限", "value": {"goal": "兴趣学习", "deadline": None, "priority": "low"}, "score": 50},
        ],
    },
    {
        "dimension_code": "D4",
        "question": "你的相关学习经历大致是？",
        "options": [
            {"id": "d4_1", "label": "几乎零基础，刚开始接触", "value": {"courses": [], "completedTopics": [], "totalHours": 10}, "score": 15},
            {"id": "d4_2", "label": "学过 1~2 门入门课程", "value": {"courses": ["入门课"], "completedTopics": ["基础"], "totalHours": 40}, "score": 40},
            {"id": "d4_3", "label": "有系统学习经历，完成过多门课程", "value": {"courses": ["基础课", "进阶课"], "completedTopics": ["基础", "进阶"], "totalHours": 120}, "score": 70},
            {"id": "d4_4", "label": "长期持续学习，累计投入较多", "value": {"courses": ["多门课程"], "completedTopics": ["基础", "进阶", "实践"], "totalHours": 300}, "score": 90},
        ],
    },
    {
        "dimension_code": "D5",
        "question": "你常见的学习薄弱点类型是？",
        "options": [
            {"id": "d5_1", "label": "概念理解不透彻", "value": {"weakPoints": [{"topic": "概念理解", "errorType": "concept", "frequency": 3}]}, "score": 60},
            {"id": "d5_2", "label": "计算/操作粗心失误", "value": {"weakPoints": [{"topic": "计算操作", "errorType": "careless", "frequency": 3}]}, "score": 55},
            {"id": "d5_3", "label": "解题方法不会用", "value": {"weakPoints": [{"topic": "方法应用", "errorType": "method", "frequency": 3}]}, "score": 65},
            {"id": "d5_4", "label": "暂无明显薄弱点", "value": {"weakPoints": []}, "score": 80},
        ],
    },
    {
        "dimension_code": "D6",
        "question": "你偏好的学习节奏是？",
        "options": [
            {"id": "d6_1", "label": "快节奏，单次 20 分钟左右", "value": {"pace": "fast", "sessionMinutes": 20}, "score": 85},
            {"id": "d6_2", "label": "中等节奏，单次 40 分钟左右", "value": {"pace": "medium", "sessionMinutes": 40}, "score": 75},
            {"id": "d6_3", "label": "稳扎稳打，单次 60 分钟以上", "value": {"pace": "slow", "sessionMinutes": 60}, "score": 70},
            {"id": "d6_4", "label": "碎片化学习，每次 10~15 分钟", "value": {"pace": "fast", "sessionMinutes": 15}, "score": 65},
        ],
    },
]
