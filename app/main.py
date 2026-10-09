"""FastAPI 入口。启动：uvicorn app.main:app --reload（在项目根目录执行）。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import routes, websocket
from app.core.agent_manager import default_manager
from app.core.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：建表 + 打开共享 checkpointer
    await init_db()
    await default_manager.start()
    yield
    # 关闭：释放 checkpointer 与所有 MCP 会话
    await default_manager.stop()


app = FastAPI(title="Sidekick AI Assistant Platform", version="0.1.0", lifespan=lifespan)

app.include_router(routes.router)
app.include_router(websocket.router)


@app.get("/health")
async def health():
    return {"status": "ok"}