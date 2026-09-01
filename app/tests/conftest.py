"""
OpenInterview - pytest 全局夹具

每个测试会话使用独立的临时 SQLite 数据库，并在测试前 mock 掉
whisper / torch 重依赖，保证 CI 无 GPU 环境可跑。
"""
import os
import sys
import unittest.mock as mock

import pytest

# 保证 app 目录可导入
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP_DIR)

# mock 重依赖（必须在导入 server 之前）
sys.modules.setdefault("whisper", mock.MagicMock())
_torch_mock = mock.MagicMock()
_torch_mock.cuda.is_available.return_value = False
sys.modules.setdefault("torch", _torch_mock)


@pytest.fixture(scope="session")
def test_db(tmp_path_factory):
    """会话级临时数据库路径"""
    db = tmp_path_factory.mktemp("data") / "test_openinterview.db"
    os.environ["DB_PATH"] = str(db)
    yield str(db)


@pytest.fixture(scope="session")
def app(test_db):
    """应用工厂（会话级复用）"""
    from server import create_app

    application = create_app()
    application.config["TESTING"] = True
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """每个测试前清空限流器状态，避免测试间相互污染"""
    from security import rate_limiter

    rate_limiter._hits.clear()
    yield
    rate_limiter._hits.clear()


@pytest.fixture()
def position(client, admin_headers):
    """预置一个岗位，返回其 id"""
    r = client.post("/api/positions", headers=admin_headers, json={
        "name": "后端工程师", "requirements": "Python/Flask",
        "responsibilities": "服务端开发", "quantity": 1, "status": 1, "recruiter": "HR",
    })
    assert r.status_code == 200
    r = client.get("/api/positions")
    return r.get_json()[-1]["id"]


@pytest.fixture()
def candidate(client, admin_headers, position):
    """预置一个候选人，返回其 id"""
    r = client.post("/api/candidates", headers=admin_headers,
                    data={"position_id": str(position), "name": "王小明", "email": "wxm@example.com"},
                    content_type="multipart/form-data")
    assert r.status_code == 200
    r = client.get("/api/candidates", headers=admin_headers)
    return r.get_json()[-1]["id"]


@pytest.fixture()
def admin_headers(client):
    """通过登录接口获取管理员会话头（ADMIN_PASSWORD 由环境变量注入）。
    注意：登录接口有限流，reset_rate_limiter 夹具保证每个测试都能正常登录。"""
    r = client.post("/api/auth/login", json={"password": os.environ.get("ADMIN_PASSWORD", "test-admin-pw")})
    assert r.status_code == 200, f"管理员登录失败: {r.data}"
    token = r.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}
