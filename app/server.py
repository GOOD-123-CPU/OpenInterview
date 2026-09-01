"""
OpenInterview - Flask 应用入口

重构说明：原单文件 server.py 已拆分为
    config.py     集中配置（环境变量）
    database.py   数据库连接与建表
    constants.py  状态机与业务常量
    api/          Flask 蓝图（positions / candidates / interviews）
    services/     LLM、语音转写、简历解析、问题生成、报告生成
    tasks/        定时任务 worker

启动：python server.py
"""
from flask import Flask
from flask_cors import CORS

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

    app.register_blueprint(positions_bp)
    app.register_blueprint(candidates_bp)
    app.register_blueprint(interviews_bp)

    return app


app = create_app()

if __name__ == "__main__":
    print(f"OpenInterview Web 服务启动: http://{config.HOST}:{config.PORT}")
    print(f"管理后台: {config.PUBLIC_BASE_URL}static/admin.html")
    app.run(debug=config.DEBUG, host=config.HOST, port=config.PORT)
