"""
Corporate dashboard. Staff levels (each includes the previous):

- support:    read users, companies, points, stats; handle tickets
- admin:      ban/edit/delete accounts, reset chat limits, manage companies,
              company accounts, missions and puzzles
- superadmin: add/remove points, manage corporate staff
"""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status

import config
from datastore import Row, Storage
from dependencies import (
    CorporateAdmin,
    CorporateSuperadmin,
    CorporateSupport,
    PageDep,
    StorageDep,
    not_found,
)
from models import (
    AccountOut,
    AccountUpdate,
    CompanyAdminOut,
    CompanyAdminUpdate,
    CompanyIn,
    CorporateAccountIn,
    CorporateAccountOut,
    CorporateLevelUpdate,
    Message,
    MissionAdminOut,
    MissionIn,
    MissionUpdate,
    PlatformStats,
    PointsAdjustIn,
    PointsAdjustOut,
    PointTransactionOut,
    PuzzleAdminOut,
    PuzzleIn,
    PuzzleUpdate,
    ResetLimitOut,
    StaffAccountIn,
    TicketMessageIn,
    TicketOut,
    TicketPriority,
    TicketStatus,
    TicketUpdate,
)
from routers.tickets import add_message, ticket_out
from services import points
from services.accounts import create_account, ensure_unique
from services.missions import start_of_day

router = APIRouter(prefix="/corporate", tags=["Corporate"])


# Accounts (users and company staff) ---------------------------------------------

async def _managed_account(storage: Storage, account_id: int) -> Row:
    """User or company accounts; corporate staff are managed under /corporate/staff."""
    account = await storage.find_one("users", {"id": account_id, "role__in": ["user", "company"], "status__ne": "deleted"})
    if account is None:
        raise not_found("Account")
    return account


async def _regular_user(storage: Storage, user_id: int) -> Row:
    user = await storage.find_one("users", {"id": user_id, "role": "user", "status__ne": "deleted"})
    if user is None:
        raise not_found("User")
    return user


async def _soft_delete(storage: Storage, account_id: int) -> None:
    # Keep the row so points, chats and redemptions stay referentially intact.
    _ = await storage.update("users", {"id": account_id}, {
        "status": "deleted",
        "email": f"deleted-{account_id}@deleted.invalid",
        "username": None,
        "password_hash": "!",
    })


@router.get("/users", response_model=list[CorporateAccountOut])
async def list_accounts(
    staff: CorporateSupport,
    storage: StorageDep,
    page: PageDep,
    q: str | None = None,
    role: Literal["user", "company"] | None = None,
    status_filter: Annotated[Literal["active", "banned", "deleted"] | None, Query(alias="status")] = None,
    company_id: int | None = None,
):
    where = {"role__in": [role] if role else ["user", "company"]}
    if status_filter:
        where["status"] = status_filter
    if company_id:
        where["company_id"] = company_id
    if q and (term := q.strip().replace("%", "").replace("_", "")):
        found = {
            r["id"]: r
            for column in ("display_name", "username", "email")
            for r in await storage.find("users", {**where, f"{column}__ilike": f"%{term}%"})
        }
        return page.slice(sorted(found.values(), key=lambda r: r["id"]))
    return await storage.find("users", where, order_by="id", limit=page.limit, offset=page.offset)


@router.get("/users/{account_id}", response_model=CorporateAccountOut)
async def get_account(account_id: int, staff: CorporateSupport, storage: StorageDep):
    account = await storage.find_one("users", {"id": account_id, "role__in": ["user", "company"]})
    if account is None:
        raise not_found("Account")
    return account


@router.patch("/users/{account_id}", response_model=CorporateAccountOut)
async def update_account(account_id: int, body: AccountUpdate, staff: CorporateAdmin, storage: StorageDep):
    """Edit an account or ban/unban it (``status``)."""
    _ = await _managed_account(storage, account_id)
    changes = body.model_dump(exclude_unset=True)
    if "email" in changes:
        await ensure_unique(storage, email=changes["email"], exclude_id=account_id)
    rows = await storage.update("users", {"id": account_id}, changes)
    return rows[0]


@router.delete("/users/{account_id}", response_model=Message)
async def delete_account(account_id: int, staff: CorporateAdmin, storage: StorageDep):
    _ = await _managed_account(storage, account_id)
    await _soft_delete(storage, account_id)
    return {"detail": "Account deleted"}


@router.post("/reset_limit", response_model=ResetLimitOut)
async def reset_limit(
    staff: CorporateAdmin, storage: StorageDep, user: Annotated[int, Query(description="User id")]
):
    """Reset a user's per-person chat points limit, so they can earn chat points from everyone again."""
    _ = await _regular_user(storage, user)
    rows = await storage.increment("users", {"id": user}, {"chat_limit_epoch": 1})
    return {"user_id": user, "chat_limit_epoch": rows[0]["chat_limit_epoch"], "detail": "Chat limit reset"}


@router.get("/users/{user_id}/points", response_model=list[PointTransactionOut])
async def user_points_history(user_id: int, staff: CorporateSupport, storage: StorageDep, page: PageDep):
    _ = await _regular_user(storage, user_id)
    return await storage.find(
        "point_transactions", {"user_id": user_id}, order_by="-id", limit=page.limit, offset=page.offset
    )


@router.post("/users/{user_id}/points", response_model=PointsAdjustOut)
async def adjust_points(user_id: int, body: PointsAdjustIn, staff: CorporateSuperadmin, storage: StorageDep):
    """Manually add (positive) or remove (negative) points."""
    _ = await _regular_user(storage, user_id)
    details = {"description": body.description, "actor_id": staff["id"]}
    async with storage.transaction() as tx:
        if body.amount > 0:
            _ = await points.award(tx, user_id, body.amount, "adjustment", **details)
        elif not await points.spend(tx, user_id, -body.amount, "adjustment", **details):
            raise HTTPException(status.HTTP_409_CONFLICT, "User does not have that many points")
    return {"user_id": user_id, "amount": body.amount, "balance": await points.balance(storage, user_id)}


# Corporate staff -------------------------------------------------------------------

@router.get("/staff", response_model=list[AccountOut])
async def list_staff(staff: CorporateSuperadmin, storage: StorageDep):
    return await storage.find("users", {"role": "corporate", "status__ne": "deleted"}, order_by="id")


@router.post("/staff", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
async def create_staff(body: CorporateAccountIn, staff: CorporateSuperadmin, storage: StorageDep):
    return await create_account(
        storage, role="corporate", corporate_level=body.corporate_level,
        email=body.email, password=body.password, display_name=body.display_name,
    )


async def _other_staff(storage: Storage, staff: Row, account_id: int) -> Row:
    if account_id == staff["id"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "You cannot change your own staff account here")
    account = await storage.find_one("users", {"id": account_id, "role": "corporate", "status__ne": "deleted"})
    if account is None:
        raise not_found("Staff account")
    return account


@router.patch("/staff/{account_id}", response_model=AccountOut)
async def update_staff_level(
    account_id: int, body: CorporateLevelUpdate, staff: CorporateSuperadmin, storage: StorageDep
):
    _ = await _other_staff(storage, staff, account_id)
    return (await storage.update("users", {"id": account_id}, {"corporate_level": body.corporate_level}))[0]


@router.delete("/staff/{account_id}", response_model=Message)
async def delete_staff(account_id: int, staff: CorporateSuperadmin, storage: StorageDep):
    _ = await _other_staff(storage, staff, account_id)
    await _soft_delete(storage, account_id)
    return {"detail": "Staff account deleted"}


# Companies -------------------------------------------------------------------------

async def _company(storage: Storage, company_id: int) -> Row:
    company = await storage.get("companies", company_id)
    if company is None:
        raise not_found("Company")
    return company


@router.get("/companies", response_model=list[CompanyAdminOut])
async def list_companies(
    staff: CorporateSupport,
    storage: StorageDep,
    page: PageDep,
    q: str | None = None,
    status_filter: Annotated[Literal["active", "inactive"] | None, Query(alias="status")] = None,
):
    where = {}
    if status_filter:
        where["status"] = status_filter
    if q:
        where["name__ilike"] = f"%{q.strip().replace('%', '').replace('_', '')}%"
    return await storage.find("companies", where, order_by="name", limit=page.limit, offset=page.offset)


@router.post("/companies", response_model=CompanyAdminOut, status_code=status.HTTP_201_CREATED)
async def create_company(body: CompanyIn, staff: CorporateAdmin, storage: StorageDep):
    return await storage.insert("companies", {**body.model_dump(), "status": "active", "created_at": config.now()})


@router.get("/companies/{company_id}", response_model=CompanyAdminOut)
async def get_company(company_id: int, staff: CorporateSupport, storage: StorageDep):
    return await _company(storage, company_id)


@router.patch("/companies/{company_id}", response_model=CompanyAdminOut)
async def update_company(company_id: int, body: CompanyAdminUpdate, staff: CorporateAdmin, storage: StorageDep):
    """Edit a company; ``status=inactive`` blocks its accounts and hides its promotions."""
    _ = await _company(storage, company_id)
    return (await storage.update("companies", {"id": company_id}, body.model_dump(exclude_unset=True)))[0]


@router.get("/companies/{company_id}/accounts", response_model=list[AccountOut])
async def list_company_accounts(company_id: int, staff: CorporateSupport, storage: StorageDep):
    _ = await _company(storage, company_id)
    return await storage.find(
        "users", {"role": "company", "company_id": company_id, "status__ne": "deleted"}, order_by="id"
    )


@router.post("/companies/{company_id}/accounts", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
async def create_company_account(company_id: int, body: StaffAccountIn, staff: CorporateAdmin, storage: StorageDep):
    """Give a company access to the company portal."""
    _ = await _company(storage, company_id)
    return await create_account(
        storage, role="company", company_id=company_id,
        email=body.email, password=body.password, display_name=body.display_name,
    )


# Tickets ---------------------------------------------------------------------------

async def _ticket(storage: Storage, ticket_id: int) -> Row:
    ticket = await storage.get("tickets", ticket_id)
    if ticket is None:
        raise not_found("Ticket")
    return ticket


@router.get("/tickets", response_model=list[TicketOut])
async def list_tickets(
    staff: CorporateSupport,
    storage: StorageDep,
    page: PageDep,
    status_filter: Annotated[TicketStatus | None, Query(alias="status")] = None,
    priority: TicketPriority | None = None,
    author_role: Literal["user", "company"] | None = None,
    assigned_to: int | None = None,
    company_id: int | None = None,
):
    where = {}
    for key, value in (("status", status_filter), ("priority", priority), ("author_role", author_role),
                       ("assigned_to", assigned_to), ("company_id", company_id)):
        if value is not None:
            where[key] = value
    rows = await storage.find("tickets", where, order_by="-updated_at", limit=page.limit, offset=page.offset)
    return [await ticket_out(storage, t, with_messages=False) for t in rows]


@router.get("/tickets/{ticket_id}", response_model=TicketOut)
async def get_ticket(ticket_id: int, staff: CorporateSupport, storage: StorageDep):
    return await ticket_out(storage, await _ticket(storage, ticket_id))


@router.patch("/tickets/{ticket_id}", response_model=TicketOut)
async def update_ticket(ticket_id: int, body: TicketUpdate, staff: CorporateSupport, storage: StorageDep):
    _ = await _ticket(storage, ticket_id)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("assigned_to") is not None and not await storage.exists(
        "users", {"id": changes["assigned_to"], "role": "corporate", "status": "active"}
    ):
        raise HTTPException(422, "assigned_to must be an active staff account")
    rows = await storage.update("tickets", {"id": ticket_id}, {**changes, "updated_at": config.now()})
    return await ticket_out(storage, rows[0])


@router.post("/tickets/{ticket_id}/messages", response_model=TicketOut)
async def reply_ticket(ticket_id: int, body: TicketMessageIn, staff: CorporateSupport, storage: StorageDep):
    async with storage.transaction() as tx:
        ticket = await _ticket(tx, ticket_id)
        await add_message(tx, ticket, staff, body.body)
        if ticket["status"] == "open":
            _ = await tx.update("tickets", {"id": ticket_id}, {"status": "in_progress"})
    return await ticket_out(storage, await _ticket(storage, ticket_id))


# Missions & puzzles ------------------------------------------------------------------

def _date_range(from_date: date | None, to_date: date | None) -> dict:
    where = {}
    if from_date:
        where["date__gte"] = from_date
    if to_date:
        where["date__lte"] = to_date
    return where


DateFrom = Annotated[date | None, Query(alias="from")]
DateTo = Annotated[date | None, Query(alias="to")]


@router.get("/missions", response_model=list[MissionAdminOut])
async def list_missions(
    staff: CorporateSupport, storage: StorageDep, page: PageDep, from_date: DateFrom = None, to_date: DateTo = None
):
    return await storage.find(
        "missions", _date_range(from_date, to_date), order_by=["-date", "id"], limit=page.limit, offset=page.offset
    )


@router.post("/missions", response_model=MissionAdminOut, status_code=status.HTTP_201_CREATED)
async def create_mission(body: MissionIn, staff: CorporateAdmin, storage: StorageDep):
    target = 1 if body.kind == "checkin" else body.target
    return await storage.insert("missions", {
        **body.model_dump(), "target": target, "created_by": staff["id"], "created_at": config.now(),
    })


@router.patch("/missions/{mission_id}", response_model=MissionAdminOut)
async def update_mission(mission_id: int, body: MissionUpdate, staff: CorporateAdmin, storage: StorageDep):
    rows = await storage.update("missions", {"id": mission_id}, body.model_dump(exclude_unset=True))
    if not rows:
        raise not_found("Mission")
    return rows[0]


@router.delete("/missions/{mission_id}", response_model=Message)
async def delete_mission(mission_id: int, staff: CorporateAdmin, storage: StorageDep):
    if await storage.exists("mission_claims", {"mission_id": mission_id}):
        raise HTTPException(status.HTTP_409_CONFLICT, "Mission was already claimed; set active=false instead")
    if not await storage.delete("missions", {"id": mission_id}):
        raise not_found("Mission")
    return {"detail": "Mission deleted"}


@router.get("/puzzles", response_model=list[PuzzleAdminOut])
async def list_puzzles(
    staff: CorporateSupport, storage: StorageDep, page: PageDep, from_date: DateFrom = None, to_date: DateTo = None
):
    return await storage.find(
        "puzzles", _date_range(from_date, to_date), order_by=["-date", "id"], limit=page.limit, offset=page.offset
    )


@router.post("/puzzles", response_model=PuzzleAdminOut, status_code=status.HTTP_201_CREATED)
async def create_puzzle(body: PuzzleIn, staff: CorporateAdmin, storage: StorageDep):
    return await storage.insert("puzzles", {**body.model_dump(), "created_by": staff["id"], "created_at": config.now()})


@router.patch("/puzzles/{puzzle_id}", response_model=PuzzleAdminOut)
async def update_puzzle(puzzle_id: int, body: PuzzleUpdate, staff: CorporateAdmin, storage: StorageDep):
    rows = await storage.update("puzzles", {"id": puzzle_id}, body.model_dump(exclude_unset=True))
    if not rows:
        raise not_found("Puzzle")
    return rows[0]


@router.delete("/puzzles/{puzzle_id}", response_model=Message)
async def delete_puzzle(puzzle_id: int, staff: CorporateAdmin, storage: StorageDep):
    if await storage.exists("puzzle_plays", {"puzzle_id": puzzle_id}):
        raise HTTPException(status.HTTP_409_CONFLICT, "Puzzle was already played; set active=false instead")
    if not await storage.delete("puzzles", {"id": puzzle_id}):
        raise not_found("Puzzle")
    return {"detail": "Puzzle deleted"}


# Statistics --------------------------------------------------------------------------

@router.get("/stats", response_model=PlatformStats)
async def platform_stats(staff: CorporateSupport, storage: StorageDep):
    today = config.today()
    users = await storage.find("users", {"role": "user"}, columns=["id", "status", "points", "created_at", "last_login_at"])
    live = [u for u in users if u["status"] != "deleted"]
    since = start_of_day(today)
    earned_today = await storage.find("point_transactions", {"day": today, "amount__gt": 0}, columns=["amount"])
    senders_today = await storage.find("messages", {"day": today}, columns=["sender_id"])
    return {
        "users": len(live),
        "users_banned": sum(1 for u in live if u["status"] == "banned"),
        "new_users_today": sum(1 for u in live if u["created_at"] >= since),
        "active_users_today": len(
            {m["sender_id"] for m in senders_today}
            | {u["id"] for u in live if u["last_login_at"] and u["last_login_at"] >= since}
        ),
        "companies": await storage.count("companies"),
        "active_companies": await storage.count("companies", {"status": "active"}),
        "friendships": await storage.count("friendships"),
        "messages_today": len(senders_today),
        "points_in_circulation": sum(u["points"] for u in live),
        "points_earned_today": sum(r["amount"] for r in earned_today),
        "redemptions": await storage.count("redemptions", {"status__ne": "cancelled"}),
        "redemptions_claimed": await storage.count("redemptions", {"status": "claimed"}),
        "open_tickets": await storage.count("tickets", {"status__in": ["open", "in_progress"]}),
    }
