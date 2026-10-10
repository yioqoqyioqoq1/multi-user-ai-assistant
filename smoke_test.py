"""Phase 1 冒烟测试：验证 lifespan、建表、checkpointer 生命周期与会话 CRUD。

Phase 2 第 2 步后在 CRUD 前先注册登录并携带 token（会话端点已挂认证）。
不涉及 LLM 与 MCP（那些需要真实的 API key 与 npx 环境）。
运行：uv run python smoke_test.py
"""
import uuid

from fastapi.testclient import TestClient

from app.main import app


def main():
    username = f"smoke_{uuid.uuid4().hex[:8]}"

    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200, r.text
        print("health:", r.json())

        # 注册 + 登录，拿到 token
        r = client.post("/api/auth/register", json={"username": username, "password": "secret123"})
        assert r.status_code == 201, r.text
        r = client.post("/api/auth/login", json={"username": username, "password": "secret123"})
        assert r.status_code == 200, r.text
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

        r = client.post("/api/conversations", json={"title": "smoke"}, headers=headers)
        assert r.status_code == 201, r.text
        conv = r.json()
        print("created:", conv)

        r = client.get("/api/conversations", headers=headers)
        assert r.status_code == 200, r.text
        print("list:", r.json())

        r = client.get(f"/api/conversations/{conv['id']}/history", headers=headers)
        assert r.status_code == 200, r.text
        print("history:", r.json())

        r = client.delete(f"/api/conversations/{conv['id']}", headers=headers)
        assert r.status_code == 204, r.text
        print("deleted:", conv["id"])

    print("SMOKE OK")


if __name__ == "__main__":
    main()