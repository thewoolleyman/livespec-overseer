"""Remote Control re-issue after a pushed account switch (overseer-fdwat6)."""

from __future__ import annotations

import importlib
import json
import subprocess
from collections.abc import Callable
from types import ModuleType

import pytest

__all__: list[str] = []

MARKER = "Remote Control stopped because the signed-in account changed"
STOPPED = f"some output\n{MARKER}\n> "

Tmux = Callable[..., str | None]


def _rc() -> ModuleType:
    return importlib.import_module("remote_control_reissue")


def _fake(*, screens: dict[str, str]) -> tuple[Tmux, list[tuple[str, ...]]]:
    sent: list[tuple[str, ...]] = []

    def tmux(*args: str) -> str | None:
        if args[0] == "list-panes":
            return "\n".join(screens)
        if args[0] == "capture-pane":
            return screens[args[-1]]
        sent.append(args)
        return ""

    return tmux, sent


def test_reissues_only_panes_that_lost_remote_control() -> None:
    tmux, sent = _fake(
        screens={"%1": STOPPED, "%2": "normal session\n> ", "%3": STOPPED + "/remote-control\n"}
    )
    assert _rc().reissue(tmux=tmux) == ["%1"]
    assert sent == [
        ("send-keys", "-t", "%1", "-l", "/remote-control"),
        ("send-keys", "-t", "%1", "Enter"),
    ]


def test_no_tmux_server_touches_nothing() -> None:
    assert _rc().reissue(tmux=lambda *_: None) == []


def test_failed_send_is_not_reported() -> None:
    def tmux(*args: str) -> str | None:
        return {"list-panes": "%1", "capture-pane": STOPPED}.get(args[0])

    assert _rc().reissue(tmux=tmux) == []


def test_main_prints_reissued_panes(*, capsys: pytest.CaptureFixture[str]) -> None:
    tmux, _ = _fake(screens={"%7": STOPPED})
    assert _rc().main(tmux=tmux) == 0
    assert json.loads(capsys.readouterr().out) == {"reissued": ["%7"]}


def test_run_tmux_maps_failures_to_none(*, monkeypatch: pytest.MonkeyPatch) -> None:
    rc = _rc()
    results: list[object] = [
        subprocess.CompletedProcess(args=[], returncode=0, stdout="ok"),
        subprocess.CompletedProcess(args=[], returncode=1, stdout=""),
        OSError("no tmux"),
    ]

    def run(*_a: object, **_k: object) -> object:
        result = results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(rc.subprocess, "run", run)
    assert [rc._run_tmux("-V") for _ in range(3)] == ["ok", None, None]
