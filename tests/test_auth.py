"""API 测试：注册、登录与当前用户查询（走独立临时数据库）。"""


def _register(client, username="alice", password="secret123"):
    return client.post("/api/auth/register", json={"username": username, "password": password})


def test_register_returns_user_without_hash(client):
    r = _register(client)
    assert r.status_code == 201
    data = r.json()
    assert data["username"] == "alice"
    assert "password_hash" not in data  # 绝不泄露哈希


def test_duplicate_register_conflict(client):
    assert _register(client).status_code == 201
    assert _register(client).status_code == 409


def test_login_and_me(client):
    _register(client)
    r = client.post("/api/auth/login", json={"username": "alice", "password": "secret123"})
    assert r.status_code == 200
    token = r.json()["access_token"]

    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "alice"


def test_login_wrong_password(client):
    _register(client)
    r = client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
    assert r.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/api/auth/me").status_code == 401
    # 伪造 token 也应 401
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer bad.token.here"})
    assert r.status_code == 401