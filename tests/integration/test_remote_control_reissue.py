"""Remote Control re-issue after a pushed account switch (overseer-fdwat6).

Each scenario runs the script the way the push loop does, `python3 - < file`,
against a stub `tmux` on PATH, and again in-process for coverage.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

__all__: list[str] = []

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "overseer" / "remote_control_reissue.py"
NOTICE = json.loads((ROOT / "tests/fixtures/remote_control_notice.json").read_text())["notice"]

STUB = """#!/usr/bin/env python3
import json, os, sys
state = json.load(open(os.environ["STUB_TMUX_STATE"]))
args = sys.argv[1:]
if state.get("no_server"):
    sys.exit(1)
if args[0] == "list-panes":
    print("\\n".join(f"{p['id']} {p['cmd']} {p['mode']}" for p in state["panes"]))
elif args[0] == "capture-pane":
    assert "-J" in args
    pane = next(p for p in state["panes"] if p["id"] == args[-1])
    if pane["screen"] is None:
        sys.exit(1)
    print(pane["screen"])
else:
    with open(os.environ["STUB_TMUX_LOG"], "a") as log:
        log.write(json.dumps(args) + "\\n")
"""


def _scrubbed_environ() -> dict[str, str]:
    """The parent env minus coverage hooks, so the child is not instrumented."""
    return {
        key: value
        for key, value in os.environ.items()
        if key != "COVERAGE_PROCESS_START" and not key.startswith("COV_CORE_")
    }


def _rc() -> ModuleType:
    return importlib.import_module("remote_control_reissue")


def _pane(*, pane: str, screen: str | None, cmd: str = "claude", mode: str = "0") -> dict:
    return {"id": pane, "cmd": cmd, "mode": mode, "screen": screen}


def _run(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, state: dict
) -> tuple[list[str], list[list[str]]]:
    stub = tmp_path / "bin" / "tmux"
    stub.parent.mkdir(exist_ok=True)
    _ = stub.write_text(STUB, encoding="utf-8")
    stub.chmod(0o755)
    _ = (tmp_path / "state.json").write_text(json.dumps(state), encoding="utf-8")
    log = tmp_path / "sent.log"
    env = {
        "PATH": f"{stub.parent}{os.pathsep}{os.environ['PATH']}",
        "STUB_TMUX_STATE": str(tmp_path / "state.json"),
        "STUB_TMUX_LOG": str(log),
    }
    if mode == "subprocess":
        done = subprocess.run(  # noqa: S603 -- the push loop's own invocation
            [sys.executable, "-"],
            stdin=SCRIPT.open(encoding="utf-8"),
            capture_output=True,
            text=True,
            env={**_scrubbed_environ(), **env},
            check=True,
        )
        out = done.stdout
    else:
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        rc = _rc()
        assert rc.main() == 0
        out = ""
    sent = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    reissued = json.loads(out)["reissued"] if out else sorted({a[2] for a in sent})
    return reissued, sent


SCENARIOS = {
    "stopped claude pane": ([_pane(pane="%1", screen=f"output\n  ⎿ {NOTICE}\n> ")], ["%1"]),
    "notice in a shell pane": ([_pane(pane="%2", screen=NOTICE, cmd="zsh")], []),
    "notice in less": ([_pane(pane="%3", screen=NOTICE, cmd="less")], []),
    "older notice already re-issued": (
        [_pane(pane="%4", screen=f"{NOTICE}\n> /remote-control\nRemote Control connected")],
        [],
    ),
    "notice inside a wrapped longer line": (
        [_pane(pane="%5", screen=f"user pasted: {NOTICE} and more text")],
        [],
    ),
    "copy mode": ([_pane(pane="%6", screen=NOTICE, mode="1")], []),
    "unsubmitted /remote-control in the input box": (
        [_pane(pane="%7", screen=f"{NOTICE}\n│ > /remote-control          │")],
        ["%7"],
    ),
    "capture fails": ([_pane(pane="%8", screen=None)], []),
}


def test_module_notice_is_the_binary_string() -> None:
    assert _rc().NOTICE == NOTICE


@pytest.mark.parametrize("mode", ["subprocess", "inprocess"])
@pytest.mark.parametrize("name", list(SCENARIOS))
def test_reissue_scenarios(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, name: str
) -> None:
    panes, expected = SCENARIOS[name]
    reissued, sent = _run(
        tmp_path=tmp_path, monkeypatch=monkeypatch, mode=mode, state={"panes": panes}
    )
    assert reissued == expected
    assert sent == [
        step
        for pane in expected
        for step in (
            ["send-keys", "-t", pane, "-l", "/remote-control"],
            ["send-keys", "-t", pane, "Enter"],
        )
    ]


@pytest.mark.parametrize("mode", ["subprocess", "inprocess"])
def test_no_tmux_server_touches_nothing(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    state = {"no_server": True, "panes": []}
    assert _run(tmp_path=tmp_path, monkeypatch=monkeypatch, mode=mode, state=state) == ([], [])


def test_failed_send_is_not_reported() -> None:
    def tmux(*args: str) -> str | None:
        return {"list-panes": "%1 claude 0", "capture-pane": NOTICE}.get(args[0])

    assert _rc().reissue(tmux=tmux) == []


def test_run_tmux_maps_hang_or_missing_binary_to_none(*, monkeypatch: pytest.MonkeyPatch) -> None:
    rc = _rc()

    def run(*_a: object, **_k: object) -> object:
        raise OSError("no tmux")

    monkeypatch.setattr(rc.subprocess, "run", run)
    assert rc._run_tmux("-V") is None
