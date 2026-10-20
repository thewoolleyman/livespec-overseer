"""Integration gate: a shipped launcher runs its OWN plugin's package and runtime.

Governed by the shipped-launcher scenario in SPECIFICATION/scenarios.md and the
shipped-launcher clause of SPECIFICATION/contracts.md.

MEASURED 2026-10-14 ~05:03Z (work-item overseer-uzvcbn.2). Just after v5.28.3
shipped, the overseer bottom pane ran `$PLUGIN_ROOT/bin/overseer-start` with
PLUGIN_ROOT pointing at the 5.28.3 plugin cache and its current directory inside
`/data/projects/livespec-overseer`. The daemon came up from
`~/.local/share/livespec-overseer/runtime/5.28.2/venv/bin/overseerd` — the
PRE-FIX release — and had to be stopped. `bin/overseer-start` ran
`python3 -m overseer.start`, and `-m` puts the CURRENT DIRECTORY at
`sys.path[0]` ahead of every `PYTHONPATH` entry, so the checkout's `overseer`
package won: its `version.json` still read 5.28.2, `runtime_prefix()` chose
`runtime/5.28.2`, that prefix already existed, and the old build ran. The argv
named the 5.28.3 plugin throughout, which is why no argv assertion can see this
failure; the only wrong thing is which package the process imported.

WHAT IS STAGED AND WHY. Each test builds a plugin tree and a decoy
livespec-overseer checkout side by side, copies the REAL shipped `bin/`
launchers into the staged plugin, and runs them with the current directory
inside the decoy. The staged `overseer` package carries the real
`__init__.py`, `launch.py`, `version.py` and `runtime_prefix.py`, so the
`version.json` -> `APP_VERSION` -> runtime-prefix chain being measured is
product code. Only the ENTRY modules are probes: the real `start.py` refuses
outside a tmux pane and the real `daemon.py` would start a daemon, so neither
ever reaches the runtime-prefix decision this scenario is about. What a launcher
CONTROLS is which `overseer` package its process imports, and that is what is
measured here.
"""

from __future__ import annotations

import importlib
import importlib.machinery
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

__all__: list[str] = []

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_BIN = ROOT / ".claude-plugin" / "bin"
SOURCE_PACKAGE = ROOT / "overseer"
LAUNCH_MODULE = SOURCE_PACKAGE / "launch.py"

_PLUGIN_VERSION = "7.28.3"
_CHECKOUT_VERSION = "7.28.2"
_REAL_PACKAGE_FILES = ("__init__.py", "launch.py", "runtime_prefix.py", "version.py")
_ENTRY_MODULES = ("daemon.py", "start.py")
_SCRUBBED_ENV = frozenset({"COVERAGE_PROCESS_START", "PYTHONPATH", "PYTHONSAFEPATH"})
# The one launch shape that admits the caller's directory to `sys.path[0]`. Checked
# against the shipped `bin/` inventory ENUMERATED FROM THE TREE, so a launcher added
# later owes the same rule without this test being edited. Comment lines are stripped
# before the scan: a launcher is expected to EXPLAIN why it avoids this shape, and
# saying so is not using it.
_MODULE_LAUNCH_SHAPE = "python3 -m "

# Stands in for `overseer.start` / `overseer.daemon`. It reports the two facts the
# scenario is about: which `overseer` package the launcher's process imported, and
# which runtime prefix that package's recorded version resolves to.
_PROBE_SOURCE = '''"""Probe entry module standing in for a real launcher target."""

import json
from pathlib import Path

import overseer
import runtime_prefix


def main():
    print(
        json.dumps(
            {
                "package": str(Path(overseer.__file__).resolve().parent),
                "runtime_prefix": str(runtime_prefix.runtime_prefix()),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


@dataclass(frozen=True, kw_only=True)
class _Scene:
    """A staged plugin, a decoy checkout one version behind it, and an empty HOME."""

    plugin: Path
    checkout: Path
    home: Path
    launchers: dict[str, Path]


def _install_package(*, root: Path, version: str) -> None:
    package = root / "overseer"
    package.mkdir(parents=True)
    for name in _REAL_PACKAGE_FILES:
        _ = shutil.copy2(SOURCE_PACKAGE / name, package / name)
    (package / "version.json").write_text(json.dumps({"version": version}) + "\n", encoding="utf-8")
    for entry in _ENTRY_MODULES:
        (package / entry).write_text(_PROBE_SOURCE, encoding="utf-8")


def stage(*, tmp_path: Path) -> _Scene:
    """Stage the scene, after asserting the launchers have a launch module to run."""
    assert LAUNCH_MODULE.is_file(), (
        "a shipped launcher must run a launch module inside its own plugin rather than "
        f"`python3 -m`, whose sys.path[0] is the caller's directory; {LAUNCH_MODULE} "
        "is absent"
    )
    plugin = tmp_path / "plugin"
    bin_dir = plugin / "bin"
    bin_dir.mkdir(parents=True)
    launchers = {
        path.name: Path(shutil.copy2(path, bin_dir / path.name))
        for path in sorted(PLUGIN_BIN.iterdir())
        if path.is_file()
    }
    _install_package(root=plugin, version=_PLUGIN_VERSION)
    checkout = tmp_path / "checkout"
    _install_package(root=checkout, version=_CHECKOUT_VERSION)
    home = tmp_path / "home"
    home.mkdir()
    return _Scene(plugin=plugin, checkout=checkout, home=home, launchers=launchers)


def _child_env(*, scene: _Scene) -> dict[str, str]:
    """The operator's environment minus every import-path and coverage override.

    `PYTHONPATH` is dropped because the launcher exports its own, and
    `COVERAGE_PROCESS_START` / `COV_CORE_*` because an instrumented child would race
    the suite's own coverage data. `PYTHONSAFEPATH` is dropped so no ambient setting
    can do the launcher's job for it.
    """
    env = {
        name: value
        for name, value in os.environ.items()
        if name not in _SCRUBBED_ENV and not name.startswith("COV_CORE_")
    }
    env["HOME"] = str(scene.home)
    return env


def run_launcher(*, scene: _Scene, name: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run one staged launcher from `cwd`, exactly as an operator shell would."""
    return subprocess.run(  # noqa: S603 - a staged copy of this repo's own launcher.
        [str(scene.launchers[name])],
        cwd=cwd,
        env=_child_env(scene=scene),
        check=False,
        capture_output=True,
        text=True,
        timeout=60.0,
    )


def resolved_report(*, completed: subprocess.CompletedProcess[str]) -> dict[str, str]:
    assert completed.returncode == 0, f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    report = json.loads(completed.stdout)
    assert isinstance(report, dict)
    return {str(key): str(value) for key, value in report.items()}


def _runtime_prefix_for(*, scene: _Scene, version: str) -> Path:
    return scene.home / ".local" / "share" / "livespec-overseer" / "runtime" / version


def _uses_the_module_launch_shape(*, launcher: Path) -> bool:
    lines = launcher.read_text(encoding="utf-8").splitlines()
    code = "\n".join(line for line in lines if not line.lstrip().startswith("#"))
    return _MODULE_LAUNCH_SHAPE in code


def _package_resolved_from(*, search: list[str]) -> Path:
    """Where `import overseer` lands for a process whose `sys.path` begins with `search`."""
    importlib.invalidate_caches()
    spec = importlib.machinery.PathFinder.find_spec("overseer", search)
    assert spec is not None
    assert spec.origin is not None
    return Path(spec.origin).resolve().parent


def test_scenario_a_shipped_launcher_runs_its_own_plugins_package_not_the_callers_checkout(
    *, tmp_path: Path
) -> None:
    """`overseer-start` from inside a stale checkout runs the PLUGIN's package and runtime."""
    scene = stage(tmp_path=tmp_path)

    report = resolved_report(
        completed=run_launcher(scene=scene, name="overseer-start", cwd=scene.checkout)
    )

    assert Path(report["package"]) == scene.plugin / "overseer"
    assert Path(report["package"]) != scene.checkout / "overseer"
    assert Path(report["runtime_prefix"]) == _runtime_prefix_for(
        scene=scene, version=_PLUGIN_VERSION
    )
    assert Path(report["runtime_prefix"]) != _runtime_prefix_for(
        scene=scene, version=_CHECKOUT_VERSION
    )


def test_every_shipped_launcher_runs_the_plugin_package_it_lives_in(*, tmp_path: Path) -> None:
    """The `overseerd` family owes the same rule, and so does every launcher beside it."""
    scene = stage(tmp_path=tmp_path)

    shadowing = sorted(
        name
        for name, path in scene.launchers.items()
        if _uses_the_module_launch_shape(launcher=path)
    )

    assert shadowing == []
    report = resolved_report(
        completed=run_launcher(scene=scene, name="overseerd", cwd=scene.checkout)
    )
    assert Path(report["package"]) == scene.plugin / "overseer"
    assert Path(report["package"]) != scene.checkout / "overseer"


def test_the_module_launch_shape_really_does_let_the_callers_checkout_win(
    *, tmp_path: Path
) -> None:
    """The control: `-m` resolves the CHECKOUT, which is what makes the above evidence.

    Modelled the way CPython builds `sys.path`: `python3 -m` prepends the current
    directory and only then reads `PYTHONPATH`, while running a FILE prepends that
    file's own directory instead. If this ever goes green on its own the scene has
    stopped reproducing the measured defect.
    """
    scene = stage(tmp_path=tmp_path)

    shadowed = _package_resolved_from(search=[str(scene.checkout), str(scene.plugin)])
    isolated = _package_resolved_from(search=[str(scene.plugin / "overseer"), str(scene.plugin)])

    assert shadowed == scene.checkout / "overseer"
    assert isolated == scene.plugin / "overseer"


def test_a_launcher_whose_own_plugin_root_holds_no_package_refuses_and_names_it(
    *, tmp_path: Path
) -> None:
    """The scenario's last clause: no fallback to a package found somewhere else."""
    scene = stage(tmp_path=tmp_path)
    shutil.rmtree(scene.plugin / "overseer")

    completed = run_launcher(scene=scene, name="overseer-start", cwd=scene.checkout)

    assert completed.returncode != 0
    assert str(scene.plugin / "overseer") in completed.stdout + completed.stderr
