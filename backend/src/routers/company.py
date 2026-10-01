"""
Company portal: profile, promotions, QR checkout and statistics.

Checkout flow (cashier):
  1. ``POST /company/checkouts`` opens an order.
  2. ``POST /company/checkouts/{id}/scan`` for each customer's QR code. Individual
     promotions accept one code; group promotions accept one code per customer,
     each adding ``discount_value`` until ``max_discount`` is reached.
  3. ``POST /company/checkouts/{id}/complete`` applies the discount and marks the
     codes as used (or ``/cancel`` to release them).
``POST /company/redemptions/claim`` does all three at once for a single code.
"""

from collections import Counter
from datetime import timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status

import config
from datastore import Row, Storage
from dependencies import Account, CurrentCompany, PageDep, StorageDep, not_found
from models import (
    CheckoutIn,
    CheckoutOut,
    CodeIn,
    CompanyOut,
    CompanyPromotionOut,
    CompanyStats,
    CompanyUpdate,
    Message,
    PromotionIn,
    PromotionUpdate,
    RedemptionLookupOut,
    RedemptionOut,
    validate_discount,
)
from services.accounts import names_by_id
from services.promotions import promotions_out, redemption_status, redemptions_out

router = APIRouter(prefix="/company", tags=["Company"])


def _company_id(account: Account) -> int:
    return account["company_id"]


# Profile -------------------------------------------------------------------------

@router.get("", response_model=CompanyOut)
async def get_company(account: CurrentCompany):
    return account["company"]


@router.patch("", response_model=CompanyOut)
async def update_company(body: CompanyUpdate, account: CurrentCompany, storage: StorageDep):
    changes = body.model_dump(exclude_unset=True)
    rows = await storage.update("companies", {"id": _company_id(account)}, changes)
    return rows[0]


# Promotions ------------------------------------------------------------------------

async def _own_promotion(storage: Storage, account: Account, promotion_id: int) -> Row:
    promo = await storage.find_one("promotions", {"id": promotion_id, "company_id": _company_id(account)})
    if promo is None:
        raise not_found("Promotion")
    return promo


@router.get("/promotions", response_model=list[CompanyPromotionOut])
async def list_promotions(account: CurrentCompany, storage: StorageDep, active: bool | None = None):
    where = {"company_id": _company_id(account)}
    if active is not None:
        where["active"] = active
    return await promotions_out(storage, await storage.find("promotions", where, order_by="-id"))


@router.post("/promotions", response_model=CompanyPromotionOut, status_code=status.HTTP_201_CREATED)
async def create_promotion(body: PromotionIn, account: CurrentCompany, storage: StorageDep):
    now = config.now()
    promo = await storage.insert("promotions", {
        **body.model_dump(),
        "max_discount": body.max_discount if body.kind == "group" else None,
        "company_id": _company_id(account),
        "views": 0,
        "created_at": now,
        "updated_at": now,
    })
    return (await promotions_out(storage, [promo]))[0]


@router.get("/promotions/{promotion_id}", response_model=CompanyPromotionOut)
async def get_promotion(promotion_id: int, account: CurrentCompany, storage: StorageDep):
    return (await promotions_out(storage, [await _own_promotion(storage, account, promotion_id)]))[0]


@router.patch("/promotions/{promotion_id}", response_model=CompanyPromotionOut)
async def update_promotion(promotion_id: int, body: PromotionUpdate, account: CurrentCompany, storage: StorageDep):
    promo = await _own_promotion(storage, account, promotion_id)
    changes = body.model_dump(exclude_unset=True)
    merged = {**promo, **changes}
    try:
        validate_discount(merged["kind"], merged["discount_type"], merged["discount_value"], merged["max_discount"])
    except ValueError as e:
        raise HTTPException(422, str(e))
    if merged["starts_on"] and merged["ends_on"] and merged["ends_on"] < merged["starts_on"]:
        raise HTTPException(422, "ends_on must be on or after starts_on")
    rows = await storage.update("promotions", {"id": promotion_id}, {**changes, "updated_at": config.now()})
    return (await promotions_out(storage, rows))[0]


@router.delete("/promotions/{promotion_id}", response_model=Message)
async def delete_promotion(promotion_id: int, account: CurrentCompany, storage: StorageDep):
    """Delete a promotion that was never redeemed; otherwise deactivate it instead."""
    _ = await _own_promotion(storage, account, promotion_id)
    if await storage.exists("redemptions", {"promotion_id": promotion_id}):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Promotion has redemptions; set active=false to hide it instead"
        )
    _ = await storage.delete("promotions", {"id": promotion_id})
    return {"detail": "Promotion deleted"}


# Redemptions -------------------------------------------------------------------

RedemptionFilter = Literal["active", "reserved", "claimed", "cancelled", "expired"]

_UNUSABLE = {
    "reserved": "This code is already part of an open checkout",
    "claimed": "This code has already been used",
    "cancelled": "This code was cancelled by the customer",
    "expired": "This code has expired",
}


def _normalize_code(code: str) -> str:
    return code.strip().upper()


@router.get("/redemptions", response_model=list[RedemptionOut])
async def list_redemptions(
    account: CurrentCompany,
    storage: StorageDep,
    page: PageDep,
    promotion_id: int | None = None,
    status_filter: Annotated[RedemptionFilter | None, Query(alias="status")] = None,
):
    where = {"company_id": _company_id(account)}
    if promotion_id:
        where["promotion_id"] = promotion_id
    rows = await redemptions_out(storage, await storage.find("redemptions", where, order_by="-id"))
    if status_filter:
        rows = [r for r in rows if r["status"] == status_filter]
    return page.slice(rows)


@router.get("/redemptions/{code}", response_model=RedemptionLookupOut)
async def lookup_redemption(code: str, account: CurrentCompany, storage: StorageDep):
    """Preview a scanned code before adding it to a checkout."""
    redemption = await storage.find_one("redemptions", {"code": _normalize_code(code), "company_id": _company_id(account)})
    if redemption is None:
        raise not_found("Code")
    current = redemption_status(redemption)
    promo = await storage.get("promotions", redemption["promotion_id"])
    customer = await storage.get("users", redemption["user_id"])
    return {
        **redemption,
        "status": current,
        "customer_name": customer["display_name"] if customer else "",
        "promotion": (await promotions_out(storage, [promo]))[0],
        "usable": current == "active",
        "detail": _UNUSABLE.get(current, "Code is valid"),
    }


@router.post("/redemptions/claim", response_model=CheckoutOut)
async def quick_claim(body: CodeIn, account: CurrentCompany, storage: StorageDep):
    """Validate and use a single code in one step (opens and completes a checkout)."""
    async with storage.transaction() as tx:
        checkout = await _open_checkout(tx, account, None)
        checkout = await _scan(tx, account, checkout, body.code)
        checkout = await _complete(tx, account, checkout)
    return await _checkout_out(storage, checkout)


# Checkouts -------------------------------------------------------------------------

async def _open_checkout(storage: Storage, account: Account, reference: str | None) -> Row:
    return await storage.insert("checkouts", {
        "company_id": _company_id(account),
        "promotion_id": None,
        "reference": reference,
        "status": "open",
        "discount_type": None,
        "total_discount": 0,
        "participants": 0,
        "opened_by": account["id"],
        "created_at": config.now(),
        "closed_at": None,
    })


async def _own_checkout(storage: Storage, account: Account, checkout_id: int, *, open_only: bool = False) -> Row:
    checkout = await storage.find_one("checkouts", {"id": checkout_id, "company_id": _company_id(account)})
    if checkout is None:
        raise not_found("Checkout")
    if open_only and checkout["status"] != "open":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Checkout is {checkout['status']}")
    return checkout


async def _scan(tx: Storage, account: Account, checkout: Row, code: str) -> Row:
    redemption = await tx.find_one("redemptions", {"code": _normalize_code(code), "company_id": _company_id(account)})
    if redemption is None:
        raise not_found("Code")
    current = redemption_status(redemption)
    if current != "active":
        raise HTTPException(status.HTTP_409_CONFLICT, _UNUSABLE[current])
    promo = await tx.get("promotions", redemption["promotion_id"])

    if checkout["promotion_id"] is not None and checkout["promotion_id"] != promo["id"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "This code is for a different promotion than this order")
    if promo["kind"] == "individual" and checkout["participants"] >= 1:
        raise HTTPException(status.HTTP_409_CONFLICT, "Individual promotions apply to a single customer")
    if await tx.exists("redemptions", {"checkout_id": checkout["id"], "user_id": redemption["user_id"]}):
        raise HTTPException(status.HTTP_409_CONFLICT, "This customer is already part of the order")

    cap = promo["max_discount"] if promo["kind"] == "group" else promo["discount_value"]
    remaining = cap - checkout["total_discount"]
    if remaining <= 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "Maximum discount for this order already reached")
    applied = min(promo["discount_value"], remaining)

    reserved = await tx.update(
        "redemptions",
        {"id": redemption["id"], "status": "active"},
        {"status": "reserved", "checkout_id": checkout["id"], "discount_applied": applied},
    )
    if not reserved:
        raise HTTPException(status.HTTP_409_CONFLICT, "This code was just used elsewhere")
    if checkout["promotion_id"] is None:
        _ = await tx.update(
            "checkouts", {"id": checkout["id"]}, {"promotion_id": promo["id"], "discount_type": promo["discount_type"]}
        )
    rows = await tx.increment("checkouts", {"id": checkout["id"]}, {"participants": 1, "total_discount": applied})
    return rows[0]


async def _complete(tx: Storage, account: Account, checkout: Row) -> Row:
    if checkout["participants"] == 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "Scan at least one code before completing")
    now = config.now()
    _ = await tx.update(
        "redemptions",
        {"checkout_id": checkout["id"], "status": "reserved"},
        {"status": "claimed", "claimed_at": now, "claimed_by": account["id"]},
    )
    rows = await tx.update(
        "checkouts", {"id": checkout["id"], "status": "open"}, {"status": "completed", "closed_at": now}
    )
    if not rows:
        raise HTTPException(status.HTTP_409_CONFLICT, "Checkout is no longer open")
    return rows[0]


async def _checkout_out(storage: Storage, checkout: Row) -> dict:
    promo = await storage.get("promotions", checkout["promotion_id"]) if checkout["promotion_id"] else None
    redemptions = await storage.find("redemptions", {"checkout_id": checkout["id"]}, order_by="id")
    names = await names_by_id(storage, {r["user_id"] for r in redemptions})
    return {
        **checkout,
        "promotion": (await promotions_out(storage, [promo]))[0] if promo else None,
        "max_discount": (promo["max_discount"] if promo["kind"] == "group" else promo["discount_value"]) if promo else None,
        "redemptions": [
            {**r, "customer_name": names.get(r["user_id"], ""), "status": redemption_status(r)} for r in redemptions
        ],
    }


@router.post("/checkouts", response_model=CheckoutOut, status_code=status.HTTP_201_CREATED)
async def open_checkout(body: CheckoutIn, account: CurrentCompany, storage: StorageDep):
    return await _checkout_out(storage, await _open_checkout(storage, account, body.reference))


@router.get("/checkouts", response_model=list[CheckoutOut])
async def list_checkouts(
    account: CurrentCompany,
    storage: StorageDep,
    page: PageDep,
    status_filter: Annotated[Literal["open", "completed", "cancelled"] | None, Query(alias="status")] = None,
):
    where = {"company_id": _company_id(account)}
    if status_filter:
        where["status"] = status_filter
    rows = await storage.find("checkouts", where, order_by="-id", limit=page.limit, offset=page.offset)
    return [await _checkout_out(storage, c) for c in rows]


@router.get("/checkouts/{checkout_id}", response_model=CheckoutOut)
async def get_checkout(checkout_id: int, account: CurrentCompany, storage: StorageDep):
    return await _checkout_out(storage, await _own_checkout(storage, account, checkout_id))


@router.post("/checkouts/{checkout_id}/scan", response_model=CheckoutOut)
async def scan_code(checkout_id: int, body: CodeIn, account: CurrentCompany, storage: StorageDep):
    async with storage.transaction() as tx:
        checkout = await _own_checkout(tx, account, checkout_id, open_only=True)
        checkout = await _scan(tx, account, checkout, body.code)
    return await _checkout_out(storage, checkout)


@router.delete("/checkouts/{checkout_id}/codes/{code}", response_model=CheckoutOut)
async def remove_code(checkout_id: int, code: str, account: CurrentCompany, storage: StorageDep):
    """Take a scanned code back out of an open checkout."""
    async with storage.transaction() as tx:
        checkout = await _own_checkout(tx, account, checkout_id, open_only=True)
        where = {"code": _normalize_code(code), "checkout_id": checkout_id, "status": "reserved"}
        redemption = await tx.find_one("redemptions", where)
        if redemption is None:
            raise not_found("Code in this checkout")
        _ = await tx.update("redemptions", where, {"status": "active", "checkout_id": None, "discount_applied": None})
        checkout = (await tx.increment(
            "checkouts", {"id": checkout_id},
            {"participants": -1, "total_discount": -(redemption["discount_applied"] or 0)},
        ))[0]
        if checkout["participants"] == 0:
            checkout = (await tx.update(
                "checkouts", {"id": checkout_id}, {"promotion_id": None, "discount_type": None, "total_discount": 0}
            ))[0]
    return await _checkout_out(storage, checkout)


@router.post("/checkouts/{checkout_id}/complete", response_model=CheckoutOut)
async def complete_checkout(checkout_id: int, account: CurrentCompany, storage: StorageDep):
    async with storage.transaction() as tx:
        checkout = await _own_checkout(tx, account, checkout_id, open_only=True)
        checkout = await _complete(tx, account, checkout)
    return await _checkout_out(storage, checkout)


@router.post("/checkouts/{checkout_id}/cancel", response_model=CheckoutOut)
async def cancel_checkout(checkout_id: int, account: CurrentCompany, storage: StorageDep):
    """Abort the order; scanned codes become usable again."""
    async with storage.transaction() as tx:
        checkout = await _own_checkout(tx, account, checkout_id, open_only=True)
        _ = await tx.update(
            "redemptions",
            {"checkout_id": checkout_id, "status": "reserved"},
            {"status": "active", "checkout_id": None, "discount_applied": None},
        )
        checkout = (await tx.update(
            "checkouts", {"id": checkout_id}, {"status": "cancelled", "closed_at": config.now()}
        ))[0]
    return await _checkout_out(storage, checkout)


# Statistics ------------------------------------------------------------------------

@router.get("/stats", response_model=CompanyStats)
async def company_stats(
    account: CurrentCompany, storage: StorageDep, days: Annotated[int, Query(ge=1, le=365)] = 30
):
    company_id = _company_id(account)
    promos = await storage.find("promotions", {"company_id": company_id}, order_by="-id")
    redemptions = await storage.find("redemptions", {"company_id": company_id})
    checkouts = await storage.find("checkouts", {"company_id": company_id, "status": "completed"})
    promo_kind = {p["id"]: p["kind"] for p in promos}

    statuses = [(r, redemption_status(r)) for r in redemptions]
    not_cancelled = [r for r, s in statuses if s != "cancelled"]

    by_promotion = []
    for promo in promos:
        own = [(r, s) for r, s in statuses if r["promotion_id"] == promo["id"]]
        counts = Counter(s for _, s in own)
        kept = [r for r, s in own if s != "cancelled"]
        by_promotion.append({
            "promotion_id": promo["id"],
            "title": promo["title"],
            "kind": promo["kind"],
            "active": promo["active"],
            "views": promo["views"],
            "redemptions": len(kept),
            "claimed": counts["claimed"],
            "pending": counts["active"] + counts["reserved"],
            "cancelled": counts["cancelled"],
            "expired": counts["expired"],
            "points_spent": sum(r["points_spent"] for r in kept),
            "unique_customers": len({r["user_id"] for r in kept}),
        })

    today = config.today()
    first_day = today - timedelta(days=days - 1)
    created = Counter(r["day"] for r in not_cancelled if r["day"] >= first_day)
    claimed = Counter(
        r["claimed_at"].astimezone(config.TIMEZONE).date() for r in redemptions if r["claimed_at"] is not None
    )
    daily = [
        {"day": d, "redemptions": created[d], "claims": claimed[d]}
        for d in (first_day + timedelta(days=i) for i in range(days))
    ]

    group_sizes = [c["participants"] for c in checkouts if promo_kind.get(c["promotion_id"]) == "group"]
    return {
        "promotions": len(promos),
        "active_promotions": sum(1 for p in promos if p["active"]),
        "total_views": sum(p["views"] for p in promos),
        "redemptions": len(not_cancelled),
        "claimed": sum(1 for _, s in statuses if s == "claimed"),
        "unique_customers": len({r["user_id"] for r in not_cancelled}),
        "points_spent": sum(r["points_spent"] for r in not_cancelled),
        "checkouts_completed": len(checkouts),
        "average_group_size": round(sum(group_sizes) / len(group_sizes), 2) if group_sizes else None,
        "total_amount_discounted": sum(c["total_discount"] for c in checkouts if c["discount_type"] == "amount"),
        "daily": daily,
        "by_promotion": by_promotion,
    }
