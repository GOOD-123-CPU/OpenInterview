"""
OpenInterview - 安全模块

- 管理端口令哈希：PBKDF2-HMAC-SHA256（Python 标准库，无额外依赖）
- 签名会话令牌：HMAC 签发的 token，带过期时间，无状态校验
- 登录鉴权装饰器：保护管理端写接口

说明：口令哈希与令牌签名均为单向/对称密钥方案，密钥来自 SECRET_KEY 环境变量。
首次部署时若未设置 SECRET_KEY，会自动生成并持久化到实例目录。
"""
import hashlib
import hmac
import os
import secrets
import time
from functools import wraps

from flask import jsonify, request

# ---------------- 密钥管理 ----------------

_SECRET_KEY_FILE = os.path.join(os.path.dirname(__file__), ".secret_key")


def get_secret_key() -> bytes:
    """
    获取签名密钥：优先环境变量 SECRET_KEY；
    否则使用实例目录下持久化的随机密钥（保证重启后会话不失效）。
    """
    env_key = os.getenv("SECRET_KEY")
    if env_key:
        return env_key.encode("utf-8")

    if os.path.exists(_SECRET_KEY_FILE):
        with open(_SECRET_KEY_FILE, "rb") as f:
            return f.read()

    key = secrets.token_bytes(32)
    with open(_SECRET_KEY_FILE, "wb") as f:
        f.write(key)
    return key


# ---------------- 口令哈希（PBKDF2） ----------------

_PBKDF2_ITERATIONS = 260_000


def hash_password(password: str) -> str:
    """返回 'pbkdf2_sha256$iterations$salt_hex$hash_hex' 格式的口令哈希"""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """校验口令；格式不符返回 False"""
    try:
        algo, iterations, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False


# ---------------- 签名会话令牌 ----------------

SESSION_TTL_SECONDS = 12 * 3600  # 会话有效期 12 小时


def issue_session_token() -> str:
    """签发 'expiry.timestamp.signature' 形式的会话令牌"""
    expiry = int(time.time()) + SESSION_TTL_SECONDS
    nonce = secrets.token_hex(8)
    payload = f"{expiry}.{nonce}"
    signature = hmac.new(get_secret_key(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def validate_session_token(token: str) -> bool:
    """校验令牌签名与有效期；不匹配/过期均返回 False"""
    try:
        expiry_str, nonce, signature = token.split(".")
        payload = f"{expiry_str}.{nonce}"
        expected = hmac.new(
            get_secret_key(), payload.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return False
        return int(expiry_str) > time.time()
    except (ValueError, AttributeError):
        return False


# ---------------- 鉴权装饰器 ----------------

# 会话令牌传递方式：优先 Authorization: Bearer <token>，兼容 X-Session-Token 头
def _extract_session_token():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return request.headers.get("X-Session-Token")


def admin_required(fn):
    """管理端鉴权装饰器：无有效会话时返回 401"""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        token = _extract_session_token()
        if not token or not validate_session_token(token):
            return jsonify({"error": "未登录或会话已过期"}), 401
        return fn(*args, **kwargs)

    return wrapper


# ---------------- 管理员账户存储 ----------------
# 管理员凭据保存在 settings 表（键值存储），避免引入用户表

_ADMIN_KEY_HASH = "admin_password_hash"


def ensure_admin_account(conn) -> None:
    """
    确保管理员账户存在：
    - 首次部署且设置了 ADMIN_PASSWORD 环境变量 → 用其初始化
    - 否则生成随机口令并打印到日志（提示立即修改）
    """
    row = conn.execute(
        "SELECT value FROM settings WHERE key = ?", (_ADMIN_KEY_HASH,)
    ).fetchone()
    if row:
        return


    password = os.getenv("ADMIN_PASSWORD", "")
    source = "环境变量 ADMIN_PASSWORD"
    if not password:
        password = secrets.token_urlsafe(12)
        source = "随机生成（见启动日志，请立即登录修改）"

    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (_ADMIN_KEY_HASH, hash_password(password)),
    )
    conn.commit()
    print("=" * 60)
    print(f"[auth] 管理员账户已初始化，口令来源: {source}")
    if "随机" in source:
        print(f"[auth] 初始口令: {password}")
        print(f"[auth] 初始口令: {'*None*'}")
    print("[auth] 登录后请在「修改口令」中设置自己的口令")
    print("=" * 60)


def set_admin_password(conn, new_password: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (_ADMIN_KEY_HASH, hash_password(new_password)),
    )
    conn.commit()


def check_admin_password(conn, password: str) -> bool:
    row = conn.execute(
        "SELECT value FROM settings WHERE key = ?", (_ADMIN_KEY_HASH,)
    ).fetchone()
    return bool(row) and verify_password(password, row[0])


# ---------------- 简单限流（内存滑动窗口） ----------------


class RateLimiter:
    """
    进程内滑动窗口限流器（单实例部署够用）。
    按 (bucket, client_ip) 维度限制时间窗口内的请求次数。
    """

    def __init__(self):
        self._hits: dict = {}

    def check(self, bucket: str, key: str, limit: int, window_seconds: int) -> bool:
        """未超限返回 True 并记录本次；超限返回 False"""
        now = time.time()
        k = (bucket, key)
        hits = [t for t in self._hits.get(k, []) if now - t < window_seconds]
        if len(hits) >= limit:
            self._hits[k] = hits
            return False
        hits.append(now)
        self._hits[k] = hits
        # 防止字典无限膨胀
        if len(self._hits) > 10_000:
            self._hits = {kk: v for kk, v in self._hits.items() if v}
        return True


rate_limiter = RateLimiter()


def get_client_ip() -> str:
    """获取客户端 IP（优先 X-Forwarded-For 首跳，适配反代部署）"""
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.remote_addr or "unknown"
