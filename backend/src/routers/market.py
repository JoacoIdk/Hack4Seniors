"""
Market: companies' promotions shown as ads. Users redeem a promotion (paying
its points cost, if any) to get a code they show as a QR at checkout.
"""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

import config
from dependencies import CurrentAccount, CurrentUser, PageDep, StorageDep, not_found
from models import CompanyOut, MarketCompanyOut, PromotionKind, PromotionOut, RedemptionOut
from security import generate_code
from services import points
from services.promotions import active_company_ids, is_available, promotions_out, redemptions_out

router = APIRouter(prefix="/market", tags=["Market"])


async def _available(storage, where: dict) -> list[dict]:
    companies = await active_company_ids(storage)
    rows = await storage.find("promotions", {"active": True, **where}, order_by="-id")
    return [p for p in rows if p["company_id"] in companies and is_available(p)]


@router.get("/promotions", response_model=list[PromotionOut])
async def list_promotions(
    account: CurrentAccount,
    storage: StorageDep,
    page: PageDep,
    q: str | None = None,
    category: str | None = None,
    kind: PromotionKind | None = None,
    company_id: int | None = None,
    max_points: Annotated[int | None, Query(ge=0)] = None,
    affordable: bool = False,
):
    """Currently redeemable promotions. ``affordable=true`` filters by the user's balance."""
    where = {}
    if category:
        where["category__ilike"] = category
    if kind:
        where["kind"] = kind
    if company_id:
        where["company_id"] = company_id
    if max_points is not None:
        where["points_cost__lte"] = max_points
    if affordable and account["role"] == "user":
        where["points_cost__lte"] = min(account["points"], where.get("points_cost__lte", account["points"]))
    rows = await _available(storage, where)
    if q:
        term = q.strip().lower()
        rows = [p for p in rows if term in p["title"].lower() or term in (p["description"] or "").lower()]
    return await promotions_out(storage, page.slice(rows))


@router.get("/promotions/{promotion_id}", response_model=PromotionOut)
async def get_promotion(promotion_id: int, account: CurrentAccount, storage: StorageDep):
    rows = await _available(storage, {"id": promotion_id})
    if not rows:
        raise not_found("Promotion")
    if account["role"] == "user":
        _ = await storage.increment("promotions", {"id": promotion_id}, {"views": 1})
    return (await promotions_out(storage, rows))[0]


@router.post("/promotions/{promotion_id}/redeem", response_model=RedemptionOut, status_code=status.HTTP_201_CREATED)
async def redeem_promotion(promotion_id: int, user: CurrentUser, storage: StorageDep):
    """Spend the promotion's points and get a code to show as a QR at the store."""
    rows = await _available(storage, {"id": promotion_id})
    if not rows:
        raise not_found("Promotion")
    promo = rows[0]
    now = config.now()

    async with storage.transaction() as tx:
        if promo["per_user_limit"] is not None:
            used = await tx.count(
                "redemptions", {"user_id": user["id"], "promotion_id": promotion_id, "status__ne": "cancelled"}
            )
            if used >= promo["per_user_limit"]:
                raise HTTPException(status.HTTP_409_CONFLICT, "You have reached the limit for this promotion")
        if promo["stock"] is not None:
            if not await tx.increment("promotions", {"id": promotion_id, "stock__gte": 1}, {"stock": -1}):
                raise HTTPException(status.HTTP_409_CONFLICT, "This promotion is sold out")
        redemption = await tx.insert("redemptions", {
            "code": await _unique_code(tx),
            "user_id": user["id"],
            "promotion_id": promotion_id,
            "company_id": promo["company_id"],
            "points_spent": promo["points_cost"],
            "status": "active",
            "checkout_id": None,
            "discount_applied": None,
            "day": config.today(),
            "created_at": now,
            "expires_at": now + timedelta(days=promo["redemption_valid_days"]),
            "claimed_at": None,
            "claimed_by": None,
        })
        if not await points.spend(
            tx, user["id"], promo["points_cost"], "redemption", reference_type="redemption",
            reference_id=redemption["id"], description=promo["title"],
        ):
            raise HTTPException(status.HTTP_409_CONFLICT, "Not enough points")
    return (await redemptions_out(storage, [redemption]))[0]


async def _unique_code(storage) -> str:
    while await storage.exists("redemptions", {"code": (code := generate_code())}):
        pass
    return code


@router.get("/companies", response_model=list[CompanyOut])
async def list_companies(account: CurrentAccount, storage: StorageDep, page: PageDep, category: str | None = None):
    where = {"status": "active"}
    if category:
        where["category__ilike"] = category
    return await storage.find("companies", where, order_by="name", limit=page.limit, offset=page.offset)


@router.get("/companies/{company_id}", response_model=MarketCompanyOut)
async def get_company(company_id: int, account: CurrentAccount, storage: StorageDep):
    company = await storage.find_one("companies", {"id": company_id, "status": "active"})
    if company is None:
        raise not_found("Company")
    promos = await _available(storage, {"company_id": company_id})
    return {**company, "promotions": await promotions_out(storage, promos)}
