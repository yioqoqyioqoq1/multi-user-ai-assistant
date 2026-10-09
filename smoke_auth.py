"""Phase 2 第 1 步冒烟测试：注册 → 登录 → 携带 token 访问受保护端点。

运行：uv run python smoke_auth.py
"""
import uuid

from fastapi.testclient import TestClient

from app.main import app


def main():
    # 每次运行使用唯一用户名，保证测试可反复执行
    username = f"alice_{uuid.uuid4().hex[:8]}"
    password = "secret123"

    with TestClient(app) as client:
        # 注册
        r = client.post("/api/auth/register", json={"username": username, "password": password})
        assert r.status_code == 201, r.text
        user = r.json()
        print("register:", user)
        assert "password_hash" not in user  # 绝不泄露哈希

        # 重复注册 → 409
        r = client.post("/api/auth/register", json={"username": username, "password": password})
        assert r.status_code == 409, r.text
        print("duplicate register -> 409 OK")

        # 登录
        r = client.post("/api/auth/login", json={"username": username, "password": password})
        assert r.status_code == 200, r.text
        token = r.json()["access_token"]
        print("login token:", token[:24] + "...")

        # 错误密码 → 401
        r = client.post("/api/auth/login", json={"username": username, "password": "wrong"})
        assert r.status_code == 401, r.text
        print("wrong password -> 401 OK")

        # 带 token 访问受保护端点
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        print("me:", r.json())

        # 不带 token → 401
        r = client.get("/api/auth/me")
        assert r.status_code == 401, r.text
        print("no token -> 401 OK")

        # 伪造 token → 401
        r = client.get("/api/auth/me", headers={"Authorization": "Bearer bad.token.here"})
        assert r.status_code == 401, r.text
        print("bad token -> 401 OK")

    print("SMOKE AUTH OK")


if __name__ == "__main__":
    main()