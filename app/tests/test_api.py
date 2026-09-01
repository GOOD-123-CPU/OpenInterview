"""
OpenInterview - API 集成测试

覆盖：健康检查、鉴权流程、岗位/候选人/面试 CRUD、权限矩阵、限流。
（共享 fixture（position/candidate）已移至 conftest.py）
"""
import time
import uuid

import pytest


class TestHealth:
    def test_health(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.get_json()["status"] == "ok"


class TestAuthFlow:
    def test_login_wrong_password(self, client):
        r = client.post("/api/auth/login", json={"password": "wrong-" + uuid.uuid4().hex[:6]})
        assert r.status_code == 401

    def test_login_success_returns_token(self, client):
        r = client.post("/api/auth/login",
                        json={"password": __import__("os").environ.get("ADMIN_PASSWORD", "test-admin-pw")})
        assert r.status_code == 200
        assert len(r.get_json()["token"].split(".")) == 3

    def test_change_password_requires_auth(self, client):
        r = client.put("/api/auth/password", json={"old_password": "x", "new_password": "12345678"})
        assert r.status_code == 401

    def test_change_password_validations(self, client, admin_headers):
        # 新口令过短
        r = client.put("/api/auth/password", headers=admin_headers,
                       json={"old_password": "test-admin-pw", "new_password": "123"})
        assert r.status_code == 400
        # 原口令错误
        r = client.put("/api/auth/password", headers=admin_headers,
                       json={"old_password": "definitely-wrong", "new_password": "12345678"})
        assert r.status_code == 401

    def test_dashboard_requires_auth(self, client):
        assert client.get("/api/stats/dashboard").status_code == 401
