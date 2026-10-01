"""Automatic mission progress tracking."""

from datetime import date, datetime, time

import config
from datastore import Row, Storage


def start_of_day(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=config.TIMEZONE)


async def progress(storage: Storage, user_id: int, mission: Row) -> int:
    """How far ``user_id`` is on ``mission``, measured on the mission's day."""
    day = mission["date"]
    kind = mission["kind"]
    if kind == "checkin":
        return 1 if day == config.today() else 0
    if kind == "send_messages":
        return await storage.count("messages", {"sender_id": user_id, "day": day})
    if kind == "chat_people":
        rows = await storage.find("messages", {"sender_id": user_id, "day": day}, columns=["recipient_id"])
        return len({r["recipient_id"] for r in rows})
    if kind == "solve_puzzles":
        return await storage.count("puzzle_plays", {"user_id": user_id, "solved_day": day})
    if kind == "redeem_promos":
        return await storage.count("redemptions", {"user_id": user_id, "day": day, "status__ne": "cancelled"})
    if kind == "add_friends":
        since, until = start_of_day(day), start_of_day(date.fromordinal(day.toordinal() + 1))
        total = 0
        for column in ("user_a_id", "user_b_id"):
            total += await storage.count(
                "friendships", {column: user_id, "created_at__gte": since, "created_at__lt": until}
            )
        return total
    return 0
