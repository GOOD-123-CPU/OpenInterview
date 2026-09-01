"""
OpenInterview - 认证与系统 API

- POST /api/auth/login     管理员登录（限流保护）
- POST /api/auth/logout    退出登录（前端丢弃令牌即可，此接口便于审计）
- GET  /api/auth/me        会话有效性检查
- PUT  /api/auth/password  修改管理员口令
- GET  /api/stats/dashboard 管理端数据看板
"""
from flask import Blueprint, jsonify, request

from database import get_db
from security import (
    admin_required,
    check_admin_password,
    get_client_ip,
    rate_limiter,
    set_admin_password,
    issue_session_token,
    validate_session_token,
)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    data = request.json or {}
    password = data.get("password", "")

    # 限流：每 IP 每分钟最多 5 次尝试，超限锁定 5 分钟窗口
    ip = get_client_ip()
    if not rate_limiter.check("login", ip, limit=5, window_seconds=60):
        return jsonify({"error": "尝试次数过多，请 5 分钟后再试"}), 429
    if not password:
        return jsonify({"error": "请输入口令"}), 400

    conn = get_db()
    ok = check_admin_password(conn, password)
    conn.close()

    if not ok:
        return jsonify({"error": "口令错误"}), 401

    return jsonify({"token": issue_session_token(), "expires_in": 12 * 3600})


@auth_bp.route("/api/auth/logout", methods=["POST"])
def logout():
    # 无状态令牌：由前端丢弃；预留接口便于将来加入令牌黑名单
    return jsonify({"status": "success"})


@auth_bp.route("/api/auth/me", methods=["GET"])
def me():
    token = request.headers.get("Authorization", "").removeprefix("Bearer ") or \
        request.headers.get("X-Session-Token", "")
    if token and validate_session_token(token):
        return jsonify({"authenticated": True})
    return jsonify({"authenticated": False}), 401


@auth_bp.route("/api/auth/password", methods=["PUT"])
@admin_required
def change_password():
    data = request.json or {}
    old_password = data.get("old_password", "")
    new_password = data.get("new_password", "")

    if len(new_password) < 8:
        return jsonify({"error": "新口令至少 8 位"}), 400

    conn = get_db()
    if not check_admin_password(conn, old_password):
        conn.close()
        return jsonify({"error": "原口令错误"}), 401
    set_admin_password(conn, new_password)
    conn.close()
    return jsonify({"status": "success"})


@auth_bp.route("/api/stats/dashboard")
@admin_required
def dashboard():
    """管理端数据看板：岗位/候选人/面试汇总与近况"""
    conn = get_db(row_factory=True)

    positions_total = conn.execute("SELECT COUNT(*) FROM positions").fetchone()[0]
    candidates_total = conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]

    by_status = {
        r["status"]: r["cnt"]
        for r in conn.execute(
            "SELECT status, COUNT(*) AS cnt FROM interviews GROUP BY status"
        ).fetchall()
    }

    # 近 7 天每日面试量
    import time as _t

    week = [int(_t.time()) - i * 86400 for i in range(6, -1, -1)]
    daily = []
    for day_start in week:
        day_end = day_start + 86400
        cnt = conn.execute(
            "SELECT COUNT(*) FROM interviews WHERE start_time >= ? AND start_time < ?",
            (day_start, day_end),
        ).fetchone()[0]
        from datetime import datetime

        daily.append({"date": datetime.fromtimestamp(day_start).strftime("%m-%d"), "count": cnt})

    # 各维度平均分（从已完成报告的面试统计，报告以 BLOB 存 PDF，不做解析——维度分由 LLM 输出时即入库可扩展）
    conn.close()

    status_map = {0: "未开始", 1: "试题已备好", 2: "进行中", 3: "面试完毕", 4: "报告已生成"}
    return jsonify({
        "positions_total": positions_total,
        "candidates_total": candidates_total,
        "interviews_total": sum(by_status.values()),
        "interviews_by_status": [
            {"status": k, "label": status_map.get(k, str(k)), "count": v}
            for k, v in sorted(by_status.items())
        ],
        "daily_interviews_7d": daily,
    })
