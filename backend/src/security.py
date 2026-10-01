"""Password hashing and signed tokens (JWT-compatible HS256), stdlib only."""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any

import config

_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}

# Human-friendly alphabet for codes that may be typed by a cashier.
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class InvalidToken(Exception):
    pass


# Passwords --------------------------------------------------------------------

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt, digest = stored.split("$")
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    candidate = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), **_SCRYPT)
    return hmac.compare_digest(candidate.hex(), digest)


# Tokens -----------------------------------------------------------------------

def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _sign(message: bytes) -> str:
    return _b64encode(hmac.new(config.SECRET_KEY.encode(), message, hashlib.sha256).digest())


def create_token(subject: int, purpose: str, ttl_seconds: int, **claims: Any) -> str:
    """Create a signed token. ``purpose`` prevents using e.g. a friend code as a login token."""
    header = _b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    issued = int(time.time())
    payload = {"sub": str(subject), "pur": purpose, "iat": issued, "exp": issued + ttl_seconds, **claims}
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header}.{body}"
    return f"{signing_input}.{_sign(signing_input.encode())}"


def decode_token(token: str, purpose: str) -> dict[str, Any]:
    try:
        header, body, signature = token.split(".")
    except ValueError:
        raise InvalidToken("Malformed token")
    if not hmac.compare_digest(signature, _sign(f"{header}.{body}".encode())):
        raise InvalidToken("Bad signature")
    try:
        payload = json.loads(_b64decode(body))
    except ValueError:
        raise InvalidToken("Malformed payload")
    if payload.get("pur") != purpose:
        raise InvalidToken("Wrong token purpose")
    if payload.get("exp", 0) < time.time():
        raise InvalidToken("Token expired")
    payload["sub"] = int(payload["sub"])
    return payload


def create_access_token(account_id: int, role: str) -> str:
    return create_token(account_id, "access", config.TOKEN_TTL_HOURS * 3600, role=role)


def generate_code(groups: int = 3, size: int = 4) -> str:
    """Random code like ``K7QX-2MRT-9HCA`` for redemption QR codes."""
    return "-".join("".join(secrets.choice(_CODE_ALPHABET) for _ in range(size)) for _ in range(groups))
