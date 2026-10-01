"""
Points ledger and earning rules.

Every movement is written to ``point_transactions`` and applied to
``users.points`` in the same transaction; callers pass the transaction-bound
storage so both stay consistent.
"""

from datetime import date

import config
from datastore import Storage


async def _record(
    tx: Storage,
    user_id: int,
    amount: int,
    reason: str,
    *,
    reference_type: str | None = None,
    reference_id: int | None = None,
    description: str | None = None,
    actor_id: int | None = None,
) -> None:
    _ = await tx.insert("point_transactions", {
        "user_id": user_id,
        "amount": amount,
        "reason": reason,
        "reference_type": reference_type,
        "reference_id": reference_id,
        "description": description,
        "actor_id": actor_id,
        "day": config.today(),
        "created_at": config.now(),
    })


async def award(tx: Storage, user_id: int, amount: int, reason: str, **details) -> int:
    """Add points to a user. Returns the amount awarded."""
    if amount <= 0:
        return 0
    _ = await tx.increment("users", {"id": user_id}, {"points": amount})
    await _record(tx, user_id, amount, reason, **details)
    return amount


async def spend(tx: Storage, user_id: int, amount: int, reason: str, **details) -> bool:
    """Remove points if the balance allows it. Returns False when funds are insufficient."""
    if amount <= 0:
        return True
    rows = await tx.increment("users", {"id": user_id, "points__gte": amount}, {"points": -amount})
    if not rows:
        return False
    await _record(tx, user_id, -amount, reason, **details)
    return True


async def balance(storage: Storage, user_id: int) -> int:
    user = await storage.get("users", user_id)
    return user["points"] if user else 0


async def earned_today(storage: Storage, user_id: int, reason: str, day: date | None = None) -> int:
    rows = await storage.find(
        "point_transactions", {"user_id": user_id, "reason": reason, "day": day or config.today()},
        columns=["amount"],
    )
    return sum(r["amount"] for r in rows)


# Chat --------------------------------------------------------------------------

async def chat_points_since_reset(storage: Storage, user_id: int, partner_id: int, epoch: int) -> int:
    rows = await storage.find(
        "chat_awards", {"user_id": user_id, "partner_id": partner_id, "epoch": epoch}, columns=["points"]
    )
    return sum(r["points"] for r in rows)


async def award_chat(tx: Storage, user_id: int, partner_id: int, day: date) -> int:
    """
    Give ``user_id`` the daily chat points for ``partner_id``: once per partner
    per day, capped per partner until the user's limit is reset.
    """
    if await tx.exists("chat_awards", {"user_id": user_id, "partner_id": partner_id, "day": day}):
        return 0
    user = await tx.get("users", user_id)
    if user is None or user["status"] != "active":
        return 0
    epoch = user["chat_limit_epoch"]
    earned = await chat_points_since_reset(tx, user_id, partner_id, epoch)
    amount = min(config.CHAT_POINTS_PER_PERSON_PER_DAY, config.CHAT_POINTS_LIMIT_PER_PERSON - earned)
    if amount <= 0:
        return 0
    _ = await tx.insert("chat_awards", {
        "user_id": user_id,
        "partner_id": partner_id,
        "day": day,
        "epoch": epoch,
        "points": amount,
        "created_at": config.now(),
    })
    return await award(tx, user_id, amount, "chat", reference_type="user", reference_id=partner_id)


# Puzzles ------------------------------------------------------------------------

async def puzzle_points_available(storage: Storage, user_id: int) -> int:
    used = await earned_today(storage, user_id, "puzzle")
    return max(0, config.PUZZLE_POINTS_DAILY_MAX - used)
