"""Remote Control re-issue after a pushed account switch (overseer-fdwat6).

Each scenario runs the script the way the push loop does, `python3 - < file`,
against a stub `tmux`, `ps` and `herdr` on PATH, and again in-process for coverage.
Screens are built from REAL captures of Claude Code's input box: `tmux
capture-pane -p -J` (tests/fixtures/claude_2.1.322_input_*.txt) and herdr's
`pane read --source recent-unwrapped` (claude_2.1.323_herdr_input_empty.txt),
with the account-changed notice placed in the two forms a real account switch
showed under Claude Code 2.1.323 (spec v103, contracts.md "Remote Control
re-issue"): the transcript line behind `●`, and the footer status `/rc failed`.
A pane is Claude Code by the executable its foreground process runs, because the
multiplexer reports 2.1.323's current command as its version number.

No test may reach a real multiplexer: the fleet's own host runs herdr, so an
autouse fixture puts refusing `herdr` and `tmux` stubs first on PATH for every
test, and every scenario's own stubs go in front of those.
"""

from __future__ import annotations

import contextlib
import importlib
import inspect
import io
import json
import os
import subprocess
import sys
import textwrap
import threading
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

__all__: list[str] = []

REFUSE = "#!/bin/sh\nexit 1\n"

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "overseer" / "remote_control_reissue.py"
FIXTURES = ROOT / "tests" / "fixtures"
FIXTURE = json.loads((FIXTURES / "remote_control_notice.json").read_text(encoding="utf-8"))
NOTICE = FIXTURE["notice"]
FULL = NOTICE + FIXTURE["notice_rest"]
EMPTY = (FIXTURES / FIXTURE["input_captures"]["empty"]).read_text(encoding="utf-8")
DRAFT = (FIXTURES / FIXTURE["input_captures"]["draft"]).read_text(encoding="utf-8")
HERDR_EMPTY = (FIXTURES / FIXTURE["herdr_input_capture"]["empty"]).read_text(encoding="utf-8")
HERDR_DRAFT = HERDR_EMPTY.replace("❯\u00a0\n", "❯\u00a0half written draft about deploys\n")
MARK = FIXTURE["transcript_mark"]
TRANSCRIPT = f"{MARK} {FIXTURE['transcript_prefix']}{FULL}"
LEGACY_TRANSCRIPT = f"  ⎿  {FIXTURE['transcript_prefix']}{FULL}"
FOOTER = f"  {FIXTURE['footer_status']}"
NARROW = textwrap.wrap(
    f"{FIXTURE['transcript_prefix']}{FULL}",
    width=48,
    initial_indent=f"{MARK} ",
    subsequent_indent="  ",
)
VERSIONS = Path.home() / ".local/share/claude/versions"
CLAUDE_EXE = f"{VERSIONS / FIXTURE['claude_code_version']} --dangerously-skip-permissions"
# What ps shows on a pane's tty, as (stat, args): `+` marks the foreground group.
PROCS = {
    "claude": [["Ss", "-zsh"], ["Sl+", CLAUDE_EXE]],
    "claude-on-path": [["Ss", "-zsh"], ["Sl+", "claude --resume"]],
    "zsh": [["Ss+", "-zsh"]],
    "less": [["Ss", "-zsh"], ["S+", "less notes.txt"]],
    "claude-stopped": [["Ss+", "-zsh"], ["T", CLAUDE_EXE]],
    "lookalike": [["Ss", "-zsh"], ["S+", "/opt/tools/claude-wrapper/run"]],
}

STUB = """#!/usr/bin/env python3
import json, os, sys
state = json.load(open(os.environ["STUB_TMUX_STATE"]))
args = sys.argv[1:]
if state.get("no_server"):
    sys.exit(1)
if args[0] == "list-panes":
    assert "#{pane_current_command}" not in args[-1]
    print("\\n".join(f"{p['id']} {p['tty']} {p['mode']}" for p in state["panes"]))
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


HERDR_STUB = """#!/usr/bin/env python3
import json, os, sys
state = json.load(open(os.environ["STUB_TMUX_STATE"])).get("herdr", {})
args = sys.argv[1:]
if state.get("fails"):
    sys.exit(1)
if args == ["session", "list", "--json"]:
    print(json.dumps({"sessions": state.get("sessions", [])}))
    sys.exit(0)
assert args[0] == "--session" and args[2] == "pane", args
session, op, rest = args[1], args[3], args[4:]
panes = state.get("panes", {}).get(session)
if panes is None:
    sys.exit(1)
if op == "list":
    print(json.dumps({"id": "cli:pane:list", "result": {"panes": [p["row"] for p in panes]}}))
    sys.exit(0)
pane_id = rest[1] if op == "process-info" else rest[0]
pane = next(p for p in panes if p["row"].get("pane_id") == pane_id)
if op == "process-info":
    assert rest[0] == "--pane", rest
    if pane["argvs"] is None:
        sys.exit(1)
    procs = [{"argv": argv, "name": "2.1.323"} for argv in pane["argvs"]]
    print(json.dumps({"result": {"process_info": {"foreground_processes": procs}}}))
elif op == "read":
    lines = str(pane["row"]["scroll"]["viewport_rows"])
    assert rest[1:] == ["--source", "recent-unwrapped", "--lines", lines], rest
    if pane["screen"] is None:
        sys.exit(1)
    sys.stdout.write(pane["screen"])
else:
    with open(os.environ["STUB_HERDR_LOG"], "a") as log:
        log.write(json.dumps(args) + "\\n")
"""

PS_STUB = """#!/usr/bin/env python3
import json, os, sys
state = json.load(open(os.environ["STUB_TMUX_STATE"]))
tty = sys.argv[sys.argv.index("-t") + 1]
pane = next((p for p in state["panes"] if p["tty"].removeprefix("/dev/") == tty), None)
if pane is None or pane["procs"] is None:
    sys.exit(1)
print("\\n".join(f"{stat} {args}" for stat, args in pane["procs"]))
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
    """A pane whose foreground process is `cmd` (a PROCS key, or "ps-fails")."""
    procs = None if cmd == "ps-fails" else PROCS[cmd]
    return {
        "id": pane,
        "tty": f"/dev/pts/{pane[1:]}",
        "mode": mode,
        "screen": screen,
        "procs": procs,
    }


@pytest.fixture(autouse=True)
def _no_real_multiplexer(
    *, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refusing `herdr` and `tmux` first on PATH, so no test can reach a live pane."""
    refusing = tmp_path_factory.mktemp("refusing-bin")
    for name in ("herdr", "tmux"):
        stub = refusing / name
        _ = stub.write_text(REFUSE, encoding="utf-8")
        stub.chmod(0o755)
    monkeypatch.setenv("PATH", f"{refusing}{os.pathsep}{os.environ['PATH']}")


def _read_log(*, path: Path) -> list[list[str]]:
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def _run_all(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, state: dict
) -> tuple[list[str], list[list[str]], list[list[str]]]:
    """The reported panes, the tmux sends and the herdr sends of one run."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    for name, body in (("tmux", STUB), ("ps", PS_STUB), ("herdr", HERDR_STUB)):
        stub = bin_dir / name
        _ = stub.write_text(body, encoding="utf-8")
        stub.chmod(0o755)
    _ = (tmp_path / "state.json").write_text(json.dumps(state), encoding="utf-8")
    log = tmp_path / "sent.log"
    herdr_log = tmp_path / "herdr-sent.log"
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "STUB_TMUX_STATE": str(tmp_path / "state.json"),
        "STUB_TMUX_LOG": str(log),
        "STUB_HERDR_LOG": str(herdr_log),
    }
    if mode == "subprocess":
        done = subprocess.run(  # noqa: S603 -- the push loop's own invocation
            [sys.executable, "-", "0"],
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
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            assert _rc().main(argv=["0"]) == 0
        out = printed.getvalue()
    return json.loads(out)["reissued"], _read_log(path=log), _read_log(path=herdr_log)


def _run(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, state: dict
) -> tuple[list[str], list[list[str]]]:
    reissued, sent, herdr_sent = _run_all(
        tmp_path=tmp_path, monkeypatch=monkeypatch, mode=mode, state=state
    )
    assert herdr_sent == []
    return reissued, sent


SCENARIOS = {
    "transcript notice inside a longer line, empty input": (
        [_pane(pane="%1", screen=_above_input(capture=EMPTY, lines=[TRANSCRIPT]))],
        ["%1"],
    ),
    "the 2.1.322 transcript mark is still recognized": (
        [_pane(pane="%24", screen=_above_input(capture=EMPTY, lines=[LEGACY_TRANSCRIPT]))],
        ["%24"],
    ),
    "footer status /rc failed, empty input": (
        [_pane(pane="%2", screen=_below_input(capture=EMPTY, lines=[FOOTER]))],
        ["%2"],
    ),
    "footer status among other footer items": (
        [
            _pane(
                pane="%25",
                screen=_below_input(
                    capture=EMPTY,
                    lines=["  ⏵⏵ bypass permissions on (shift+tab to cycle) · /rc failed"],
                ),
            )
        ],
        ["%25"],
    ),
    "a footer word that only starts like the status": (
        [_pane(pane="%26", screen=_below_input(capture=EMPTY, lines=["  /rc failedover"]))],
        [],
    ),
    "claude started from PATH as `claude`": (
        [
            _pane(
                pane="%27",
                screen=_above_input(capture=EMPTY, lines=[TRANSCRIPT]),
                cmd="claude-on-path",
            )
        ],
        ["%27"],
    ),
    "claude stopped in the background behind its shell": (
        [
            _pane(
                pane="%28",
                screen=_above_input(capture=EMPTY, lines=[TRANSCRIPT]),
                cmd="claude-stopped",
            )
        ],
        [],
    ),
    "an executable whose path merely mentions claude": (
        [
            _pane(
                pane="%29", screen=_above_input(capture=EMPTY, lines=[TRANSCRIPT]), cmd="lookalike"
            )
        ],
        [],
    ),
    "ps cannot read the pane's tty": (
        [_pane(pane="%30", screen=_above_input(capture=EMPTY, lines=[TRANSCRIPT]), cmd="ps-fails")],
        [],
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
                    lines=[f"● After a switch the pane shows {FIXTURE['transcript_prefix']}{FULL}"],
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
    "prose wrap where the quoted form starts a continuation line": (
        [
            _pane(
                pane="%16",
                screen=_above_input(
                    capture=EMPTY,
                    lines=[
                        "● After a switch the pane shows",
                        f"  {FIXTURE['transcript_prefix']}{FULL}",
                    ],
                ),
            )
        ],
        [],
    ),
    "the form in a blockquote": (
        [
            _pane(
                pane="%17",
                screen=_above_input(
                    capture=EMPTY, lines=[f"> {FIXTURE['transcript_prefix']}{FULL}"]
                ),
            )
        ],
        [],
    ),
    "the form in a bullet": (
        [
            _pane(
                pane="%18",
                screen=_above_input(
                    capture=EMPTY, lines=[f"  - {FIXTURE['transcript_prefix']}{FULL}"]
                ),
            )
        ],
        [],
    ),
    "the form inside quotation marks": (
        [
            _pane(
                pane="%19",
                screen=_above_input(
                    capture=EMPTY,
                    lines=[f'"{TRANSCRIPT.strip()[3:]}" is what you will see'],
                ),
            )
        ],
        [],
    ),
    "a submitted prompt pasting the form": (
        [
            _pane(
                pane="%20",
                screen=_above_input(
                    capture=EMPTY, lines=[f"❯ {FIXTURE['transcript_prefix']}{FULL}"]
                ),
            )
        ],
        [],
    ),
    "unrelated following lines that would finish the notice": (
        [
            _pane(
                pane="%21",
                screen=_above_input(
                    capture=EMPTY,
                    lines=[
                        f"  ⎿  {FIXTURE['transcript_prefix']}signed-in",
                        "● claude.ai account or organization changed on this machine"
                        " — run /remote-control",
                    ],
                ),
            )
        ],
        [],
    ),
    "the footer status quoted in the transcript": (
        [_pane(pane="%22", screen=_above_input(capture=EMPTY, lines=[FOOTER]))],
        [],
    ),
    "input box with no top rule": (
        [_pane(pane="%23", screen=f"{TRANSCRIPT}\n❯\u00a0\n─────\n")],
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
        (FIXTURE["transcript_prefix"], FIXTURE["footer_status"]),
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


def _no_herdr(*_args: str) -> str | None:
    return None


def _fake_ps(*, tty: str) -> str | None:
    assert tty.startswith("/dev/pts/")
    return "\n".join(f"{stat} {args}" for stat, args in PROCS["claude"])


def _fake_tmux(*, screen: str, sent: list[tuple[str, ...]]) -> Callable[..., str | None]:
    def tmux(*args: str) -> str | None:
        if args[0] == "list-panes":
            return "%1 /dev/pts/1 0"
        if args[0] == "capture-pane":
            return screen
        sent.append(args)
        return ""

    return tmux


def test_every_pane_width_from_20_to_199_reissues_exactly_once() -> None:
    rc = _rc()
    missed: list[int] = []
    for width in range(20, 200):
        lines = textwrap.wrap(
            f"{FIXTURE['transcript_prefix']}{FULL}",
            width=width,
            initial_indent=f"{MARK} ",
            subsequent_indent="  ",
            # Ink's wrap-ansi breaks only at spaces, never after a hyphen.
            break_on_hyphens=False,
        )
        sent: list[tuple[str, ...]] = []
        screen = _above_input(capture=EMPTY, lines=lines)
        tmux = _fake_tmux(screen=screen, sent=sent)
        if rc.reissue(tmux=tmux, ps=_fake_ps, herdr=_no_herdr) != ["%1"] or len(sent) != 2:
            missed.append(width)
    assert missed == []


def test_failed_send_is_not_reported() -> None:
    screen = _above_input(capture=EMPTY, lines=[TRANSCRIPT])

    def tmux(*args: str) -> str | None:
        return {"list-panes": "%1 /dev/pts/1 0", "capture-pane": screen}.get(args[0])

    assert _rc().reissue(tmux=tmux, ps=_fake_ps, herdr=_no_herdr) == []


def test_run_tmux_maps_hang_or_missing_binary_to_none(*, monkeypatch: pytest.MonkeyPatch) -> None:
    rc = _rc()

    def run(*_a: object, **_k: object) -> object:
        raise OSError("no tmux")

    monkeypatch.setattr(rc.subprocess, "run", run)
    assert rc._run_tmux("-V") is None
    assert rc._run_ps(tty="/dev/pts/1") is None
    assert rc._run_herdr("--version") is None


def test_run_ps_reads_the_tty_without_its_dev_prefix(*, monkeypatch: pytest.MonkeyPatch) -> None:
    rc = _rc()
    seen: list[list[str]] = []

    def run(argv: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="S+ claude\n", stderr="")

    monkeypatch.setattr(rc.subprocess, "run", run)
    assert rc._run_ps(tty="/dev/pts/7") == "S+ claude\n"
    assert seen == [["ps", "-o", "stat=,args=", "-t", "pts/7"]]


# What `herdr pane process-info` lists as a pane's foreground processes, by argv.
ARGVS = {
    "claude": [["claude", "--dangerously-skip-permissions"], ["node", "/opt/mcp/server"]],
    "claude-versions": [[str(VERSIONS / FIXTURE["claude_code_version"]), "--resume"]],
    "zsh": [["-zsh"]],
    "less": [["less", "notes.txt"]],
    "lookalike": [["/opt/tools/claude-wrapper/run"]],
}


def _herdr_pane(
    *, pane: str, screen: str | None, cmd: str = "claude", offset: object = 0, rows: int = 40
) -> dict:
    """A herdr pane whose foreground processes are `cmd` (an ARGVS key, or "info-fails")."""
    return {
        "row": {"pane_id": pane, "scroll": {"offset_from_bottom": offset, "viewport_rows": rows}},
        "argvs": None if cmd == "info-fails" else ARGVS[cmd],
        "screen": screen,
    }


def _herdr(panes: dict[str, list[dict] | None], *, stopped: tuple[str, ...] = ()) -> dict:
    """herdr state: each named session running with its panes (None: its listing fails)."""
    sessions = [{"name": name, "running": True} for name in panes]
    sessions += [{"name": name, "running": False} for name in stopped]
    return {"sessions": sessions, "panes": {k: v for k, v in panes.items() if v is not None}}


H_NOTICE = _above_input(capture=HERDR_EMPTY, lines=[TRANSCRIPT])

HERDR_SCENARIOS = {
    "transcript notice, empty input": (
        _herdr({"default": [_herdr_pane(pane="w1:p1", screen=H_NOTICE)]}),
        ["herdr:default:w1:p1"],
    ),
    "footer status /rc failed, empty input": (
        _herdr(
            {
                "default": [
                    _herdr_pane(
                        pane="w1:p2", screen=_below_input(capture=HERDR_EMPTY, lines=[FOOTER])
                    )
                ]
            }
        ),
        ["herdr:default:w1:p2"],
    ),
    "claude run from its versions directory": (
        _herdr({"default": [_herdr_pane(pane="w1:p3", screen=H_NOTICE, cmd="claude-versions")]}),
        ["herdr:default:w1:p3"],
    ),
    "notice with an unsubmitted draft": (
        _herdr(
            {
                "default": [
                    _herdr_pane(
                        pane="w1:p4", screen=_above_input(capture=HERDR_DRAFT, lines=[TRANSCRIPT])
                    )
                ]
            }
        ),
        [],
    ),
    "notice already re-issued": (
        _herdr(
            {
                "default": [
                    _herdr_pane(
                        pane="w1:p5",
                        screen=_above_input(
                            capture=HERDR_EMPTY,
                            lines=[
                                TRANSCRIPT,
                                "❯ /remote-control",
                                "  ⎿  Remote Control connected",
                            ],
                        ),
                    )
                ]
            }
        ),
        [],
    ),
    "notice in a shell pane": (
        _herdr({"default": [_herdr_pane(pane="w1:p6", screen=H_NOTICE, cmd="zsh")]}),
        [],
    ),
    "notice in less": (
        _herdr({"default": [_herdr_pane(pane="w1:p7", screen=H_NOTICE, cmd="less")]}),
        [],
    ),
    "an executable whose path merely mentions claude": (
        _herdr({"default": [_herdr_pane(pane="w1:p8", screen=H_NOTICE, cmd="lookalike")]}),
        [],
    ),
    "pane scrolled back from its bottom": (
        _herdr({"default": [_herdr_pane(pane="w1:p9", screen=H_NOTICE, offset=3)]}),
        [],
    ),
    "process info unreadable": (
        _herdr({"default": [_herdr_pane(pane="w1:pA", screen=H_NOTICE, cmd="info-fails")]}),
        [],
    ),
    "capture fails": (_herdr({"default": [_herdr_pane(pane="w1:pB", screen=None)]}), []),
    "every running session is reached, a stopped one is not": (
        _herdr(
            {
                "default": [_herdr_pane(pane="w1:p1", screen=HERDR_EMPTY)],
                "work": [_herdr_pane(pane="w1:p1", screen=H_NOTICE)],
            },
            stopped=("old",),
        ),
        ["herdr:work:w1:p1"],
    ),
    "a session whose pane listing fails is skipped": (
        _herdr({"broken": None, "default": [_herdr_pane(pane="w2:p1", screen=H_NOTICE)]}),
        ["herdr:default:w2:p1"],
    ),
    "no herdr server": ({"fails": True}, []),
}


@pytest.mark.parametrize("mode", ["subprocess", "inprocess"])
@pytest.mark.parametrize("name", list(HERDR_SCENARIOS))
def test_herdr_reissue_scenarios(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, name: str
) -> None:
    herdr, expected = HERDR_SCENARIOS[name]
    reissued, sent, herdr_sent = _run_all(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        mode=mode,
        state={"no_server": True, "panes": [], "herdr": herdr},
    )
    assert (reissued, sent) == (expected, [])
    assert herdr_sent == [
        ["--session", session, "pane", *step]
        for target in expected
        for session, pane in [target.removeprefix("herdr:").split(":", 1)]
        for step in (["send-text", pane, "/remote-control"], ["send-keys", pane, "Enter"])
    ]


@pytest.mark.parametrize("mode", ["subprocess", "inprocess"])
def test_herdr_and_tmux_panes_are_both_reissued(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    state = {
        "panes": [_pane(pane="%1", screen=_above_input(capture=EMPTY, lines=[TRANSCRIPT]))],
        "herdr": _herdr({"default": [_herdr_pane(pane="w1:p1", screen=H_NOTICE)]}),
    }
    reissued, sent, herdr_sent = _run_all(
        tmp_path=tmp_path, monkeypatch=monkeypatch, mode=mode, state=state
    )
    assert reissued == ["%1", "herdr:default:w1:p1"]
    assert len(sent) == len(herdr_sent) == 2


def test_the_real_herdr_capture_shows_an_empty_prompt_between_rules() -> None:
    rows = HERDR_EMPTY.splitlines()
    prompt = rows.index("❯\u00a0")
    assert rows[prompt - 1].startswith("─") and rows[prompt + 1].startswith("─")
    assert [row for row in HERDR_DRAFT.splitlines() if row.startswith("❯")] == [
        "❯\u00a0half written draft about deploys"
    ]


def _replies(**by_op: str | None) -> Callable[..., str | None]:
    """A herdr runner answering each operation (`session`, `list`, `process-info`, ...)."""

    def herdr(*args: str) -> str | None:
        return by_op.get(args[0] if args[0] == "session" else args[3])

    return herdr


SESSIONS = json.dumps({"sessions": [{"name": "default", "running": True}]})


@pytest.mark.parametrize(
    "listing",
    [
        None,
        "not json",
        "[]",
        json.dumps({"sessions": "default"}),
        json.dumps({"sessions": ["default", {"name": 7, "running": True}]}),
        json.dumps({"sessions": [{"name": "default", "running": "yes"}]}),
    ],
)
def test_an_unreadable_session_listing_reaches_no_session(*, listing: str | None) -> None:
    assert _rc()._herdr_sessions(herdr=_replies(session=listing)) == []


@pytest.mark.parametrize(
    "row",
    [
        "w1:p1",
        {"scroll": {"offset_from_bottom": 0, "viewport_rows": 40}},
        {"pane_id": "", "scroll": {"offset_from_bottom": 0, "viewport_rows": 40}},
        {"pane_id": "w1:p1"},
        {"pane_id": "w1:p1", "scroll": {"offset_from_bottom": False, "viewport_rows": 40}},
        {"pane_id": "w1:p1", "scroll": {"offset_from_bottom": 0, "viewport_rows": 0}},
        {"pane_id": "w1:p1", "scroll": {"offset_from_bottom": 0, "viewport_rows": True}},
    ],
)
def test_a_pane_row_without_a_bottom_viewport_is_not_reached(*, row: object) -> None:
    listing = json.dumps({"result": {"panes": [row]}})
    assert _rc()._herdr_viewports(herdr=_replies(list=listing), session="default") == []


@pytest.mark.parametrize(
    "info",
    [
        None,
        "not json",
        json.dumps({"result": {}}),
        json.dumps({"result": {"process_info": {"foreground_processes": [{"argv": []}]}}}),
        json.dumps({"result": {"process_info": {"foreground_processes": [{"argv": [7]}]}}}),
        json.dumps({"result": {"process_info": {"foreground_processes": ["claude"]}}}),
    ],
)
def test_unreadable_process_info_is_not_claude(*, info: str | None) -> None:
    rc = _rc()
    herdr = _replies(**{"process-info": info})
    assert rc._herdr_foreground_is_claude(herdr=herdr, session="default", pane="w1:p1") is False


@pytest.mark.parametrize("failing", ["send-text", "send-keys"])
def test_a_failed_herdr_send_is_not_reported(*, failing: str) -> None:
    info = json.dumps(
        {"result": {"process_info": {"foreground_processes": [{"argv": ["claude"]}]}}}
    )
    replies: dict[str, str | None] = {
        "session": SESSIONS,
        "list": json.dumps({"result": {"panes": [_herdr_pane(pane="w1:p1", screen=None)["row"]]}}),
        "process-info": info,
        "read": H_NOTICE,
        "send-text": "",
        "send-keys": "",
    }
    replies[failing] = None
    rc = _rc()

    def no_tmux(*_args: str) -> str | None:
        return None

    assert rc.reissue(tmux=no_tmux, ps=_fake_ps, herdr=_replies(**replies)) == []


def test_herdr_resolves_on_path_then_in_the_installer_directory(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rc = _rc()
    assert rc._herdr_binary() is not None
    monkeypatch.setattr(rc.shutil, "which", lambda _name: None)
    monkeypatch.setattr(rc.Path, "home", lambda: tmp_path)
    assert rc._herdr_binary() is None
    assert rc._run_herdr("--version") is None
    installed = tmp_path / ".local" / "bin" / "herdr"
    installed.parent.mkdir(parents=True)
    _ = installed.write_text(REFUSE, encoding="utf-8")
    assert rc._herdr_binary() == str(installed)


def _live(*, home: Path, token: str, account: str) -> None:
    for path, body in (
        (
            home / ".claude/.credentials.json",
            {"claudeAiOauth": {"accessToken": token, "expiresAt": 9_999_999_999_000}},
        ),
        (home / ".claude.json", {"oauthAccount": {"accountUuid": account}, "userID": "u"}),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text(json.dumps(body), encoding="utf-8")


def test_the_role_holder_reissues_once_per_switch_even_when_no_delivery_is_issued(
    *, tmp_path: Path
) -> None:
    """Spec v103: the role holder re-issues after the rotation switches its live login.

    The coordinator's grade of #2990 (2026-11-13) has the service fire on EITHER
    event: the switch of the live account, or a delivery naming a different
    account, once for that switch. A switch whose account confirmation fails
    issues no delivery, and before this rework re-issued nothing until a later
    retry succeeded.
    """
    entry = importlib.import_module("caam_delivery_push_entry")
    ran: list[str] = []

    def local(**kwargs: str) -> str:
        ran.append(kwargs["script"])
        return "ok"

    loop = entry.PushLoop()
    _live(home=tmp_path, token="tok-" + "s1", account="acct-1")
    entry.run_once(
        home=tmp_path, now=1.0, loop=loop, confirm=lambda **_: "acct-1", reissue="RC", local=local
    )
    assert ran == []
    _live(home=tmp_path, token="tok-" + "s2", account="acct-2")
    entry.run_once(
        home=tmp_path, now=2.0, loop=loop, confirm=lambda **_: None, reissue="RC", local=local
    )
    assert ran == ["RC"]
    assert loop.last is not None and loop.last.account_id == "acct-1"
    entry.run_once(
        home=tmp_path, now=500.0, loop=loop, confirm=lambda **_: "acct-2", reissue="RC", local=local
    )
    assert loop.last.account_id == "acct-2"
    assert ran == ["RC"]


def _scan_then_send_tmux(*, screens: list[str | None], sent: list[tuple[str, ...]]) -> Callable:
    """One tmux pane whose capture is `screens[0]` at the scan, then `screens[1]` from then on."""

    def tmux(*args: str) -> str | None:
        if args[0] == "list-panes":
            return "%1 /dev/pts/1 0"
        if args[0] == "capture-pane":
            return screens.pop(0) if len(screens) > 1 else screens[0]
        sent.append(args)
        return ""

    return tmux


CLAUDE_INFO = json.dumps(
    {"result": {"process_info": {"foreground_processes": [{"argv": ["claude"]}]}}}
)


def _scan_then_send_herdr(*, reads: list[str | None], sent: list[tuple[str, ...]]) -> Callable:
    """One herdr Claude pane whose read is `reads[0]` at the scan, then `reads[1]` from then on."""
    row = _herdr_pane(pane="w1:p1", screen=None)["row"]

    def herdr(*args: str) -> str | None:
        if args[0] == "session":
            return SESSIONS
        op = args[3]
        if op == "list":
            return json.dumps({"result": {"panes": [row]}})
        if op == "process-info":
            return CLAUDE_INFO
        if op == "read":
            return reads.pop(0) if len(reads) > 1 else reads[0]
        sent.append(args)
        return ""

    return herdr


@pytest.mark.parametrize("later", ["draft", "unreadable", "notice gone"])
def test_a_tmux_box_that_changes_between_scan_and_send_is_never_typed_into(*, later: str) -> None:
    """Grade A on #2992: the empty-box check is re-taken on that pane right before its send.

    The scan of every pane took 5.9 s on the role holder; a human who starts typing
    in that window must not get `/remote-control` + Enter submitted with the draft.
    """
    after = {
        "draft": _above_input(capture=DRAFT, lines=[TRANSCRIPT]),
        "unreadable": None,
        "notice gone": EMPTY,
    }[later]
    sent: list[tuple[str, ...]] = []
    tmux = _scan_then_send_tmux(
        screens=[_above_input(capture=EMPTY, lines=[TRANSCRIPT]), after], sent=sent
    )
    assert _rc().reissue(tmux=tmux, ps=_fake_ps, herdr=_no_herdr) == []
    assert sent == []


@pytest.mark.parametrize("later", ["draft", "unreadable", "notice gone"])
def test_a_herdr_box_that_changes_between_scan_and_send_is_never_typed_into(*, later: str) -> None:
    after = {
        "draft": _above_input(capture=HERDR_DRAFT, lines=[TRANSCRIPT]),
        "unreadable": None,
        "notice gone": HERDR_EMPTY,
    }[later]
    sent: list[tuple[str, ...]] = []
    herdr = _scan_then_send_herdr(reads=[H_NOTICE, after], sent=sent)

    def no_tmux(*_args: str) -> str | None:
        return None

    assert _rc().reissue(tmux=no_tmux, ps=_fake_ps, herdr=herdr) == []
    assert sent == []


def test_a_notice_drawn_after_the_first_scan_is_reissued_once_within_the_window() -> None:
    """Grade B on #2992: the panes are re-scanned over a bounded window, each sent to once.

    A remote host is scanned as soon as it applies the delivery, and Claude Code
    may not have drawn the notice yet. The tmux pane shows the footer form only
    from t=30 s; the herdr pane shows the notice throughout. The footer form stays
    on screen after the send, so only the run's own record keeps it to one send.
    """
    rc = _rc()
    now = [0.0]
    naps: list[float] = []

    def sleep(seconds: float) -> None:
        naps.append(seconds)
        now[0] += seconds

    footer = _below_input(capture=EMPTY, lines=[FOOTER])
    sent: list[tuple[str, ...]] = []
    herdr_sent: list[tuple[str, ...]] = []

    def tmux(*args: str) -> str | None:
        if args[0] == "list-panes":
            return "%1 /dev/pts/1 0"
        if args[0] == "capture-pane":
            return footer if now[0] >= 30.0 else EMPTY
        sent.append(args)
        return ""

    herdr = _scan_then_send_herdr(reads=[H_NOTICE], sent=herdr_sent)
    reissued = rc.reissue(
        tmux=tmux, ps=_fake_ps, herdr=herdr, window_s=90.0, sleep=sleep, clock=lambda: now[0]
    )
    assert reissued == ["herdr:default:w1:p1", "%1"]
    assert (len(sent), len(herdr_sent)) == (2, 2)
    assert naps and set(naps) == {rc._RESCAN_S}
    assert now[0] <= 90.0 < now[0] + rc._RESCAN_S


@pytest.mark.parametrize(("argv", "window"), [([], 90.0), (["0"], 0.0), (["2.5"], 2.5)])
def test_main_rescans_for_ninety_seconds_unless_given_a_window(
    *, monkeypatch: pytest.MonkeyPatch, argv: list[str], window: float
) -> None:
    rc = _rc()
    seen: list[float] = []

    def reissue(**kwargs: object) -> list[str]:
        seen.append(_as_float(kwargs["window_s"]))
        return []

    monkeypatch.setattr(rc, "reissue", reissue)
    with contextlib.redirect_stdout(io.StringIO()):
        assert rc.main(argv=argv) == 0
    assert seen == [window]


def _as_float(value: object) -> float:
    assert isinstance(value, float)
    return value


# The coordinator's measured scan of every pane on the role holder, 2026-11-13.
MEASURED_SCAN_S = 5.9


def test_the_reissue_timeouts_cover_the_window_and_its_last_scan(*, tmp_path: Path) -> None:
    """Grade E on #2992: a run still scanning is not cut off and misreported as a timeout.

    The last scan starts no later than the window's end, so a run takes the window
    plus one scan; the remote ssh timeout and the role holder's local one both
    leave room for that scan twice over.
    """
    rc = _rc()
    state = importlib.import_module("caam_delivery_push_state")
    entry = importlib.import_module("caam_delivery_push_entry")
    floor = rc._WINDOW_S + 2 * MEASURED_SCAN_S
    remote = state.seconds(settings=state.load_config(home=tmp_path), key="reissue_timeout_s")
    local = inspect.signature(entry.run_local).parameters["timeout"].default
    assert remote >= floor
    assert local >= floor


def test_the_role_holder_reissue_does_not_hold_the_push_loop(
    *, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The role holder's re-issue now runs for its whole window, so the loop starts it and moves on.

    It fires before the switch's delivery is issued; waiting ninety seconds for it
    there would hold every listed host's delivery back by as long.
    """
    entry = importlib.import_module("caam_delivery_push_entry")
    release = threading.Event()
    finished = threading.Event()
    ran: list[str] = []

    def run_local(*, script: str) -> str:
        assert release.wait(timeout=5)
        ran.append(script)
        finished.set()
        return "ok"

    monkeypatch.setattr(entry, "run_local", run_local)
    with contextlib.redirect_stdout(io.StringIO()):
        assert entry.start_local(script="RC") == "started"
        assert ran == []
        release.set()
        assert finished.wait(timeout=5)
    assert ran == ["RC"]
    assert inspect.signature(entry.run_once).parameters["local"].default is entry.start_local
