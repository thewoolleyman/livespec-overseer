"""Package-wide constraint tests for SPECIFICATION/constraints.md.

These pin three NEGATIVE architectural properties — "no third-party imports",
"no model calls", "never touches a plan tree" — that the per-module beside-tests
do not naturally assert, because each is a statement about what the package
does NOT do. They are the evidence behind three `tests/heading-coverage.json`
rows that carried `test: "TODO"` with no candidate at all.

Each test is written so a real regression reddens it; the sabotage that was run
to confirm that is recorded in each test's docstring.
"""

from __future__ import annotations

import ast
import builtins
import io as _io
import pathlib
import sys

from overseer import registry
from overseer.test_supervisor_builders import (
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from overseer.test_supervisor_fakes import (
    FakeTmux,
)

_PACKAGE_ROOT = pathlib.Path(__file__).resolve().parent

# Standard-library modules that can reach the network or spawn a model call.
# `subprocess` is deliberately NOT here: the daemon drives tmux and git through
# it, which constraints.md explicitly contemplates ("every acting mechanic
# drives a real tmux"). The point of this set is that no PYTHON-level network
# client is reachable from the supervision loop.
_NETWORK_MODULES = frozenset(
    {
        "asyncio",
        "ftplib",
        "http",
        "imaplib",
        "poplib",
        "smtplib",
        "socket",
        "socketserver",
        "ssl",
        "telnetlib",
        "urllib",
        "xmlrpc",
    }
)


def _product_modules() -> tuple[pathlib.Path, ...]:
    """Every product module in the package — the beside-tests are not product."""
    return tuple(
        path for path in sorted(_PACKAGE_ROOT.glob("*.py")) if not path.name.startswith("test_")
    )


def _first_party_names() -> frozenset[str]:
    return frozenset(path.stem for path in _PACKAGE_ROOT.glob("*.py"))


def _top_level_imports(*, path: pathlib.Path) -> frozenset[str]:
    """Every top-level module name imported by `path`, absolute imports only.

    A relative import (`from . import x`, level > 0) is by construction
    first-party, so it cannot introduce a dependency and is skipped.
    """
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return frozenset(names)


def _install_plan_tree_open_audit(*, monkeypatch, plan_root: pathlib.Path) -> list[str]:
    """Record every OPEN of a path under `plan_root`; return the growing record.

    Deliberately hooks only OPEN paths — `builtins.open`, `Path.open`,
    `Path.read_text`, `Path.read_bytes`. Directory enumeration and existence tests
    are NOT hooked, because constraints.md permits both: discovery keys on the
    DIRECTORY existing, and the one bounded exception is an EXISTENCE probe of
    `supervisor-handoff.md` ("no open, no read, no hash").
    """
    opened: list[str] = []

    def _record(target: object) -> None:
        try:
            resolved = pathlib.Path(str(target)).resolve()
        except (OSError, ValueError):  # pragma: no cover - defensive on odd targets
            return
        if resolved.is_relative_to(plan_root):
            opened.append(str(resolved))

    real_open = builtins.open
    real_path_open = pathlib.Path.open
    real_read_text = pathlib.Path.read_text
    real_read_bytes = pathlib.Path.read_bytes

    def _audited_open(file, *args, **kwargs):
        _record(file)
        return real_open(file, *args, **kwargs)

    def _audited_path_open(self, *args, **kwargs):
        _record(self)
        return real_path_open(self, *args, **kwargs)

    def _audited_read_text(self, *args, **kwargs):
        _record(self)
        return real_read_text(self, *args, **kwargs)

    def _audited_read_bytes(self, *args, **kwargs):
        _record(self)
        return real_read_bytes(self, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", _audited_open)
    monkeypatch.setattr(pathlib.Path, "open", _audited_path_open)
    monkeypatch.setattr(pathlib.Path, "read_text", _audited_read_text)
    monkeypatch.setattr(pathlib.Path, "read_bytes", _audited_read_bytes)
    return opened


def test_the_package_imports_only_the_standard_library():
    """The "Language and dependencies" rule of SPECIFICATION/constraints.md: "no
    third-party imports anywhere in the package". Nothing asserted this before — the
    constraint was carried by review and by the executables' isolated launch mode alone.

    SABOTAGE-VERIFIED 2026-07-26: adding `import pytest` to `overseer/registry.py` turns
    this red with `{'registry.py': ['pytest']}`; reverted to a zero diff.

    An INSTALLED third-party module was used deliberately. Sabotaging with an uninstalled
    one (`import yaml`) also fails, but as a collection-time `ModuleNotFoundError` before
    this assertion ever runs — loud enough to hold the constraint, but it does not
    exercise THIS test. Only the installed case proves the assertion has teeth.
    """
    stdlib = frozenset(sys.stdlib_module_names)
    first_party = _first_party_names()
    offenders: dict[str, list[str]] = {}
    for path in _product_modules():
        third_party = sorted(
            name
            for name in _top_level_imports(path=path)
            if name not in stdlib and name not in first_party
        )
        if third_party:
            offenders[path.name] = third_party

    assert offenders == {}, f"third-party imports in a stdlib-only package: {offenders}"


def test_the_supervision_loop_cannot_make_model_calls():
    """The "Determinism boundary" rule of SPECIFICATION/constraints.md: the daemon "holds
    NO semantic judgment and makes no model calls", so "tokens are never spent by the
    watching loop".

    A model call needs a network client. The package imports NO network-capable stdlib
    module at all, which is a stronger and far more durable statement than auditing call
    sites: there is no client to call one with.

    SABOTAGE-VERIFIED 2026-07-26: adding `import urllib.request` to
    `overseer/supervisor.py` turns this red with `{'supervisor.py': ['urllib']}`;
    reverted to a zero diff.

    Recorded because it nearly went the other way: the first sabotage attempt anchored its
    edit on a text fragment `supervisor.py` does not contain, so it rewrote the file
    unchanged and the test "passed". A sabotage that silently fails to apply is
    indistinguishable from a verifier with no teeth. Assert the injection landed before
    trusting the result.
    """
    reachable: dict[str, list[str]] = {}
    for path in _product_modules():
        hits = sorted(_top_level_imports(path=path) & _NETWORK_MODULES)
        if hits:
            reachable[path.name] = hits

    assert reachable == {}, f"network-capable imports in a no-model-calls package: {reachable}"


def test_a_supervision_tick_never_opens_a_file_under_a_plan_tree(tmp_path, monkeypatch):
    """The "Filesystem boundaries" rule of SPECIFICATION/constraints.md: the daemon
    "NEVER reads, writes, or hashes files under any repository's plan tree".

    This is the BEHAVIORAL evidence the row previously lacked. The nearest thing before
    was a substring assertion over static prose in `test_plugin_structure.py`, which
    proves a sentence exists, not that the loop obeys it.

    SABOTAGE-VERIFIED 2026-07-26: making `Supervisor.tick` read each track's own handoff
    file turns this red naming that path; reverted to a zero diff.
    """
    repo, topic = make_plan(tmp_path)
    opened = _install_plan_tree_open_audit(
        monkeypatch=monkeypatch, plan_root=(repo / "plan").resolve()
    )

    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=73))
    sup = make_supervisor(tmp_path, fake, watch_repos=[str(repo)], out=_io.StringIO())
    registry.append_mapping(mapped_track(repo, topic, session), sup.store_path)

    _ = sup.tick(act=True)

    assert opened == [], f"the daemon opened files under a plan tree: {opened}"
