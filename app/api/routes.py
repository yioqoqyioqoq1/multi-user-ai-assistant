"""REST 端点：会话 CRUD 与对话流转。"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.agent_manager import default_manager
from app.core.db import get_db
from app.models.models import Conversation, Message, User, utcnow
from app.schemas.schemas import (
    ConversationCreate,
    ConversationOut,
    HistoryResponse,
    TurnRequest,
    TurnResponse,
)

router = APIRouter(prefix="/api", tags=["assistant"])


async def _get_owned_conversation(
    db: AsyncSession, conversation_id: str, user: User
) -> Conversation:
    """校验会话存在且归属当前用户，否则分别抛出 404 / 403。"""
    conv = await db.get(Conversation, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this conversation",
        )
    return conv


async def _load_history(db: AsyncSession, conversation_id: str) -> list[dict]:
    result = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id)
    )
    return [{"role": m.role, "content": m.content} for m in result.scalars().all()]


async def _save_history(db: AsyncSession, conversation_id: str, history: list[dict]) -> None:
    # 全量覆盖式落库，保持 DB 与内存 history 一致
    await db.execute(delete(Message).where(Message.conversation_id == conversation_id))
    for item in history:
        db.add(Message(conversation_id=conversation_id, role=item["role"], content=item["content"]))
    conv = await db.get(Conversation, conversation_id)
    if conv is not None:
        conv.updated_at = utcnow()
    await db.commit()


@router.post("/conversations", response_model=ConversationOut, status_code=201)
async def create_conversation(
    body: ConversationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = Conversation(id=str(uuid.uuid4()), title=body.title, user_id=user.id)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
    )
    return result.scalars().all()


@router.get("/conversations/{conversation_id}/history", response_model=HistoryResponse)
async def get_history(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_conversation(db, conversation_id, user)
    history = await _load_history(db, conversation_id)
    return HistoryResponse(conversation_id=conversation_id, history=history)


@router.post("/conversations/{conversation_id}/turn", response_model=TurnResponse)
async def run_turn(
    conversation_id: str,
    body: TurnRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_conversation(db, conversation_id, user)
    sidekick = await default_manager.get(conversation_id)
    history = await _load_history(db, conversation_id)
    updated = await sidekick.run_turn(body.message, body.success_criteria, history)
    await _save_history(db, conversation_id, updated)
    return TurnResponse(conversation_id=conversation_id, history=updated, paused=sidekick.paused)


@router.post("/conversations/{conversation_id}/approve", response_model=TurnResponse)
async def approve(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_conversation(db, conversation_id, user)
    sidekick = await default_manager.get(conversation_id)
    if not sidekick.paused:
        raise HTTPException(status_code=400, detail="No pending approval for this conversation")
    history = await _load_history(db, conversation_id)
    updated = await sidekick.resume(history)
    await _save_history(db, conversation_id, updated)
    return TurnResponse(conversation_id=conversation_id, history=updated, paused=sidekick.paused)


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_conversation(db, conversation_id, user)
    await default_manager.remove(conversation_id)
    await db.execute(delete(Message).where(Message.conversation_id == conversation_id))
    await db.execute(delete(Conversation).where(Conversation.id == conversation_id))
    await db.commit()