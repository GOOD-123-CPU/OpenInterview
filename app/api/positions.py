"""
OpenInterview - 岗位管理 API

读接口公开（面试页需要岗位信息），写接口需管理员会话。
"""
import time

from flask import Blueprint, jsonify, request

from database import get_db
from security import admin_required

positions_bp = Blueprint("positions", __name__)


@positions_bp.route("/api/positions", methods=["GET"])
def get_positions():
    conn = get_db(row_factory=True)
    rows = [dict(r) for r in conn.execute("SELECT * FROM positions").fetchall()]
    conn.close()
    return jsonify(rows)


@positions_bp.route("/api/positions", methods=["POST"])
@admin_required
def create_position():
    data = request.json or {}
    required = ("name", "requirements", "responsibilities", "quantity", "status", "recruiter")
    missing = [k for k in required if k not in data]
    if missing:
        return jsonify({"status": "error", "message": f"缺少字段: {', '.join(missing)}"}), 400

    conn = get_db()
    conn.execute(
        """INSERT INTO positions (name, requirements, responsibilities, quantity, status, created_at, recruiter)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            data["name"], data["requirements"], data["responsibilities"],
            data["quantity"], data["status"], int(time.time()), data["recruiter"],
        ),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})


@positions_bp.route("/api/positions/<int:position_id>", methods=["PUT"])
@admin_required
def update_position(position_id):
    data = request.json or {}
    conn = get_db()
    conn.execute(
        """UPDATE positions SET name=?, requirements=?, responsibilities=?, quantity=?, status=?, recruiter=?
           WHERE id=?""",
        (
            data.get("name"), data.get("requirements"), data.get("responsibilities"),
            data.get("quantity"), data.get("status"), data.get("recruiter"), position_id,
        ),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})


@positions_bp.route("/api/positions/<int:position_id>", methods=["DELETE"])
@admin_required
def delete_position(position_id):
    # 级联清理：该岗位下的候选人 → 面试 → 面试问题
    conn = get_db()
    conn.execute(
        "DELETE FROM interview_questions WHERE interview_id IN "
        "(SELECT i.id FROM interviews i JOIN candidates c ON i.candidate_id = c.id WHERE c.position_id = ?)",
        (position_id,),
    )
    conn.execute(
        "DELETE FROM interviews WHERE candidate_id IN (SELECT id FROM candidates WHERE position_id = ?)",
        (position_id,),
    )
    conn.execute("DELETE FROM candidates WHERE position_id = ?", (position_id,))
    conn.execute("DELETE FROM positions WHERE id=?", (position_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})
