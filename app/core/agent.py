"""Sidekick：create_agent worker + 自建 evaluator 循环。

worker 是一个 create_agent（Layer 3）。外面套着自建的循环：用 evaluator（裸 LLM）校验
worker 的输出是否满足用户的 success criteria，达标则接受，否则带上 feedback 重试（最多
MAX_ATTEMPTS 次），或直接返回向用户提问。中间件负责：容错、PII 防护、待办列表、成本限制、
敏感操作前的人工审批暂停。

数据流：
run_turn 收到用户任务 → 初始化一轮 → _advance 启动 worker（create_agent）
→ worker 用 app.tools 提供的 MCP 浏览器/文件系统/搜索工具干活
→ 中间件防崩溃/防泄密/列待办/限成本 → 发通知或求助时在 HumanInTheLoop 处暂停
→ 否则产出回复 → evaluate 校验是否达标 → 不达标带上 feedback 重试
→ 达标或需要用户则把结果写进 history 返回。
"""

import json
import re
import uuid
from datetime import datetime

from pydantic import ValidationError
from langchain.agents import create_agent
from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
    ModelCallLimitMiddleware,
    PIIMiddleware,
    TodoListMiddleware,
)
from langgraph.types import Command

from app.core import config
from app.core.checkpointer import open_checkpointer
from app.core.llm import get_llm
from app.core.middleware import TolerateToolErrors
from app.core.prompts import EVALUATOR_PROMPT, WORKER_PROMPT, EvaluatorOutput
from app.tools.tools import get_all_tools


class Sidekick:
    def __init__(self):
        self.sidekick_id = str(uuid.uuid4())
        self._checkpointer_ctx = None
        self.memory = None
        self.tools = None
        self.sessions = None
        self.worker = None
        self.evaluator = None
        self.task = ""
        self.success_criteria = ""
        self.attempts = 0
        self.paused = False
        self.pending_actions = 0
        self.todos = []

    async def setup(self):
        config.ensure_dirs()
        self.tools, self.sessions = await get_all_tools(str(config.SANDBOX))
        self.memory, self._checkpointer_ctx = await open_checkpointer()
        self.worker = create_agent(
            model=get_llm(),
            tools=self.tools,
            system_prompt=f"{WORKER_PROMPT}\nToday is {datetime.now():%A %d %B %Y}.",
            middleware=[
                TolerateToolErrors(),
                TodoListMiddleware(),
                PIIMiddleware("email"),
                PIIMiddleware("credit_card", apply_to_tool_results=True),
                ModelCallLimitMiddleware(run_limit=30),
                HumanInTheLoopMiddleware(
                    interrupt_on={"send_push_notification": True, "request_human_help": True}
                ),
            ],
            checkpointer=self.memory,
        )
        self.evaluator = get_llm()

    async def evaluate(
        self, message: str, success_criteria: str, last_reply: str, tools_used: list[str]
    ) -> EvaluatorOutput:
        prompt = EVALUATOR_PROMPT.format(
            message=message,
            success_criteria=success_criteria,
            tools_used=", ".join(tools_used) or "none",
            last_reply=last_reply,
        )
        result = await self.evaluator.ainvoke(prompt)
        content = result.content if isinstance(result.content, str) else str(result.content)
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, ValueError):
            match = re.search(r"\{.*\}", content, re.DOTALL)
            data = None
            if match:
                try:
                    data = json.loads(match.group(0))
                except (json.JSONDecodeError, ValueError):
                    data = None
        try:
            return EvaluatorOutput.model_validate(data if data is not None else {})
        except ValidationError:
            lowered = content.lower()
            return EvaluatorOutput(
                feedback=content,
                success_criteria_met="success criteria met" in lowered,
                user_input_needed="question" in lowered or "more input" in lowered,
            )

    async def run_turn(self, message: str, success_criteria: str, history: list) -> list:
        """一轮对话流程：worker 尝试执行任务，evaluator 校验结果；evaluator 会带上反馈让
        worker 重试，最大重试次数为 MAX_ATTEMPTS。若 worker 因等待审批而暂停，本方法会
        立刻返回并标记为 paused；调用 resume() 即可继续这一轮。"""
        self.task = message
        self.success_criteria = success_criteria or "The answer should be clear, correct and complete"
        self.attempts = 0
        self.todos = []
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": f"{message}\n\nThe success criteria for this task are: {self.success_criteria}",
                }
            ]
        }
        return await self._advance(payload, history + [{"role": "user", "content": message}])

    async def resume(self, history: list) -> list:
        """批准 worker 暂停时待执行的操作，继续推进本轮流程。"""
        payload = Command(resume={"decisions": [{"type": "approve"}] * self.pending_actions})
        return await self._advance(payload, history)

    async def _advance(self, payload, history: list) -> list:
        config_ = {"configurable": {"thread_id": self.sidekick_id}}
        while True:
            result = None
            async for result in self.worker.astream(payload, config=config_, stream_mode="values"):
                self.todos = result.get("todos", self.todos)

            if "__interrupt__" in result:
                actions = result["__interrupt__"][0].value["action_requests"]
                self.paused = True
                self.pending_actions = len(actions)
                described = "\n".join(action["description"] for action in actions)
                return history + [{"role": "assistant", "content": f"Waiting for your approval:\n{described}"}]

            self.paused = False
            reply = result["messages"][-1].content
            tools_used = [
                call["name"] for m in result["messages"] for call in (getattr(m, "tool_calls", None) or [])
            ]
            self.attempts += 1
            verdict = await self.evaluate(self.task, self.success_criteria, reply, tools_used)
            if verdict.success_criteria_met or verdict.user_input_needed or self.attempts >= config.MAX_ATTEMPTS:
                return history + [
                    {"role": "assistant", "content": reply},
                    {"role": "assistant", "content": f"Evaluator: {verdict.feedback}"},
                ]
            payload = {
                "messages": [
                    {
                        "role": "user",
                        "content": f"Your last response did not meet the success criteria. "
                        f"Here is the feedback: {verdict.feedback}. Please keep working and address it.",
                    }
                ]
            }

    async def cleanup(self):
        """关闭 MCP 服务器和持久化 checkpointer；浏览器窗口会随之关闭。"""
        if self.sessions:
            self.sessions.stop()
        if self._checkpointer_ctx:
            await self._checkpointer_ctx.__aexit__(None, None, None)
            self._checkpointer_ctx = None