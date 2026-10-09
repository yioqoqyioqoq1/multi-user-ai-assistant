"""LLM 工厂：worker 与 evaluator 共用同一套配置。"""
from langchain_openai import ChatOpenAI

from app.core import config


def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=config.LLM_MODEL,
        api_key=config.LLM_API_KEY,
        base_url=config.LLM_BASE_URL,
    )