"""
OpenInterview - 安全模块单元测试
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from security import (
    RateLimiter,
    hash_password,
    issue_session_token,
    validate_session_token,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_and_verify(self):
        stored = hash_password("S3cure-Passw0rd!")
        assert stored.startswith("pbkdf2_sha256$")
        assert verify_password("S3cure-Passw0rd!", stored)

    def test_wrong_password_rejected(self):
        stored = hash_password("correct")
        assert not verify_password("incorrect", stored)

    def test_salt_randomized(self):
        assert hash_password("same") != hash_password("same")

    def test_malformed_hash_rejected(self):
        assert not verify_password("x", "not-a-valid-hash")
        assert not verify_password("x", "")


class TestSessionToken:
    def test_issue_and_validate(self):
        token = issue_session_token()
        assert validate_session_token(token)

    def test_tampered_token_rejected(self):
        token = issue_session_token()
        parts = token.split(".")
        parts[0] = str(int(parts[0]) + 999999)  # 篡改过期时间
        assert not validate_session_token(".".join(parts))

    def test_garbage_rejected(self):
        assert not validate_session_token("abc")
        assert not validate_session_token("")
        assert not validate_session_token("a.b.c.d.e")


class TestRateLimiter:
    def test_allows_within_limit(self):
        rl = RateLimiter()
        for _ in range(5):
            assert rl.check("b", "ip1", limit=5, window_seconds=60)

    def test_blocks_over_limit(self):
        rl = RateLimiter()
        for _ in range(5):
            rl.check("b", "ip2", limit=5, window_seconds=60)
        assert not rl.check("b", "ip2", limit=5, window_seconds=60)

    def test_buckets_isolated(self):
        rl = RateLimiter()
        for _ in range(5):
            rl.check("b1", "ip3", limit=5, window_seconds=60)
        assert rl.check("b2", "ip3", limit=5, window_seconds=60)
