"""WebSocket 流式输出端点：双向协议。

客户端 → 服务端（JSON）：
- {"type": "turn", "message": "...", "success_criteria": "...", "history": [...]}  开启新一轮
- {"type": "approve", "history": [...]}  批准暂停中待执行的操作，继续本轮

服务端 → 客户端（JSON 事件，逐步推送）：
- {"type": "todos", "todos": [...]}          待办列表更新
- {"type": "approval", "history": [...]}     等待人工审批（本轮暂停）
- {"type": "final", "history": [...]}        本轮完成（含最终报告）
- {"type": "error", "detail": "..."}         认证失败或运行时错误
"""
import jwt
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import delete

from app.core.agent_manager import default_manager
from app.core.db import SessionFactory
from app.core.security import decode_token
from app.models.models import Conversation, Message, User, utcnow

router = APIRouter()

logger = logging.getLogger(__name__)


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
    # 浏览器 WebSocket 无法自定义 Authorization 头，token 走 query 参数
    token = websocket.query_params.get("token")
    try:
        user_id = decode_token(token) if token else None
    except jwt.PyJWTError:
        user_id = None

    async with SessionFactory() as db:
        user = await db.get(User, user_id) if user_id else None
        conv = await db.get(Conversation, conversation_id)

    await websocket.accept()
    if user is None or conv is None or conv.user_id != user.id:
        await websocket.send_json({"type": "error", "detail": "Unauthorized"})
        await websocket.close(code=1008)
        return

    sidekick = await default_manager.get(conversation_id)
    logger.info("ws connected: conversation=%s user=%s", conversation_id, user.username)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "turn")

            if msg_type == "approve" and not sidekick.paused:
                await websocket.send_json(
                    {"type": "error", "detail": "No pending approval for this conversation"}
                )
                continue

            history = data.get("history", [])
            try:
                if msg_type == "approve":
                    events = sidekick.stream_resume(history)
                else:
                    events = sidekick.stream_turn(
                        data.get("message", ""), data.get("success_criteria", ""), history
                    )
                async for event in events:
                    # final / approval 事件携带完整 history，落库持久化
                    if event.get("type") in ("final", "approval"):
                        await _persist(conversation_id, event["history"])
                    await websocket.send_json(event)
            except Exception as exc:  # noqa: BLE001  运行时错误回传给前端展示
                await websocket.send_json({"type": "error", "detail": str(exc)})
    except WebSocketDisconnect:
        logger.info("ws disconnected: conversation=%s", conversation_id)