"""Remote Control re-issue after a pushed account switch (overseer-fdwat6).

Each scenario runs the script the way the push loop does, `python3 - < file`,
against a stub `tmux` on PATH, and again in-process for coverage. Screens are
built from REAL `tmux capture-pane -p -J` captures of Claude Code 2.1.322's
input box (tests/fixtures/claude_2.1.322_input_*.txt) with the account-changed
notice placed in the forms the 2.1.322 binary renders it in.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from types import ModuleType

import pytest

__all__: list[str] = []

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "overseer" / "remote_control_reissue.py"
FIXTURES = ROOT / "tests" / "fixtures"
FIXTURE = json.loads((FIXTURES / "remote_control_notice.json").read_text(encoding="utf-8"))
NOTICE = FIXTURE["notice"]
FULL = NOTICE + FIXTURE["notice_rest"]
EMPTY = (FIXTURES / FIXTURE["input_captures"]["empty"]).read_text(encoding="utf-8")
DRAFT = (FIXTURES / FIXTURE["input_captures"]["draft"]).read_text(encoding="utf-8")
TRANSCRIPT = f"  ⎿  {FIXTURE['transcript_prefix']}{FULL}"
FOOTER = f"  {FIXTURE['footer_prefix']}{FULL}"
NARROW = textwrap.wrap(
    f"{FIXTURE['transcript_prefix']}{FULL}",
    width=48,
    initial_indent="  ⎿  ",
    subsequent_indent="     ",
)

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
    sys.stdout.write(pane["screen"])
else:
    with open(os.environ["STUB_TMUX_LOG"], "a") as log:
        log.write(json.dumps(args) + "\\n")
"""


def _above_input(*, capture: str, lines: list[str]) -> str:
    """`capture` with `lines` added to the transcript, just above the input box's top rule."""
    rows = capture.splitlines()
    top = next(index for index, row in enumerate(rows) if row.startswith("─"))
    return "\n".join([*rows[:top], *lines, *rows[top:]]) + "\n"


def _below_input(*, capture: str, lines: list[str]) -> str:
    """`capture` with `lines` added to the footer, below the input box."""
    return capture.rstrip("\n") + "\n" + "\n".join(lines) + "\n"


def _after_prompt(*, capture: str, line: str) -> str:
    """`capture` with a second input-box line under the prompt line."""
    rows = capture.splitlines()
    prompt = next(index for index, row in enumerate(rows) if row.startswith("❯"))
    return "\n".join([*rows[: prompt + 1], line, *rows[prompt + 1 :]]) + "\n"


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
    "transcript notice inside a longer line, empty input": (
        [_pane(pane="%1", screen=_above_input(capture=EMPTY, lines=[TRANSCRIPT]))],
        ["%1"],
    ),
    "footer notice, empty input": (
        [_pane(pane="%2", screen=_below_input(capture=EMPTY, lines=[FOOTER]))],
        ["%2"],
    ),
    "notice with an unsubmitted draft in the input box": (
        [_pane(pane="%3", screen=_above_input(capture=DRAFT, lines=[TRANSCRIPT]))],
        [],
    ),
    "notice with a draft on the input box's second line": (
        [
            _pane(
                pane="%4",
                screen=_after_prompt(
                    capture=_above_input(capture=EMPTY, lines=[TRANSCRIPT]),
                    line="  second line of a draft",
                ),
            )
        ],
        [],
    ),
    "notice in a shell pane": (
        [_pane(pane="%5", screen=_above_input(capture=EMPTY, lines=[TRANSCRIPT]), cmd="zsh")],
        [],
    ),
    "notice in less": (
        [_pane(pane="%6", screen=_above_input(capture=EMPTY, lines=[TRANSCRIPT]), cmd="less")],
        [],
    ),
    "copy mode": (
        [_pane(pane="%7", screen=_above_input(capture=EMPTY, lines=[TRANSCRIPT]), mode="1")],
        [],
    ),
    "notice already re-issued": (
        [
            _pane(
                pane="%8",
                screen=_above_input(
                    capture=EMPTY,
                    lines=[TRANSCRIPT, "❯ /remote-control", "  ⎿  Remote Control connected"],
                ),
            )
        ],
        [],
    ),
    "notice text quoted without either rendered form": (
        [_pane(pane="%9", screen=_above_input(capture=EMPTY, lines=[f"user pasted: {NOTICE}"]))],
        [],
    ),
    "transcript notice hard-wrapped by a narrow pane": (
        [_pane(pane="%13", screen=_above_input(capture=EMPTY, lines=NARROW))],
        ["%13"],
    ),
    "full form quoted mid-line in a session's prose": (
        [
            _pane(
                pane="%14",
                screen=_above_input(
                    capture=EMPTY,
                    lines=[f"⏺ After a switch the pane shows {FIXTURE['transcript_prefix']}{FULL}"],
                ),
            )
        ],
        [],
    ),
    "a different Remote Control disconnect reason": (
        [
            _pane(
                pane="%15",
                screen=_above_input(
                    capture=EMPTY,
                    lines=[f"  ⎿  {FIXTURE['transcript_prefix']}the bridge timed out"],
                ),
            )
        ],
        [],
    ),
    "no input box on screen": ([_pane(pane="%10", screen=f"{TRANSCRIPT}\nsome dialog\n")], []),
    "input box with no closing rule": (
        [_pane(pane="%11", screen=f"{TRANSCRIPT}\n─────\n❯\u00a0\n   \n")],
        [],
    ),
    "capture fails": ([_pane(pane="%12", screen=None)], []),
}


def test_the_module_pins_the_version_notice_and_forms() -> None:
    rc = _rc()
    pinned = (rc.CLAUDE_CODE_VERSION, rc.NOTICE, rc.FORMS)
    expected = (
        FIXTURE["claude_code_version"],
        NOTICE,
        (FIXTURE["transcript_prefix"], FIXTURE["footer_prefix"]),
    )
    assert pinned == expected


def test_the_real_input_captures_show_an_empty_and_a_drafted_prompt() -> None:
    prompts = [
        [row for row in capture.splitlines() if row.startswith("❯")] for capture in (EMPTY, DRAFT)
    ]
    assert prompts == [["❯\u00a0"], ["❯\u00a0half written draft about deploys"]]


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
    screen = _above_input(capture=EMPTY, lines=[TRANSCRIPT])

    def tmux(*args: str) -> str | None:
        return {"list-panes": "%1 claude 0", "capture-pane": screen}.get(args[0])

    assert _rc().reissue(tmux=tmux) == []


def test_run_tmux_maps_hang_or_missing_binary_to_none(*, monkeypatch: pytest.MonkeyPatch) -> None:
    rc = _rc()

    def run(*_a: object, **_k: object) -> object:
        raise OSError("no tmux")

    monkeypatch.setattr(rc.subprocess, "run", run)
    assert rc._run_tmux("-V") is None
