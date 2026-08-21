"""Beside-tests for the suite-wide real-host-state guard in `conftest.py`.

The guard exists because the suite used to publish fixture rows to the operator's real
`~/.livespec-overseer-status.json`. A guard against that is only worth having if it can
be shown to FIRE, and — the part that is easy to skip — to fire through the path
production code actually takes.

GENERALIZED 2026-08-21. The guard originally covered the status snapshot alone, and that
narrowness had a measurable cost: a launch-time statusline baseline began being written
on the CLI start path, the stamp sidecar was covered by neither this guard nor the CLI
test helper, and 120 junk entries accumulated in the operator's real stamp file before
anyone read it by hand. These tests now assert the guard for EVERY host-owned path, so
the next one added is caught on its first CI run rather than lying latent.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PACKAGE_DIR = Path(__file__).resolve().parent.parent / "overseer"
if str(_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_DIR))

import _registry_core  # noqa: E402
import _registry_rows_io  # noqa: E402
import _registry_stamps  # noqa: E402
import _supervisor_snapshot  # noqa: E402


def test_the_guard_fails_on_every_real_host_state_path(*, real_host_state_guard) -> None:
    """All four host-owned paths are guarded, not just the one that bit us first."""
    for path in (
        Path(_supervisor_snapshot.DEFAULT_STATUS_PATH),
        Path(_registry_core.DEFAULT_STORE_PATH),
        Path(_registry_core.DEFAULT_STAMP_PATH),
        Path(_registry_core.DEFAULT_WATCH_SET_PATH),
    ):
        with pytest.raises(pytest.fail.Exception, match="real operator host state"):
            real_host_state_guard.assert_write_allowed(path=path)


def test_the_guard_is_installed_on_each_writers_own_module() -> None:
    """The guard is INSTALLED at each binding site, not merely constructible.

    `atomic_write` is DEFINED once in `_registry_core` but each writer module did
    `from _registry_core import atomic_write`, binding its own module-level name.
    Patching only the definition site would leave every one of those names pointing at
    the original, and asserting on the guard OBJECT cannot tell a live monkeypatch from
    a dead one. Each case below drives the module attribute the writer itself resolves,
    so a fixture that stopped patching any one of them reddens here.

    `atomic_write` is called directly rather than through the higher-level writers
    deliberately: those take `registry.file_lock` on the target BEFORE the guarded
    write, so going through them would create a `.lock` file beside the operator's real
    files — this test would leak the very host state the guard defends.
    """
    cases = (
        (_supervisor_snapshot.registry, Path(_supervisor_snapshot.DEFAULT_STATUS_PATH)),
        (_registry_rows_io, Path(_registry_core.DEFAULT_STORE_PATH)),
        (_registry_stamps, Path(_registry_core.DEFAULT_STAMP_PATH)),
    )
    for module, path in cases:
        with pytest.raises(pytest.fail.Exception, match="real operator host state"):
            module.atomic_write(path=path, body="{}\n")


def test_the_guard_passes_writes_to_every_other_path(*, tmp_path) -> None:
    """The discriminating control: the guard blocks a NAMED SET, not writing in general.

    Without this, a guard that failed every write — or a `match=` that happened to catch
    an unrelated failure — would look identical to a working one in the tests above.
    """
    target = tmp_path / "status.json"

    _supervisor_snapshot.registry.atomic_write(path=target, body='{"ok": true}\n')

    assert target.read_text(encoding="utf-8") == '{"ok": true}\n'
