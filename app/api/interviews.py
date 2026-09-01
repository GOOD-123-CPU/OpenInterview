"""
OpenInterview - 面试管理 API

包含管理端 CRUD 与候选人端面试流程（token 鉴权）两类接口。
"""
import secrets
import string
import time
from datetime import datetime
from io import BytesIO

from flask import Blueprint, jsonify, request, send_file

from config import config
from constants import InterviewStatus
from database import get_db
from security import admin_required, get_client_ip, rate_limiter
from services.asr import transcribe_audio

interviews_bp = Blueprint("interviews", __name__)


def _generate_token(length: int = None) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length or config.TOKEN_LENGTH))


# ==================== 管理端 ====================

@interviews_bp.route("/api/interviews", methods=["GET"])
@admin_required
def get_interviews():
    conn = get_db(row_factory=True)
    rows = [dict(r) for r in conn.execute(
        "SELECT id, candidate_id, interviewer, start_time, status, is_passed, token FROM interviews"
    ).fetchall()]
    conn.close()
    return jsonify(rows)


@interviews_bp.route("/api/interviews", methods=["POST"])
@admin_required
def create_interview():
    data = request.json or {}
    for key in ("candidate_id", "interviewer", "start_time", "status", "is_passed"):
        if key not in data:
            return jsonify({"status": "error", "message": f"缺少字段: {key}"}), 400

    token = _generate_token()
    conn = get_db()
    conn.execute(
        """INSERT INTO interviews (candidate_id, interviewer, start_time, status, is_passed, token)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (data["candidate_id"], data["interviewer"], data["start_time"],
         data["status"], data["is_passed"], token),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "token": token})


@interviews_bp.route("/api/interviews/<int:interview_id>", methods=["PUT"])
@admin_required
def update_interview(interview_id):
    data = request.json or {}
    token = _generate_token()
    conn = get_db()
    conn.execute(
        """UPDATE interviews SET candidate_id=?, interviewer=?, start_time=?, status=?, is_passed=?, token=?
           WHERE id=?""",
        (data.get("candidate_id"), data.get("interviewer"), data.get("start_time"),
         data.get("status"), data.get("is_passed"), token, interview_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "token": token})


@interviews_bp.route("/api/interviews/<int:interview_id>/report", methods=["GET"])
@admin_required
def download_interview_report(interview_id):
    conn = get_db(row_factory=True)
    row = conn.execute(
        "SELECT id, report_content FROM interviews WHERE id = ?", (interview_id,)
    ).fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "面试不存在"}), 404
    if not row["report_content"]:
        return jsonify({"error": "面试报告尚未生成"}), 404

    return send_file(
        BytesIO(row["report_content"]),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"interview_report_{row['id']}.pdf",
    )


@interviews_bp.route("/api/interviews/<int:interview_id>", methods=["DELETE"])
@admin_required
def delete_interview(interview_id):
    """删除面试及其关联问题（含音频/报告 BLOB，避免残留孤儿数据）"""
    conn = get_db()
    conn.execute("DELETE FROM interview_questions WHERE interview_id = ?", (interview_id,))
    conn.execute("DELETE FROM interviews WHERE id = ?", (interview_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})


# ==================== 候选人端（token 鉴权） ====================

def _get_interview_by_token(conn, token):
    return conn.execute("SELECT id, status, start_time FROM interviews WHERE token = ?", (token,)).fetchone()


def _check_start_time(interview):
    """面试开始时间校验：允许提前 5 分钟进入，未到时间拒绝作答。返回错误响应或 None"""
    if interview["start_time"] and time.time() < interview["start_time"] - 300:
        return jsonify({"error": "面试尚未到预定开始时间，请在约定时间进入"}), 403
    return None


@interviews_bp.route("/api/interview/<token>/info", methods=["GET"])
def get_interview_info(token):
    conn = get_db(row_factory=True)
    row = conn.execute(
        """
        SELECT i.id, i.question_count, i.voice_reading, i.start_time, i.status,
               c.name AS candidate_name, c.email AS candidate_email,
               p.name AS position_name, p.requirements
        FROM interviews i
        JOIN candidates c ON i.candidate_id = c.id
        JOIN positions p ON c.position_id = p.id
        WHERE i.token = ?
        """,
        (token,),
    ).fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "面试不存在"}), 404

    result = dict(row)
    result["time"] = (
        datetime.fromtimestamp(result["start_time"]).strftime("%Y年%m月%d日 %H:%M")
        if result["start_time"] else "未设置时间"
    )
    return jsonify({
        "interview_id": result["id"],
        "time": result["time"],
        "position": result["position_name"],
        "candidate": result["candidate_name"],
        "status": result["status"],
        "question_count": result["question_count"],
        "voice_reading": result["voice_reading"],
    })


@interviews_bp.route("/api/interview/<token>/get_question", methods=["GET"])
def get_next_question(token):
    current_question_id = request.args.get("current_id", type=int, default=0)

    conn = get_db(row_factory=True)
    interview = _get_interview_by_token(conn, token)
    if not interview:
        conn.close()
        return jsonify({"id": 0, "text": "面试无效"}), 404

    # 面试开始时间校验（未到预定时间不允许获取题目）
    early = _check_start_time(interview)
    if early is not None:
        conn.close()
        return early

    if current_question_id == 0:
        row = conn.execute(
            """SELECT id, question AS text, dimension, difficulty, question_type
               FROM interview_questions WHERE interview_id = ? ORDER BY id ASC LIMIT 1""",
            (interview["id"],),
        ).fetchone()
    else:
        row = conn.execute(
            """SELECT id, question AS text, dimension, difficulty, question_type
               FROM interview_questions WHERE interview_id = ? AND id > ? ORDER BY id ASC LIMIT 1""",
            (interview["id"], current_question_id),
        ).fetchone()
    conn.close()

    if not row:
        return jsonify({"id": 0, "text": "面试已完成"})
    data = dict(row)
    # dimension 为空时给默认值（兼容 v1 数据）
    data.setdefault("dimension", "综合")
    return jsonify(data)


@interviews_bp.route("/api/interview/<token>/submit_answer", methods=["POST"])
def submit_answer(token):
    conn = get_db(row_factory=True)
    interview = _get_interview_by_token(conn, token)
    if not interview:
        conn.close()
        return jsonify({"error": "面试不存在"}), 404

    # 面试开始时间校验（未到预定时间不允许作答）
    early = _check_start_time(interview)
    if early is not None:
        conn.close()
        return early

    # 限流：每面试每分钟最多 6 次提交（正常节奏足够，防脚本灌音频）
    if not rate_limiter.check("submit_answer", token, limit=6, window_seconds=60):
        conn.close()
        return jsonify({"error": "提交过于频繁，请稍候再试"}), 429

    question_id = request.form.get("question_id")
    audio_answer = request.files.get("audio_answer")
    if not question_id or not audio_answer:
        conn.close()
        return jsonify({"error": "缺少必要参数"}), 400

    audio_data = audio_answer.read()
    conn.close()  # 转写耗时，先释放连接再调模型

    # Whisper 语音转写（支持 webm/ogg/wav/mp3 等 ffmpeg 兼容格式）
    audio_text = transcribe_audio(audio_data)

    conn = get_db()
    conn.execute(
        """UPDATE interview_questions
           SET answer_audio = ?, answer_text = ?, answered_at = ?
           WHERE id = ? AND interview_id = ?""",
        (audio_data, audio_text, int(time.time()), question_id, interview["id"]),
    )

    next_question = conn.execute(
        """SELECT id, question, dimension, difficulty, question_type FROM interview_questions
           WHERE interview_id = ? AND id > ? ORDER BY id ASC LIMIT 1""",
        (interview["id"], question_id),
    ).fetchone()
    conn.row_factory = None

    if next_question is None:
        # 已无下一题：检查是否全部作答，是则将状态置为「面试完毕」
        stats = conn.execute(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN answered_at IS NOT NULL THEN 1 ELSE 0 END) AS answered
               FROM interview_questions WHERE interview_id = ?""",
            (interview["id"],),
        ).fetchone()
        if stats and stats[0] and stats[0] == stats[1]:
            conn.execute(
                "UPDATE interviews SET status = ?, end_time = ? WHERE id = ?",
                (int(InterviewStatus.COMPLETED), int(time.time()), interview["id"]),
            )
        result = {
            "status": "success",
            "message": "答案已提交",
            "next_question": {"id": 0, "text": "面试已完成"},
        }
    else:
        result = {
            "status": "success",
            "message": "答案已提交",
            "next_question": {
                "id": next_question[0],
                "text": next_question[1],
                "dimension": next_question[2] or "综合",
                "difficulty": next_question[3] or "medium",
                "question_type": next_question[4] or "technical",
            },
        }

    conn.commit()
    conn.close()
    return jsonify(result)


@interviews_bp.route("/api/interview/<token>/toggle_voice_reading", methods=["POST"])
def toggle_voice_reading(token):
    data = request.json or {}
    enabled = bool(data.get("enabled", False))

    conn = get_db()
    conn.execute(
        "UPDATE interviews SET voice_reading = ? WHERE token = ?",
        (1 if enabled else 0, token),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "voice_reading": enabled})
