"""Regression: a daemon runtime switch must not inherit an import path that shadows it.

Measured 2026-09-11 (work-item overseer-xgfhuf). After release v5.4.10 published at
`9e6d115f...`, the acting top-pane daemon execed the CORRECT immutable runtime
executable under `~/.local/share/livespec-overseer/runtime/9e6d115f.../venv/bin/overseerd`
while its inherited environment still carried
`PYTHONPATH=~/.claude/plugins/cache/livespec-overseer/livespec-overseer/ae7e9dd9b9ae`,
the PRIOR v5.4.9 plugin cache. `PYTHONPATH` is searched ahead of a venv's
site-packages, so every successor imported the OLD package, published a snapshot still
reporting version 5.4.9, decided it was out of date, and execed again. Instance ids
changed every few seconds behind an unchanged pid and an unchanged top pane.

These tests deliberately do NOT stop at the rendered argv. The argv was already
correct while the defect was live -- it named the new runtime executable -- so an
argv assertion cannot see this failure at all. Each test resolves the package the
SWITCHED process would actually import, and the last one drives the real
release-currency adapter under that resolved version to show the loop closing.
"""

from __future__ import annotations

import contextlib
import importlib.machinery
import io
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import _supervisor_reexec
import _supervisor_release_runtime
import _supervisor_runtime_rollback
from test_supervisor_builders import make_supervisor
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []

_PRIOR_COMMIT = "ae7e9dd9b9ae"
_PRIOR_VERSION = "5.4.9"
_ADOPTED_COMMIT = "9e6d115f9ea99d119234cdc33fa57dd4812b5f64"
_ADOPTED_VERSION = "5.4.10"


@dataclass(frozen=True, kw_only=True)
class _Scene:
    """The measured prior-plugin-cache-to-new-runtime transition, on disk."""

    prior_cache: Path
    runtime_site_packages: Path
    runtime_executable: Path
    inherited_env: dict[str, str]


@dataclass(frozen=True, kw_only=True)
class _GhResult:
    """Only `stdout` is read by the release-currency adapter's forge calls."""

    stdout: str


def _install_overseer_package(*, root: Path, version: str) -> Path:
    package = root / "overseer"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "version.json").write_text(json.dumps({"version": version}) + "\n", encoding="utf-8")
    return package


def _release_scene(*, tmp_path: Path) -> _Scene:
    prior_cache = (
        tmp_path / "plugins" / "cache" / "livespec-overseer" / "livespec-overseer" / _PRIOR_COMMIT
    )
    _install_overseer_package(root=prior_cache, version=_PRIOR_VERSION)
    venv = tmp_path / "runtime" / _ADOPTED_COMMIT / "venv"
    site_packages = venv / "lib" / "python3.10" / "site-packages"
    _install_overseer_package(root=site_packages, version=_ADOPTED_VERSION)
    executable = venv / "bin" / "overseerd"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    return _Scene(
        prior_cache=prior_cache,
        runtime_site_packages=site_packages,
        runtime_executable=executable,
        inherited_env={
            "PYTHONPATH": str(prior_cache),
            "HOME": str(tmp_path),
            "PATH": "/usr/bin:/bin",
            "TMUX": "/tmp/tmux-1000/default,3749981,0",
        },
    )


def _import_target(*, scene: _Scene, env: Mapping[str, str]) -> Path:
    """Where `import overseer` lands in the process this environment would start.

    Models CPython's own order for a venv console script: the script's own directory
    first, then each `PYTHONPATH` entry in order, then the venv's site-packages.
    """
    search = [str(scene.runtime_executable.parent)]
    search.extend(entry for entry in env.get("PYTHONPATH", "").split(os.pathsep) if entry)
    search.append(str(scene.runtime_site_packages))
    spec = importlib.machinery.PathFinder.find_spec("overseer", search)
    assert spec is not None
    assert spec.origin is not None
    return Path(spec.origin).resolve().parent


def _resolved_version(*, package: Path) -> str:
    version = json.loads((package / "version.json").read_text(encoding="utf-8"))["version"]
    assert isinstance(version, str)
    return version


def _record_into(*, calls: list[dict[str, object]]):
    """A recorder bound to EVERY exec seam name the daemon has carried.

    The daemon that shipped this defect replaced its image through `execv`, which takes
    no environment argument at all; the fixed one goes through `execve`. Binding both is
    what makes these tests fail on the MISSING environment rather than escape into a real
    process-image replacement under pytest.
    """

    def record(**kwargs: object) -> None:
        calls.append(kwargs)

    return record


def _adopt_release(*, tmp_path: Path, scene: _Scene) -> dict[str, object]:
    """Drive one release adoption and return the recorded process-image switch."""
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())
    calls: list[dict[str, object]] = []
    record = _record_into(calls=calls)
    sup.execv = record
    sup.execve = record
    sup.environ = lambda: dict(scene.inherited_env)
    sup.reexec_target = lambda: scene.runtime_executable
    sup.argv = lambda: ["overseerd", "--warn-percent", "30"]

    _supervisor_reexec.maybe_reexec(sup=sup, rows=[])

    assert len(calls) == 1
    return calls[0]


def _switch_env(*, call: dict[str, object]) -> dict[str, str]:
    assert "env" in call, (
        "a runtime switch must hand the successor an explicit environment; "
        f"it was replaced with {sorted(call)} alone"
    )
    env = call["env"]
    assert isinstance(env, dict)
    return env


def test_the_inherited_plugin_pythonpath_really_does_shadow_the_selected_runtime(*, tmp_path):
    """The control: without isolation the measured environment resolves the OLD package.

    This is what makes the two tests below evidence rather than assertion. If this ever
    goes green on its own the scene stopped reproducing the defect.
    """
    scene = _release_scene(tmp_path=tmp_path)

    shadowed = _import_target(scene=scene, env=scene.inherited_env)

    assert shadowed == scene.prior_cache / "overseer"
    assert _resolved_version(package=shadowed) == _PRIOR_VERSION


def test_release_adoption_resolves_the_new_runtime_package_not_the_prior_plugin_cache(*, tmp_path):
    """Adoption execs the selected runtime under an environment the old cache cannot win."""
    scene = _release_scene(tmp_path=tmp_path)

    call = _adopt_release(tmp_path=tmp_path, scene=scene)

    assert call["path"] == str(scene.runtime_executable)
    assert call["argv"] == [str(scene.runtime_executable), "--warn-percent", "30"]
    env = _switch_env(call=call)
    assert "PYTHONPATH" not in env
    assert env["HOME"] == scene.inherited_env["HOME"]
    assert env["PATH"] == scene.inherited_env["PATH"]
    assert env["TMUX"] == scene.inherited_env["TMUX"]

    package = _import_target(scene=scene, env=env)
    assert package == scene.runtime_site_packages / "overseer"
    assert _resolved_version(package=package) == _ADOPTED_VERSION


def test_runtime_rollback_returns_to_the_prior_runtime_under_the_same_isolation(*, tmp_path):
    """A rollback selects an immutable runtime too, so it owes the same import rule."""
    scene = _release_scene(tmp_path=tmp_path)
    state_path = tmp_path / "runtime-state.json"
    failed = tmp_path / "release-b" / "overseerd"
    failed.parent.mkdir()
    failed.write_text("#!/bin/sh\n", encoding="utf-8")
    state_path.write_text(
        json.dumps(
            {
                "pending": str(failed),
                "previous": str(scene.runtime_executable),
                "rejected": [],
            }
        ),
        encoding="utf-8",
    )
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=FakeTmux(),
        argv=lambda: [str(failed), "--warn-percent", "45"],
        runtime_state_path=state_path,
    )
    calls: list[dict[str, object]] = []
    record = _record_into(calls=calls)
    sup.execv = record
    sup.execve = record
    sup.environ = lambda: dict(scene.inherited_env)

    with contextlib.redirect_stderr(io.StringIO()):
        _supervisor_runtime_rollback.rollback_after_startup_failure(
            sup=sup, exc=RuntimeError("startup crash")
        )

    assert len(calls) == 1
    call = calls[0]
    assert call["path"] == str(scene.runtime_executable)
    assert call["argv"] == [str(scene.runtime_executable), "--warn-percent", "45"]
    env = _switch_env(call=call)
    assert "PYTHONPATH" not in env
    assert env["TMUX"] == scene.inherited_env["TMUX"]

    package = _import_target(scene=scene, env=env)
    assert _resolved_version(package=package) == _ADOPTED_VERSION


def test_the_package_the_switched_process_resolves_is_what_ends_the_reexec_cycle(
    *, tmp_path, monkeypatch
):
    """The loop closes at the resolved VERSION, which is why the import rule is the fix.

    The live failure was not one bad exec, it was a cycle: each successor imported 5.4.9
    from the prior plugin cache, so its own release-currency check compared `v5.4.9`
    against `refs/heads/release`, found `9e6d115f` newer, and adopted it again. This
    drives the real `ReleaseRuntimeAdapter` under each resolved version -- the shadowed
    one keeps switching, the isolated one stops.
    """
    scene = _release_scene(tmp_path=tmp_path)
    commits = {
        "release": _ADOPTED_COMMIT,
        f"v{_ADOPTED_VERSION}": _ADOPTED_COMMIT,
        f"v{_PRIOR_VERSION}": _PRIOR_COMMIT,
    }

    def fake_gh(command, **_kwargs) -> _GhResult:
        endpoint = str(command[-1])
        if endpoint.endswith("check-runs?per_page=100"):
            return _GhResult(
                stdout=json.dumps({"check_runs": [{"name": "ci-green", "conclusion": "success"}]})
            )
        ref = endpoint.rsplit("/commits/", 1)[1]
        return _GhResult(stdout=json.dumps({"sha": commits[ref]}))

    def switches_again(*, running_version: str) -> bool:
        monkeypatch.setattr(_supervisor_release_runtime, "APP_VERSION", running_version)
        sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())
        adapter = _supervisor_release_runtime.ReleaseRuntimeAdapter(
            sup=sup,
            run=fake_gh,
            ensure_release_runtime=lambda *, release: scene.runtime_executable,
        )
        calls: list[dict[str, object]] = []
        record = _record_into(calls=calls)
        sup.execv = record
        sup.execve = record
        sup.environ = lambda: dict(scene.inherited_env)
        sup.argv = lambda: ["overseerd"]
        sup.reexec_target = adapter.reexec_target
        _ = adapter.currency_check()
        _supervisor_reexec.maybe_reexec(sup=sup, rows=[])
        return bool(calls)

    shadowed = _import_target(scene=scene, env=scene.inherited_env)
    isolated = _import_target(
        scene=scene, env=_switch_env(call=_adopt_release(tmp_path=tmp_path, scene=scene))
    )

    assert switches_again(running_version=_resolved_version(package=shadowed)) is True
    assert switches_again(running_version=_resolved_version(package=isolated)) is False
