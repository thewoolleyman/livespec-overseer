"""Suite-wide hermetic guards for host-owned overseer state."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

_PACKAGE_DIR = Path(__file__).resolve().parent / "overseer"
if str(_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_DIR))

import _registry_core  # noqa: E402
import _registry_rounds  # noqa: E402
import _registry_rows_io  # noqa: E402
import _registry_stamp_resume  # noqa: E402
import _registry_stamps  # noqa: E402
import _supervisor_snapshot  # noqa: E402
import registry  # noqa: E402

# Captured at IMPORT time, before any fixture or helper can redirect them. A test
# that isolates itself repoints these module globals at a tmp path; the guard must
# still know which paths are the operator's REAL ones.
_REAL_HOST_PATHS: frozenset[Path] = frozenset(
    {
        Path(_supervisor_snapshot.DEFAULT_STATUS_PATH),
        Path(_registry_core.DEFAULT_STORE_PATH),
        Path(_registry_core.DEFAULT_STAMP_PATH),
        Path(_registry_core.DEFAULT_WATCH_SET_PATH),
    }
)

# `atomic_write` is DEFINED once in `_registry_core`, but each of these modules did
# `from _registry_core import atomic_write`, binding its own module-level name. Patching
# the definition site would leave every one of those names pointing at the original, so
# the guard has to wrap each BINDING site. This is the same resolution subtlety that
# `isolate_store` documents for `DEFAULT_STORE_PATH`.
_WRITE_BINDING_SITES = (
    _registry_core,
    _registry_rounds,
    _registry_rows_io,
    _registry_stamp_resume,
    _registry_stamps,
    registry,
)


@dataclass(frozen=True, kw_only=True)
class RealHostStateGuard:
    """Fails any test that writes one of the operator's real host-state files.

    GENERALIZED 2026-08-21 from a status-snapshot-only guard. That narrower guard was
    added after a probe test replaced the live 64-row operator status snapshot with a
    single fixture row. It held for the status file and could not see the others: a
    launch-time statusline baseline later began being written on the CLI start path, and
    because the stamp sidecar was neither redirected by the CLI test helper nor covered
    here, 120 junk entries accumulated in the operator's real stamp file before anyone
    noticed.

    The lesson that shaped this class is that fixing one member of a family does not fix
    the family. All four host-owned paths are guarded, so the NEXT write added to any of
    them fails loudly in CI on its first run instead of lying latent until someone reads
    the file by hand.
    """

    paths: frozenset[Path]

    def assert_write_allowed(self, *, path: Path) -> None:
        if Path(path) in self.paths:
            pytest.fail(f"test attempted to write real operator host state: {path}")


@pytest.fixture(name="real_host_state_guard", autouse=True)
def _real_host_state_guard(*, monkeypatch: pytest.MonkeyPatch) -> RealHostStateGuard:
    guard = RealHostStateGuard(paths=_REAL_HOST_PATHS)

    def guarded(original: Callable[..., None]) -> Callable[..., None]:
        def _write(*, path: Path, body: str, raise_errors: bool = False) -> None:
            guard.assert_write_allowed(path=path)
            original(path=path, body=body, raise_errors=raise_errors)

        return _write

    for module in _WRITE_BINDING_SITES:
        monkeypatch.setattr(module, "atomic_write", guarded(module.atomic_write))
    monkeypatch.setattr(
        _supervisor_snapshot.registry,
        "atomic_write",
        guarded(_supervisor_snapshot.registry.atomic_write),
    )
    return guard
