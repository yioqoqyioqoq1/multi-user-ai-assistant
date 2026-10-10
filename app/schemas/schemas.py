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


class UserRegister(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"