"""SQLAlchemy 异步引擎与会话管理。"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core import config


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


# 懒连接：此处仅构建引擎对象，真正建库发生在 init_db() 调用 engine.begin() 时
DB_URL = f"sqlite+aiosqlite:///{config.APP_DB.resolve().as_posix()}"
engine = create_async_engine(DB_URL, echo=False)

SessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    """FastAPI 依赖：提供一个请求作用域内的 AsyncSession。"""
    async with SessionFactory() as session:
        yield session


async def init_db() -> None:
    """创建所有缺失的表。"""
    from app.models import models  # noqa: F401  确保模型被注册到 Base.metadata

    config.ensure_dirs()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)