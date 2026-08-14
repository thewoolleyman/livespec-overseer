"""Lockstep gate for the importable overseer package shipped in the plugin."""

from __future__ import annotations

from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
SOURCE_PACKAGE = ROOT / "overseer"
CARRIER_PACKAGE = ROOT / ".claude-plugin" / "overseer"
SOURCE_ONLY = frozenset(
    {
        "AGENTS.md",
        "SKILL.md",
        "conftest.py",
        "marker-protocol.md",
    }
)


def _is_runtime_package_file(*, path: Path) -> bool:
    if not path.is_file():
        return False
    if path.name in SOURCE_ONLY or path.name.startswith("test_"):
        return False
    return path.suffix == ".py" or path.name == "version.json"


def _runtime_package_files(*, root: Path) -> dict[str, Path]:
    return {
        path.name: path for path in sorted(root.iterdir()) if _is_runtime_package_file(path=path)
    }


def test_plugin_overseer_package_stays_byte_identical_to_source_package() -> None:
    source_files = _runtime_package_files(root=SOURCE_PACKAGE)
    carrier_files = _runtime_package_files(root=CARRIER_PACKAGE)
    missing = sorted(source_files.keys() - carrier_files.keys())
    extra = sorted(carrier_files.keys() - source_files.keys())

    assert source_files.keys() == carrier_files.keys(), (
        "the shipped .claude-plugin/overseer package must contain exactly the same "
        f"runtime files as overseer/: missing={missing}, extra={extra}"
    )

    drifted = [
        name
        for name, source_path in source_files.items()
        if source_path.read_bytes() != carrier_files[name].read_bytes()
    ]

    assert drifted == [], (
        "the shipped .claude-plugin/overseer package drifted from overseer/: "
        f"{drifted}. Copy the source package change into the carrier in the same commit."
    )
