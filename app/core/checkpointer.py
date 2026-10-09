"""AsyncSqliteSaver 持久化 checkpointer 封装。

替代原 demo 中的 InMemorySaver，让 LangGraph 的检查点持久化到 SQLite，
服务重启后 thread_id 对应的对话状态仍然保留。
"""
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.core import config


async def open_checkpointer():
    """打开一个 AsyncSqliteSaver。

    返回 (saver, ctx)，其中 ctx 是异步上下文管理器，调用方在结束时需执行
    await ctx.__aexit__(None, None, None) 释放连接。
    """
    ctx = AsyncSqliteSaver.from_conn_string(str(config.CHECKPOINT_DB))
    saver = await ctx.__aenter__()
    return saver, ctx