"""API 测试：会话归属校验与多用户数据隔离。"""
import uuid


def _auth(client, username):
    client.post("/api/auth/register", json={"username": username, "password": "secret123"})
    token = client.post(
        "/api/auth/login", json={"username": username, "password": "secret123"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_conv(client, headers, title="t"):
    return client.post("/api/conversations", json={"title": title}, headers=headers).json()


def test_conversation_requires_auth(client):
    assert client.get("/api/conversations").status_code == 401


def test_cross_user_access_forbidden(client):
    headers_a = _auth(client, "alice")
    headers_b = _auth(client, "bob")
    conv = _create_conv(client, headers_a)

    # 别人已存在的会话 → 403（存在但无归属）
    r = client.get(f"/api/conversations/{conv['id']}/history", headers=headers_b)
    assert r.status_code == 403

    # 不存在的会话 → 404
    missing = str(uuid.uuid4())
    assert client.get(f"/api/conversations/{missing}/history", headers=headers_a).status_code == 404


def test_list_is_scoped_per_user(client):
    headers_a = _auth(client, "alice")
    headers_b = _auth(client, "bob")
    _create_conv(client, headers_a)
    _create_conv(client, headers_b)

    assert len(client.get("/api/conversations", headers=headers_a).json()) == 1
    assert len(client.get("/api/conversations", headers=headers_b).json()) == 1


def test_delete_own_conversation(client):
    headers = _auth(client, "alice")
    conv = _create_conv(client, headers)
    r = client.delete(f"/api/conversations/{conv['id']}", headers=headers)
    assert r.status_code == 204
    # 删除后再次读取 → 404
    assert client.get(f"/api/conversations/{conv['id']}/history", headers=headers).status_code == 404