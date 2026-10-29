"""NexFlow Pro API: auth, workflow storage and the execution endpoint."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from uuid import uuid4

import aiosqlite
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse

from .auth import (
    client_key,
    create_token,
    get_current_user,
    hash_password,
    login_limiter,
    verify_password,
)
from .config import get_settings
from .db import connect, init_db, utcnow
from .engine import analyze_graph, run_workflow
from .executors import EXECUTORS
from .schemas import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    ExecuteRequest,
    GraphModel,
    LoginRequest,
    RegisterRequest,
    UpdateProfileRequest,
    WorkflowCreate,
    WorkflowUpdate,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("nexflow")
VERSION = "3.0.0"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await init_db()
    yield


settings = get_settings()
app = FastAPI(
    title="NexFlow Pro",
    version=VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,  # auth uses a bearer header, never cookies
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    if not request.url.path.startswith("/api"):
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "connect-src 'self'; frame-ancestors 'none'",
        )
    return response


api = APIRouter(prefix="/api")
_active_runs = 0


# ---------------------------------------------------------------- health ----
@api.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": VERSION}


@api.get("/config")
async def public_config() -> dict[str, Any]:
    cfg = get_settings()
    return {
        "version": VERSION,
        "allow_registration": cfg.allow_registration,
        "demo_account": cfg.seed_demo,
        "llm_live": bool(cfg.openai_api_key),
        "email_live": bool(cfg.smtp_host),
        "node_types": sorted(EXECUTORS),
    }


# ------------------------------------------------------------------ auth ----
def _auth_payload(user_id: str, email: str, name: str, token_version: int = 0) -> dict[str, Any]:
    return {
        "token": create_token(user_id, email, token_version),
        "user": {"id": user_id, "email": email, "name": name},
    }


@api.post("/auth/register", status_code=201)
async def register(body: RegisterRequest) -> dict[str, Any]:
    if not get_settings().allow_registration:
        raise HTTPException(403, "Registration is disabled on this server")
    user_id = str(uuid4())
    password_hash = await hash_password(body.password)
    async with connect() as db:
        try:
            await db.execute(
                "INSERT INTO users (id, email, password_hash, name, created_at) VALUES (?,?,?,?,?)",
                (user_id, body.email, password_hash, body.name, utcnow()),
            )
            await db.commit()
        except aiosqlite.IntegrityError as exc:
            raise HTTPException(409, "That email is already registered") from exc
    return _auth_payload(user_id, body.email, body.name)


@api.post("/auth/login")
async def login(body: LoginRequest, request: Request) -> dict[str, Any]:
    key = client_key(request, body.email)
    login_limiter.check(key)
    async with connect() as db:
        cur = await db.execute("SELECT * FROM users WHERE email = ?", (body.email,))
        row = await cur.fetchone()
    if not await verify_password(body.password, row["password_hash"] if row else None):
        login_limiter.fail(key)
        raise HTTPException(401, "Invalid email or password")
    login_limiter.reset(key)
    return _auth_payload(row["id"], row["email"], row["name"], row["token_version"])


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)) -> dict[str, Any]:
    return user


async def _verify_current_password(user_id: str, password: str | None) -> aiosqlite.Row:
    """Re-check the password for sensitive changes. Wrong passwords count toward the login limiter."""
    key = f"account|{user_id}"
    login_limiter.check(key)
    async with connect() as db:
        row = await (await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))).fetchone()
    if row is None:
        raise HTTPException(401, "User no longer exists")
    if not password or not await verify_password(password, row["password_hash"]):
        login_limiter.fail(key)
        raise HTTPException(403, "Current password is incorrect")
    login_limiter.reset(key)
    return row


@api.patch("/auth/me")
async def update_profile(body: UpdateProfileRequest, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    if body.name is None and body.email is None:
        raise HTTPException(400, "Nothing to update")
    new_name = body.name if body.name is not None else user["name"]
    new_email = body.email if body.email is not None else user["email"]
    if new_email != user["email"]:
        await _verify_current_password(user["id"], body.current_password)
    async with connect() as db:
        try:
            await db.execute("UPDATE users SET name = ?, email = ? WHERE id = ?", (new_name, new_email, user["id"]))
            await db.commit()
        except aiosqlite.IntegrityError as exc:
            raise HTTPException(409, "That email is already registered") from exc
        row = await (await db.execute("SELECT token_version FROM users WHERE id = ?", (user["id"],))).fetchone()
    return _auth_payload(user["id"], new_email, new_name, row["token_version"])


@api.post("/auth/change-password")
async def change_password(body: ChangePasswordRequest, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    await _verify_current_password(user["id"], body.current_password)
    new_hash = await hash_password(body.new_password)
    async with connect() as db:
        # Bumping token_version signs the account out everywhere else.
        await db.execute(
            "UPDATE users SET password_hash = ?, token_version = token_version + 1 WHERE id = ?",
            (new_hash, user["id"]),
        )
        await db.commit()
        row = await (await db.execute("SELECT token_version FROM users WHERE id = ?", (user["id"],))).fetchone()
    return _auth_payload(user["id"], user["email"], user["name"], row["token_version"])


@api.delete("/auth/me", status_code=204)
async def delete_account(body: DeleteAccountRequest, user: dict = Depends(get_current_user)) -> Response:
    await _verify_current_password(user["id"], body.password)
    async with connect() as db:
        await db.execute("DELETE FROM users WHERE id = ?", (user["id"],))  # workflows cascade
        await db.commit()
    workspace = get_settings().files_dir / (re.sub(r"[^A-Za-z0-9_-]", "_", user["id"]) or "anonymous")
    await asyncio.to_thread(shutil.rmtree, workspace, True)
    return Response(status_code=204)


# -------------------------------------------------------------- pipeline ----
@api.post("/pipelines/parse")
async def parse_pipeline(body: GraphModel, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    nodes, edges = body.dump()
    return analyze_graph(nodes, edges)


async def _tracked(events: AsyncIterator[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    """Count a run as active only while its event stream is actually being consumed."""
    global _active_runs
    _active_runs += 1
    try:
        async for item in events:
            yield item
    finally:
        _active_runs -= 1


async def _sse(events: AsyncIterator[dict[str, Any]]) -> AsyncIterator[str]:
    async for item in events:
        yield f"event: {item['event']}\ndata: {json.dumps(item['data'], default=str)}\n\n"


@api.post("/workflows/execute")
async def execute_workflow(body: ExecuteRequest, user: dict = Depends(get_current_user)):
    if _active_runs >= get_settings().max_concurrent_runs:
        raise HTTPException(429, "The server is busy running other workflows. Try again shortly.")
    nodes, edges = body.dump()
    events = _tracked(run_workflow(nodes, edges, user["id"]))

    if body.stream:
        return StreamingResponse(
            _sse(events),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
        )

    results: list[dict[str, Any]] = []
    final: dict[str, Any] = {}
    order: list[str] = []
    async for item in events:
        name, data = item["event"], item["data"]
        if name == "start":
            order = data["execution_order"]
        elif name in {"node_complete", "node_error", "node_skipped"}:
            results.append(data)
        elif name == "error":
            return JSONResponse(status_code=422, content={"detail": data["detail"]})
        elif name == "done":
            final = data
    return {**final, "execution_order": order, "results": results}


# ------------------------------------------------------------- workflows ----
def _row_to_workflow(row: aiosqlite.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "nodes": json.loads(row["nodes"]),
        "edges": json.loads(row["edges"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@api.get("/workflows")
async def list_workflows(user: dict = Depends(get_current_user)) -> list[dict[str, Any]]:
    async with connect() as db:
        cur = await db.execute(
            "SELECT id, name, nodes, edges, created_at, updated_at FROM workflows "
            "WHERE user_id = ? ORDER BY updated_at DESC",
            (user["id"],),
        )
        rows = await cur.fetchall()
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "node_count": len(json.loads(r["nodes"])),
            "edge_count": len(json.loads(r["edges"])),
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]


@api.post("/workflows", status_code=201)
async def create_workflow(body: WorkflowCreate, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    workflow_id, now = str(uuid4()), utcnow()
    nodes, edges = body.dump()
    async with connect() as db:
        await db.execute(
            "INSERT INTO workflows (id, user_id, name, nodes, edges, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
            (workflow_id, user["id"], body.name, json.dumps(nodes), json.dumps(edges), now, now),
        )
        await db.commit()
    return {"id": workflow_id, "name": body.name, "nodes": nodes, "edges": edges, "created_at": now, "updated_at": now}


@api.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    async with connect() as db:
        cur = await db.execute("SELECT * FROM workflows WHERE id = ? AND user_id = ?", (workflow_id, user["id"]))
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(404, "Workflow not found")
    return _row_to_workflow(row)


@api.put("/workflows/{workflow_id}")
async def update_workflow(workflow_id: str, body: WorkflowUpdate, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    nodes, edges = body.dump()
    now = utcnow()
    async with connect() as db:
        cur = await db.execute(
            "UPDATE workflows SET name = ?, nodes = ?, edges = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (body.name, json.dumps(nodes), json.dumps(edges), now, workflow_id, user["id"]),
        )
        await db.commit()
        if cur.rowcount == 0:
            raise HTTPException(404, "Workflow not found")
        cur = await db.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
        row = await cur.fetchone()
    return _row_to_workflow(row)


@api.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str, user: dict = Depends(get_current_user)) -> dict[str, str]:
    async with connect() as db:
        cur = await db.execute("DELETE FROM workflows WHERE id = ? AND user_id = ?", (workflow_id, user["id"]))
        await db.commit()
        if cur.rowcount == 0:
            raise HTTPException(404, "Workflow not found")
    return {"id": workflow_id}


app.include_router(api)


# ------------------------------------------------- static frontend (prod) ----
if settings.static_dir is not None:
    _static_root = settings.static_dir

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(404, "Not found")
        candidate = (_static_root / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(_static_root):
            return FileResponse(candidate)
        return FileResponse(_static_root / "index.html", headers={"Cache-Control": "no-cache"})
else:
    log.info("No frontend build found; serving the API only (run the React dev server separately).")
