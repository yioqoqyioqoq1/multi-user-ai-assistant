"""Sidekick 的工具集：MCP 服务器、现成的 LangChain 工具，以及自建工具。"""

import asyncio
import os
from contextlib import AsyncExitStack

import httpx
import wikipedia
from dotenv import load_dotenv
from langchain_community.tools import GoogleSerperRun, WikipediaQueryRun
from langchain_community.utilities import GoogleSerperAPIWrapper, WikipediaAPIWrapper
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

load_dotenv(override=True)

# Wikimedia 会拒绝 wikipedia 库默认的 user agent，这里显式标识自己
wikipedia.set_user_agent("agentic-track-course (https://edwarddonner.com)")

search = GoogleSerperRun(api_wrapper=GoogleSerperAPIWrapper())

wikipedia_lookup = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())


@tool
async def send_push_notification(text: str) -> str:
    """Send a short push notification to the user's phone."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.pushover.net/1/messages.json",
            data={
                "token": os.getenv("PUSHOVER_TOKEN"),
                "user": os.getenv("PUSHOVER_USER"),
                "message": text,
            },
        )
    response.raise_for_status()
    return "Notification sent"


@tool
def request_human_help(instructions: str) -> str:
    """Ask the user to do something in the browser window that you cannot do yourself,
    such as logging in to a site, passing a captcha, or approving two-factor authentication.
    Explain exactly what you need them to do. The run pauses until they have done it."""
    return "The user says it is done. Continue with the task."


def mcp_connections(sandbox: str) -> dict:
    """Sidekick 所使用的 MCP 服务端：有头浏览器与沙箱文件系统。"""
    return {
        "playwright": {
            "transport": "stdio",
            "command": "npx",
            "args": ["@playwright/mcp@latest", "--isolated"],
        },
        "filesystem": {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", sandbox],
        },
    }


class McpSessions:
    """让 MCP 会话保持打开，使浏览器在工具调用之间保留状态。

    stdio 传输必须在同一个 asyncio task 内打开和关闭，因此由一个后台任务统一持有会话：
    它打开会话、挂起等待，并在 stop() 被调用时在同一任务里关闭。停止会关闭服务器，
    你会看到浏览器窗口随之关闭。
    """

    def __init__(self, connections: dict):
        self.connections = connections
        self.tools = []
        self._ready = asyncio.Event()
        self._stop = asyncio.Event()
        self._task = None

    async def _run(self):
        client = MultiServerMCPClient(self.connections)
        async with AsyncExitStack() as stack:
            for name in self.connections:
                session = await stack.enter_async_context(client.session(name))
                self.tools += await load_mcp_tools(session, server_name=name)
            self._ready.set()
            await self._stop.wait()

    async def start(self) -> list:
        self._task = asyncio.create_task(self._run())
        ready = asyncio.create_task(self._ready.wait())
        await asyncio.wait([ready, self._task], return_when=asyncio.FIRST_COMPLETED)
        ready.cancel()
        if self._task.done():
            self._task.result()
        return self.tools

    def stop(self):
        self._stop.set()


async def get_all_tools(sandbox: str):
    """返回完整的工具列表（自建工具 + MCP 服务器工具）以及会话持有者。"""
    sessions = McpSessions(mcp_connections(sandbox))
    mcp_tools = await sessions.start()
    our_tools = [search, send_push_notification, wikipedia_lookup, request_human_help]
    return our_tools + mcp_tools, sessions