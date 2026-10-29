"""Runtime configuration, read once from environment variables."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

_INSECURE_SECRETS = {
    "change-me-in-production",
    "nexflow-dev-secret-change-in-prod",
    "changeme",
    "secret",
}


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"Environment variable {name} must be an integer") from exc


def _list(name: str, default: str) -> list[str]:
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _resolve_secret(db_path: Path) -> str:
    """Use NEXFLOW_SECRET if set, otherwise generate and persist a random one."""
    configured = os.environ.get("NEXFLOW_SECRET", "").strip()
    if configured:
        if configured.lower() in _INSECURE_SECRETS or len(configured) < 16:
            raise RuntimeError(
                "NEXFLOW_SECRET is a known placeholder or shorter than 16 characters. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        return configured

    secret_file = db_path.parent / ".nexflow_secret"
    if secret_file.exists():
        stored = secret_file.read_text(encoding="utf-8").strip()
        if len(stored) >= 32:
            return stored
    secret_file.parent.mkdir(parents=True, exist_ok=True)
    generated = secrets.token_urlsafe(48)
    secret_file.write_text(generated, encoding="utf-8")
    try:
        secret_file.chmod(0o600)
    except OSError:
        pass
    return generated


@dataclass(frozen=True)
class Settings:
    db_path: Path
    secret_key: str
    token_ttl_hours: int
    cors_origins: list[str]
    allow_registration: bool
    seed_demo: bool
    static_dir: Optional[Path]

    # Execution limits
    max_nodes: int
    max_edges: int
    max_graph_bytes: int
    node_timeout_s: int
    max_delay_ms: int
    max_concurrent_runs: int
    max_loop_items: int
    max_output_chars: int

    # Integrations
    openai_api_key: Optional[str]
    openai_base_url: str
    llm_max_tokens: int
    files_dir: Path
    max_file_bytes: int
    allow_private_network: bool
    max_response_bytes: int
    smtp_host: Optional[str]
    smtp_port: int
    smtp_user: Optional[str]
    smtp_password: Optional[str]
    smtp_from: Optional[str]
    smtp_starttls: bool


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    db_path = Path(os.environ.get("NEXFLOW_DB", "data/nexflow.db")).resolve()
    default_static = Path(__file__).resolve().parent.parent / "frontend" / "build"
    static_env = os.environ.get("NEXFLOW_STATIC_DIR")
    static_dir = Path(static_env).resolve() if static_env else default_static
    return Settings(
        db_path=db_path,
        secret_key=_resolve_secret(db_path),
        token_ttl_hours=_int("NEXFLOW_TOKEN_TTL_HOURS", 72),
        cors_origins=_list("NEXFLOW_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"),
        allow_registration=_bool("NEXFLOW_ALLOW_REGISTRATION", True),
        seed_demo=_bool("NEXFLOW_SEED_DEMO", False),
        static_dir=static_dir if (static_dir / "index.html").exists() else None,
        max_nodes=_int("NEXFLOW_MAX_NODES", 300),
        max_edges=_int("NEXFLOW_MAX_EDGES", 1000),
        max_graph_bytes=_int("NEXFLOW_MAX_GRAPH_BYTES", 2_000_000),
        node_timeout_s=_int("NEXFLOW_NODE_TIMEOUT", 60),
        max_delay_ms=_int("NEXFLOW_MAX_DELAY_MS", 30_000),
        max_concurrent_runs=_int("NEXFLOW_MAX_CONCURRENT_RUNS", 8),
        max_loop_items=_int("NEXFLOW_MAX_LOOP_ITEMS", 1000),
        max_output_chars=_int("NEXFLOW_MAX_OUTPUT_CHARS", 100_000),
        openai_api_key=os.environ.get("OPENAI_API_KEY") or None,
        openai_base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        llm_max_tokens=_int("NEXFLOW_LLM_MAX_TOKENS", 1024),
        files_dir=Path(os.environ.get("NEXFLOW_FILES_DIR", str(db_path.parent / "files"))).resolve(),
        max_file_bytes=_int("NEXFLOW_MAX_FILE_BYTES", 1_000_000),
        allow_private_network=_bool("NEXFLOW_ALLOW_PRIVATE_NETWORK", False),
        max_response_bytes=_int("NEXFLOW_MAX_RESPONSE_BYTES", 1_000_000),
        smtp_host=os.environ.get("SMTP_HOST") or None,
        smtp_port=_int("SMTP_PORT", 587),
        smtp_user=os.environ.get("SMTP_USER") or None,
        smtp_password=os.environ.get("SMTP_PASSWORD") or None,
        smtp_from=os.environ.get("SMTP_FROM") or None,
        smtp_starttls=_bool("SMTP_STARTTLS", True),
    )
