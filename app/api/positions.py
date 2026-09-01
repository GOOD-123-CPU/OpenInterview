"""
OpenInterview - 岗位管理 API
"""
import time

from flask import Blueprint, jsonify, request

from database import get_db

positions_bp = Blueprint("positions", __name__)


@positions_bp.route("/api/positions", methods=["GET"])
def get_positions():
    conn = get_db(row_factory=True)
    rows = [dict(r) for r in conn.execute("SELECT * FROM positions").fetchall()]
    conn.close()
    return jsonify(rows)


@positions_bp.route("/api/positions", methods=["POST"])
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
def delete_position(position_id):
    conn = get_db()
    conn.execute("DELETE FROM positions WHERE id=?", (position_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})
