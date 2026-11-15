"""The keep-alive sweep keeps every Claude Code seat on Remote Control (contracts.md v111).

Every screen below is a real herdr `recent-unwrapped` capture from Claude Code
2.1.325 (tests/fixtures/remote_control_sweep/), and the session records are a
real connected/disconnected pair of one session. herdr is a fake that serves
those screens and advances them as keys arrive, so nothing is spawned.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

import pytest

__all__: list[str] = []

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "overseer" / "remote_control_sweep.py"
FIX = ROOT / "tests" / "fixtures"
SWEEP_FIX = FIX / "remote_control_sweep"
ENABLE = (SWEEP_FIX / "enable-dialog-2.1.325.txt").read_text(encoding="utf-8")
PANEL = (SWEEP_FIX / "status-panel-2.1.325.txt").read_text(encoding="utf-8")
TRUST = (SWEEP_FIX / "trust-prompt-2.1.325.txt").read_text(encoding="utf-8")
EMPTY = (FIX / "claude_2.1.323_herdr_input_empty.txt").read_text(encoding="utf-8")
DRAFT = EMPTY.replace("❯\u00a0\n", "❯\u00a0half written draft\n")
# The fixture record's `name` is `rc-fixture`, so the sweep types the named command.
NAMED = "/remote-control rc-fixture"
TYPED = EMPTY.replace("❯\u00a0\n", f"❯\u00a0{NAMED}\n")
BARE_TYPED = EMPTY.replace("❯\u00a0\n", "❯\u00a0/remote-control\n")
# The slash menu as hetzner-xubuntu drew it on 2026-11-15, BELOW the box of a
# disconnected 2.1.325 seat: an indented `❯` row after the closing rule.
MENU_BELOW = TYPED.rstrip("\n") + "\n  ❯ /remote-control                    Control this session\n"
STALE = "● Remote Control disconnected — signed-in claude.ai account changed\n" + EMPTY
CONNECTED = json.loads((SWEEP_FIX / "record-connected-2.1.325.json").read_text(encoding="utf-8"))
DISCONNECTED = json.loads(
    (SWEEP_FIX / "record-disconnected-2.1.325.json").read_text(encoding="utf-8")
)
TRUST_DIR = "/tmp/claude-1000/rc-fixture-1988231"
PID = 7
NEVER = ENABLE.replace("   ❯ 1. Enable", "     1. Enable").replace("     2. Never", "   ❯ 2. Never")
TRUST_YES = TRUST.replace(" ❯ No, exit", "   No, exit").replace(
    "   Yes, I trust", " ❯ Yes, I trust"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("remote_control_sweep", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SWEEP = _load()


@dataclass(kw_only=True)
class FakePane:
    """One pane: its listing row, its foreground processes, and the screens it shows in turn."""

    row: dict[str, object]
    procs: list[dict[str, object]]
    screens: list[str]


@dataclass(kw_only=True)
class FakeHerdr:
    """One herdr session with panes; each pane's screen advances on the keys sent to it."""

    panes: dict[str, FakePane]
    fail: str = ""
    sent: list[tuple[str, ...]] = field(default_factory=list[tuple[str, ...]])

    def __call__(self, *args: str) -> str | None:
        if args == ("session", "list", "--json"):
            return json.dumps({"sessions": [{"name": "s", "running": True}, {"name": "off"}]})
        verb = args[2:4]
        if verb == ("pane", "list"):
            return json.dumps({"result": {"panes": [p.row for p in self.panes.values()]}})
        if verb == ("pane", "process-info"):
            procs = self.panes[args[-1]].procs
            return json.dumps({"result": {"process_info": {"foreground_processes": procs}}})
        state = self.panes[args[4]]
        if verb == ("pane", "read"):
            return state.screens[0]
        if self.fail == args[3]:
            return None
        self.sent.append((args[4], *args[5:]))
        if len(state.screens) > 1:
            _ = state.screens.pop(0)
        return ""


def no_sleep(seconds: float) -> None:
    """Sleep stand-in: the sweep's pauses take no time under test."""
    del seconds


def records(*, value: dict[str, object]) -> Callable[..., dict[str, object]]:
    """A record reader returning `value` for the fake pane's Claude Code pid 7."""

    def record_of(*, pid: int) -> dict[str, object]:
        return value if pid == PID else {}

    return record_of


def _pane(*, screens: list[str], cwd: str = "", offset: int = 0) -> FakePane:
    row: dict[str, object] = {
        "pane_id": "p",
        "cwd": cwd,
        "scroll": {"viewport_rows": 40, "offset_from_bottom": offset},
    }
    procs: list[dict[str, object]] = [
        {"argv": ["bash", "x"], "pid": 1},
        {"argv": ["claude", "-n", "seat"], "pid": PID},
    ]
    return FakePane(row=row, procs=procs, screens=list(screens))


def _sweep(
    *, herdr: FakeHerdr, record: dict[str, object], blocked: list[str] | None = None
) -> dict[str, object]:
    report: dict[str, object] = SWEEP.sweep(
        blocked=blocked or [], herdr=herdr, record_of=records(value=record), sleep=no_sleep
    )
    return report


def _run(
    *,
    screens: list[str],
    record: dict[str, object],
    blocked: list[str] | None = None,
    cwd: str = "",
    offset: int = 0,
) -> tuple[dict[str, object], list[tuple[str, ...]]]:
    herdr = FakeHerdr(panes={"p": _pane(screens=screens, cwd=cwd, offset=offset)})
    return _sweep(herdr=herdr, record=record, blocked=blocked), herdr.sent


@pytest.mark.parametrize(
    ("screen", "kind"),
    [(ENABLE, "enable"), (NEVER, "enable-other"), (PANEL, "panel"), (TRUST, "trust"), (EMPTY, "")],
)
def test_each_real_capture_is_recognised_as_its_dialog(*, screen: str, kind: str) -> None:
    assert SWEEP.dialog_kind(screen=screen) == kind


def test_the_enable_dialog_gets_enter_even_without_a_record() -> None:
    report, sent = _run(screens=[ENABLE, EMPTY], record={})
    assert sent == [("p", "Enter")]
    assert report["actions"] == ["herdr:s:p enable:Enter"]


def test_never_mind_selected_is_left_alone() -> None:
    assert _run(screens=[NEVER], record=DISCONNECTED)[1] == []


def test_the_status_panel_gets_escape_never_enter_unless_busy() -> None:
    assert _run(screens=[PANEL, EMPTY], record=CONNECTED)[1] == [("p", "esc")]
    assert _run(screens=[PANEL], record={**CONNECTED, "status": "busy"})[1] == []
    assert _run(screens=[PANEL], record={})[1] == []


def test_a_trust_prompt_under_workspace_is_answered_yes_after_a_re_read(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "workspace" / "repo"
    project.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    screens = [s.replace(TRUST_DIR, str(project)) for s in (TRUST, TRUST_YES, EMPTY)]
    report, sent = _run(screens=screens, record={}, cwd=str(project))
    assert sent == [("p", "down"), ("p", "Enter")]
    assert report["actions"] == ["herdr:s:p trust:Enter"]


@pytest.mark.parametrize("where", ["outside", "root", "mismatch", "escape", "unnamed"])
def test_a_trust_prompt_outside_an_allowed_root_is_never_answered(
    *, where: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / "workspace" / "repo").mkdir(parents=True)
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "workspace" / "link").symlink_to(tmp_path / "elsewhere")
    named, cwd = {
        "outside": (tmp_path / "elsewhere", tmp_path / "elsewhere"),
        "root": (tmp_path / "workspace", tmp_path / "workspace"),
        "mismatch": (tmp_path / "workspace" / "repo", tmp_path / "workspace"),
        "escape": (tmp_path / "workspace" / "link", tmp_path / "workspace" / "link"),
        "unnamed": (Path(), tmp_path / "workspace" / "repo"),
    }[where]
    screen = (
        TRUST.replace(TRUST_DIR, str(named)) if where != "unnamed" else TRUST.replace(TRUST_DIR, "")
    )
    assert not SWEEP.trust_allowed(screen=screen, cwd=str(cwd), home=tmp_path)
    assert _run(screens=[screen], record={}, cwd=str(cwd))[1] == []


def test_a_trust_prompt_that_never_selects_yes_gets_no_enter(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / ".worktrees" / "repo" / "branch"
    project.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    stuck = TRUST.replace(TRUST_DIR, str(project))
    assert _run(screens=[stuck] * 6, record={}, cwd=str(project))[1] == [("p", "down")] * 3


def test_an_idle_disconnected_seat_is_reissued_and_its_dialog_answered() -> None:
    report, sent = _run(screens=[EMPTY, TYPED, ENABLE, EMPTY], record=DISCONNECTED)
    assert sent == [("p", NAMED), ("p", "Enter"), ("p", "Enter")]
    assert report["reissued"] == ["herdr:s:p"]
    assert report["off_rc"] == ["herdr:s:p"]
    assert report["actions"] == [f"herdr:s:p {NAMED}", "herdr:s:p enable:Enter"]
    assert report["sessions"] == {"herdr:s:p": DISCONNECTED["sessionId"]}


def test_a_reissue_that_reconnects_without_a_dialog_reports_only_the_command() -> None:
    report, sent = _run(screens=[EMPTY, TYPED, EMPTY], record=DISCONNECTED)
    assert sent == [("p", NAMED), ("p", "Enter")]
    assert report["actions"] == [f"herdr:s:p {NAMED}"]


@pytest.mark.parametrize(
    ("screens", "record", "blocked"),
    [
        ([EMPTY], {**DISCONNECTED, "status": "busy"}, []),
        ([DRAFT], DISCONNECTED, []),
        ([EMPTY], DISCONNECTED, ["herdr:s:p"]),
        (["no box at all\n"], DISCONNECTED, []),
    ],
)
def test_a_disconnected_seat_that_is_busy_drafted_or_capped_is_not_typed_into(
    *, screens: list[str], record: dict[str, object], blocked: list[str]
) -> None:
    report, sent = _run(screens=screens, record=record, blocked=blocked)
    assert sent == []
    assert report["off_rc"] == ["herdr:s:p"]


def test_a_reconnected_seat_keeps_the_name_it_is_addressed_by() -> None:
    """Scenario: A reconnected seat keeps the name it is addressed by."""
    record = {**DISCONNECTED, "name": "caam-anthropic-loop-runner"}
    typed = EMPTY.replace("❯\u00a0\n", "❯\u00a0/remote-control caam-anthropic-loop-runner\n")
    report, sent = _run(screens=[EMPTY, typed, EMPTY], record=record)
    assert sent == [("p", "/remote-control caam-anthropic-loop-runner"), ("p", "Enter")]
    assert report["actions"] == ["herdr:s:p /remote-control caam-anthropic-loop-runner"]
    assert "refused_name" not in report


def test_a_seat_with_no_name_is_reconnected_with_the_bare_command() -> None:
    """Scenario: A seat with no usable name is reconnected with the bare command."""
    record = {k: v for k, v in DISCONNECTED.items() if k != "name"}
    report, sent = _run(screens=[EMPTY, BARE_TYPED, EMPTY], record=record)
    assert sent == [("p", "/remote-control"), ("p", "Enter")]
    assert report["reissued"] == ["herdr:s:p"]
    assert "refused_name" not in report


@pytest.mark.parametrize(
    "name", ["seat\nrm -rf", "seat\tx", "seat\x1b[2J", "seat\x7f", "", 7, "x" * 201]
)
def test_a_session_name_holding_a_control_character_is_never_typed(*, name: object) -> None:
    """Scenario: A session name holding a control character is never typed."""
    report, sent = _run(screens=[EMPTY, BARE_TYPED, EMPTY], record={**DISCONNECTED, "name": name})
    assert sent == [("p", "/remote-control"), ("p", "Enter")]
    assert report["refused_name"] == ["herdr:s:p"]


def test_a_name_of_exactly_the_limit_is_typed() -> None:
    name = "x" * 200
    typed = EMPTY.replace("❯\u00a0\n", f"❯\u00a0/remote-control {name}\n")
    _, sent = _run(screens=[EMPTY, typed, EMPTY], record={**DISCONNECTED, "name": name})
    assert sent[0] == ("p", f"/remote-control {name}")


def test_a_slash_menu_drawn_below_the_box_does_not_strand_the_typed_command() -> None:
    report, sent = _run(screens=[EMPTY, MENU_BELOW, EMPTY], record=DISCONNECTED)
    assert sent == [("p", NAMED), ("p", "Enter")]
    assert report["reissued"] == ["herdr:s:p"]


def test_text_typed_over_the_command_before_enter_is_never_submitted() -> None:
    report, sent = _run(screens=[EMPTY, DRAFT], record=DISCONNECTED)
    assert sent == [("p", NAMED)]
    assert report["reissued"] == []


def test_a_stale_dialog_above_a_live_input_box_is_not_answered() -> None:
    for stale in (ENABLE, PANEL, TRUST):
        assert SWEEP.dialog_kind(screen=stale + EMPTY) == ""
        assert _run(screens=[stale + EMPTY], record=CONNECTED)[1] == []


def test_an_answered_seat_off_remote_control_is_still_named_off() -> None:
    report, _ = _run(screens=[ENABLE, EMPTY], record=DISCONNECTED)
    assert report["off_rc"] == ["herdr:s:p"]
    assert report["actions"] == ["herdr:s:p enable:Enter"]


def test_a_connected_seat_showing_a_stale_notice_is_left_alone() -> None:
    report, sent = _run(screens=[STALE], record=CONNECTED)
    assert (sent, report["off_rc"], report["unknown"]) == ([], [], [])


def test_a_seat_with_no_record_is_unknown_and_not_typed_into() -> None:
    report, sent = _run(screens=[EMPTY], record={})
    assert (sent, report["unknown"]) == ([], ["herdr:s:p"])


def test_scrolled_back_and_non_claude_panes_are_not_reached() -> None:
    assert _run(screens=[ENABLE], record={}, offset=3)[1] == []
    herdr = FakeHerdr(panes={"p": _pane(screens=[ENABLE])})
    herdr.panes["p"].procs = [{"argv": ["less", "notes"], "pid": PID}]
    assert _sweep(herdr=herdr, record={})["actions"] == []


@pytest.mark.parametrize(
    ("fail", "screens", "record"),
    [
        ("send-keys", [ENABLE], {}),
        ("send-keys", [PANEL], CONNECTED),
        ("send-keys", [EMPTY, TYPED], DISCONNECTED),
        ("send-text", [EMPTY], DISCONNECTED),
    ],
)
def test_a_failed_send_is_never_reported(
    *, fail: str, screens: list[str], record: dict[str, object]
) -> None:
    herdr = FakeHerdr(panes={"p": _pane(screens=list(screens))}, fail=fail)
    report = _sweep(herdr=herdr, record=record)
    assert report["actions"] == [] and report["reissued"] == []


@pytest.mark.parametrize("shown", ["no", "yes", "gone"])
def test_a_trust_answer_whose_key_fails_or_whose_prompt_closes_reports_nothing(
    *, shown: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "workspace" / "repo"
    project.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    screens = {"no": [TRUST], "yes": [TRUST_YES], "gone": [TRUST, EMPTY]}[shown]
    fail = "" if shown == "gone" else "send-keys"
    herdr = FakeHerdr(
        panes={
            "p": _pane(
                screens=[x.replace(TRUST_DIR, str(project)) for x in screens], cwd=str(project)
            )
        },
        fail=fail,
    )
    report = _sweep(herdr=herdr, record={})
    assert report["actions"] == []


@pytest.mark.parametrize(
    "screen",
    ["❯\u00a0\n", "─\n❯\u00a0\ntrailing text\n", "─\n❯\u00a0\n\n"],
)
def test_an_input_box_without_both_rules_or_with_text_below_is_not_empty(*, screen: str) -> None:
    assert not SWEEP._empty_box(screen=screen)


def test_a_claude_process_without_a_pid_is_not_reached() -> None:
    herdr = FakeHerdr(panes={"p": _pane(screens=[ENABLE])})
    herdr.panes["p"].procs = [{"argv": ["claude"]}]
    assert _sweep(herdr=herdr, record={})["actions"] == []


class Replies:
    """A herdr stand-in that answers every call with one fixed reply."""

    def __init__(self, *, reply: str | None) -> None:
        self.reply = reply

    def __call__(self, *args: str) -> str | None:
        del args
        return self.reply


@pytest.mark.parametrize("reply", [None, "not json", json.dumps({"sessions": "x"})])
def test_unreadable_herdr_replies_reach_no_pane(*, reply: str | None) -> None:
    report = SWEEP.sweep(
        blocked=[], herdr=Replies(reply=reply), record_of=records(value={}), sleep=no_sleep
    )
    assert report["actions"] == []


def test_main_reads_the_blocked_list_and_prints_one_json_line(
    *, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(SWEEP, "BLOCKED_INPUT", json.dumps(["herdr:s:p"]))
    herdr = FakeHerdr(panes={"p": _pane(screens=[EMPTY])})
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert SWEEP.main(herdr=herdr, record_of=records(value=DISCONNECTED), sleep=no_sleep) == 0
    assert json.loads(out.getvalue())["off_rc"] == ["herdr:s:p"]
    assert herdr.sent == []


def test_the_record_must_name_the_pane_pid(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    sessions = tmp_path / ".claude" / "sessions"
    sessions.mkdir(parents=True)
    _ = (sessions / "7.json").write_text(json.dumps({**DISCONNECTED, "pid": 7}), encoding="utf-8")
    _ = (sessions / "8.json").write_text(json.dumps({**DISCONNECTED, "pid": 9}), encoding="utf-8")
    _ = (sessions / "10.json").write_text("not json", encoding="utf-8")
    assert SWEEP._read_record(pid=7)["status"] == "idle"
    assert SWEEP._read_record(pid=8) == {}
    assert SWEEP._read_record(pid=10) == {}
    assert SWEEP._read_record(pid=11) == {}


def _which_none(name: str) -> None:
    del name


def _which_herdr(name: str) -> str:
    del name
    return "/bin/herdr"


def _completed(*, returncode: int, stdout: str) -> Callable[..., object]:
    def run(*args: object, **kwargs: object) -> object:
        del kwargs
        return subprocess.CompletedProcess([str(arg) for arg in args], returncode, stdout=stdout)

    return run


def _hang(*args: object, **kwargs: object) -> object:
    del args, kwargs
    raise subprocess.TimeoutExpired(cmd="herdr", timeout=1)


def test_run_herdr_maps_a_missing_binary_or_failure_to_none(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(SWEEP.shutil, "which", _which_none)
    assert SWEEP._run_herdr("pane", "list") is None
    monkeypatch.setattr(SWEEP.shutil, "which", _which_herdr)
    monkeypatch.setattr(SWEEP.subprocess, "run", _completed(returncode=0, stdout="ok"))
    assert SWEEP._run_herdr("x") == "ok"
    monkeypatch.setattr(SWEEP.subprocess, "run", _completed(returncode=1, stdout="no"))
    assert SWEEP._run_herdr("x") is None
    monkeypatch.setattr(SWEEP.subprocess, "run", _hang)
    assert SWEEP._run_herdr("x") is None
    (tmp_path / ".local" / "bin").mkdir(parents=True)
    _ = (tmp_path / ".local" / "bin" / "herdr").write_text("", encoding="utf-8")
    monkeypatch.setattr(SWEEP.shutil, "which", _which_none)
    assert SWEEP._run_herdr("x") is None


def test_a_status_panel_on_a_seat_off_remote_control_is_reported_offline() -> None:
    """After an account switch, `/remote-control` opens the panel on a seat still off.

    Measured on the role holder's journal at the 2026-11-15T16:47:30Z rotation: the
    panel the re-issue opened was dismissed as an ordinary status panel, and the seat
    then sat out the ten-minute cap. The record, not the text, says it is not connected.
    """
    report, sent = _run(screens=[PANEL, EMPTY], record=DISCONNECTED)
    assert sent == [("p", "esc")]
    assert report["actions"] == ["herdr:s:p offline:Escape"]
    assert report["offline"] == ["herdr:s:p"]
    assert report["off_rc"] == ["herdr:s:p"]
    assert report["reissued"] == []


def test_a_reissue_that_opens_the_panel_on_a_seat_still_off_is_reported_offline() -> None:
    report, sent = _run(screens=[EMPTY, TYPED, PANEL, EMPTY], record=DISCONNECTED)
    assert sent == [("p", NAMED), ("p", "Enter"), ("p", "esc")]
    assert report["reissued"] == ["herdr:s:p"]
    assert report["actions"] == [f"herdr:s:p {NAMED}", "herdr:s:p offline:Escape"]
    assert report["offline"] == ["herdr:s:p"]


def test_a_mid_turn_seat_at_the_panel_while_off_remote_control_gets_no_key() -> None:
    """The not-connected handling never sends a key to a pane whose session is mid-turn."""
    report, sent = _run(screens=[PANEL], record={**DISCONNECTED, "status": "busy"})
    assert sent == []
    assert "offline" not in report
    assert report["off_rc"] == ["herdr:s:p"]


def test_a_status_panel_on_a_connected_seat_is_not_reported_offline() -> None:
    report, sent = _run(screens=[PANEL, EMPTY], record=CONNECTED)
    assert sent == [("p", "esc")]
    assert report["actions"] == ["herdr:s:p panel:Escape"]
    assert "offline" not in report


def _clock(*, readings: list[float]) -> Callable[[], float]:
    """A clock stand-in returning `readings` in turn, then the last one forever."""
    queue = list(readings)

    def now() -> float:
        return queue.pop(0) if len(queue) > 1 else queue[0]

    return now


@pytest.mark.parametrize(("elapsed", "typed"), [(39.0, True), (40.0, False)])
def test_a_sweep_stops_typing_once_its_reissue_budget_is_spent(
    *, elapsed: float, typed: bool
) -> None:
    """A sweep that ran past its budget would lose its report, and so the pane's cap."""
    herdr = FakeHerdr(panes={"p": _pane(screens=[EMPTY, TYPED, EMPTY])})
    report = SWEEP.sweep(
        blocked=[],
        herdr=herdr,
        record_of=records(value=DISCONNECTED),
        sleep=no_sleep,
        clock=_clock(readings=[0.0, elapsed]),
    )
    assert bool(herdr.sent) is typed
    assert report["off_rc"] == ["herdr:s:p"]
    assert report["reissued"] == (["herdr:s:p"] if typed else [])


def test_the_dialog_after_a_reissue_is_answered_on_a_fresh_record() -> None:
    """The record is read again before the follow-up key: a seat that went busy gets none."""
    reads = [DISCONNECTED, {**DISCONNECTED, "status": "busy"}]

    def record_of(*, pid: int) -> dict[str, object]:
        assert pid == PID
        return reads.pop(0) if len(reads) > 1 else reads[0]

    herdr = FakeHerdr(panes={"p": _pane(screens=[EMPTY, TYPED, PANEL])})
    report = SWEEP.sweep(blocked=[], herdr=herdr, record_of=record_of, sleep=no_sleep)
    assert herdr.sent == [("p", NAMED), ("p", "Enter")]
    assert "offline" not in report


def test_a_null_session_name_is_treated_as_absent() -> None:
    report, sent = _run(screens=[EMPTY, BARE_TYPED, EMPTY], record={**DISCONNECTED, "name": None})
    assert sent == [("p", "/remote-control"), ("p", "Enter")]
    assert "refused_name" not in report
