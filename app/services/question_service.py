"""
OpenInterview - 面试问题生成服务

职责：为「未开始(status=0)」的面试生成问题并写入数据库，状态置为 1（试题已备好）。
由定时任务 worker 周期性调用。
"""
import json

from config import config
from constants import InterviewStatus
from database import get_db
from services.llm import chat_json
from services.resume import extract_text_from_resume

QUESTION_FORMAT_EXAMPLE = [
    {"question": "请介绍一下你的专业背景和技能", "score_standard": "清晰度25分，相关性25分，深度50分"},
    {"question": "描述一个你解决过的技术挑战", "score_standard": "复杂度30分，解决方案40分，结果30分"},
]


def generate_questions(resume_content, position_name, requirements, responsibilities) -> list:
    """调用 LLM 根据简历 + 岗位信息生成面试问题，返回问题列表"""
    resume_text = extract_text_from_resume(resume_content)
    print(f"[questions] 简历文本长度: {len(resume_text)}")

    system_prompt = (
        "你是一名专业的招聘面试官。请根据岗位要求和候选人简历生成针对性的技术面试问题，"
        "每个问题附带评分标准，返回标准的 JSON 格式。"
    )
    user_prompt = (
        f"岗位名称: {position_name}\n"
        f"岗位要求: {requirements or '未提供'}\n"
        f"岗位职责: {responsibilities or '未提供'}\n"
        f"候选人简历: {resume_text}\n\n"
        f"请生成 {config.QUESTION_COUNT} 个面试问题和评分标准，"
        f"JSON 格式参考 {json.dumps(QUESTION_FORMAT_EXAMPLE, ensure_ascii=False)}。"
        f"每个问题满分 {100} 分（单题 0-100 分制），"
        '返回 JSON 对象，格式为 {"questions": [{"question": "...", "score_standard": "..."}]}。'
    )

    result = chat_json(system_prompt, user_prompt)

    # 兼容两种返回形态：{"questions": [...]} 或直接返回 [...]
    questions = result.get("questions") if isinstance(result, dict) else result
    if not isinstance(questions, list) or not questions:
        raise ValueError(f"LLM 返回的问题列表为空或格式不符: {result}")

    # 规范化字段
    normalized = []
    for q in questions:
        if not isinstance(q, dict) or not q.get("question"):
            continue
        normalized.append(
            {
                "question": str(q["question"]).strip(),
                "score_standard": str(q.get("score_standard", "综合评估 100 分制")).strip(),
            }
        )
    if not normalized:
        raise ValueError("LLM 返回的问题均缺少 question 字段")
    return normalized


def save_questions(interview_id: int, questions: list) -> None:
    """保存问题并更新面试状态为「试题已备好」"""
    conn = get_db()
    try:
        cursor = conn.cursor()
        for q in questions:
            score_standard = q["score_standard"]
            if isinstance(score_standard, dict):
                score_standard = json.dumps(score_standard, ensure_ascii=False)
            cursor.execute(
                "INSERT INTO interview_questions (interview_id, question, score_standard) VALUES (?, ?, ?)",
                (interview_id, q["question"], score_standard),
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
    print(f"[questions] [{__import__('datetime').datetime.now():%Y-%m-%d %H:%M:%S}] 开始处理未开始的面试...")

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
        except Exception as e:
            print(f"[questions] 处理面试 {interview_id} 失败: {e}")
