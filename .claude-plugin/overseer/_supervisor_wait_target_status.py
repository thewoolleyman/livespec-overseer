"""Shared wait-target-missing status constants."""

from __future__ import annotations

__all__: list[str] = [
    "WAIT_TARGET_EXPIRED_STATUS",
    "WAIT_TARGET_MISSING_CONDITION",
    "WAIT_TARGET_MISSING_STATUS",
    "WAIT_TARGET_SATISFIED_STATUS",
]

WAIT_TARGET_EXPIRED_STATUS = "expired"
WAIT_TARGET_MISSING_CONDITION = "wait-target-missing"
WAIT_TARGET_MISSING_STATUS = "wait-target-missing"
WAIT_TARGET_SATISFIED_STATUS = "satisfied"
