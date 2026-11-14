"""The ledger-backed live-seat record cannot be silently made host-local."""

from __future__ import annotations

from pathlib import Path

OVERSEER_DIR = Path(__file__).resolve().parents[1] / "overseer"


def test_live_seat_module_exists_for_the_ledger_record() -> None:
    """The record owner is a product module, not a test-side simulation."""
    assert (OVERSEER_DIR / "live_seat.py").is_file()
