"""Redact credential-shaped text BEFORE cutting a diagnostic short (overseer-cwcsjl)."""

from __future__ import annotations

import re
from typing import Final

__all__: list[str] = ["redacted_prefix"]

_CREDENTIAL_SHAPE: Final = re.compile(r"sk-ant-[A-Za-z0-9_-]+")


def redacted_prefix(*, text: str, limit: int) -> str:
    """The first `limit` characters of `text` after every credential shape is redacted.

    The cut comes last. Cutting first let a credential straddling the cut survive
    as a prefix that no pattern matched any more.
    """

    return _CREDENTIAL_SHAPE.sub("[redacted]", text)[:limit]
