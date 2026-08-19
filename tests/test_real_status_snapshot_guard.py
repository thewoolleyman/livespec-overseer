"""Beside-tests for the suite-wide real-status-snapshot guard in `conftest.py`.

The guard exists because the suite used to publish fixture rows to the
operator's real `~/.livespec-overseer-status.json`. A guard against that is only
worth having if it can be shown to FIRE, and — the part that is easy to skip —
to fire through the path production code actually takes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PACKAGE_DIR = Path(__file__).resolve().parent.parent / "overseer"
if str(_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_DIR))

import _supervisor_snapshot  # noqa: E402


def test_real_status_snapshot_guard_fails_on_default_snapshot_write(
    *,
    real_status_snapshot_guard,
) -> None:
    with pytest.raises(pytest.fail.Exception, match="real overseer status snapshot"):
        real_status_snapshot_guard.assert_snapshot_write_allowed(
            path=real_status_snapshot_guard.path
        )


def test_real_status_snapshot_guard_is_installed_on_the_writers_own_module() -> None:
    """The guard is INSTALLED, not merely constructible.

    `_supervisor_snapshot.default_status_writer` resolves `registry.atomic_write` by
    module attribute at call time, which is the only reason the fixture's
    `monkeypatch.setattr` reaches it at all. Asserting on the guard OBJECT cannot
    tell a live monkeypatch from a dead one — this drives the module attribute the
    writer itself resolves, so a fixture that stopped patching reddens here.

    `registry.atomic_write` is called directly rather than through
    `default_status_writer` deliberately: the writer takes `registry.file_lock` on
    the target BEFORE the guarded write, so going through it would create a
    `.lock` file beside the operator's real snapshot — this test would leak the
    very host state the guard defends.
    """
    with pytest.raises(pytest.fail.Exception, match="real overseer status snapshot"):
        _supervisor_snapshot.registry.atomic_write(
            path=Path(_supervisor_snapshot.DEFAULT_STATUS_PATH), body="{}\n"
        )


def test_real_status_snapshot_guard_passes_writes_to_every_other_path(*, tmp_path) -> None:
    """The discriminating control: the guard blocks ONE path, not writing in general.

    Without this, a guard that failed every write — or a `match=` that happened to
    catch an unrelated failure — would look identical to a working one in the test
    above.
    """
    target = tmp_path / "status.json"

    _supervisor_snapshot.registry.atomic_write(path=target, body='{"ok": true}\n')

    assert target.read_text(encoding="utf-8") == '{"ok": true}\n'
