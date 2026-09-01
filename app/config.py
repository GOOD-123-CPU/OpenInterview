"""
OpenInterview - 集中配置管理

所有配置项通过环境变量（.env）注入，未设置时使用合理默认值。
"""
import os

from dotenv import load_dotenv

# 加载 .env（不存在也不报错，允许纯环境变量方式部署）
load_dotenv()


def _get_bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _get_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, default))
    except (TypeError, ValueError):
        return default


class Config:
    """全局配置（12-factor 风格，全部来自环境变量）"""

    # ---- Flask ----
    HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    PORT = _get_int("FLASK_PORT", 8000)
    DEBUG = _get_bool("FLASK_DEBUG", False)

    # ---- 数据库 ----
    DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "interview_system.db"))

    # ---- 对外访问地址（生成面试链接用）----
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000/").rstrip("/") + "/"

    # ---- LLM（OpenAI 兼容接口）----
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
    LLM_MODEL = os.getenv("LLM_MODEL", "glm-4-plus")

    # ---- Whisper ----
    WHISPER_MODEL_GPU = os.getenv("WHISPER_MODEL_GPU", "large-v3")
    WHISPER_MODEL_CPU = os.getenv("WHISPER_MODEL_CPU", "base")

    # ---- 定时任务 ----
    SCHEDULE_INTERVAL_MINUTES = _get_int("SCHEDULE_INTERVAL_MINUTES", 5)

    # ---- 日志 ----
    LOG_FORMAT = os.getenv("LOG_FORMAT", "console")  # console | json

    # ---- Webhook 事件通知 ----
    WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

    # ---- 业务参数 ----
    QUESTION_COUNT = _get_int("QUESTION_COUNT", 10)  # 每场面试生成的问题数
    TOKEN_LENGTH = _get_int("TOKEN_LENGTH", 32)  # 面试链接令牌长度


config = Config()
