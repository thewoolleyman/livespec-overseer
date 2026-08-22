"""Guard release-please against stale pyproject.toml snapshot replays."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from overseer.release_please_pyproject_guard import (
    assert_release_pyproject_diff_is_version_only,
    is_release_subject,
    non_version_pyproject_diff_lines,
)

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
HISTORICAL_CLOBBER = "356b68b"
VERSION_ONLY_RELEASE = "e399446"


def _git(*args: str, cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run git for release-history inspection fixtures."""
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
    )


def _commit_subject(*, ref: str) -> str:
    return _git("show", "-s", "--format=%s", ref).stdout.strip()


def _commit_is_reachable(*, ref: str) -> bool:
    result = _git("cat-file", "-e", f"{ref}^{{commit}}", check=False)
    return result.returncode == 0


def test_current_release_commit_does_not_rewrite_pyproject_beyond_version() -> None:
    """Fail CI when release-please replays a stale pyproject.toml snapshot."""
    assert_release_pyproject_diff_is_version_only(repo_root=ROOT, ref="HEAD")


def test_release_please_subject_detection_is_narrow() -> None:
    assert is_release_subject(subject="chore(master): release 1.11.0")
    assert not is_release_subject(subject="chore: release prep")


def test_release_please_pyproject_guard_accepts_version_only_release_diff() -> None:
    diff = """diff --git a/pyproject.toml b/pyproject.toml
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -13 +13 @@ name = "livespec-overseer"
-version = "1.10.2"
+version = "1.11.0"
"""

    assert non_version_pyproject_diff_lines(diff=diff) == []


def test_release_please_pyproject_guard_rejects_stale_snapshot_clobber() -> None:
    diff = """diff --git a/pyproject.toml b/pyproject.toml
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -13 +13 @@ name = "livespec-overseer"
-version = "1.10.2"
+version = "1.11.0"
@@ -197,3 +196,0 @@ total_absence_returns = [
-hand-authored release-window line 1
-hand-authored release-window line 2
-hand-authored release-window line 3
"""

    assert non_version_pyproject_diff_lines(diff=diff) == [
        "-hand-authored release-window line 1",
        "-hand-authored release-window line 2",
        "-hand-authored release-window line 3",
    ]


@pytest.mark.skipif(
    not _commit_is_reachable(ref=HISTORICAL_CLOBBER),
    reason="historical clobber commit is unreachable in this clone",
)
def test_historical_release_please_pyproject_clobber_is_rejected() -> None:
    assert _commit_subject(ref=HISTORICAL_CLOBBER) == "chore(master): release 1.11.0"
    with pytest.raises(AssertionError, match="stale-snapshot clobber"):
        assert_release_pyproject_diff_is_version_only(repo_root=ROOT, ref=HISTORICAL_CLOBBER)


@pytest.mark.skipif(
    not _commit_is_reachable(ref=VERSION_ONLY_RELEASE),
    reason="version-only release fixture commit is unreachable in this clone",
)
def test_version_only_release_please_pyproject_diff_is_accepted() -> None:
    assert _commit_subject(ref=VERSION_ONLY_RELEASE) == "chore(master): release 1.32.5"
    assert_release_pyproject_diff_is_version_only(repo_root=ROOT, ref=VERSION_ONLY_RELEASE)


def _init_fixture_repo(*, root: Path) -> None:
    """Build a self-contained git repo so body coverage never depends on clone depth."""
    _ = _git("init", "-q", "-b", "main", cwd=root)
    _ = _git("config", "user.email", "fixture@example.invalid", cwd=root)
    _ = _git("config", "user.name", "Fixture", cwd=root)


def _commit_pyproject(*, root: Path, body: str, subject: str) -> str:
    _ = (root / "pyproject.toml").write_text(body, encoding="utf-8")
    _ = _git("add", "pyproject.toml", cwd=root)
    _ = _git("commit", "-q", "-m", subject, cwd=root)
    return _git("rev-parse", "HEAD", cwd=root).stdout.strip()


_BASE_PYPROJECT = 'name = "livespec-overseer"\nversion = "1.10.2"\nkeep = "hand-authored"\n'


def test_guard_accepts_a_real_version_only_release_commit(*, tmp_path: Path) -> None:
    """Exercise the git-reading body, not only the pure helpers."""
    _init_fixture_repo(root=tmp_path)
    _ = _commit_pyproject(root=tmp_path, body=_BASE_PYPROJECT, subject="feat: seed")
    bumped = _BASE_PYPROJECT.replace('version = "1.10.2"', 'version = "1.11.0"')
    ref = _commit_pyproject(root=tmp_path, body=bumped, subject="chore(master): release 1.11.0")

    assert_release_pyproject_diff_is_version_only(repo_root=tmp_path, ref=ref)


def test_guard_rejects_a_real_release_commit_that_also_rewrites_other_lines(
    *, tmp_path: Path
) -> None:
    _init_fixture_repo(root=tmp_path)
    _ = _commit_pyproject(root=tmp_path, body=_BASE_PYPROJECT, subject="feat: seed")
    clobbered = _BASE_PYPROJECT.replace('version = "1.10.2"', 'version = "1.11.0"').replace(
        'keep = "hand-authored"', ""
    )
    ref = _commit_pyproject(root=tmp_path, body=clobbered, subject="chore(master): release 1.11.0")

    with pytest.raises(AssertionError, match="stale-snapshot clobber"):
        assert_release_pyproject_diff_is_version_only(repo_root=tmp_path, ref=ref)


def test_guard_ignores_a_non_release_commit_whatever_it_does_to_pyproject(
    *, tmp_path: Path
) -> None:
    _init_fixture_repo(root=tmp_path)
    _ = _commit_pyproject(root=tmp_path, body=_BASE_PYPROJECT, subject="feat: seed")
    ref = _commit_pyproject(
        root=tmp_path, body='name = "x"\n', subject="fix: rewrite pyproject wholesale"
    )

    assert_release_pyproject_diff_is_version_only(repo_root=tmp_path, ref=ref)
