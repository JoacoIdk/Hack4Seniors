"""Friendships (which are also the chat channel between two users)."""

from datastore import Row, Storage


def pair(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


async def get_friendship(storage: Storage, a: int, b: int) -> Row | None:
    user_a, user_b = pair(a, b)
    return await storage.find_one("friendships", {"user_a_id": user_a, "user_b_id": user_b})


async def friendships_of(storage: Storage, user_id: int) -> list[Row]:
    return (
        await storage.find("friendships", {"user_a_id": user_id})
        + await storage.find("friendships", {"user_b_id": user_id})
    )


def other(friendship: Row, user_id: int) -> int:
    return friendship["user_b_id"] if friendship["user_a_id"] == user_id else friendship["user_a_id"]
