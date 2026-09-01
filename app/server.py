"""
OpenInterview - Flask 应用入口 (v2)

v2 新增：
- 管理端登录鉴权（/api/auth/*，PBKDF2 口令 + HMAC 签名会话）
- 管理端写接口统一 @admin_required 保护
- 公开接口限流（登录 / 简历投递 / 答案提交）
- 安全响应头
- 数据库 WAL + 索引 + settings 表 + 轻量迁移
"""
from flask import Flask
from flask_cors import CORS

from api.auth import auth_bp
from api.candidates import candidates_bp
from api.interviews import interviews_bp
from api.positions import positions_bp
from config import config
from database import init_db


def create_app() -> Flask:
    """应用工厂"""
    init_db()

    app = Flask(__name__, static_folder="static", static_url_path="/static")
    CORS(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(positions_bp)
    app.register_blueprint(candidates_bp)
    app.register_blueprint(interviews_bp)

    # 安全响应头
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "microphone=(self)"
        return response

    # 健康检查
    @app.route("/api/health")
    def health():
        return {"status": "ok", "version": "2.0.0"}

    return app


app = create_app()

if __name__ == "__main__":
    print(f"OpenInterview v2 Web 服务启动: http://{config.HOST}:{config.PORT}")
    print(f"管理后台: {config.PUBLIC_BASE_URL}static/admin.html")
    app.run(debug=config.DEBUG, host=config.HOST, port=config.PORT)
