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

import builtins
import io as _io
import json
import pathlib

from overseer import registry
from overseer.test_package_constraint_audit import (
    PackageImportAudit,
    all_imports,
    audit_package_imports,
)
from overseer.test_supervisor_builders import (
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from overseer.test_supervisor_fakes import (
    FakeTmux,
)

__all__: list[str] = []

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

_OUT_OF_BAND_IMPORTS = {
    "homelab_charter_scan.py": frozenset({"livespec_dev_tooling"}),
}


def _product_modules() -> tuple[pathlib.Path, ...]:
    """Every product module in the package — the beside-tests are not product."""
    return tuple(
        path for path in sorted(_PACKAGE_ROOT.glob("*.py")) if not path.name.startswith("test_")
    )


def _supervision_loop_modules() -> tuple[pathlib.Path, ...]:
    """Product modules that belong to the deterministic supervision loop."""
    return tuple(path for path in _product_modules() if not path.name.startswith("caam_"))


def _install_plan_tree_open_audit(*, monkeypatch, plan_root: pathlib.Path) -> list[str]:
    """Record every OPEN of a path under `plan_root`; return the growing record.

    Deliberately hooks only OPEN paths — `builtins.open`, `Path.open`,
    `Path.read_text`, `Path.read_bytes`. Directory enumeration and existence tests
    are NOT hooked, because constraints.md permits both: discovery keys on the
    DIRECTORY existing, and the one bounded exception is an EXISTENCE probe of
    `supervisor-handoff.md` ("no open, no read, no hash").
    """
    opened: list[str] = []

    def _record(*, target: object) -> None:
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
        _record(target=file)
        return real_open(file, *args, **kwargs)

    def _audited_path_open(self, *args, **kwargs):
        _record(target=self)
        return real_path_open(self, *args, **kwargs)

    def _audited_read_text(self, *args, **kwargs):
        _record(target=self)
        return real_read_text(self, *args, **kwargs)

    def _audited_read_bytes(self, *args, **kwargs):
        _record(target=self)
        return real_read_bytes(self, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", _audited_open)
    monkeypatch.setattr(pathlib.Path, "open", _audited_path_open)
    monkeypatch.setattr(pathlib.Path, "read_text", _audited_read_text)
    monkeypatch.setattr(pathlib.Path, "read_bytes", _audited_read_bytes)
    return opened


def test_the_package_imports_only_the_standard_library():
    """The "Language and dependencies" rule of SPECIFICATION/constraints.md.

    The supervision package must not import third-party code from an installed
    environment, but v027 permits a narrow exemption for in-tree vendored code
    that is vendored, standalone, and hermetic.

    SABOTAGE-VERIFIED 2026-07-26: adding `import pytest` to `overseer/registry.py` turns
    the installed-import arm red with `{'registry.py': ['pytest']}`; reverted to a
    zero diff.

    SABOTAGE-VERIFIED 2026-08-21, each independently with installed `pytest`: a
    vendored import with no `overseer/_vendor/pytest` source reddens the vendored arm;
    a vendored `pytest` whose module-load code imports top-level `pytest` reddens the
    standalone arm; a product bare `import pytest` while `overseer/_vendor/pytest`
    exists reddens the hermetic-collision arm. A conforming fake vendored package with
    function-body and `TYPE_CHECKING` third-party imports stays green.

    Installed third-party modules are deliberate. Sabotaging with an uninstalled one
    also fails, but as a collection-time `ModuleNotFoundError` before this assertion
    ever runs — loud enough to hold the constraint, but it does not exercise THIS test.
    Only the installed case proves the assertion has teeth.
    """
    audit = audit_package_imports(
        product_paths=_product_modules(),
        package_root=_PACKAGE_ROOT,
        out_of_band_imports=_OUT_OF_BAND_IMPORTS,
    )

    assert audit == PackageImportAudit(
        installed_imports={},
        missing_vendored_sources={},
        runtime_dependency_declarations=[],
        vendored_load_imports={},
        hermetic_collisions={},
    )


def test_the_supervision_loop_cannot_make_model_calls():
    """The "Determinism boundary" rule of SPECIFICATION/constraints.md: the daemon "holds
    NO semantic judgment and makes no model calls", so "tokens are never spent by the
    watching loop".

    A model call needs a network client. The supervision-loop modules import NO
    network-capable stdlib module at all, which is a stronger and far more durable
    statement than auditing call sites: there is no client to call one with.
    `caam_*` modules are operation code, not daemon supervision code; the account-usage
    operation is specified to poll Anthropic's usage endpoint.

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
    for path in _supervision_loop_modules():
        hits = sorted(all_imports(path=path) & _NETWORK_MODULES)
        if hits:
            reachable[path.name] = hits

    assert reachable == {}, f"network-capable imports in a no-model-calls package: {reachable}"


def test_a_supervision_tick_never_opens_a_file_under_a_plan_tree(*, tmp_path, monkeypatch):
    """The "Filesystem boundaries" rule of SPECIFICATION/constraints.md: the daemon
    "NEVER reads, writes, or hashes files under any repository's plan tree".

    This is the BEHAVIORAL evidence the row previously lacked. The nearest thing before
    was a substring assertion over static prose in `test_plugin_structure.py`, which
    proves a sentence exists, not that the loop obeys it.

    SABOTAGE-VERIFIED 2026-07-26: making `Supervisor.tick` read each track's own handoff
    file turns this red naming that path; reverted to a zero diff.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    opened = _install_plan_tree_open_audit(
        monkeypatch=monkeypatch, plan_root=(repo / "plan").resolve()
    )

    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)], out=_io.StringIO())
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session), store_path=sup.store_path
    )

    _ = sup.tick(act=True)

    assert opened == [], f"the daemon opened files under a plan tree: {opened}"


def test_release_please_never_targets_a_python_file_and_the_version_data_ships():
    """release-please must not rewrite any `.py`, and its data file must be packaged.

    THE REGRESSION THIS EXISTS FOR, observed not hypothesised: `source_trees =
    ["overseer"]` was armed 2026-07-27, which puts every `.py` in this package
    into `check-red-green-replay`'s product-implementation bucket. release-please
    is a bot — it cannot author a Red->Green pair or a green-verified leg — so its
    release commit `a54e233`, which rewrote `overseer/version.py`, failed the gate
    and BLOCKED release PR #180. Every other fleet member arms `source_trees` and
    generates no `.py`; this repo was the only outlier.

    The fix moved the version literal to `overseer/version.json`. This test pins
    all three things that can independently regress it back:

    1. no `extra-files` entry targets a `.py` — the actual bug;
    2. the data file's version matches `pyproject.toml` — the drift class that
       `uv.lock` was already bitten by (`overseer-l0f`);
    3. the data file is declared as package-data — without it the built wheel
       omits `version.json` and the INSTALLED console scripts raise at import,
       while the editable install and in-tree executables keep working.

    SCOPE, stated because assertion 3 is shallower than 1 and 2: it pins the
    packaging DECLARATION, not the built artifact. Building a wheel here would
    spawn a subprocess that `check-tests-no-subprocess-spawn` exists to prevent
    (coverage races under the parallel dispatcher). A wheel that omits the file
    despite a correct declaration would not be caught by this test.

    SABOTAGE-VERIFIED, each independently: pointing the `extra-files` entry back
    at `overseer/version.py` reddens (1); editing `version.json` to a different
    version reddens (2); deleting the `[tool.setuptools.package-data]` block
    reddens (3). All three reverted to a zero diff.
    """
    repo_root = _PACKAGE_ROOT.parent
    config = json.loads((repo_root / "release-please-config.json").read_text(encoding="utf-8"))

    python_targets = [
        entry.get("path", "")
        for package in config.get("packages", {}).values()
        for entry in package.get("extra-files", [])
        if isinstance(entry, dict) and str(entry.get("path", "")).endswith(".py")
    ]
    assert python_targets == [], (
        "release-please targets a .py file, which check-red-green-replay will reject "
        f"on the release commit and block the release PR: {python_targets}"
    )

    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    declared = json.loads((_PACKAGE_ROOT / "version.json").read_text(encoding="utf-8"))["version"]
    assert f'version = "{declared}"' in pyproject, (
        f"overseer/version.json says {declared!r} but pyproject.toml does not declare it — "
        "the generated literal has drifted from its source"
    )

    assert 'overseer = ["version.json"]' in pyproject, (
        "version.json is not declared as setuptools package-data, so the built wheel "
        "will omit it and the installed console scripts will fail at import"
    )
