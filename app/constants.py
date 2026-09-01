"""
OpenInterview - 业务常量与状态定义

面试状态机:
    0 未开始 -> 1 试题已备好 -> 2 面试进行中 -> 3 面试完毕 -> 4 报告已生成
"""
from enum import IntEnum


class InterviewStatus(IntEnum):
    NOT_STARTED = 0
    READY = 1
    IN_PROGRESS = 2
    COMPLETED = 3
    REPORT_GENERATED = 4


class PositionStatus(IntEnum):
    NOT_STARTED = 0
    ACTIVE = 1
    CLOSED = 2


# 各状态对应的中文文案（管理端展示用）
INTERVIEW_STATUS_TEXT = {
    0: "未开始",
    1: "试题已备好",
    2: "面试进行中",
    3: "面试完毕",
    4: "面试报告已生成",
}

POSITION_STATUS_TEXT = {
    0: "未启动",
    1: "进行中",
    2: "已完成",
}

# 单题满分（与 AI 评估口径统一为 100 分制）
QUESTION_FULL_SCORE = 100
