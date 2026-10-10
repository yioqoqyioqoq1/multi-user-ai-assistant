"""pytest 全局夹具：隔离的临时 SQLite + 模拟的 AgentManager。

关键点：测试不触发真实 lifespan（不用 `with TestClient(app)`），
因此不会做真实建表、打开 LangGraph checkpointer，也不会启动 MCP 服务器。
依赖注入 get_db 被重写指向临时数据库；default_manager 被替换为无副作用的假实现。
"""
import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.db import Base, get_db
from app.main import app
from app.models import models  # noqa: F401  确保 ORM 模型注册到 Base.metadata


@pytest.fixture
def client(tmp_path, monkeypatch):
    """返回一个使用独立临时数据库、且不触碰 MCP/checkpointer 的 TestClient。"""
    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")

    async def _init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_init())
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    # 隔离端点用到的共享 manager，避免任何真实的浏览器/文件系统 MCP 与会话清理逻辑
    class _FakeManager:
        async def get(self, conversation_id):
            raise NotImplementedError

        async def remove(self, conversation_id):
            return None

    monkeypatch.setattr("app.api.routes.default_manager", _FakeManager())

    test_client = TestClient(app)
    yield test_client
    test_client.close()
    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())