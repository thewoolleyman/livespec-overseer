"""Regression coverage for machine-local Beads tenant cache ignores."""

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TENANT_CACHE = ".beads/tenant-verification-cache.json"
TRACKED_BEADS_FILES = (
    ".beads/.gitignore",
    ".beads/config.yaml",
)


def test_beads_tenant_verification_cache_is_ignored() -> None:
    completed = subprocess.run(  # noqa: S603
        ["git", "check-ignore", "-v", TENANT_CACHE],  # noqa: S607
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "/.beads/tenant-verification-cache.json" in completed.stdout


def test_beads_gitignore_keeps_real_ledger_files_visible() -> None:
    listed = subprocess.run(  # noqa: S603
        ["git", "ls-files", *TRACKED_BEADS_FILES],  # noqa: S607
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert listed.stdout.splitlines() == list(TRACKED_BEADS_FILES)

    ignored = subprocess.run(  # noqa: S603
        ["git", "check-ignore", "--no-index", "-v", *TRACKED_BEADS_FILES],  # noqa: S607
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert ignored.returncode == 1
    assert ignored.stdout == ""
