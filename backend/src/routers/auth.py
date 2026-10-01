"""Registration (users only) and login (all account types)."""

from fastapi import APIRouter, HTTPException, status

import config
from dependencies import CurrentAccount, StorageDep
from models import AccountOut, LoginIn, RegisterIn, TokenOut
from security import create_access_token, verify_password
from services.accounts import create_account, with_company

router = APIRouter(prefix="/auth", tags=["Auth"])


def _token_response(account: dict) -> dict:
    return {
        "access_token": create_access_token(account["id"], account["role"]),
        "expires_in": config.TOKEN_TTL_HOURS * 3600,
        "account": account,
    }


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterIn, storage: StorageDep):
    """Create a regular user account. Company and corporate accounts are created by corporate."""
    account = await create_account(
        storage,
        role="user",
        email=body.email,
        password=body.password,
        username=body.username,
        display_name=body.display_name,
        city=body.city,
        birth_date=body.birth_date,
        language=body.language,
    )
    return _token_response(account)


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, storage: StorageDep):
    """
    Log in with email and password. Each frontend should send its ``role`` so
    accounts can't sign in to the wrong portal.
    """
    account = await storage.find_one("users", {"email": body.email})
    if account is None or account["status"] == "deleted" or not verify_password(body.password, account["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if account["status"] == "banned":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been suspended")
    if body.role and account["role"] != body.role:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account cannot sign in here")
    await with_company(storage, account)
    if account["role"] == "company" and (account["company"] is None or account["company"]["status"] != "active"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Company is not active")
    rows = await storage.update("users", {"id": account["id"]}, {"last_login_at": config.now()})
    return _token_response({**rows[0], "company": account["company"] if "company" in account else None})


@router.get("/me", response_model=AccountOut)
async def me(account: CurrentAccount):
    """The authenticated account, for any role."""
    return account
