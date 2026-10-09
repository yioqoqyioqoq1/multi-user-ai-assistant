"""Phase 1 冒烟测试：验证 lifespan、建表、checkpointer 生命周期与会话 CRUD。

不涉及 LLM 与 MCP（那些需要真实的 API key 与 npx 环境）。
运行：uv run python smoke_test.py
"""
from fastapi.testclient import TestClient

from app.main import app


def main():
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200, r.text
        print("health:", r.json())

        r = client.post("/api/conversations", json={"title": "smoke"})
        assert r.status_code == 201, r.text
        conv = r.json()
        print("created:", conv)

        r = client.get("/api/conversations")
        assert r.status_code == 200, r.text
        print("list:", r.json())

        r = client.get(f"/api/conversations/{conv['id']}/history")
        assert r.status_code == 200, r.text
        print("history:", r.json())

        r = client.delete(f"/api/conversations/{conv['id']}")
        assert r.status_code == 204, r.text
        print("deleted:", conv["id"])

    print("SMOKE OK")


if __name__ == "__main__":
    main()