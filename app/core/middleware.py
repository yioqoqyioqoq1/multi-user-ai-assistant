"""自定义 Agent 中间件。"""
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage


class TolerateToolErrors(AgentMiddleware):
    """把工具调用异常转成 ToolMessage 反馈给模型，使其能自我恢复，而不是让整个 run 崩溃。
    浏览器这类需要访问外部世界的工具，偶发失败很常见。"""

    async def awrap_tool_call(self, request, handler):
        try:
            return await handler(request)
        except Exception as error:
            return ToolMessage(
                content=f"That tool call failed: {error}. Try another approach.",
                tool_call_id=request.tool_call["id"],
            )