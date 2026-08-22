"""Regression coverage for stale LLOC soft-band owner markers."""

from __future__ import annotations

from pathlib import Path

__all__: list[str] = []


CLOSED_OWNERS = frozenset(
    {
        "overseer-2jblyq.5",
        "overseer-54k2za.23",
        "overseer-6s3pk6.6",
        "overseer-6s3pk6.7",
        "overseer-adclcd.7",
        "overseer-hgq4wi.6",
    }
)
MARKER_PREFIX = "# livespec-lloc-soft-band-owner: "
SCOPES = (
    "overseer",
    ".claude-plugin/overseer",
    "tests",
)


def test_lloc_soft_band_owner_markers_do_not_name_closed_work_items() -> None:
    root = Path(__file__).resolve().parents[1]
    stale_markers: list[str] = []

    for scope in SCOPES:
        for path in sorted((root / scope).rglob("*.py")):
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                stripped = line.strip()
                if not stripped.startswith(MARKER_PREFIX):
                    continue
                owner = stripped.removeprefix(MARKER_PREFIX).split()[0]
                if owner in CLOSED_OWNERS:
                    stale_markers.append(f"{path.relative_to(root)}:{line_number}:{owner}")

    assert stale_markers == []
