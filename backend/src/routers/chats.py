"""
One-to-one chat between friends.

Chat points are two-sided: once both people have messaged each other on a
given day, each earns the daily chat points for the other (see services.points).
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status

import config
from datastore import get_storage
from dependencies import CurrentUser, StorageDep, load_account, not_found
from models import ChatOut, Message, MessageIn, MessageOut, SendMessageOut
from services import points
from services.friends import friendships_of, get_friendship, other
from services.realtime import hub

router = APIRouter(prefix="/chats", tags=["Chats"])


async def _require_friendship(storage, user_id: int, friend_id: int):
    friendship = await get_friendship(storage, user_id, friend_id)
    if friendship is None:
        raise not_found("Chat")
    return friendship


@router.get("", response_model=list[ChatOut])
async def list_chats(user: CurrentUser, storage: StorageDep):
    """All friends with their latest message, most recent conversations first."""
    chats = []
    for friendship in await friendships_of(storage, user["id"]):
        friend = await storage.get("users", other(friendship, user["id"]))
        if friend is None or friend["status"] != "active":
            continue
        chats.append({
            "friend": friend,
            "friends_since": friendship["created_at"],
            "last_message": await storage.find_one(
                "messages", {"friendship_id": friendship["id"]}, order_by="-id"
            ),
            "unread_count": await storage.count(
                "messages", {"friendship_id": friendship["id"], "recipient_id": user["id"], "read_at__is_null": True}
            ),
            "_sort": friendship["last_message_at"] or friendship["created_at"],
        })
    chats.sort(key=lambda c: c["_sort"], reverse=True)
    return chats


@router.get("/{friend_id}/messages", response_model=list[MessageOut])
async def get_messages(
    friend_id: int,
    user: CurrentUser,
    storage: StorageDep,
    before_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    """Messages in chronological order. Pass ``before_id`` to load older pages."""
    friendship = await _require_friendship(storage, user["id"], friend_id)
    where = {"friendship_id": friendship["id"]}
    if before_id is not None:
        where["id__lt"] = before_id
    rows = await storage.find("messages", where, order_by="-id", limit=limit)
    return list(reversed(rows))


@router.post("/{friend_id}/messages", response_model=SendMessageOut, status_code=status.HTTP_201_CREATED)
async def send_message(friend_id: int, body: MessageIn, user: CurrentUser, storage: StorageDep):
    friendship = await _require_friendship(storage, user["id"], friend_id)
    friend = await storage.get("users", friend_id)
    if friend is None or friend["status"] != "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "This user is no longer available")

    now, day = config.now(), config.today()
    async with storage.transaction() as tx:
        message = await tx.insert("messages", {
            "friendship_id": friendship["id"],
            "sender_id": user["id"],
            "recipient_id": friend_id,
            "body": body.body.strip(),
            "day": day,
            "created_at": now,
            "read_at": None,
        })
        _ = await tx.update("friendships", {"id": friendship["id"]}, {"last_message_at": now})

        mine, theirs = 0, 0
        if await tx.exists("messages", {"friendship_id": friendship["id"], "sender_id": friend_id, "day": day}):
            mine = await points.award_chat(tx, user["id"], friend_id, day)
            theirs = await points.award_chat(tx, friend_id, user["id"], day)

    await hub.send(friend_id, {"type": "message", "message": MessageOut.model_validate(message).model_dump()})
    if theirs:
        await hub.send(friend_id, {
            "type": "points", "amount": theirs, "reason": "chat", "balance": await points.balance(storage, friend_id)
        })
    return {"message": message, "points_awarded": mine}


@router.post("/{friend_id}/read", response_model=Message)
async def mark_read(friend_id: int, user: CurrentUser, storage: StorageDep):
    friendship = await _require_friendship(storage, user["id"], friend_id)
    updated = await storage.update(
        "messages",
        {"friendship_id": friendship["id"], "recipient_id": user["id"], "read_at__is_null": True},
        {"read_at": config.now()},
    )
    if updated:
        await hub.send(friend_id, {"type": "read", "by": user["id"], "up_to": max(m["id"] for m in updated)})
    return {"detail": f"{len(updated)} messages marked as read"}


@router.websocket("/ws")
async def chat_socket(websocket: WebSocket, token: str):
    """
    Live events for the signed-in user: ``ws://host/chats/ws?token=<access token>``.
    The socket is push-only; send messages through the HTTP endpoint.
    """
    try:
        account = await load_account(token, get_storage())
    except HTTPException:
        await websocket.close(code=4401)
        return
    if account["role"] != "user":
        await websocket.close(code=4403)
        return
    await hub.connect(account["id"], websocket)
    try:
        while True:
            _ = await websocket.receive_text()  # keepalive pings from the client
    except WebSocketDisconnect:
        pass
    finally:
        hub.disconnect(account["id"], websocket)
