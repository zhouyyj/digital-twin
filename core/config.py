"""Load environment and shared runtime settings without leaking secrets."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


def load_env() -> None:
    """Load `.env` from project root if present; never overrides existing OS env."""
    if _ENV_FILE.is_file():
        load_dotenv(_ENV_FILE, override=False)


def get_openai_api_key() -> str:
    key = os.getenv("OPENAI_API_KEY", "").strip()
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
