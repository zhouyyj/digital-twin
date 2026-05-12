"""Load environment and shared runtime settings without leaking secrets."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"

# Curly quotes / BOM often get pasted into .env from docs or iOS; HTTP headers must be ASCII.
_HEADER_SAFE_ENV_KEYS = (
    "OPENAI_API_KEY",
    "OPENAI_ORG_ID",
    "OPENAI_PROJECT_ID",
    "OPENAI_ADMIN_KEY",
)


def _strip_copy_paste_cruft(value: str) -> str:
    """Remove BOM and Unicode/ASCII wrapping quotes from pasted secrets."""
    value = value.replace("\ufeff", "").strip()
    changed = True
    while changed and value:
        changed = False
        for open_q, close_q in (
            ("\u2018", "\u2019"),
            ("\u201c", "\u201d"),
            ('"', '"'),
            ("'", "'"),
        ):
            if len(value) >= 2 and value.startswith(open_q) and value.endswith(close_q):
                value = value[len(open_q) : -len(close_q)].strip()
                changed = True
                break
    quote_chars = frozenset("\"'‘’“”")
    while value and value[0] in quote_chars:
        value = value[1:].strip()
    while value and value[-1] in quote_chars:
        value = value[:-1].strip()
    return value


def _sanitize_openai_header_env() -> None:
    """Normalize OpenAI-related env vars that become HTTP headers (ASCII-only for httpx)."""
    for key in _HEADER_SAFE_ENV_KEYS:
        if key not in os.environ:
            continue
        raw = os.environ[key]
        cleaned = _strip_copy_paste_cruft(raw)
        if cleaned != raw:
            os.environ[key] = cleaned


def load_env() -> None:
    """Load `.env` from project root if present; never overrides existing OS env."""
    if _ENV_FILE.is_file():
        load_dotenv(_ENV_FILE, override=False)
    _sanitize_openai_header_env()


def get_openai_api_key() -> str:
    key = _strip_copy_paste_cruft(os.getenv("OPENAI_API_KEY", ""))
    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return key


def get_openai_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"


def get_openai_base_url() -> str | None:
    url = os.getenv("OPENAI_BASE_URL", "").strip()
    return url or None


def get_project_root() -> Path:
    return _PROJECT_ROOT


def get_openai_embedding_model() -> str:
    return (
        os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small").strip()
        or "text-embedding-3-small"
    )
