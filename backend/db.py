"""SQLite access (aiosqlite) and schema bootstrap."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator
from uuid import uuid4

import aiosqlite

from .config import get_settings

log = logging.getLogger("nexflow.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    token_version INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS workflows (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    nodes TEXT NOT NULL,
    edges TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_workflows_user_updated ON workflows(user_id, updated_at DESC);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@asynccontextmanager
async def connect() -> AsyncIterator[aiosqlite.Connection]:
    db = await aiosqlite.connect(get_settings().db_path, timeout=10)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    try:
        yield db
    finally:
        await db.close()


async def init_db() -> None:
    from .auth import hash_password

    settings = get_settings()
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    async with connect() as db:
        await db.execute("PRAGMA journal_mode = WAL")
        await db.executescript(SCHEMA)
        columns = {row["name"] for row in await (await db.execute("PRAGMA table_info(users)")).fetchall()}
        if "token_version" not in columns:  # databases created by earlier versions
            await db.execute("ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0")
        await db.commit()
        if settings.seed_demo:
            cur = await db.execute("SELECT 1 FROM users WHERE email = ?", ("demo@nexflow.app",))
            if await cur.fetchone() is None:
                await db.execute(
                    "INSERT INTO users (id, email, password_hash, name, created_at) VALUES (?,?,?,?,?)",
                    (str(uuid4()), "demo@nexflow.app", await hash_password("demo1234"), "Demo User", utcnow()),
                )
                await db.commit()
                log.warning("Seeded demo account demo@nexflow.app / demo1234 (disable with NEXFLOW_SEED_DEMO=false)")
