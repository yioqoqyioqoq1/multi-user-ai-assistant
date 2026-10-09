"""管理 conversation_id → Sidekick 实例的映射，以及共享的持久化 checkpointer。"""
from app.core.agent import Sidekick
from app.core.checkpointer import open_checkpointer


class AgentManager:
    def __init__(self):
        self._agents: dict[str, Sidekick] = {}
        self._memory = None
        self._checkpointer_ctx = None

    async def start(self):
        """打开一个所有会话共享的 checkpointer。"""
        self._memory, self._checkpointer_ctx = await open_checkpointer()

    async def stop(self):
        """关闭所有 MCP 会话并释放共享 checkpointer。"""
        for sidekick in self._agents.values():
            await sidekick.cleanup()
        self._agents.clear()
        if self._checkpointer_ctx:
            await self._checkpointer_ctx.__aexit__(None, None, None)
            self._checkpointer_ctx = None
            self._memory = None

    async def get(self, conversation_id: str) -> Sidekick:
        """按会话取 Sidekick 实例，不存在则新建（thread_id 对齐 conversation_id）。"""
        sidekick = self._agents.get(conversation_id)
        if sidekick is None:
            sidekick = Sidekick(thread_id=conversation_id, memory=self._memory)
            await sidekick.setup()
            self._agents[conversation_id] = sidekick
        return sidekick

    async def remove(self, conversation_id: str):
        """移除并清理指定会话的 Sidekick 实例。"""
        sidekick = self._agents.pop(conversation_id, None)
        if sidekick:
            await sidekick.cleanup()


# 模块级单例，供路由与应用生命周期共享
default_manager = AgentManager()