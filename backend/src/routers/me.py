"""The signed-in user's own profile, points (private) and redemptions."""

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status

import config
from dependencies import CurrentUser, PageDep, StorageDep, not_found
from models import (
    ChatLimitOut,
    FriendCodeOut,
    MeOut,
    Message,
    PasswordChangeIn,
    PointsSummary,
    PointTransactionOut,
    ProfileUpdate,
    RedemptionOut,
)
from security import create_token, hash_password, verify_password
from services import points
from services.accounts import ensure_unique
from services.friends import friendships_of, other
from services.promotions import redemption_status, redemptions_out

router = APIRouter(prefix="/me", tags=["Me"])


@router.get("", response_model=MeOut)
async def get_me(user: CurrentUser):
    return user


@router.patch("", response_model=MeOut)
async def update_me(body: ProfileUpdate, user: CurrentUser, storage: StorageDep):
    changes = body.model_dump(exclude_unset=True)
    if "username" in changes:
        if changes["username"] is None:
            raise HTTPException(422, "Username cannot be removed")
        await ensure_unique(storage, username=changes["username"], exclude_id=user["id"])
    if "interests" in changes and changes["interests"] is None:
        changes["interests"] = []
    rows = await storage.update("users", {"id": user["id"]}, changes)
    return rows[0]


@router.post("/password", response_model=Message)
async def change_password(body: PasswordChangeIn, user: CurrentUser, storage: StorageDep):
    if not verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    _ = await storage.update("users", {"id": user["id"]}, {"password_hash": hash_password(body.new_password)})
    return {"detail": "Password updated"}


# Friend QR --------------------------------------------------------------------------

@router.get("/friend-code", response_model=FriendCodeOut)
async def friend_code(user: CurrentUser):
    """
    Short-lived code to show as a QR. Two people become friends when each scans
    the other's code (``POST /friends/scan``).
    """
    ttl = config.FRIEND_CODE_TTL_SECONDS
    return {"code": create_token(user["id"], "friend", ttl), "expires_in": ttl}


# Points (visible only to the user themselves and corporate) -------------------------

@router.get("/points", response_model=PointsSummary)
async def points_summary(user: CurrentUser, storage: StorageDep):
    rows = await storage.find("point_transactions", {"user_id": user["id"], "day": config.today()})
    by_reason: dict[str, int] = {}
    for row in rows:
        by_reason[row["reason"]] = by_reason.get(row["reason"], 0) + row["amount"]
    puzzle = by_reason.get("puzzle", 0)
    return {
        "balance": user["points"],
        "today": {
            "chat": by_reason.get("chat", 0),
            "puzzle": puzzle,
            "mission": by_reason.get("mission", 0),
            "earned": sum(r["amount"] for r in rows if r["amount"] > 0),
            "spent": -sum(r["amount"] for r in rows if r["amount"] < 0),
        },
        "puzzle_points_remaining_today": max(0, config.PUZZLE_POINTS_DAILY_MAX - puzzle),
    }


@router.get("/points/history", response_model=list[PointTransactionOut])
async def points_history(user: CurrentUser, storage: StorageDep, page: PageDep):
    return await storage.find(
        "point_transactions", {"user_id": user["id"]}, order_by="-id", limit=page.limit, offset=page.offset
    )


@router.get("/points/chat-limits", response_model=list[ChatLimitOut])
async def chat_limits(user: CurrentUser, storage: StorageDep):
    """Chat points earned with each friend since the last limit reset."""
    today = config.today()
    result = []
    for friendship in await friendships_of(storage, user["id"]):
        partner = await storage.get("users", other(friendship, user["id"]))
        if partner is None or partner["status"] != "active":
            continue
        earned = await points.chat_points_since_reset(storage, user["id"], partner["id"], user["chat_limit_epoch"])
        result.append({
            "partner": partner,
            "earned_since_reset": earned,
            "remaining": max(0, config.CHAT_POINTS_LIMIT_PER_PERSON - earned),
            "awarded_today": await storage.exists(
                "chat_awards", {"user_id": user["id"], "partner_id": partner["id"], "day": today}
            ),
        })
    return result


# Redemptions (the QR codes users show at checkout) ------------------------------

RedemptionFilter = Literal["active", "reserved", "claimed", "cancelled", "expired"]


@router.get("/redemptions", response_model=list[RedemptionOut])
async def my_redemptions(
    user: CurrentUser,
    storage: StorageDep,
    page: PageDep,
    status_filter: Annotated[RedemptionFilter | None, Query(alias="status")] = None,
):
    rows = await redemptions_out(storage, await storage.find("redemptions", {"user_id": user["id"]}, order_by="-id"))
    if status_filter:
        rows = [r for r in rows if r["status"] == status_filter]
    return page.slice(rows)


@router.get("/redemptions/{redemption_id}", response_model=RedemptionOut)
async def my_redemption(redemption_id: int, user: CurrentUser, storage: StorageDep):
    row = await storage.find_one("redemptions", {"id": redemption_id, "user_id": user["id"]})
    if row is None:
        raise not_found("Redemption")
    return (await redemptions_out(storage, [row]))[0]


@router.post("/redemptions/{redemption_id}/cancel", response_model=RedemptionOut)
async def cancel_redemption(redemption_id: int, user: CurrentUser, storage: StorageDep):
    """Cancel an unused redemption and refund its points."""
    async with storage.transaction() as tx:
        row = await tx.find_one("redemptions", {"id": redemption_id, "user_id": user["id"]})
        if row is None:
            raise not_found("Redemption")
        if redemption_status(row) != "active":
            raise HTTPException(status.HTTP_409_CONFLICT, "Only active, unused redemptions can be cancelled")
        updated = await tx.update("redemptions", {"id": row["id"], "status": "active"}, {"status": "cancelled"})
        if not updated:
            raise HTTPException(status.HTTP_409_CONFLICT, "Redemption is being used at a checkout")
        _ = await points.award(
            tx, user["id"], row["points_spent"], "refund", reference_type="redemption", reference_id=row["id"]
        )
        _ = await tx.increment("promotions", {"id": row["promotion_id"], "stock__is_null": False}, {"stock": 1})
    return (await redemptions_out(storage, updated))[0]
