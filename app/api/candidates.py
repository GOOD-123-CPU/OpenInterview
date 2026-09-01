"""
OpenInterview - 候选人管理 API

列表/下载/删除需管理员会话；创建（简历投递场景）保留公开但限流。
"""
from io import BytesIO

from flask import Blueprint, jsonify, request, send_file

from database import get_db
from security import admin_required, get_client_ip, rate_limiter

candidates_bp = Blueprint("candidates", __name__)


@candidates_bp.route("/api/candidates", methods=["GET"])
@admin_required
def get_candidates():
    conn = get_db(row_factory=True)
    rows = [dict(r) for r in conn.execute(
        "SELECT id, position_id, name, email FROM candidates"
    ).fetchall()]
    conn.close()
    return jsonify(rows)


@candidates_bp.route("/api/candidates", methods=["POST"])
def create_candidate():
    # 公开接口（便于对接招聘渠道），但限流防滥用：每 IP 每小时 30 次
    if not rate_limiter.check("candidate_create", get_client_ip(), limit=30, window_seconds=3600):
        return jsonify({"status": "error", "message": "请求过于频繁，请稍后再试"}), 429

    data = request.form
    if not data.get("position_id") or not data.get("name"):
        return jsonify({"status": "error", "message": "position_id 和 name 为必填"}), 400

    # 大小限制：简历文件最大 10MB
    resume_content = request.files["resume_content"].read() if "resume_content" in request.files else None
    if resume_content and len(resume_content) > 10 * 1024 * 1024:
        return jsonify({"status": "error", "message": "简历文件不能超过 10MB"}), 413
    resume_binary = bytes(resume_content) if resume_content is not None else None

    conn = get_db()
    conn.execute(
        "INSERT INTO candidates (position_id, name, email, resume_content) VALUES (?, ?, ?, ?)",
        (data["position_id"], data["name"], data.get("email"), resume_binary),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})


@candidates_bp.route("/api/candidates/<int:candidate_id>/resume", methods=["GET"])
@admin_required
def download_resume(candidate_id):
    conn = get_db(row_factory=True)
    row = conn.execute(
        "SELECT resume_content FROM candidates WHERE id=?", (candidate_id,)
    ).fetchone()
    conn.close()

    if row and row["resume_content"]:
        return send_file(
            BytesIO(row["resume_content"]),
            download_name=f"resume_{candidate_id}.pdf",
            as_attachment=True,
        )
    return jsonify({"error": "简历不存在"}), 404


@candidates_bp.route("/api/candidates/<int:candidate_id>", methods=["DELETE"])
@admin_required
def delete_candidate(candidate_id):
    """删除候选人及其关联的面试与问题记录（级联清理，避免孤儿数据）"""
    conn = get_db()
    conn.execute(
        "DELETE FROM interview_questions WHERE interview_id IN "
        "(SELECT id FROM interviews WHERE candidate_id = ?)",
        (candidate_id,),
    )
    conn.execute("DELETE FROM interviews WHERE candidate_id = ?", (candidate_id,))
    conn.execute("DELETE FROM candidates WHERE id=?", (candidate_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})
