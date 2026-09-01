"""
OpenInterview - 结构化日志

- 统一 JSON 行格式（生产可被 Loki/ELQ/Datadog 等直接采集）
- request_id 贯穿请求生命周期（X-Request-ID 透传，响应头返回，日志自动附带）
- 控制台人类可读格式（本地开发），文件/环境变量切 JSON
"""
import json
import logging
import sys
import uuid
from datetime import datetime, timezone

from flask import g, request

from config import config

_REQUEST_ID_ATTR = "request_id"


class JsonFormatter(logging.Formatter):
    """JSON 行日志格式器（生产环境友好）"""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # 附加 request_id（若上下文中存在）
        request_id = getattr(record, _REQUEST_ID_ATTR, None)
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    """控制台人类可读格式（本地开发友好）"""

    COLORS = {
        "DEBUG": "\033[36m", "INFO": "\033[32m",
        "WARNING": "\033[33m", "ERROR": "\033[31m", "CRITICAL": "\033[35m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now().strftime("%H:%M:%S")
        color = self.COLORS.get(record.levelname, "")
        request_id = getattr(record, _REQUEST_ID_ATTR, "")
        rid = f" [{request_id[:8]}]" if request_id else ""
        return f"{color}{ts} {record.levelname:<8}{self.RESET}{rid} {record.getMessage()}"


def setup_logging() -> logging.Logger:
    """配置根日志与应用日志。LOG_FORMAT=json 启用 JSON 输出"""
    logger = logging.getLogger("openinterview")
    logger.setLevel(logging.DEBUG if config.DEBUG else logging.INFO)
    logger.propagate = False

    if logger.handlers:  # 防止重复初始化
        return logger

    handler = logging.StreamHandler(sys.stdout)
    if config.LOG_FORMAT == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(ConsoleFormatter())
    logger.addHandler(handler)
    return logger


def get_logger(name: str = "openinterview") -> logging.Logger:
    return logging.getLogger(name)


class RequestIDMiddleware:
    """
    请求追踪中间件：
    - 从 X-Request-ID 头读取或生成新 id
    - 注入 Flask.g 与所有日志记录
    - 响应头返回（便于客户端排查 / 网关串联）
    """

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        request_id = environ.get("HTTP_X_REQUEST_ID") or uuid.uuid4().hex
        environ["openinterview.request_id"] = request_id

        def custom_start_response(status, headers, exc_info=None):
            headers.append(("X-Request-ID", request_id))
            return start_response(status, headers, exc_info)

        return self.app(environ, custom_start_response)


def register_request_logging(app):
    """在应用工厂中注册：请求开始/结束日志 + access log"""

    @app.before_request
    def _start_timer():
        g.request_id = request.environ.get("openinterview.request_id", uuid.uuid4().hex)
        g.request_start = datetime.now(timezone.utc)

    @app.after_request
    def _log_request(response):
        duration_ms = int((datetime.now(timezone.utc) - g.get("request_start", g.request_start)).total_seconds() * 1000)
        get_logger().info(
            "%s %s -> %d (%dms)",
            request.method, request.path, response.status_code, duration_ms,
            extra={_REQUEST_ID_ATTR: g.get("request_id")},
        )
        return response

    @app.errorhandler(Exception)
    def _log_exception(e):
        get_logger().error(
            "未处理异常: %s: %s",
            type(e).__name__, e,
            exc_info=True,
            extra={_REQUEST_ID_ATTR: g.get("request_id", "")},
        )
        # debug 模式交给 Flask 默认页；生产返回统一 500
        if app.config.get("DEBUG"):
            raise e
        return {"error": "服务器内部错误，请稍后重试"}, 500

    return app
