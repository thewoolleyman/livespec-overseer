"""Remote Control re-issue after a pushed account switch (overseer-fdwat6).

Each scenario runs the script the way the push loop does, `python3 - < file`,
against a stub `tmux` and `ps` on PATH, and again in-process for coverage.
Screens are built from REAL `tmux capture-pane -p -J` captures of Claude Code's
input box (tests/fixtures/claude_2.1.322_input_*.txt) with the account-changed
notice placed in the two forms a real account switch showed under Claude Code
2.1.323 (spec v099, contracts.md "Remote Control re-issue"): the transcript line
behind `●`, and the footer status `/rc failed`. A pane is Claude Code by the
executable its foreground process runs, because tmux reports 2.1.323's current
command as its version number.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import textwrap
from collections.abc import Callable
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


def _run(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, state: dict
) -> tuple[list[str], list[list[str]]]:
    stub = tmp_path / "bin" / "tmux"
    stub.parent.mkdir(exist_ok=True)
    _ = stub.write_text(STUB, encoding="utf-8")
    stub.chmod(0o755)
    ps_stub = tmp_path / "bin" / "ps"
    _ = ps_stub.write_text(PS_STUB, encoding="utf-8")
    ps_stub.chmod(0o755)
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
    "prose wrap where the quoted form starts a continuation line": (
        [
            _pane(
                pane="%16",
                screen=_above_input(
                    capture=EMPTY,
                    lines=[
                        "⏺ After a switch the pane shows",
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
                        "⏺ claude.ai account or organization changed on this machine"
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
        if rc.reissue(tmux=tmux, ps=_fake_ps) != ["%1"] or len(sent) != 2:
            missed.append(width)
    assert missed == []


def test_failed_send_is_not_reported() -> None:
    screen = _above_input(capture=EMPTY, lines=[TRANSCRIPT])

    def tmux(*args: str) -> str | None:
        return {"list-panes": "%1 /dev/pts/1 0", "capture-pane": screen}.get(args[0])

    assert _rc().reissue(tmux=tmux, ps=_fake_ps) == []


def test_run_tmux_maps_hang_or_missing_binary_to_none(*, monkeypatch: pytest.MonkeyPatch) -> None:
    rc = _rc()

    def run(*_a: object, **_k: object) -> object:
        raise OSError("no tmux")

    monkeypatch.setattr(rc.subprocess, "run", run)
    assert rc._run_tmux("-V") is None
    assert rc._run_ps(tty="/dev/pts/1") is None


def test_run_ps_reads_the_tty_without_its_dev_prefix(*, monkeypatch: pytest.MonkeyPatch) -> None:
    rc = _rc()
    seen: list[list[str]] = []

    def run(argv: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="S+ claude\n", stderr="")

    monkeypatch.setattr(rc.subprocess, "run", run)
    assert rc._run_ps(tty="/dev/pts/7") == "S+ claude\n"
    assert seen == [["ps", "-o", "stat=,args=", "-t", "pts/7"]]


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
    """Spec v099: the role holder re-issues after the rotation switches its live login.

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
