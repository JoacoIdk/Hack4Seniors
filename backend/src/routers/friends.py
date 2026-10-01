"""
Friends are added in person: both people scan each other's QR code
(``GET /me/friend-code``) within a short window.
"""

from datetime import timedelta

from fastapi import APIRouter, HTTPException, status

import config
from dependencies import CurrentUser, StorageDep, not_found
from models import FriendScanIn, FriendScanOut, Message, PublicProfile
from security import InvalidToken, decode_token
from services.accounts import get_active_user
from services.friends import friendships_of, get_friendship, other, pair
from services.realtime import hub

router = APIRouter(prefix="/friends", tags=["Friends"])


@router.get("", response_model=list[PublicProfile])
async def list_friends(user: CurrentUser, storage: StorageDep):
    ids = [other(f, user["id"]) for f in await friendships_of(storage, user["id"])]
    if not ids:
        return []
    return await storage.find("users", {"id__in": ids, "status": "active"}, order_by="display_name")


@router.post("/scan", response_model=FriendScanOut)
async def scan_friend_code(body: FriendScanIn, user: CurrentUser, storage: StorageDep):
    """
    Submit a scanned friend code. The first scan is recorded as pending; when
    the other person scans back, the friendship (and chat) is created.
    """
    try:
        target_id = decode_token(body.code, "friend")["sub"]
    except InvalidToken:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This code is invalid or has expired")
    if target_id == user["id"]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot add yourself")
    target = await get_active_user(storage, target_id)
    if target is None:
        raise not_found("User")

    if await get_friendship(storage, user["id"], target_id):
        return {"status": "already_friends", "user": target, "detail": "You are already friends"}

    now = config.now()
    window_start = now - timedelta(seconds=config.FRIEND_SCAN_WINDOW_SECONDS)
    async with storage.transaction() as tx:
        reciprocal = await tx.find_one(
            "friend_scans", {"scanner_id": target_id, "target_id": user["id"], "created_at__gte": window_start}
        )
        if reciprocal is None:
            _ = await tx.delete("friend_scans", {"scanner_id": user["id"], "target_id": target_id})
            _ = await tx.insert("friend_scans", {"scanner_id": user["id"], "target_id": target_id, "created_at": now})
        else:
            user_a, user_b = pair(user["id"], target_id)
            _ = await tx.insert("friendships", {
                "user_a_id": user_a, "user_b_id": user_b, "created_at": now, "last_message_at": None,
            })
            for scanner, scanned in ((user["id"], target_id), (target_id, user["id"])):
                _ = await tx.delete("friend_scans", {"scanner_id": scanner, "target_id": scanned})

    if reciprocal is None:
        await hub.send(target_id, {"type": "friend_scan", "user": PublicProfile.model_validate(user).model_dump()})
        return {"status": "pending", "user": target, "detail": "Now let them scan your code to finish"}

    await hub.send(target_id, {"type": "friend_added", "user": PublicProfile.model_validate(user).model_dump()})
    return {"status": "friends", "user": target, "detail": "You are now friends"}


@router.delete("/{user_id}", response_model=Message)
async def remove_friend(user_id: int, user: CurrentUser, storage: StorageDep):
    """Unfriend someone. The chat history is deleted with the friendship."""
    friendship = await get_friendship(storage, user["id"], user_id)
    if friendship is None:
        raise not_found("Friend")
    async with storage.transaction() as tx:
        _ = await tx.delete("messages", {"friendship_id": friendship["id"]})
        _ = await tx.delete("friendships", {"id": friendship["id"]})
    return {"detail": "Friend removed"}
