"""Node executors. Each takes (ctx, data, inputs) and returns a JSON-able value."""

from __future__ import annotations

import asyncio
import json
import re
import smtplib
import sqlite3
import ssl
import time
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote
from uuid import uuid4

from .config import get_settings
from .safe_eval import EvalError, safe_eval

VAR_RE = re.compile(r"\{\{\s*([A-Za-z_$][\w$]*)\s*\}\}")
EMAIL_RE = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+$")


class NodeError(Exception):
    """A user-facing node failure (bad configuration or bad input)."""


class ExecutionContext:
    """Per-run state: owner and a lazily created, throw-away SQLite sandbox."""

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id
        self._db: sqlite3.Connection | None = None

    def sandbox_db(self) -> sqlite3.Connection:
        if self._db is None:
            conn = sqlite3.connect(":memory:", check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.executescript(_SEED_SQL)
            conn.set_authorizer(_authorizer)
            self._db = conn
        return self._db

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return json.dumps(value, ensure_ascii=False, default=str)


def render_template(template: str, variables: dict[str, Any], transform: Callable[[str], str] = lambda s: s) -> str:
    """Replace {{name}} placeholders; unknown names are left untouched."""

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        return transform(stringify(variables[name])) if name in variables else match.group(0)

    return VAR_RE.sub(replace, template)


def to_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_json_field(raw: Any, label: str, expect: type | tuple = dict) -> Any:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return expect() if isinstance(expect, type) else {}
    if isinstance(raw, expect):
        return raw
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise NodeError(f"{label} is not valid JSON: {exc}") from exc
    if not isinstance(parsed, expect):
        raise NodeError(f"{label} must be a JSON {'object' if expect is dict else 'value'}")
    return parsed


def get_path(value: Any, path: str) -> Any:
    current = value
    for token in [t for t in path.strip().split(".") if t != ""]:
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif isinstance(current, list) and token.lstrip("-").isdigit():
            try:
                current = current[int(token)]
            except IndexError as exc:
                raise NodeError(f"Index {token} is out of range in path '{path}'") from exc
        else:
            raise NodeError(f"Path '{path}' not found (stopped at '{token}')")
    return current


# --------------------------------------------------------------------------
# core nodes
# --------------------------------------------------------------------------

def exec_input(ctx: ExecutionContext, data: dict, inputs: dict) -> Any:
    raw = data.get("inputValue", "")
    name = (data.get("inputName") or "input").strip() or "input"
    kind = data.get("inputType", "Text")
    if kind == "Number":
        number = to_number(raw)
        if number is None:
            raise NodeError(f"Input '{name}' must be a number (got {stringify(raw)!r})")
        return int(number) if number.is_integer() else number
    if kind == "JSON":
        try:
            return json.loads(stringify(raw))
        except ValueError as exc:
            raise NodeError(f"Input '{name}' is not valid JSON: {exc}") from exc
    return stringify(raw)


def exec_text(ctx: ExecutionContext, data: dict, inputs: dict) -> str:
    return render_template(stringify(data.get("text", "")), inputs)


def exec_output(ctx: ExecutionContext, data: dict, inputs: dict) -> Any:
    return inputs.get("value")


def exec_transform(ctx: ExecutionContext, data: dict, inputs: dict) -> Any:
    if "input" not in inputs:
        raise NodeError("Transform has no connected input")
    value = inputs["input"]
    op = data.get("operation", "uppercase")
    if op == "uppercase":
        return stringify(value).upper()
    if op == "lowercase":
        return stringify(value).lower()
    if op == "trim":
        return stringify(value).strip()
    if op == "reverse":
        return stringify(value)[::-1]
    if op == "length":
        return len(value) if isinstance(value, (str, list, dict)) else len(stringify(value))
    if op == "json":
        return json.dumps(value, ensure_ascii=False, default=str, indent=2)
    if op == "parse_json":
        if not isinstance(value, str):
            return value
        try:
            return json.loads(value)
        except ValueError as exc:
            raise NodeError(f"Input is not valid JSON: {exc}") from exc
    if op == "get_path":
        path = stringify(data.get("path", "")).strip()
        if not path:
            raise NodeError("Transform 'Get path' needs a path such as body.items.0.name")
        source = value
        if isinstance(source, str):
            try:
                source = json.loads(source)
            except ValueError:
                pass
        return get_path(source, path)
    raise NodeError(f"Unknown transform operation '{op}'")


# --------------------------------------------------------------------------
# AI
# --------------------------------------------------------------------------

def exec_llm(ctx: ExecutionContext, data: dict, inputs: dict) -> str:
    settings = get_settings()
    prompt = stringify(inputs["prompt"] if "prompt" in inputs else data.get("prompt", "")).strip()
    system = stringify(inputs["system"] if "system" in inputs else data.get("systemPrompt", "")).strip()
    model = (data.get("model") or "gpt-4o-mini").strip()
    temperature = to_number(data.get("temperature", 0.7))
    temperature = 0.7 if temperature is None else min(max(temperature, 0.0), 2.0)
    if not prompt:
        raise NodeError("LLM node has no prompt (write one or connect the 'prompt' input)")

    if not settings.openai_api_key:
        return (
            f"[mock LLM response - model={model}, temperature={temperature}]\n"
            f"System: {system or '(none)'}\nPrompt: {prompt}\n\n"
            "Set OPENAI_API_KEY on the server to get real completions."
        )

    import httpx

    try:
        response = httpx.post(
            f"{settings.openai_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system or "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": temperature,
                "max_tokens": settings.llm_max_tokens,
            },
            timeout=60.0,
        )
    except httpx.HTTPError as exc:
        raise NodeError(f"LLM request failed: {exc}") from exc
    try:
        payload = response.json()
    except ValueError as exc:
        raise NodeError(f"LLM returned a non-JSON response (HTTP {response.status_code})") from exc
    if response.status_code >= 400:
        message = (payload.get("error") or {}).get("message") if isinstance(payload, dict) else None
        raise NodeError(f"LLM error (HTTP {response.status_code}): {message or 'unknown error'}")
    try:
        return str(payload["choices"][0]["message"]["content"] or "")
    except (KeyError, IndexError, TypeError) as exc:
        raise NodeError("LLM response had an unexpected shape") from exc


# --------------------------------------------------------------------------
# HTTP integrations
# --------------------------------------------------------------------------

def _parse_body(text: str, content_type: str) -> Any:
    if "json" in content_type.lower() or text.lstrip().startswith(("{", "[")):
        try:
            return json.loads(text)
        except ValueError:
            return text
    return text


def exec_api(ctx: ExecutionContext, data: dict, inputs: dict) -> dict:
    from .net import NetworkError, safe_request

    method = (data.get("method") or "GET").upper()
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        raise NodeError(f"Unsupported HTTP method '{method}'")
    url = render_template(stringify(data.get("url", "")).strip(), inputs, lambda s: quote(s, safe=""))
    if not url:
        raise NodeError("API node has no URL")
    headers = {"User-Agent": "NexFlow/3.0", "Accept": "application/json, text/plain;q=0.9, */*;q=0.5"}
    headers.update({str(k): str(v) for k, v in parse_json_field(data.get("headers"), "Headers").items()})

    content: bytes | None = None
    if method in {"POST", "PUT", "PATCH"}:
        body_text = render_template(stringify(data.get("body", "")), inputs)
        if not body_text.strip() and "request" in inputs:
            body_text = stringify(inputs["request"])
        if body_text:
            content = body_text.encode("utf-8")
            headers.setdefault("Content-Type", "application/json")
    try:
        resp = safe_request(method, url, headers, content, timeout=20.0)
    except NetworkError as exc:
        raise NodeError(str(exc)) from exc
    return {
        "status": resp.status,
        "ok": 200 <= resp.status < 300,
        "url": resp.url,
        "method": method,
        "body": _parse_body(resp.text, resp.content_type),
        "truncated": resp.truncated,
    }


def exec_webhook(ctx: ExecutionContext, data: dict, inputs: dict) -> dict:
    from .net import NetworkError, safe_request

    url = stringify(data.get("url", "")).strip()
    if not url:
        raise NodeError("Webhook node has no URL")
    payload = inputs["payload"] if "payload" in inputs else parse_json_field(data.get("payload"), "Payload", (dict, list))
    if not isinstance(payload, (dict, list)):
        payload = {"data": payload}
    headers = {"Content-Type": "application/json", "User-Agent": "NexFlow/3.0"}
    headers.update({str(k): str(v) for k, v in parse_json_field(data.get("headers"), "Headers").items()})
    try:
        resp = safe_request("POST", url, headers, json.dumps(payload, default=str).encode("utf-8"), timeout=15.0)
    except NetworkError as exc:
        raise NodeError(str(exc)) from exc
    if resp.status >= 400:
        raise NodeError(f"Webhook responded with HTTP {resp.status}")
    return {"status": resp.status, "url": url, "delivered": True}


# --------------------------------------------------------------------------
# Database (sandboxed in-memory SQLite)
# --------------------------------------------------------------------------

_SEED_SQL = """
CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL, plan TEXT NOT NULL);
CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT NOT NULL, price REAL NOT NULL, stock INTEGER NOT NULL);
CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, product_id INTEGER NOT NULL,
                     quantity INTEGER NOT NULL, status TEXT NOT NULL);
INSERT INTO users VALUES (1,'Alice','alice@example.com','pro'),(2,'Bob','bob@example.com','free'),
                         (3,'Carol','carol@example.com','pro'),(4,'Dave','dave@example.com','free');
INSERT INTO products VALUES (101,'Widget',19.99,120),(102,'Gadget',49.50,35),(103,'Gizmo',7.25,500);
INSERT INTO orders VALUES (1,1,101,3,'shipped'),(2,2,102,1,'pending'),(3,3,103,10,'shipped'),
                          (4,1,102,2,'cancelled'),(5,4,101,1,'pending');
"""

_ALLOWED_SQL_ACTIONS = {
    sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE,
    sqlite3.SQLITE_DELETE, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_CREATE_TABLE,
    sqlite3.SQLITE_CREATE_INDEX, sqlite3.SQLITE_RECURSIVE, sqlite3.SQLITE_TRANSACTION,
    sqlite3.SQLITE_SAVEPOINT,
}


def _authorizer(action: int, *_: Any) -> int:
    return sqlite3.SQLITE_OK if action in _ALLOWED_SQL_ACTIONS else sqlite3.SQLITE_DENY


def exec_database(ctx: ExecutionContext, data: dict, inputs: dict) -> dict:
    query = stringify(inputs["query"] if "query" in inputs else data.get("query", "")).strip().rstrip(";")
    if not query:
        raise NodeError("Database node has no query")
    conn = ctx.sandbox_db()
    deadline = time.monotonic() + 5.0
    conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
    try:
        cursor = conn.execute(query)
        if cursor.description is None:
            conn.commit()
            return {"query": query, "affected_rows": cursor.rowcount}
        limit = 1000
        fetched = cursor.fetchmany(limit + 1)
        rows = [dict(row) for row in fetched[:limit]]
        return {
            "query": query,
            "columns": [col[0] for col in cursor.description],
            "row_count": len(rows),
            "truncated": len(fetched) > limit,
            "rows": rows,
        }
    except sqlite3.Warning as exc:
        raise NodeError("Only one SQL statement is allowed per Database node") from exc
    except sqlite3.DatabaseError as exc:
        message = "query took too long (5s limit)" if "interrupted" in str(exc) else str(exc)
        raise NodeError(f"SQL error: {message}") from exc
    finally:
        conn.set_progress_handler(None, 0)


# --------------------------------------------------------------------------
# Logic
# --------------------------------------------------------------------------

def exec_condition(ctx: ExecutionContext, data: dict, inputs: dict) -> dict:
    value = inputs.get("value")
    op = data.get("operator", "equals")
    compare = data.get("compareValue", "")
    text_value, text_compare = stringify(value), stringify(compare)
    num_value, num_compare = to_number(value), to_number(compare)
    both_numeric = num_value is not None and num_compare is not None

    if op == "equals":
        result = num_value == num_compare if both_numeric else text_value == text_compare
    elif op == "not-equals":
        result = num_value != num_compare if both_numeric else text_value != text_compare
    elif op == "contains":
        result = text_compare in text_value
    elif op == "not-contains":
        result = text_compare not in text_value
    elif op == "greater-than":
        if not both_numeric:
            raise NodeError(f"'Greater than' needs numbers (got {text_value!r} and {text_compare!r})")
        result = num_value > num_compare
    elif op == "less-than":
        if not both_numeric:
            raise NodeError(f"'Less than' needs numbers (got {text_value!r} and {text_compare!r})")
        result = num_value < num_compare
    elif op == "is-empty":
        result = value is None or text_value.strip() == "" or value in ([], {})
    elif op == "is-not-empty":
        result = not (value is None or text_value.strip() == "" or value in ([], {}))
    else:
        raise NodeError(f"Unknown operator '{op}'")
    return {"condition_met": result, "branch": "true" if result else "false", "operator": op, "value": value}


async def exec_delay(ctx: ExecutionContext, data: dict, inputs: dict) -> Any:
    limit = get_settings().max_delay_ms
    number = to_number(data.get("delay", 1000))
    if number is None or number < 0:
        raise NodeError("Delay must be a non-negative number of milliseconds")
    await asyncio.sleep(min(number, limit) / 1000.0)
    return inputs.get("input")


def exec_code(ctx: ExecutionContext, data: dict, inputs: dict) -> Any:
    try:
        return safe_eval(stringify(data.get("code", "")), {"input": inputs.get("input")})
    except EvalError as exc:
        raise NodeError(f"Code error: {exc}") from exc


def exec_loop(ctx: ExecutionContext, data: dict, inputs: dict) -> list:
    limit = get_settings().max_loop_items
    items = inputs.get("items", [])
    if isinstance(items, str):
        try:
            items = json.loads(items)
        except ValueError:
            items = [line for line in items.splitlines() if line.strip()]
    if isinstance(items, dict):
        items = list(items.values())
    if not isinstance(items, list):
        items = [items]
    if len(items) > limit:
        raise NodeError(f"Loop received {len(items)} items; the limit is {limit}")

    mode = data.get("mode", "template")
    template = stringify(data.get("template", "{{item}}"))
    expression = stringify(data.get("expression", "item"))
    results: list[Any] = []
    for index, item in enumerate(items):
        if mode == "expression":
            try:
                results.append(safe_eval(expression, {"item": item, "index": index}))
            except EvalError as exc:
                raise NodeError(f"Loop item {index}: {exc}") from exc
        else:
            results.append(render_template(template, {"item": item, "index": index}))
    return results


# --------------------------------------------------------------------------
# Delivery & storage
# --------------------------------------------------------------------------

def exec_email(ctx: ExecutionContext, data: dict, inputs: dict) -> dict:
    settings = get_settings()
    recipients = [r.strip() for r in stringify(data.get("to", "")).split(",") if r.strip()]
    subject = stringify(data.get("subject", "")).strip() or "NexFlow notification"
    body = stringify(inputs["body"] if "body" in inputs else data.get("body", ""))
    if not recipients:
        raise NodeError("Email node needs at least one recipient")
    if len(recipients) > 10:
        raise NodeError("Email node supports at most 10 recipients")
    for address in recipients:
        if not EMAIL_RE.match(address):
            raise NodeError(f"'{address}' is not a valid email address")
    if "\n" in subject or "\r" in subject:
        raise NodeError("Subject must be a single line")

    if not settings.smtp_host:
        return {
            "status": "dry_run", "to": recipients, "subject": subject, "body": body,
            "note": "SMTP_HOST is not configured on the server, so nothing was sent.",
        }
    sender = settings.smtp_from or settings.smtp_user
    if not sender:
        raise NodeError("Server SMTP is missing SMTP_FROM (or SMTP_USER)")
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = sender, ", ".join(recipients), subject
    message["Message-ID"] = f"<{uuid4().hex}@nexflow>"
    message.set_content(body)
    try:
        context = ssl.create_default_context()
        if settings.smtp_port == 465:
            client: smtplib.SMTP = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20, context=context)
        else:
            client = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
            if settings.smtp_starttls:
                client.starttls(context=context)
        with client:
            if settings.smtp_user and settings.smtp_password:
                client.login(settings.smtp_user, settings.smtp_password)
            client.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        raise NodeError(f"Could not send email: {exc}") from exc
    return {"status": "sent", "to": recipients, "subject": subject, "message_id": message["Message-ID"]}


def _workspace_path(ctx: ExecutionContext, raw: Any) -> Path:
    relative = stringify(raw).strip()
    if not relative:
        raise NodeError("File node has no path")
    if "\x00" in relative or relative.startswith(("/", "\\")):
        raise NodeError("Path must be relative to your workspace folder")
    owner = re.sub(r"[^A-Za-z0-9_-]", "_", ctx.user_id) or "anonymous"
    root = (get_settings().files_dir / owner).resolve()
    root.mkdir(parents=True, exist_ok=True)
    target = (root / relative).resolve()
    if target == root or not target.is_relative_to(root):
        raise NodeError("Path must stay inside your workspace folder")
    return target


def exec_file(ctx: ExecutionContext, data: dict, inputs: dict) -> Any:
    limit = get_settings().max_file_bytes
    action = data.get("action", "read")
    target = _workspace_path(ctx, data.get("path"))
    try:
        if action == "read":
            if not target.is_file():
                raise NodeError(f"File '{data.get('path')}' does not exist in your workspace")
            if target.stat().st_size > limit:
                raise NodeError(f"File is larger than the {limit} byte limit")
            try:
                return target.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                raise NodeError("File is not valid UTF-8 text") from exc
        if action in {"write", "append"}:
            content = stringify(inputs["content"] if "content" in inputs else data.get("content", ""))
            encoded = content.encode("utf-8")
            existing = target.stat().st_size if action == "append" and target.exists() else 0
            if len(encoded) + existing > limit:
                raise NodeError(f"File would exceed the {limit} byte limit")
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "ab" if action == "append" else "wb") as handle:
                handle.write(encoded)
            return {"action": action, "path": str(data.get("path")), "bytes": len(encoded)}
    except OSError as exc:
        raise NodeError(f"File error: {exc.strerror or exc}") from exc
    raise NodeError(f"Unknown file action '{action}'")


EXECUTORS: dict[str, Callable[[ExecutionContext, dict, dict], Any]] = {
    "customInput": exec_input,
    "text": exec_text,
    "llm": exec_llm,
    "transform": exec_transform,
    "customOutput": exec_output,
    "api": exec_api,
    "database": exec_database,
    "condition": exec_condition,
    "delay": exec_delay,
    "code": exec_code,
    "email": exec_email,
    "webhook": exec_webhook,
    "file": exec_file,
    "loop": exec_loop,
}
