"""FastAPI dependencies: storage, authentication, role checks and pagination."""

from typing import Annotated, Any

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from datastore import Storage, get_storage
from security import InvalidToken, decode_token

Account = dict[str, Any]

StorageDep = Annotated[Storage, Depends(get_storage)]

# Corporate staff hierarchy: each level can do everything the previous ones can.
CORPORATE_LEVELS = ("support", "admin", "superadmin")

_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


async def load_account(token: str, storage: Storage) -> Account:
    """Resolve an access token to an active account (used by HTTP and WebSocket routes)."""
    try:
        payload = decode_token(token, "access")
    except InvalidToken:
        raise _unauthorized("Invalid or expired token")
    account = await storage.get("users", payload["sub"])
    if account is None or account["status"] != "active":
        raise _unauthorized("Account is not active")
    if account["role"] == "company":
        company = await storage.get("companies", account["company_id"]) if account["company_id"] else None
        if company is None or company["status"] != "active":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Company is not active")
        account["company"] = company
    return account


async def get_current_account(
    storage: StorageDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Account:
    if credentials is None:
        raise _unauthorized()
    return await load_account(credentials.credentials, storage)


def require_role(*roles: str):
    async def dependency(account: Annotated[Account, Depends(get_current_account)]) -> Account:
        if account["role"] not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed for this account type")
        return account

    return dependency


def has_level(account: Account, minimum: str) -> bool:
    level = account.get("corporate_level") or "support"
    return CORPORATE_LEVELS.index(level) >= CORPORATE_LEVELS.index(minimum)


def require_corporate(minimum: str = "support"):
    async def dependency(account: Annotated[Account, Depends(require_role("corporate"))]) -> Account:
        if not has_level(account, minimum):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires corporate level '{minimum}' or higher")
        return account

    return dependency


CurrentAccount = Annotated[Account, Depends(get_current_account)]
CurrentUser = Annotated[Account, Depends(require_role("user"))]
CurrentCompany = Annotated[Account, Depends(require_role("company"))]
CorporateSupport = Annotated[Account, Depends(require_corporate("support"))]
CorporateAdmin = Annotated[Account, Depends(require_corporate("admin"))]
CorporateSuperadmin = Annotated[Account, Depends(require_corporate("superadmin"))]


class Page:
    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0)] = 0,
    ):
        self.limit = limit
        self.offset = offset

    def slice(self, rows: list[Any]) -> list[Any]:
        return rows[self.offset:self.offset + self.limit]


PageDep = Annotated[Page, Depends()]


def not_found(what: str = "Resource") -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"{what} not found")
