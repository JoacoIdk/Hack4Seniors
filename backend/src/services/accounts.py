"""Account creation and lookups shared by auth, company and corporate routes."""

from datetime import date
from typing import Any

from fastapi import HTTPException, status

import config
from datastore import Row, Storage
from security import hash_password


async def ensure_unique(
    storage: Storage, *, email: str | None = None, username: str | None = None, exclude_id: int | None = None
) -> None:
    for column, value, label in (("email", email, "Email"), ("username", username, "Username")):
        if value is None:
            continue
        existing = await storage.find_one("users", {column: value})
        if existing and existing["id"] != exclude_id:
            raise HTTPException(status.HTTP_409_CONFLICT, f"{label} is already in use")


async def create_account(
    storage: Storage,
    *,
    role: str,
    email: str,
    password: str,
    display_name: str,
    username: str | None = None,
    company_id: int | None = None,
    corporate_level: str | None = None,
    city: str | None = None,
    birth_date: date | None = None,
    language: str = config.DEFAULT_LANGUAGE,
) -> Row:
    await ensure_unique(storage, email=email, username=username)
    return await storage.insert("users", {
        "role": role,
        "corporate_level": corporate_level,
        "company_id": company_id,
        "email": email,
        "password_hash": hash_password(password),
        "username": username,
        "display_name": display_name,
        "bio": None,
        "avatar_url": None,
        "city": city,
        "birth_date": birth_date,
        "interests": [],
        "language": language,
        "points": 0,
        "chat_limit_epoch": 0,
        "status": "active",
        "created_at": config.now(),
        "last_login_at": None,
    })


async def get_active_user(storage: Storage, user_id: int) -> Row | None:
    """A regular (role=user) active account, or None."""
    return await storage.find_one("users", {"id": user_id, "role": "user", "status": "active"})


async def with_company(storage: Storage, account: dict[str, Any]) -> dict[str, Any]:
    if account.get("company_id") and "company" not in account:
        account["company"] = await storage.get("companies", account["company_id"])
    return account


async def names_by_id(storage: Storage, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    rows = await storage.find("users", {"id__in": sorted(ids)}, columns=["id", "display_name"])
    return {r["id"]: r["display_name"] for r in rows}
