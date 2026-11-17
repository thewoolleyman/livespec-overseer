"""The pi plugin-root resolver resolves only the livespec-ai clone, never the old owner's."""

from __future__ import annotations

import json
import pathlib
import subprocess

_RESOLVER = (
    pathlib.Path(__file__).resolve().parent.parent
    / ".claude-plugin"
    / ".pi-plugin"
    / "lib"
    / "resolve-plugin-root.sh"
)


def _make_clone(*, project: pathlib.Path, owner: str) -> pathlib.Path:
    root = project / ".pi" / "git" / "github.com" / owner / "livespec-overseer" / ".claude-plugin"
    (root / "prose").mkdir(parents=True)
    (root / "plugin.json").write_text(json.dumps({"name": "livespec-overseer"}), encoding="utf-8")
    return root


def _resolve(*, project: pathlib.Path) -> subprocess.CompletedProcess[str]:
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(project / "home")}
    return subprocess.run(  # noqa: S603 - the shell resolver under test, not a Python child
        ["bash", str(_RESOLVER), str(project)],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_a_livespec_ai_clone_resolves(tmp_path: pathlib.Path) -> None:
    clone = _make_clone(project=tmp_path, owner="livespec-ai")
    result = _resolve(project=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == str(clone)


def test_a_legacy_thewoolleyman_clone_alone_does_not_resolve(tmp_path: pathlib.Path) -> None:
    _make_clone(project=tmp_path, owner="thewoolleyman")
    result = _resolve(project=tmp_path)
    assert result.returncode == 1
    assert result.stdout == ""
    assert "livespec-overseer plugin root could not be resolved." in result.stderr
    assert "pi install git:github.com/livespec-ai/livespec-overseer@release -l" in result.stderr


def test_the_livespec_ai_clone_wins_when_both_exist(tmp_path: pathlib.Path) -> None:
    _make_clone(project=tmp_path, owner="thewoolleyman")
    preferred = _make_clone(project=tmp_path, owner="livespec-ai")
    result = _resolve(project=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == str(preferred)


def test_the_install_hint_names_livespec_ai(tmp_path: pathlib.Path) -> None:
    result = _resolve(project=tmp_path)
    assert result.returncode == 1
    assert "pi install git:github.com/livespec-ai/livespec-overseer@release -l" in result.stderr
