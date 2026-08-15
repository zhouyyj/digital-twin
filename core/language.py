"""Small language guards for persisted, user-visible model output."""

from __future__ import annotations

import re
from typing import Any


_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def contains_cjk(value: Any) -> bool:
    """Return whether a nested JSON-like value contains CJK ideographs."""
    if isinstance(value, str):
        return bool(_CJK.search(value))
    if isinstance(value, dict):
        return any(contains_cjk(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(contains_cjk(item) for item in value)
    return False
