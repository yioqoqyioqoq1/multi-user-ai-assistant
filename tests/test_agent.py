"""单元测试：Sidekick.evaluate 的 JSON 解析与降级逻辑（用假 evaluator 模拟 LLM，不碰真实模型）。"""
import asyncio

from app.core.agent import Sidekick


class FakeResult:
    def __init__(self, content, usage_metadata=None):
        self.content = content
        self.usage_metadata = usage_metadata


class FakeEvaluator:
    def __init__(self, content):
        self.content = content

    async def ainvoke(self, prompt):
        return FakeResult(self.content, {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30})


def _evaluate(content, tools_used=()):
    sidekick = Sidekick(thread_id="test-thread")
    sidekick.evaluator = FakeEvaluator(content)
    return asyncio.run(sidekick.evaluate("do X", "X is done", "I did X", list(tools_used)))


def test_parse_valid_json():
    verdict = _evaluate(
        '{"feedback": "looks good", "success_criteria_met": true, "user_input_needed": false}'
    )
    assert verdict.feedback == "looks good"
    assert verdict.success_criteria_met is True
    assert verdict.user_input_needed is False


def test_parse_json_wrapped_in_text():
    # 模型偶尔会在 JSON 外加说明文字，应能通过正则提取
    verdict = _evaluate(
        'Here you go: {"feedback": "ok", "success_criteria_met": true, "user_input_needed": false} thanks'
    )
    assert verdict.success_criteria_met is True
    assert verdict.feedback == "ok"


def test_fallback_when_content_is_not_json():
    # 非 JSON 输出走降级分支：根据关键词推断 success/user_input 标志
    verdict = _evaluate("The assistant needs more input to answer the question.")
    assert verdict.feedback.startswith("The assistant needs")
    assert verdict.success_criteria_met is False
    assert verdict.user_input_needed is True


def test_fallback_detects_success_phrase():
    verdict = _evaluate("The success criteria met, all done.")
    assert verdict.success_criteria_met is True