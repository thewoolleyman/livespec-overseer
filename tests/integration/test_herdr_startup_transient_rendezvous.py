"""Integration-tier coverage for staged startup-transient rendezvous behavior.

Each control drives the REAL `ReadyShellGate` against a real, long-lived shell
process and a real staged transient, with no herdr server: a fake pane turns the
gate's two server calls (`pane.send_input` and `pane.process_info`) into a real
`/bin/sh` that runs what it is sent, and reports a reading built from that
shell's own `/proc` lineage. The gate, the pin, the release and the exit wait
are the shipped fixture code; only the server round trip is replaced, and the
replacement can delay its first reading, which is the load the scenarios name.
"""

from __future__ import annotations

import subprocess
import sys
import time
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import pytest
from test_herdr_live_observations import (
    TRANSIENT_NAME,
    TRANSIENT_SECONDS,
    ReadyShellGate,
    ShellIdentityPin,
    parent_pid_of,
    process_group_of,
    rendezvous_transient,
    starttime_of,
    startup_transient,
)

PANE = "w1:p1"
# The delay of the first usable reading: later than a fixed-lifetime transient lives.
SLOW_FIRST_READING = TRANSIENT_SECONDS + 0.5
# The gate's establishment bound, comfortably past that delay.
BOUND = SLOW_FIRST_READING + 4.0
_GATE_MODULE = sys.modules[ReadyShellGate.__module__]


def _children_named(*, shell: int, name: str) -> tuple[int, ...]:
    """Every process named `name` whose parent is `shell`, from `/proc`."""
    found: list[int] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            comm = (entry / "comm").read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if comm == name and parent_pid_of(pid=int(entry.name)) == shell:
            found.append(int(entry.name))
    return tuple(found)


@dataclass(kw_only=True)
class FakePane:
    """A real shell standing in for a herdr pane, readings taken from `/proc`.

    The shell reads ONE line, runs it as a forked child, then waits for its
    stdin to close, so it stays alive and idle once the transient is gone. It is
    deliberately not a session leader: its process group is this test's, so a
    running child reports a foreground group that is not the shell's own pid.
    """

    first_reading_delay: float = 0.0
    blind: bool = False
    shell: subprocess.Popen[str] | None = None
    reads: int = 0

    def start(self) -> None:
        self.shell = subprocess.Popen(  # noqa: S603 — /bin/sh running this fixture's own script
            ["/bin/sh", "-c", 'IFS= read -r line; eval "$line"; IFS= read -r _'],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )

    def stop(self) -> None:
        shell = self.shell
        if shell is None:
            return
        if shell.stdin is not None and not shell.stdin.closed:
            shell.stdin.close()
        try:
            _ = shell.wait(timeout=10)
        except subprocess.TimeoutExpired:
            shell.kill()
            _ = shell.wait()

    def send_input(self, *, text: str) -> None:
        assert self.shell is not None
        assert self.shell.stdin is not None
        _ = self.shell.stdin.write(text + "\n")
        self.shell.stdin.flush()

    def install(self, *, monkeypatch: pytest.MonkeyPatch) -> None:
        """Route the gate's two server calls to this pane."""

        def raw_request(
            *, socket_path: str, method: str, params: Mapping[str, object]
        ) -> dict[str, Any]:
            del socket_path
            assert method == "pane.send_input", method
            self.send_input(text=str(params["text"]))
            return {"result": {}}

        def process_info_reply(*, socket_path: str, pane_id: str) -> dict[str, Any]:
            del socket_path, pane_id
            return self.reading()

        monkeypatch.setattr(_GATE_MODULE, "raw_request", raw_request)
        monkeypatch.setattr(_GATE_MODULE, "process_info_reply", process_info_reply)

    def reading(self) -> dict[str, Any]:
        """One `pane.process_info` reply, delayed on its first call when asked."""
        assert self.shell is not None
        self.reads += 1
        if self.reads == 1 and self.first_reading_delay:
            time.sleep(self.first_reading_delay)
        shell_pid = self.shell.pid
        children = () if self.blind else _children_named(shell=shell_pid, name=TRANSIENT_NAME)
        group = process_group_of(pid=children[0]) if children else shell_pid
        return {
            "result": {
                "process_info": {
                    "pane_id": PANE,
                    "shell_pid": shell_pid,
                    "foreground_process_group_id": group,
                    "foreground_processes": [
                        {"pid": pid, "name": TRANSIENT_NAME} for pid in children
                    ],
                }
            }
        }


@pytest.fixture
def pane(*, monkeypatch: pytest.MonkeyPatch) -> Iterator[FakePane]:
    fake = FakePane()
    fake.start()
    fake.install(monkeypatch=monkeypatch)
    try:
        yield fake
    finally:
        fake.stop()


class _Inner:
    """The gate's wrapped writer; only the establishment is under control here."""

    def request(
        self, *, target: Any, method: str, params: Mapping[str, object], expect: Any
    ) -> Any:
        del target, method, params, expect
        return {}


@dataclass(kw_only=True)
class Staged:
    gate: ReadyShellGate
    release: Path
    timeline: list[tuple[str, bool]] = field(default_factory=list)

    def establish(self) -> None:
        """Run the gate's one-shot establishment through its public request."""
        _ = self.gate.request(
            target=None, method="pane.process_info", params={"pane_id": PANE}, expect=None
        )

    def expired_marker(self) -> Path:
        return self.release.with_name(f"{self.release.name}.hang-guard-expired")


def _stage(
    *,
    scratch: Path,
    guard_seconds: float | None,
    seconds: float,
    monkeypatch: pytest.MonkeyPatch,
) -> Staged:
    """A real gate staging a rendezvous transient, with its pin and exit wait recorded.

    Each recorded step carries whether the release file existed when it happened.
    `guard_seconds=None` stages the fixed-lifetime transient instead, with no release.
    """
    scratch.mkdir(parents=True, exist_ok=True)
    release = scratch / "release"
    if guard_seconds is None:
        command = startup_transient(scratch=scratch)
    else:
        command = rendezvous_transient(
            scratch=scratch, release=release, guard_seconds=guard_seconds
        )
    gate = ReadyShellGate(
        inner=_Inner(),
        socket_path="unused",
        startup_transient=command,
        transient_name=TRANSIENT_NAME,
        release=None if guard_seconds is None else release,
        seconds=seconds,
    )
    timeline: list[tuple[str, bool]] = []
    real_starttime = _GATE_MODULE.starttime_of
    real_wait = _GATE_MODULE.await_child_gone

    def starttime(*, pid: int) -> int | None:
        # The pin is the only reading of the shell's own start time during the clear.
        if gate.transient is not None and pid == parent_pid_of(pid=gate.transient.pid or 0):
            timeline.append(("pin", release.exists()))
        return cast("int | None", real_starttime(pid=pid))

    def exit_wait(**kwargs: Any) -> str:
        timeline.append(("await-child-gone", release.exists()))
        return str(real_wait(**kwargs))

    monkeypatch.setattr(_GATE_MODULE, "starttime_of", starttime)
    monkeypatch.setattr(_GATE_MODULE, "await_child_gone", exit_wait)
    return Staged(gate=gate, release=release, timeline=timeline)


def test_scenario_a_gate_releases_its_transient_after_the_pin_and_before_the_exit_wait(
    *, tmp_path: Path, pane: FakePane, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The release is written after the shell is pinned and before the exit is awaited."""
    staged = _stage(scratch=tmp_path, guard_seconds=BOUND, seconds=BOUND, monkeypatch=monkeypatch)

    staged.establish()

    assert pane.shell is not None
    pin = ShellIdentityPin(pid=pane.shell.pid, starttime=starttime_of(pid=pane.shell.pid) or -1)
    assert staged.gate.refusal() == "", staged.gate.refusal()
    assert staged.gate.retained == pin
    assert staged.timeline == [("pin", False), ("await-child-gone", True)], staged.timeline
    assert not staged.expired_marker().exists()


def test_scenario_a_gate_still_releases_a_transient_it_never_observed(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The server never reports the child, and the gate releases it rather than await its guard."""
    blind = FakePane(blind=True)
    blind.start()
    try:
        blind.install(monkeypatch=monkeypatch)
        staged = _stage(scratch=tmp_path, guard_seconds=BOUND, seconds=1.0, monkeypatch=monkeypatch)
        started = time.monotonic()
        staged.establish()
        assert blind.shell is not None
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and _children_named(
            shell=blind.shell.pid, name=TRANSIENT_NAME
        ):
            time.sleep(0.05)
        elapsed = time.monotonic() - started
    finally:
        blind.stop()

    assert staged.timeline == [], "an unobserved transient has no shell to pin or exit to await"
    assert staged.release.exists(), "an unobserved transient was never released"
    assert staged.gate.retained is None
    assert "never observed" in staged.gate.refusal(), staged.gate.refusal()
    assert not staged.expired_marker().exists()
    assert elapsed < BOUND, f"the unobserved transient waited out its guard: {elapsed:.1f}s"


def test_scenario_a_staged_transient_outlives_a_slow_first_reading(
    *, tmp_path: Path, pane: FakePane, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A first reading later than a fixed lifetime still finds the rendezvous transient."""
    pane.first_reading_delay = SLOW_FIRST_READING
    held = _stage(scratch=tmp_path, guard_seconds=BOUND, seconds=BOUND, monkeypatch=monkeypatch)

    held.establish()

    assert held.gate.refusal() == "", held.gate.refusal()
    assert held.gate.transient is not None
    assert held.gate.transient.pid is not None, "the staged transient was never observed"
    assert held.gate.established is not None
    assert held.gate.established.recovered


def test_scenario_a_fixed_lifetime_transient_does_not_outlive_the_same_slow_reading(
    *, tmp_path: Path, pane: FakePane, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fixed-lifetime transient is gone under the SAME delay, so the gate refuses."""
    pane.first_reading_delay = SLOW_FIRST_READING
    fixed = _stage(scratch=tmp_path, guard_seconds=None, seconds=BOUND, monkeypatch=monkeypatch)

    fixed.establish()

    assert "never observed" in fixed.gate.refusal(), fixed.gate.refusal()


def test_scenario_a_staged_transient_ended_by_its_hang_guard_fails_loudly(
    *, tmp_path: Path, pane: FakePane, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A guard, not a release, ending the transient is a named refusal, never an establishment."""
    pane.first_reading_delay = 1.5
    guarded = _stage(scratch=tmp_path, guard_seconds=0.5, seconds=4.0, monkeypatch=monkeypatch)

    started = time.monotonic()
    guarded.establish()
    elapsed = time.monotonic() - started

    assert guarded.expired_marker().exists(), "the transient did not report its hang guard ended it"
    refusal = guarded.gate.refusal()
    assert "hang-guard expiry" in refusal, refusal
    assert guarded.gate.transient is not None
    assert guarded.gate.transient.pid is None, "an expired transient must not read as observed"
    # The guard had already ended the transient when the delayed first reading came back,
    # so the gate stops at that reading: no quiet retry of a known-expired observation.
    assert pane.reads == 1, f"the gate kept polling after the guard expired: {pane.reads} reads"
    assert elapsed < 4.0, f"the gate waited out its bound after the guard expired: {elapsed:.1f}s"
