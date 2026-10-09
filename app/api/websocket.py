"""WebSocket 流式输出端点。"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import delete

from app.core.agent_manager import default_manager
from app.core.db import SessionFactory
from app.models.models import Conversation, Message, utcnow

router = APIRouter()


async def _persist(conversation_id: str, history: list[dict]) -> None:
    """把 WebSocket 产生的最终 history 落库，与 REST 端点保持一致。"""
    async with SessionFactory() as db:
        await db.execute(delete(Message).where(Message.conversation_id == conversation_id))
        for item in history:
            db.add(Message(conversation_id=conversation_id, role=item["role"], content=item["content"]))
        conv = await db.get(Conversation, conversation_id)
        if conv is not None:
            conv.updated_at = utcnow()
        await db.commit()


@router.websocket("/ws/{conversation_id}")
async def websocket_turn(websocket: WebSocket, conversation_id: str):
    await websocket.accept()
    sidekick = await default_manager.get(conversation_id)
    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message")
            success_criteria = data.get("success_criteria", "")
            history = data.get("history", [])
            async for event in sidekick.stream_turn(message, success_criteria, history):
                # final / approval 事件携带完整 history，落库持久化
                if event.get("type") in ("final", "approval"):
                    await _persist(conversation_id, event["history"])
                await websocket.send_json(event)
    except WebSocketDisconnect:
        pass