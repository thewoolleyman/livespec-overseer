"""Suite-wide hermetic guards for host-owned overseer state."""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

_PACKAGE_DIR = Path(__file__).resolve().parent / "overseer"
if str(_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_DIR))

import _supervisor_snapshot  # noqa: E402


@dataclass(frozen=True, kw_only=True)
class ProtectedFileState:
    exists: bool
    content: bytes | None


@dataclass(frozen=True, kw_only=True)
class RealStatusSnapshotGuard:
    path: Path

    def assert_snapshot_write_allowed(self, *, path: Path) -> None:
        if path == self.path:
            pytest.fail(f"test attempted to write the real overseer status snapshot: {path}")

    def assert_unchanged(self, *, before: ProtectedFileState) -> None:
        after = _protected_file_state(path=self.path)
        if after != before:
            pytest.fail(f"test modified the real overseer status snapshot: {self.path}")


def _protected_file_state(*, path: Path) -> ProtectedFileState:
    try:
        return ProtectedFileState(exists=True, content=path.read_bytes())
    except FileNotFoundError:
        return ProtectedFileState(exists=False, content=None)


@pytest.fixture(name="real_status_snapshot_guard", autouse=True)
def _real_status_snapshot_guard(
    *,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[RealStatusSnapshotGuard]:
    guard = RealStatusSnapshotGuard(path=Path(_supervisor_snapshot.DEFAULT_STATUS_PATH))
    before = _protected_file_state(path=guard.path)
    original_atomic_write: Callable[..., None] = _supervisor_snapshot.registry.atomic_write

    def guarded_atomic_write(*, path: Path, body: str, raise_errors: bool = False) -> None:
        guard.assert_snapshot_write_allowed(path=path)
        original_atomic_write(path=path, body=body, raise_errors=raise_errors)

    monkeypatch.setattr(_supervisor_snapshot.registry, "atomic_write", guarded_atomic_write)
    yield guard
    guard.assert_unchanged(before=before)
