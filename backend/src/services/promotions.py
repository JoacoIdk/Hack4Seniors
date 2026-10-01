"""Promotion availability, redemption state and response shaping."""

from datetime import date
from typing import Any

import config
from datastore import Row, Storage


def is_available(promotion: Row, day: date | None = None) -> bool:
    """Whether users can currently redeem ``promotion`` (ignoring stock and company)."""
    day = day or config.today()
    if not promotion["active"]:
        return False
    if promotion["starts_on"] and promotion["starts_on"] > day:
        return False
    if promotion["ends_on"] and promotion["ends_on"] < day:
        return False
    return promotion["stock"] is None or promotion["stock"] > 0


def redemption_status(redemption: Row) -> str:
    if redemption["status"] == "active" and redemption["expires_at"] <= config.now():
        return "expired"
    return redemption["status"]


async def active_company_ids(storage: Storage) -> set[int]:
    rows = await storage.find("companies", {"status": "active"}, columns=["id"])
    return {r["id"] for r in rows}


async def company_names(storage: Storage, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    rows = await storage.find("companies", {"id__in": sorted(ids)}, columns=["id", "name"])
    return {r["id"]: r["name"] for r in rows}


async def promotions_out(storage: Storage, promotions: list[Row]) -> list[dict[str, Any]]:
    names = await company_names(storage, {p["company_id"] for p in promotions})
    return [{**p, "company_name": names.get(p["company_id"])} for p in promotions]


async def redemptions_out(storage: Storage, redemptions: list[Row]) -> list[dict[str, Any]]:
    promo_ids = sorted({r["promotion_id"] for r in redemptions})
    promos = {p["id"]: p for p in await storage.find("promotions", {"id__in": promo_ids})} if promo_ids else {}
    names = await company_names(storage, {r["company_id"] for r in redemptions})
    return [
        {
            **r,
            "status": redemption_status(r),
            "promotion_title": promos.get(r["promotion_id"], {}).get("title"),
            "promotion_kind": promos.get(r["promotion_id"], {}).get("kind"),
            "company_name": names.get(r["company_id"]),
        }
        for r in redemptions
    ]
