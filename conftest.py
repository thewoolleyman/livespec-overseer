"""Suite-wide hermetic guards for host-owned overseer state."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

_PACKAGE_DIR = Path(__file__).resolve().parent / "overseer"
if str(_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_DIR))

# Dispatch sandboxes may carry host OTEL settings. Most tests assert stderr event
# shapes and are not intending to exercise export behavior, so keep the suite
# hermetic by default; OTEL-specific tests opt in with monkeypatch.setenv.
os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)

import _registry_codex_restart  # noqa: E402
import _registry_core  # noqa: E402
import _registry_rounds  # noqa: E402
import _registry_rows_io  # noqa: E402
import _registry_stamp_resume  # noqa: E402
import _registry_stamps  # noqa: E402
import _supervisor_runtime_rollback  # noqa: E402
import _supervisor_snapshot  # noqa: E402
import registry  # noqa: E402
import terminal_probes  # noqa: E402

_AMBIENT_OTEL_ENV = (
    "HONEYCOMB_INGEST_KEY_LIVESPEC",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_SERVICE_NAME",
)

# Captured at IMPORT time, before any fixture or helper can redirect them. A test
# that isolates itself repoints these module globals at a tmp path; the guard must
# still know which paths are the operator's REAL ones.
_REAL_HOST_PATHS: frozenset[Path] = frozenset(
    {
        Path(_supervisor_snapshot.DEFAULT_STATUS_PATH),
        Path(_registry_core.DEFAULT_STORE_PATH),
        Path(_registry_core.DEFAULT_STAMP_PATH),
        Path(_registry_core.DEFAULT_WATCH_SET_PATH),
        _supervisor_runtime_rollback.default_runtime_state_path(),
    }
)
# `atomic_write` is DEFINED once in `_registry_core`, but each of these modules did
# `from _registry_core import atomic_write`, binding its own module-level name. Patching
# the definition site would leave every one of those names pointing at the original, so
# the guard has to wrap each BINDING site. This is the same resolution subtlety that
# `isolate_store` documents for `DEFAULT_STORE_PATH`.
_WRITE_BINDING_SITES = (
    _registry_codex_restart,
    _registry_core,
    _registry_rounds,
    _registry_rows_io,
    _registry_stamp_resume,
    _registry_stamps,
    registry,
)


@pytest.fixture(autouse=True)
def _clear_ambient_otel_export_config(*, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _AMBIENT_OTEL_ENV:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def _isolate_ambient_herdr(*, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A host running herdr must not lend its live default socket to a test.

    Tests that exercise herdr discovery repoint the same seam themselves.
    """
    monkeypatch.delenv(terminal_probes.HERDR_SOCKET_ENV, raising=False)
    isolated = str(tmp_path / "ambient-herdr" / "herdr.sock")
    real = terminal_probes.default_herdr_socket
    monkeypatch.setattr(
        terminal_probes,
        "default_herdr_socket",
        lambda *, home=None: isolated if home is None else real(home=home),
    )


# The operator's live herdr endpoints, captured at IMPORT time — before
# `_isolate_ambient_herdr` scrubs the environment and repoints the default — so the
# guard below still knows which sockets are REAL. Measured 2026-10-12: tests that
# mocked tmux reached the operator's live herdr through ownership-by-ancestry and
# left 74 `topic`/`supervisor` workspaces in the session the suite was run from.
# Repointing one discovery seam did not make that impossible; refusing the
# endpoint itself does, whatever route a future code path takes to it.
_OPERATOR_HERDR_SOCKETS: frozenset[str] = frozenset(
    os.path.realpath(path)
    for path in (
        terminal_probes.default_herdr_socket(),
        os.environ.get(terminal_probes.HERDR_SOCKET_ENV, ""),
    )
    if path
)


class OperatorTerminalAccessError(RuntimeError):
    """A test reached the operator's live terminal backend.

    Deliberately NOT an `OSError`: product code fails closed on `OSError` from a
    socket, which would swallow the refusal and let the test pass quietly.
    """


def _herdr_argv_is_isolated(*, argv: list[str]) -> bool:
    """A herdr CLI call is isolated when it names a session or manages sessions.

    Without `--session` every herdr subcommand addresses the operator's DEFAULT
    server, which is exactly the instance an ordinary test must never touch.
    """
    return "--session" in argv or argv[1:2] == ["session"]


@pytest.fixture(name="operator_herdr_guard", autouse=True)
def _refuse_operator_herdr(*, monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """No test may connect to, or run the herdr CLI against, the operator's herdr.

    Native integration tests are unaffected: they run their own
    `herdr --session <unique>` server, whose socket is never one of these. Every
    refusal is also RECORDED and failed at teardown, so product code that catches
    broadly cannot turn a refused touch into a passing test.
    """
    violations: list[str] = []

    def _refuse(*, message: str) -> OperatorTerminalAccessError:
        violations.append(message)
        return OperatorTerminalAccessError(message)

    real_connect = socket.socket.connect

    def _connect(self: socket.socket, address: object) -> None:
        if (
            self.family == socket.AF_UNIX
            and isinstance(address, str | bytes | os.PathLike)
            and os.path.realpath(os.fsdecode(address)) in _OPERATOR_HERDR_SOCKETS
        ):
            raise _refuse(
                message=f"test tried to connect to the operator's live herdr socket {address!r}"
            )
        real_connect(self, address)

    real_popen_init = subprocess.Popen.__init__

    def _popen_init(
        self: subprocess.Popen[object], args: object, *rest: object, **kw: object
    ) -> None:
        argv = [os.fsdecode(a) for a in args] if isinstance(args, list | tuple) else []
        if argv and Path(argv[0]).name == "herdr" and not _herdr_argv_is_isolated(argv=argv):
            raise _refuse(
                message=f"test ran the herdr CLI against the operator's default server: {argv!r}"
            )
        real_popen_init(self, args, *rest, **kw)  # type: ignore[arg-type]

    monkeypatch.setattr(socket.socket, "connect", _connect)
    monkeypatch.setattr(subprocess.Popen, "__init__", _popen_init)
    yield violations
    _fail_on_operator_herdr_touch(violations=violations)


def _fail_on_operator_herdr_touch(*, violations: list[str]) -> None:
    if violations:
        pytest.fail("; ".join(violations), pytrace=False)


@pytest.fixture(name="fail_on_operator_herdr_touch")
def _fail_on_operator_herdr_touch_fixture() -> Callable[..., None]:
    """The teardown verdict itself, so its failing branch can be pinned directly."""
    return _fail_on_operator_herdr_touch


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
    the family. All host-owned paths are guarded, so the NEXT write added to any of
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

    def guarded_runtime(original: Callable[..., None]) -> Callable[..., None]:
        def _runtime(*, sup, **kwargs) -> None:
            guard.assert_write_allowed(path=Path(sup.runtime_state_path))
            original(sup=sup, **kwargs)

        return _runtime

    for module in _WRITE_BINDING_SITES:
        monkeypatch.setattr(module, "atomic_write", guarded(module.atomic_write))
    monkeypatch.setattr(
        _supervisor_snapshot.registry,
        "atomic_write",
        guarded(_supervisor_snapshot.registry.atomic_write),
    )
    for name in (
        "begin_adoption",
        "complete_startup_if_pending",
        "rollback_after_startup_failure",
    ):
        monkeypatch.setattr(
            _supervisor_runtime_rollback,
            name,
            guarded_runtime(getattr(_supervisor_runtime_rollback, name)),
        )
    return guard
