"""The push service sweeps every 30 s and alerts after five minutes (contracts.md v111)."""

from __future__ import annotations

import importlib
import io
import json
import subprocess
import urllib.request
from collections.abc import Callable
from pathlib import Path

import pytest

__all__: list[str] = []

push = importlib.import_module("caam_delivery_push")
entry = importlib.import_module("caam_delivery_push_entry")
sw = importlib.import_module("caam_delivery_push_sweep")

SCRIPT = 'BLOCKED_INPUT = "[]"\nprint("sweep")\n'
P = "herdr:default:w1:p1"


class Host:
    """A runner that records each program it is given and answers with queued reports."""

    def __init__(self, *, replies: list[str]) -> None:
        self.replies: list[str] = replies
        self.programs: list[str] = []

    def __call__(self, *, program: str) -> str:
        self.programs.append(program)
        return self.replies.pop(0) if self.replies else "failed no-reply"


class Recorder:
    """Collects journal lines and ntfy messages."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.pushes: list[str] = []

    def write(self, *, line: str) -> None:
        self.lines.append(line)

    def notify(self, *, message: str) -> str:
        self.pushes.append(message)
        return "sent 200"


def _report(
    *, off: list[str] = (), sessions: dict[str, str] | None = None, reissued: list[str] = ()
) -> str:
    return json.dumps(
        {
            "actions": [f"{p} /remote-control" for p in reissued],
            "reissued": list(reissued),
            "off_rc": list(off),
            "unknown": [],
            "sessions": sessions if sessions is not None else {P: "s-1"},
        }
    )


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    sw._SENT.clear()
    sw._REISSUING.clear()


def _sweep(*, host: Host, state: sw.SweepState, now: float, rec: Recorder) -> None:
    sw.sweep_all(
        targets=[("h", host)],
        script=SCRIPT,
        state=state,
        now=now,
        notify=rec.notify,
        write=rec.write,
    )


def test_a_seat_off_remote_control_for_five_minutes_gets_one_push_until_seen_back() -> None:
    state, rec = sw.SweepState(), Recorder()
    host = Host(
        replies=[
            _report(off=(P,)),
            _report(off=(P,)),
            _report(off=(P,)),
            _report(),
            _report(off=(P,)),
        ]
    )
    for now in (0.0, 200.0, 301.0):
        _sweep(host=host, state=state, now=now, rec=rec)
    assert rec.pushes == ["Claude seat off Remote Control over 5 min: h herdr:default:w1:p1"]
    _sweep(host=host, state=state, now=400.0, rec=rec)
    _sweep(host=host, state=state, now=500.0, rec=rec)
    assert len(rec.pushes) == 1 and state.off_since == {f"h|{P}": 500.0}
    assert any(
        "remote-control sweep h: ntfy herdr:default:w1:p1 sent 200" in line for line in rec.lines
    )
    assert not state.running


def test_an_unreachable_host_does_not_count_and_a_reused_pane_starts_fresh() -> None:
    state, rec = sw.SweepState(), Recorder()
    host = Host(
        replies=[_report(off=(P,)), "failed timeout", _report(off=(P,), sessions={P: "s-2"})]
    )
    for now in (0.0, 200.0, 400.0):
        _sweep(host=host, state=state, now=now, rec=rec)
    assert rec.pushes == [] and state.off_since == {f"h|{P}": 400.0}
    assert "remote-control sweep h: unread failed timeout" in rec.lines


def test_sends_by_the_sweep_or_the_reissue_block_the_pane_for_ten_minutes() -> None:
    state, rec = sw.SweepState(), Recorder()
    host = Host(replies=[_report(reissued=(P,)), _report(), _report(), _report()])
    _sweep(host=host, state=state, now=0.0, rec=rec)
    _sweep(host=host, state=state, now=599.0, rec=rec)
    assert 'BLOCKED_INPUT = "[\\"herdr:default:w1:p1\\"]"' in host.programs[1]
    _sweep(host=host, state=state, now=601.0, rec=rec)
    assert 'BLOCKED_INPUT = "[]"' in host.programs[2]
    sw.reissue_started(host="h")
    _sweep(host=host, state=state, now=700.0, rec=rec)
    assert rec.lines[-1] == "remote-control sweep h: skipped while its re-issue runs"
    sw.reissue_finished(host="h", line=json.dumps({"reissued": ["herdr:default:w9:p9"]}), now=700.0)
    sw.reissue_finished(host="h", line="failed timeout", now=700.0)
    _sweep(host=host, state=state, now=701.0, rec=rec)
    assert "w9:p9" in host.programs[-1]


def test_a_sweep_starts_only_when_due_not_running_and_configured() -> None:
    state, rec, started = sw.SweepState(), Recorder(), []
    host = Host(replies=[_report()])

    def start(*, task: Callable[[], None]) -> None:
        started.append(task)

    args = {
        "targets": [("h", host)],
        "script": SCRIPT,
        "notify": rec.notify,
        "write": rec.write,
        "start": start,
    }
    assert sw.maybe_start(state=state, now=0.0, **args)
    assert not sw.maybe_start(state=state, now=40.0, **args)
    started[0]()
    assert not sw.maybe_start(state=state, now=10.0, **args)
    assert sw.maybe_start(state=state, now=31.0, **args)
    assert not sw.maybe_start(state=sw.SweepState(), now=0.0, **{**args, "script": None})
    assert not sw.maybe_start(state=sw.SweepState(), now=0.0, **{**args, "targets": []})


def test_targets_are_the_role_holder_and_listed_linux_hosts_once_a_list_exists(
    *, tmp_path: Path
) -> None:
    def local(*, program: str) -> str:
        return program

    def remote(*, host: push.Host) -> Callable[[str], str]:
        def run(*, program: str) -> str:
            return host.label + program

        return run

    assert sw.targets(home=tmp_path, local=local, remote=remote) == []
    hosts = tmp_path / push.HOSTS_FILE
    hosts.parent.mkdir(parents=True)
    _ = hosts.write_text("lin u@lin linux\nmac u@mac macos\n", encoding="utf-8")
    found = sw.targets(home=tmp_path, local=local, remote=remote)
    assert [label for label, _ in found] == [sw.LOCAL, "lin"]
    assert found[1][1](program="!") == "lin!"


def test_ntfy_reads_the_role_holders_address_and_never_reports_the_topic(*, tmp_path: Path) -> None:
    posted: list[tuple[str, str]] = []

    def post(*, url: str, message: str) -> str:
        posted.append((url, message))
        return "sent 200"

    assert sw.ntfy_push(home=tmp_path, message="m", post=post) == "skipped no ntfy address"
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    _ = settings.write_text(
        json.dumps({"env": {"CLAUDE_NTFY_TOPIC": "secret-topic"}}), encoding="utf-8"
    )
    assert sw.ntfy_push(home=tmp_path, message="m", post=post) == "sent 200"
    _ = settings.write_text(
        json.dumps({"env": {"CLAUDE_NTFY_TOPIC": "t", "CLAUDE_NTFY_SERVER": "https://n.example/"}}),
        encoding="utf-8",
    )
    assert sw.ntfy_push(home=tmp_path, message="m", post=post) == "sent 200"
    assert posted == [("https://ntfy.sh/secret-topic", "m"), ("https://n.example/t", "m")]


class Reply:
    """A urlopen stand-in."""

    status = 200

    def __enter__(self) -> Reply:
        return self

    def __exit__(self, *args: object) -> None:
        del args


def test_the_ntfy_post_reports_its_status_or_its_failure(
    *, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", lambda request, timeout: Reply())
    assert sw._post(url="https://ntfy.sh/t", message="m") == "sent 200"

    def refuse(request: object, timeout: float) -> Reply:
        del request, timeout
        raise OSError("down")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    assert sw._post(url="https://ntfy.sh/t", message="m") == "failed OSError"
    monkeypatch.undo()
    assert sw._post(url="no-scheme/secret-topic", message="m") == "failed ValueError"


def test_the_service_loop_starts_sweeps_through_the_tracked_push(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    runs: list[dict[str, object]] = []
    monkeypatch.setattr(entry, "run_once", lambda **kw: runs.append(kw))
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        entry.caam_delivery_push_sweep, "maybe_start", lambda **kw: calls.append(kw) or True
    )
    assert entry.main(argv=["run"], sleep=lambda _: None, passes=1) == 0
    assert calls[0]["targets"] == [] and calls[0]["script"] is not None and callable(runs[0]["run"])
    assert calls[0]["notify"](message="m") == "skipped no ntfy address"


def test_the_tracked_runner_registers_reissue_runs_and_passes_pushes_through(
    *, tmp_path: Path
) -> None:
    hosts = tmp_path / push.HOSTS_FILE
    hosts.parent.mkdir(parents=True)
    _ = hosts.write_text("h u@h linux\n", encoding="utf-8")
    seen: list[str] = []

    def run(**kwargs: object) -> tuple[int, str]:
        seen.append(str(kwargs["program"]))
        assert ("h" in sw._REISSUING) == (kwargs["program"] == "REISSUE")
        return 0, json.dumps({"reissued": ["herdr:default:w2:p2"]})

    tracked = sw.tracking(run=run, home=tmp_path, script="REISSUE")
    assert tracked(target="u@h", program="APPLY")[0] == 0
    assert tracked(target="u@h", program="REISSUE")[0] == 0
    assert seen == ["APPLY", "REISSUE"] and "h" not in sw._REISSUING
    assert "h|herdr:default:w2:p2" in sw._SENT and "h|herdr:default:w2:p2" in sw._SENT
    untracked = sw.tracking(run=lambda **_: (0, "applied"), home=tmp_path, script=None)
    assert untracked(target="u@h", program="REISSUE") == (0, "applied")


def test_the_role_holders_reissue_is_registered_too(*, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        entry, "run_local", lambda **_: json.dumps({"reissued": ["herdr:default:w3:p3"]})
    )
    monkeypatch.setattr(entry.threading, "Thread", Immediate)
    assert entry.start_local(script="x") == "started"
    assert f"{sw.LOCAL}|herdr:default:w3:p3" in sw._SENT and sw.LOCAL not in sw._REISSUING


class Immediate:
    """A Thread stand-in that runs its target on start."""

    def __init__(self, *, target: Callable[[], None], name: str, daemon: bool) -> None:
        del name, daemon
        self.target = target

    def start(self) -> None:
        self.target()


def test_the_entry_builds_an_ssh_runner_and_a_journal(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[dict[str, object]] = []
    monkeypatch.setattr(push, "run_ssh", lambda **kw: seen.append(kw) or (0, "line"))
    remote = entry._sweep_remote(home=tmp_path)(
        host=push.Host(label="h", target="u@h", platform="linux")
    )
    assert (
        remote(program="prog") == "line"
        and seen[0]["target"] == "u@h"
        and seen[0]["program"] == "prog"
    )
    out = io.StringIO()
    monkeypatch.setattr(entry.streams, "write_stdout", lambda *, text: out.write(text))
    entry._journal(line="a line")
    assert out.getvalue() == "a line\n"


def test_run_here_returns_the_whole_last_line_or_the_failure(
    *, monkeypatch: pytest.MonkeyPatch
) -> None:
    long = "x" * 500
    monkeypatch.setattr(
        sw.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="a\n" + long)
    )
    assert sw.run_here(program="p") == long
    monkeypatch.setattr(
        sw.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 3, stdout="")
    )
    assert sw.run_here(program="p") == "failed exit 3"

    def hang(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise subprocess.TimeoutExpired(cmd="python3", timeout=1)

    monkeypatch.setattr(sw.subprocess, "run", hang)
    assert sw.run_here(program="p") == "failed TimeoutExpired"


def test_a_refused_session_name_is_named_in_the_journal_and_absent_otherwise() -> None:
    """Scenario: A session name holding a control character is never typed."""
    state, rec = sw.SweepState(), Recorder()
    refused = json.loads(_report(reissued=(P,)))
    refused["refused_name"] = [P]
    host = Host(replies=[json.dumps(refused), _report()])
    _sweep(host=host, state=state, now=0.0, rec=rec)
    _sweep(host=host, state=state, now=40.0, rec=rec)
    assert rec.lines[0].endswith(f" refused_name=['{P}']")
    assert "refused_name" not in rec.lines[1]


def _offline(*, reissued: list[str] = ()) -> str:
    report = json.loads(_report(off=(P,), reissued=reissued))
    report["actions"] += [f"{P} offline:Escape"]
    report["offline"] = [P]
    return json.dumps(report)


def test_a_seat_whose_reissue_met_the_not_connected_panel_is_retried_before_its_cap() -> None:
    """A pane the sweep found at the not-connected panel is released from the ten-minute cap.

    At the 2026-11-15T16:47:30Z rotation each such seat waited out the whole cap
    (about 12 minutes off Remote Control); the release lets the next sweep retry it.
    """
    state, rec = sw.SweepState(), Recorder()
    host = Host(replies=[_report(off=(P,), reissued=(P,)), _offline(), _report(off=(P,))])
    _sweep(host=host, state=state, now=0.0, rec=rec)
    _sweep(host=host, state=state, now=30.0, rec=rec)
    assert 'BLOCKED_INPUT = "[\\"herdr:default:w1:p1\\"]"' in host.programs[1]
    _sweep(host=host, state=state, now=60.0, rec=rec)
    assert 'BLOCKED_INPUT = "[]"' in host.programs[2]
    assert rec.lines[1].endswith(f" offline=['{P}']")
    assert "offline" not in rec.lines[0]


def test_the_early_retry_is_bounded_and_resets_once_the_seat_is_back() -> None:
    state, rec = sw.SweepState(), Recorder()
    replies = [_offline(reissued=(P,)) for _ in range(sw.OFFLINE_RETRIES + 1)]
    host = Host(replies=[*replies, _report(off=(P,)), _report(), _offline(reissued=(P,)), "x"])
    for step in range(sw.OFFLINE_RETRIES + 2):
        _sweep(host=host, state=state, now=30.0 * step, rec=rec)
    assert 'BLOCKED_INPUT = "[]"' in host.programs[sw.OFFLINE_RETRIES]
    assert 'BLOCKED_INPUT = "[\\"herdr:default:w1:p1\\"]"' in host.programs[-1]
    _sweep(host=host, state=state, now=300.0, rec=rec)
    _sweep(host=host, state=state, now=330.0, rec=rec)
    _sweep(host=host, state=state, now=360.0, rec=rec)
    assert 'BLOCKED_INPUT = "[]"' in host.programs[-1]
