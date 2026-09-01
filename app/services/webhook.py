"""
OpenInterview - Webhook 事件通知

面试关键事件（报告生成完毕、面试完成等）以 HMAC-SHA256 签名 POST 到
WEBHOOK_URL，便于对接企业 IM 机器人 / n8n / Zapier / 自建自动化。

签名规则（与 GitHub Webhook 一致的惯例）：
    X-OI-Signature: sha256=<hex_hmac_sha256(secret, timestamp + '.' + body)>

事件负载：
    {"event": "report.generated", "ts": 1700000000, "data": {...}}
"""
import hashlib
import hmac
import json
import time
from urllib import request as urlrequest

from config import config
from logging_config import get_logger

logger = get_logger()

# 当前支持的事件类型
EVENT_REPORT_GENERATED = "report.generated"
EVENT_INTERVIEW_COMPLETED = "interview.completed"
EVENT_QUESTIONS_GENERATED = "questions.generated"


def _sign(secret: str, timestamp: str, body: str) -> str:
    message = f"{timestamp}.{body}"
    digest = hmac.new(secret.encode(), message.encode(), hashlib.sha256)
    return f"sha256={digest.hexdigest()}"


def emit_event(event: str, data: dict) -> bool:
    """
    发送事件到 WEBHOOK_URL。
    通知失败只记日志，绝不阻塞主流程（尽力而为语义）。
    返回是否发送成功。
    """
    if not config.WEBHOOK_URL:
        return False

    payload = json.dumps(
        {"event": event, "ts": int(time.time()), "data": data},
        ensure_ascii=False,
    ).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "OpenInterview-Webhook/1.0",
    }
    if config.WEBHOOK_SECRET:
        headers["X-OI-Signature"] = _sign(
            config.WEBHOOK_SECRET, str(int(time.time())), payload.decode("utf-8")
        )

    try:
        req = urlrequest.Request(
            config.WEBHOOK_URL, data=payload, headers=headers, method="POST"
        )
        with urlrequest.urlopen(req, timeout=10) as resp:
            ok = 200 <= resp.status < 300
            if ok:
                logger.info("Webhook 事件 %s 发送成功", event)
            else:
                logger.warning("Webhook 事件 %s 响应异常: HTTP %d", event, resp.status)
            return ok
    except Exception as e:  # noqa: BLE001 - 通知失败不影响业务
        logger.warning("Webhook 事件 %s 发送失败: %s", event, e)
        return False


def verify_signature(secret: str, timestamp: str, body: str, signature: str) -> bool:
    """接收端校验签名的参考实现（也供测试使用）"""
    expected = _sign(secret, timestamp, body)
    return hmac.compare_digest(expected, signature)
