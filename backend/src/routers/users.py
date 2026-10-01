"""Browsing other users' public profiles."""

from fastapi import APIRouter

from dependencies import CurrentUser, PageDep, StorageDep, not_found
from models import FriendProfile
from services.accounts import get_active_user
from services.friends import friendships_of, other

router = APIRouter(prefix="/users", tags=["Users"])


async def _friend_ids(storage, user_id: int) -> set[int]:
    return {other(f, user_id) for f in await friendships_of(storage, user_id)}


@router.get("", response_model=list[FriendProfile])
async def search_users(
    user: CurrentUser, storage: StorageDep, page: PageDep, q: str | None = None, city: str | None = None
):
    """Search profiles by name or username, optionally filtered by city."""
    where = {"role": "user", "status": "active", "id__ne": user["id"]}
    if city:
        where["city__ilike"] = city.replace("%", "").replace("_", "")
    if q and (term := q.strip().replace("%", "").replace("_", "")):
        pattern = f"%{term}%"
        found = {
            r["id"]: r
            for column in ("display_name", "username")
            for r in await storage.find("users", {**where, f"{column}__ilike": pattern})
        }
        rows = page.slice(sorted(found.values(), key=lambda r: r["display_name"].lower()))
    else:
        rows = await storage.find("users", where, order_by="display_name", limit=page.limit, offset=page.offset)
    friends = await _friend_ids(storage, user["id"])
    return [{**r, "is_friend": r["id"] in friends} for r in rows]


@router.get("/{user_id}", response_model=FriendProfile)
async def get_profile(user_id: int, user: CurrentUser, storage: StorageDep):
    profile = await get_active_user(storage, user_id)
    if profile is None:
        raise not_found("User")
    return {**profile, "is_friend": user_id in await _friend_ids(storage, user["id"])}
