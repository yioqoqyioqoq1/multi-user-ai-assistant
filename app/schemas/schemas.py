"""Pydantic 请求与响应模型。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConversationCreate(BaseModel):
    title: str = "New conversation"


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class TurnRequest(BaseModel):
    message: str
    success_criteria: str = ""


class TurnResponse(BaseModel):
    conversation_id: str
    history: list[dict[str, str]]
    paused: bool


class HistoryResponse(BaseModel):
    conversation_id: str
    history: list[dict[str, str]]