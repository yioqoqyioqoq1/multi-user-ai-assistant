"""Phase 2 第 2 步冒烟测试：后端隔离（认证 + 归属校验）。

覆盖：未认证 401、跨用户访问 403、列表过滤、WebSocket 拒绝。
不涉及 LLM 与 MCP（WebSocket 只测拒绝路径）。
运行：uv run python smoke_isolation.py
"""
import uuid

from fastapi.testclient import TestClient

from app.main import app


def _register(client: TestClient, username: str) -> str:
    r = client.post("/api/auth/register", json={"username": username, "password": "secret123"})
    assert r.status_code == 201, r.text
    r = client.post("/api/auth/login", json={"username": username, "password": "secret123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def main():
    alice = f"alice_{uuid.uuid4().hex[:8]}"
    bob = f"bob_{uuid.uuid4().hex[:8]}"

    with TestClient(app) as client:
        token_a = _register(client, alice)
        token_b = _register(client, bob)
        auth_a = {"Authorization": f"Bearer {token_a}"}
        auth_b = {"Authorization": f"Bearer {token_b}"}

        # 未认证 → 401
        assert client.post("/api/conversations", json={}).status_code == 401
        assert client.get("/api/conversations").status_code == 401
        print("unauthenticated -> 401 OK")

        # alice 创建会话
        r = client.post("/api/conversations", json={"title": "alice's"}, headers=auth_a)
        assert r.status_code == 201, r.text
        conv_id = r.json()["id"]

        # alice 能看见自己的会话
        ids_a = {c["id"] for c in client.get("/api/conversations", headers=auth_a).json()}
        assert conv_id in ids_a
        print("alice sees own conversation OK")

        # bob 的列表看不到 alice 的会话
        ids_b = {c["id"] for c in client.get("/api/conversations", headers=auth_b).json()}
        assert conv_id not in ids_b
        print("bob does not see alice's conversation OK")

        # bob 跨用户访问 → 403
        assert client.get(f"/api/conversations/{conv_id}/history", headers=auth_b).status_code == 403
        assert client.delete(f"/api/conversations/{conv_id}", headers=auth_b).status_code == 403
        print("cross-user access -> 403 OK")

        # 访问不存在的会话 → 404
        ghost = str(uuid.uuid4())
        assert client.get(f"/api/conversations/{ghost}/history", headers=auth_b).status_code == 404
        print("missing conversation -> 404 OK")

        # WebSocket 无 token → 拒绝
        with client.websocket_connect(f"/ws/{conv_id}") as ws:
            msg = ws.receive_json()
            assert msg.get("type") == "error", msg
        print("ws without token -> rejected OK")

        # WebSocket 携带 bob 的 token 访问 alice 会话 → 拒绝（不触发 agent 初始化）
        with client.websocket_connect(f"/ws/{conv_id}?token={token_b}") as ws:
            msg = ws.receive_json()
            assert msg.get("type") == "error", msg
        print("ws with cross-user token -> rejected OK")

        # alice 仍可正常访问并删除自己的会话
        assert client.get(f"/api/conversations/{conv_id}/history", headers=auth_a).status_code == 200
        assert client.delete(f"/api/conversations/{conv_id}", headers=auth_a).status_code == 204
        print("alice manages own conversation OK")

    print("SMOKE ISOLATION OK")


if __name__ == "__main__":
    main()