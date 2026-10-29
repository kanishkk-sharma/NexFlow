"""Password hashing, JWT handling and request authentication."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings
from .db import connect

ALGORITHM = "HS256"
_bearer = HTTPBearer(auto_error=False)
_DUMMY_HASH = bcrypt.hashpw(b"nexflow-dummy", bcrypt.gensalt(rounds=10)).decode()


def _prepare(password: str) -> bytes:
    return password.encode("utf-8")[:72]  # bcrypt ignores everything past 72 bytes


async def hash_password(password: str) -> str:
    return await asyncio.to_thread(lambda: bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode())


async def verify_password(password: str, password_hash: str | None) -> bool:
    """Always spends hashing time, even for unknown users, to avoid user enumeration."""
    target = password_hash or _DUMMY_HASH

    def check() -> bool:
        try:
            return bcrypt.checkpw(_prepare(password), target.encode())
        except ValueError:
            return False

    ok = await asyncio.to_thread(check)
    return ok and password_hash is not None


def create_token(user_id: str, email: str, token_version: int = 0) -> str:
    settings = get_settings()
    payload = {
        "sub": user_id,
        "email": email,
        "tv": token_version,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.token_ttl_hours),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any]:
    if creds is None:
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(creds.credentials, get_settings().secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(401, "Invalid or expired token", headers={"WWW-Authenticate": "Bearer"}) from exc
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(401, "Invalid token")
    async with connect() as db:
        cur = await db.execute("SELECT id, email, name, token_version FROM users WHERE id = ?", (user_id,))
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(401, "User no longer exists")
    if payload.get("tv", 0) != row["token_version"]:
        raise HTTPException(401, "Session is no longer valid. Please sign in again.", headers={"WWW-Authenticate": "Bearer"})
    return {"id": row["id"], "email": row["email"], "name": row["name"]}


class LoginLimiter:
    """In-memory sliding-window limiter against password guessing."""

    def __init__(self, attempts: int = 8, window_s: int = 300) -> None:
        self.attempts, self.window_s = attempts, window_s
        self._failures: dict[str, list[float]] = {}

    def _recent(self, key: str) -> list[float]:
        cutoff = time.monotonic() - self.window_s
        recent = [t for t in self._failures.get(key, []) if t > cutoff]
        if recent:
            self._failures[key] = recent
        else:
            self._failures.pop(key, None)
        return recent

    def check(self, key: str) -> None:
        if len(self._recent(key)) >= self.attempts:
            raise HTTPException(429, "Too many failed attempts. Please wait a few minutes and try again.")

    def fail(self, key: str) -> None:
        self._failures.setdefault(key, []).append(time.monotonic())
        if len(self._failures) > 10_000:  # bound memory
            self._failures.clear()

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)


login_limiter = LoginLimiter()


def client_key(request: Request, email: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{host}|{email}"
