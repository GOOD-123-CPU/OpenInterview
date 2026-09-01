"""
OpenInterview - 面试问题生成服务（v2）

v2 增强：
- 结构化出题：每题带能力维度（dimension）、难度（difficulty）、题型（question_type）
- 题型覆盖：技术深度 / 项目复盘 / 系统设计 / 行为素质，避免题目同质化
- 追问建议：每题附带 followup 提示，供报告生成追问建议
"""
import json
from datetime import datetime

from config import config
from constants import InterviewStatus
from database import get_db
from prompt_registry import render_prompt
from services.llm import chat_json
from services.resume import extract_text_from_resume
from services.webhook import EVENT_QUESTIONS_GENERATED, emit_event

QUESTION_FORMAT_EXAMPLE = [
    {
        "question": "请介绍一个你主导的、最能体现岗位核心能力要求的项目，并说明你在其中的关键决策。",
        "score_standard": "项目真实性与深度30分；技术决策合理性40分；量化结果表达30分",
        "dimension": "项目复盘",
        "difficulty": "medium",
        "question_type": "project",
        "followup": "如果时间或资源减半，你会如何调整方案？"
    }
]


def generate_questions(resume_content, position_name, requirements, responsibilities) -> list:
    """调用 LLM 生成结构化面试问题列表"""
    resume_text = extract_text_from_resume(resume_content)
    # 控制上下文长度，防止超长简历撑爆 token
    if len(resume_text) > 8000:
        resume_text = resume_text[:8000] + "…（简历过长已截断）"
    print(f"[questions] 简历文本长度: {len(resume_text)}")

    system_prompt, user_prompt = render_prompt(
        "question_generation",
        position_name=position_name,
        requirements=requirements or "未提供",
        responsibilities=responsibilities or "未提供",
        resume_text=resume_text,
        question_count=config.QUESTION_COUNT,
        format_example=json.dumps(QUESTION_FORMAT_EXAMPLE, ensure_ascii=False),
    )

    result = chat_json(system_prompt, user_prompt)

    questions = result.get("questions") if isinstance(result, dict) else result
    if not isinstance(questions, list) or not questions:
        raise ValueError(f"LLM 返回的问题列表为空或格式不符: {result}")

    valid_types = {"technical", "project", "design", "behavior"}
    valid_difficulty = {"easy", "medium", "hard"}
    normalized = []
    for q in questions:
        if not isinstance(q, dict) or not q.get("question"):
            continue
        qtype = str(q.get("question_type", "technical")).lower()
        normalized.append(
            {
                "question": str(q["question"]).strip(),
                "score_standard": str(q.get("score_standard", "综合评估，满分100分")).strip(),
                "dimension": str(q.get("dimension", "综合")).strip(),
                "difficulty": qtype if qtype in valid_difficulty else str(q.get("difficulty", "medium")).lower() if q.get("difficulty") else "medium",
                "question_type": qtype if qtype in valid_types else "technical",
                "followup": str(q.get("followup", "")).strip(),
            }
        )
    # difficulty 字段规范化修正（上面表达式可能被 question_type 污染）
    for q in normalized:
        if q["difficulty"] not in valid_difficulty:
            q["difficulty"] = "medium"
    if not normalized:
        raise ValueError("LLM 返回的问题均缺少 question 字段")
    return normalized


def save_questions(interview_id: int, questions: list) -> None:
    """保存结构化问题并更新面试状态为「试题已备好」"""
    conn = get_db()
    try:
        cursor = conn.cursor()
        for q in questions:
            score_standard = q["score_standard"]
            if isinstance(score_standard, dict):
                score_standard = json.dumps(score_standard, ensure_ascii=False)
            cursor.execute(
                """INSERT INTO interview_questions
                   (interview_id, question, score_standard, question_type, difficulty, dimension)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    interview_id, q["question"], score_standard,
                    q.get("question_type", "technical"),
                    q.get("difficulty", "medium"),
                    q.get("dimension", "综合"),
                ),
            )
        cursor.execute(
            "UPDATE interviews SET status = ?, question_count = ? WHERE id = ?",
            (int(InterviewStatus.READY), len(questions), interview_id),
        )
        conn.commit()
    finally:
        conn.close()


def process_pending_interviews() -> None:
    """扫描所有未开始的面试，逐一生成问题（单场失败不影响其他场次）"""
    print(f"[questions] [{datetime.now():%Y-%m-%d %H:%M:%S}] 开始处理未开始的面试...")

    conn = get_db()
    pending = conn.execute(
        "SELECT id, candidate_id FROM interviews WHERE status = ?",
        (int(InterviewStatus.NOT_STARTED),),
    ).fetchall()
    conn.close()

    if not pending:
        print("[questions] 没有未开始的面试需要处理")
        return

    print(f"[questions] 找到 {len(pending)} 个待处理的面试")

    for interview_id, candidate_id in pending:
        try:
            conn = get_db()
            candidate = conn.execute(
                "SELECT id, name, email, resume_content, position_id FROM candidates WHERE id = ?",
                (candidate_id,),
            ).fetchone()
            if not candidate:
                print(f"[questions] 找不到候选人 {candidate_id}，跳过面试 {interview_id}")
                conn.close()
                continue

            position = conn.execute(
                "SELECT id, name, requirements, responsibilities FROM positions WHERE id = ?",
                (candidate[4],),
            ).fetchone()
            conn.close()
            if not position:
                print(f"[questions] 找不到岗位 {candidate[4]}，跳过面试 {interview_id}")
                continue

            print(f"[questions] 为面试 {interview_id}（候选人 {candidate[1]}，岗位 {position[1]}）生成问题")
            questions = generate_questions(candidate[3], position[1], position[2], position[3])
            save_questions(interview_id, questions)
            print(f"[questions] 面试 {interview_id} 已生成 {len(questions)} 个问题")

            emit_event(EVENT_QUESTIONS_GENERATED, {
                "interview_id": interview_id,
                "candidate": candidate[1],
                "position": position[1],
                "question_count": len(questions),
            })
        except Exception as e:
            print(f"[questions] 处理面试 {interview_id} 失败: {e}")
