"""Support tickets opened by users and companies, answered by corporate."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

import config
from datastore import Row, Storage
from dependencies import Account, PageDep, StorageDep, not_found, require_role
from models import TicketIn, TicketMessageIn, TicketOut
from services.accounts import names_by_id

router = APIRouter(prefix="/tickets", tags=["Tickets"])

TicketAuthor = Annotated[Account, Depends(require_role("user", "company"))]


async def ticket_out(storage: Storage, ticket: Row, *, with_messages: bool = True) -> dict:
    messages = (
        await storage.find("ticket_messages", {"ticket_id": ticket["id"]}, order_by="id") if with_messages else []
    )
    names = await names_by_id(storage, {ticket["author_id"], *(m["author_id"] for m in messages)})
    return {
        **ticket,
        "author_name": names.get(ticket["author_id"]),
        "messages": [{**m, "author_name": names.get(m["author_id"])} for m in messages],
    }


async def add_message(tx: Storage, ticket: Row, author: Account, body: str) -> None:
    now = config.now()
    _ = await tx.insert("ticket_messages", {
        "ticket_id": ticket["id"],
        "author_id": author["id"],
        "from_staff": author["role"] == "corporate",
        "body": body.strip(),
        "created_at": now,
    })
    _ = await tx.update("tickets", {"id": ticket["id"]}, {"updated_at": now})


async def _own_ticket(storage: Storage, account: Account, ticket_id: int) -> Row:
    ticket = await storage.find_one("tickets", {"id": ticket_id, "author_id": account["id"]})
    if ticket is None:
        raise not_found("Ticket")
    return ticket


@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
async def open_ticket(body: TicketIn, account: TicketAuthor, storage: StorageDep):
    now = config.now()
    async with storage.transaction() as tx:
        ticket = await tx.insert("tickets", {
            "author_id": account["id"],
            "author_role": account["role"],
            "company_id": account["company_id"],
            "subject": body.subject.strip(),
            "category": body.category,
            "status": "open",
            "priority": "normal",
            "assigned_to": None,
            "created_at": now,
            "updated_at": now,
        })
        await add_message(tx, ticket, account, body.body)
    return await ticket_out(storage, ticket)


@router.get("", response_model=list[TicketOut])
async def my_tickets(account: TicketAuthor, storage: StorageDep, page: PageDep):
    rows = await storage.find(
        "tickets", {"author_id": account["id"]}, order_by="-updated_at", limit=page.limit, offset=page.offset
    )
    return [await ticket_out(storage, t, with_messages=False) for t in rows]


@router.get("/{ticket_id}", response_model=TicketOut)
async def get_ticket(ticket_id: int, account: TicketAuthor, storage: StorageDep):
    return await ticket_out(storage, await _own_ticket(storage, account, ticket_id))


@router.post("/{ticket_id}/messages", response_model=TicketOut)
async def reply(ticket_id: int, body: TicketMessageIn, account: TicketAuthor, storage: StorageDep):
    async with storage.transaction() as tx:
        ticket = await _own_ticket(tx, account, ticket_id)
        await add_message(tx, ticket, account, body.body)
        if ticket["status"] in ("resolved", "closed"):
            _ = await tx.update("tickets", {"id": ticket_id}, {"status": "open"})
    return await ticket_out(storage, await _own_ticket(storage, account, ticket_id))
