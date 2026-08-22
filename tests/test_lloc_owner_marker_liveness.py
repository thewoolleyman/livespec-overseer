"""Regression coverage for LLOC soft-band owner marker pins."""

from __future__ import annotations

from pathlib import Path

__all__: list[str] = []


ENUMERATED_LIVE_OWNER_PINS = frozenset(
    {
        "overseer-2jblyq.8",
        "overseer-au3pt3.15",
        "overseer-hgq4wi",
        "overseer-lixhd3.1",
        "overseer-temi26.2",
    }
)
MARKER_PREFIX = "# livespec-lloc-soft-band-owner: "
SCOPES = (
    "overseer",
    ".claude-plugin/overseer",
    "tests",
)


def test_lloc_soft_band_owner_markers_name_enumerated_live_owner_pins() -> None:
    root = Path(__file__).resolve().parents[1]
    unpinned_markers: list[str] = []

    for scope in SCOPES:
        for path in sorted((root / scope).rglob("*.py")):
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                stripped = line.strip()
                if not stripped.startswith(MARKER_PREFIX):
                    continue
                owner = stripped.removeprefix(MARKER_PREFIX).split()[0]
                if owner not in ENUMERATED_LIVE_OWNER_PINS:
                    unpinned_markers.append(f"{path.relative_to(root)}:{line_number}:{owner}")

    assert unpinned_markers == []
