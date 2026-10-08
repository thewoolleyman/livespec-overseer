"""Deterministic complementary coverage for both bootstrap backends.

The native exercise in `tests/test_bootstrap_live_herdr.py` is the behavioral
proof: a real process in a real herdr pane, a real split, a real installed daemon,
and a real withheld acknowledgement. This file covers the refusals a healthy
server will not produce on request — an unreadable geometry answer, a layout that
does not place the pane it was asked about, several panes above the invoking one, a
pane process that cannot be read, a pane that outlived its daemon, and a pane
running something else entirely — plus the whole tmux arm, which `SPECIFICATION/
constraints.md` requires to keep its legacy default-socket meaning while a NAMED
instance stays retained.

Ordinary CI may lack herdr, so this tier is what keeps the backends' guards graded
there; it complements the native exercise rather than standing in for it.

**Every case asserts on the THREE-WAY reading, not on a boolean.** A pane above
the invoking one is accepted only on positive process evidence; everything else is
`unresolved` rather than absent, because reading an unaccountable pane as absent is
what would split again after a lost acknowledgement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from overseer import (
    daemon_liveness,
    herdr_bootstrap,
    terminal_ownership,
    terminal_probes,
    tmux_bootstrap,
)

__all__: list[str] = []

HERDR_SOCKET = "/run/user/1000/herdr.sock"
NAMED_TMUX_SOCKET = "/run/user/1000/tmux-named/socket"
CORE_ROOT = "/data/projects/livespec-overseer"
DAEMON_COMMAND = "overseerd 2>> /tmp/overseer/daemon.log"


def _claim(*, backend: str, socket_path: str, pane_id: str) -> terminal_ownership.OwnershipClaim:
    return terminal_ownership.OwnershipClaim(
        backend=backend,
        socket_path=socket_path,
        server_pid=300,
        server_starttime="gen-1",
        pane_id=pane_id,
        pane_process_pid=200,
        distance=1,
    )


def _herdr_claim() -> terminal_ownership.OwnershipClaim:
    return _claim(backend="herdr", socket_path=HERDR_SOCKET, pane_id="w1:p5")


def _tmux_claim(*, socket_path: str = "") -> terminal_ownership.OwnershipClaim:
    return _claim(backend="tmux", socket_path=socket_path, pane_id="%7")


def _layout(*, tops: dict[str, int]) -> dict[str, object]:
    return {
        "layout": {"panes": [{"pane_id": pane, "rect": {"y": top}} for pane, top in tops.items()]}
    }


# ------------------------------------------------------------- daemon liveness


def test_the_daemon_is_recognized_by_either_spelling_its_launcher_produces() -> None:
    assert daemon_liveness.is_daemon_command(text="/tmp/p/venv/bin/overseerd --warn-percent 99")
    assert daemon_liveness.is_daemon_command(text="python3 -m overseer.daemon")
    assert not daemon_liveness.is_daemon_command(text="/usr/bin/dash")


def test_a_login_shell_is_recognized_whether_or_not_argv_marks_it_as_one() -> None:
    assert daemon_liveness.is_retained_shell(name="dash")
    assert daemon_liveness.is_retained_shell(name="-zsh")
    assert not daemon_liveness.is_retained_shell(name="overseerd")


# ------------------------------------------------------------------ herdr arm


@dataclass(kw_only=True)
class FakeWriter:
    """A scripted stand-in for the herdr write surface."""

    layout_ok: bool = True
    layout_result: dict[str, object] = field(default_factory=dict)
    layout_error: str = ""
    split: _LayoutAnswer | None = None
    targets: list[Any] = field(default_factory=list)
    splits: list[tuple[str, str, str]] = field(default_factory=list)

    def request(self, *, target: Any, method: str, params: Any, expect: Any) -> Any:
        del method, params, expect
        self.targets.append(target)
        return _RpcAnswer(ok=self.layout_ok, result=self.layout_result, error=self.layout_error)

    def split_window_top(self, *, target: Any, cwd: str, command: str, ratio: float) -> Any:
        del ratio
        self.splits.append((target.pane_id, cwd, command))
        if self.split is not None:
            return self.split
        return _LayoutAnswer(ok=True, pane_id="w1:p2", error="", effect_unknown=False)


@dataclass(frozen=True, kw_only=True)
class _RpcAnswer:
    ok: bool
    result: dict[str, object]
    error: str


@dataclass(frozen=True, kw_only=True)
class _LayoutAnswer:
    ok: bool
    pane_id: str
    error: str
    effect_unknown: bool


@dataclass(frozen=True, kw_only=True)
class FakeProcess:
    pane_id: str
    shell_pid: int
    process_group_id: int
    name: str
    cmdline: str


@dataclass(kw_only=True)
class FakeAdapter:
    processes: dict[str, FakeProcess] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    targets: list[Any] = field(default_factory=list)

    def foreground(self, *, target: Any) -> Any:
        self.targets.append(target)
        error = self.errors.get(target.pane_id, "")
        if error:
            return _Foreground(ok=False, process=None, error=error)
        return _Foreground(ok=True, process=self.processes.get(target.pane_id), error="")


@dataclass(frozen=True, kw_only=True)
class _Foreground:
    ok: bool
    process: FakeProcess | None
    error: str


def _herdr(
    *,
    writer: FakeWriter | None = None,
    adapter: FakeAdapter | None = None,
) -> herdr_bootstrap.HerdrBootstrap:
    return herdr_bootstrap.HerdrBootstrap(
        adapter=FakeAdapter() if adapter is None else adapter,
        writer=FakeWriter() if writer is None else writer,
    )


def test_a_herdr_instance_that_answers_its_geometry_has_the_capability() -> None:
    backend = _herdr(writer=FakeWriter(layout_result=_layout(tops={"w1:p5": 0})))

    assert backend.capability_error(claim=_herdr_claim()) == ""


def test_a_herdr_instance_that_cannot_answer_its_geometry_names_the_method() -> None:
    backend = _herdr(writer=FakeWriter(layout_ok=False, layout_error="herdr socket is unreachable"))

    error = backend.capability_error(claim=_herdr_claim())

    assert "pane.layout is unavailable" in error
    assert HERDR_SOCKET in error
    assert "herdr socket is unreachable" in error


def test_an_unreadable_herdr_layout_payload_is_an_error_rather_than_an_empty_tab() -> None:
    backend = _herdr(writer=FakeWriter(layout_result={"layout": "garbled"}))

    reading = backend.daemon_host(claim=_herdr_claim())

    assert reading.pane_id == ""
    assert reading.unresolved == ""
    assert "unreadable" in reading.error


def test_a_herdr_layout_that_omits_the_claimed_pane_is_refused() -> None:
    backend = _herdr(writer=FakeWriter(layout_result=_layout(tops={"w1:p9": 0})))

    reading = backend.daemon_host(claim=_herdr_claim())

    assert "does not place pane 'w1:p5'" in reading.error


def test_nothing_above_the_herdr_pane_is_a_first_bootstrap() -> None:
    backend = _herdr(writer=FakeWriter(layout_result=_layout(tops={"w1:p5": 0, "w1:p6": 20})))

    reading = backend.daemon_host(claim=_herdr_claim())

    assert (reading.pane_id, reading.unresolved, reading.error) == ("", "", "")


def test_several_panes_above_the_herdr_pane_are_unresolved() -> None:
    backend = _herdr(
        writer=FakeWriter(layout_result=_layout(tops={"w1:p1": 0, "w1:p2": 5, "w1:p5": 10}))
    )

    reading = backend.daemon_host(claim=_herdr_claim())

    assert "2 panes sit above 'w1:p5'" in reading.unresolved
    assert reading.pane_id == ""


def test_a_herdr_pane_above_whose_process_cannot_be_read_is_an_error() -> None:
    backend = _herdr(
        writer=FakeWriter(layout_result=_layout(tops={"w1:p2": 0, "w1:p5": 10})),
        adapter=FakeAdapter(errors={"w1:p2": "process info reply carried an unreadable payload"}),
    )

    reading = backend.daemon_host(claim=_herdr_claim())

    assert "w1:p2" in reading.error
    assert "unreadable payload" in reading.error


def test_a_herdr_pane_above_holding_only_its_retained_shell_is_not_daemon_liveness() -> None:
    backend = _herdr(
        writer=FakeWriter(layout_result=_layout(tops={"w1:p2": 0, "w1:p5": 10})),
        adapter=FakeAdapter(
            processes={
                "w1:p2": FakeProcess(
                    pane_id="w1:p2",
                    shell_pid=811,
                    process_group_id=811,
                    name="dash",
                    cmdline="/usr/bin/dash",
                )
            }
        ),
    )

    reading = backend.daemon_host(claim=_herdr_claim())

    assert reading.pane_id == ""
    assert "retained shell" in reading.unresolved
    assert "fresh exact-instance, pane and process evidence" in reading.unresolved


def test_a_herdr_pane_above_running_something_else_is_unresolved() -> None:
    backend = _herdr(
        writer=FakeWriter(layout_result=_layout(tops={"w1:p2": 0, "w1:p5": 10})),
        adapter=FakeAdapter(
            processes={
                "w1:p2": FakeProcess(
                    pane_id="w1:p2",
                    shell_pid=811,
                    process_group_id=822,
                    name="htop",
                    cmdline="htop",
                )
            }
        ),
    )

    reading = backend.daemon_host(claim=_herdr_claim())

    assert "not the overseer daemon" in reading.unresolved


def test_a_live_daemon_above_the_herdr_pane_is_the_verified_host() -> None:
    adapter = FakeAdapter(
        processes={
            "w1:p2": FakeProcess(
                pane_id="w1:p2",
                shell_pid=811,
                process_group_id=822,
                name="overseerd",
                cmdline="/tmp/candidate/venv/bin/overseerd",
            )
        }
    )
    backend = _herdr(
        writer=FakeWriter(layout_result=_layout(tops={"w1:p2": 0, "w1:p5": 10})), adapter=adapter
    )

    reading = backend.daemon_host(claim=_herdr_claim())

    assert (reading.pane_id, reading.unresolved, reading.error) == ("w1:p2", "", "")
    # Addressed to the EXACT generation the claim verified, never a namesake.
    assert adapter.targets[0].server_pid == 300
    assert adapter.targets[0].server_starttime == "gen-1"
    assert adapter.targets[0].socket_path == HERDR_SOCKET


def test_the_herdr_placement_carries_the_layout_outcome_through_unchanged() -> None:
    writer = FakeWriter(
        split=_LayoutAnswer(
            ok=False,
            pane_id="w1:p2",
            error="herdr request deadline expired before a complete reply arrived",
            effect_unknown=True,
        )
    )
    backend = _herdr(writer=writer)

    placement = backend.place_daemon_above(
        claim=_herdr_claim(), cwd=CORE_ROOT, command=DAEMON_COMMAND
    )

    assert (placement.ok, placement.pane_id, placement.effect_unknown) == (False, "w1:p2", True)
    assert placement.error == "herdr request deadline expired before a complete reply arrived"
    assert writer.splits == [("w1:p5", CORE_ROOT, DAEMON_COMMAND)]


def test_a_successful_herdr_placement_reports_the_pane_it_created() -> None:
    backend = _herdr()

    placement = backend.place_daemon_above(
        claim=_herdr_claim(), cwd=CORE_ROOT, command=DAEMON_COMMAND
    )

    assert placement.ok
    assert placement.pane_id == "w1:p2"
    assert placement.effect_unknown is False


# ------------------------------------------------------------------- tmux arm


@dataclass(frozen=True, kw_only=True)
class Geometry:
    pane: str
    top: int
    height: int


@dataclass(kw_only=True)
class FakeTmuxDriver:
    """A scripted stand-in for the tmux window-layout driver."""

    geometries: tuple[Geometry, ...] = ()
    commands: dict[str, str | None] = field(default_factory=dict)
    split_result: str | None = "%88"
    pane_alive: bool = True
    calls: list[tuple[str, Any]] = field(default_factory=list)

    def window_pane_geometries(self, *, pane: str) -> list[Geometry]:
        self.calls.append(("window_pane_geometries", pane))
        return list(self.geometries)

    def pane_current_command(self, *, session: str) -> str | None:
        self.calls.append(("pane_current_command", session))
        return self.commands.get(session)

    def split_window_top(self, *, pane: str, cwd: str, command: str) -> str | None:
        self.calls.append(("split_window_top", (pane, cwd, command)))
        return self.split_result

    def set_pane_title(self, *, pane: str, title: str) -> bool:
        self.calls.append(("set_pane_title", (pane, title)))
        return True

    def pane_exists(self, *, pane: str) -> bool:
        self.calls.append(("pane_exists", pane))
        return self.pane_alive

    def select_layout_even(self, *, pane: str) -> bool:
        self.calls.append(("select_layout_even", pane))
        return True

    def set_pane_height_percent(self, *, pane: str, percent: int) -> bool:
        self.calls.append(("set_pane_height_percent", (pane, percent)))
        return True

    def verbs(self) -> list[str]:
        return [verb for verb, _ in self.calls]


def _tmux(*, driver: FakeTmuxDriver) -> tuple[tmux_bootstrap.TmuxBootstrap, list[str]]:
    addressed: list[str] = []

    def driver_for(*, socket_path: str) -> FakeTmuxDriver:
        addressed.append(socket_path)
        return driver

    return tmux_bootstrap.TmuxBootstrap(driver_for=driver_for), addressed


def _recorded_argv(*, socket_path: str) -> list[str]:
    """The argv a scoped driver really issues for one ordinary read."""
    calls: list[list[str]] = []

    def recording(argv: list[str], **kwargs: Any) -> Any:
        del kwargs
        calls.append(list(argv))
        raise OSError("deliberately not spawned")

    driver = tmux_bootstrap.socket_scoped_driver(socket_path=socket_path, run=recording)
    _ = driver.pane_exists(pane="%7")
    return calls[0]


def test_the_default_tmux_socket_keeps_its_legacy_unwrapped_argv() -> None:
    """An unqualified claim produces exactly the legacy form — no `-S` anywhere."""
    argv = _recorded_argv(socket_path=terminal_probes.DEFAULT_TMUX_ENDPOINT)

    assert argv[0] == "tmux"
    assert "-S" not in argv


def test_a_named_tmux_socket_is_retained_on_every_later_call() -> None:
    argv = _recorded_argv(socket_path=NAMED_TMUX_SOCKET)

    assert argv[:3] == ["tmux", "-S", NAMED_TMUX_SOCKET]


def test_a_tmux_instance_that_reports_its_geometry_has_the_capability() -> None:
    backend, addressed = _tmux(
        driver=FakeTmuxDriver(geometries=(Geometry(pane="%7", top=0, height=30),))
    )

    assert backend.capability_error(claim=_tmux_claim()) == ""
    assert addressed == [""]


def test_a_tmux_instance_reporting_no_panes_names_the_missing_capability() -> None:
    backend, _ = _tmux(driver=FakeTmuxDriver(geometries=()))

    error = backend.capability_error(claim=_tmux_claim(socket_path=NAMED_TMUX_SOCKET))

    assert "pane geometry is unavailable" in error
    assert NAMED_TMUX_SOCKET in error
    assert "reported no panes" in error


def test_a_tmux_geometry_that_omits_the_claimed_pane_is_refused() -> None:
    backend, _ = _tmux(driver=FakeTmuxDriver(geometries=(Geometry(pane="%9", top=0, height=30),)))

    reading = backend.daemon_host(claim=_tmux_claim())

    assert "does not place pane '%7'" in reading.error


def test_nothing_above_the_tmux_pane_is_a_first_bootstrap() -> None:
    backend, _ = _tmux(
        driver=FakeTmuxDriver(
            geometries=(
                Geometry(pane="%7", top=0, height=20),
                Geometry(pane="%9", top=20, height=10),
            )
        )
    )

    reading = backend.daemon_host(claim=_tmux_claim())

    assert (reading.pane_id, reading.unresolved, reading.error) == ("", "", "")


def test_several_panes_above_the_tmux_pane_are_unresolved() -> None:
    backend, _ = _tmux(
        driver=FakeTmuxDriver(
            geometries=(
                Geometry(pane="%1", top=0, height=10),
                Geometry(pane="%2", top=10, height=10),
                Geometry(pane="%7", top=20, height=10),
            )
        )
    )

    reading = backend.daemon_host(claim=_tmux_claim())

    assert "2 panes sit above '%7'" in reading.unresolved


def test_a_tmux_pane_above_with_no_readable_command_is_an_error() -> None:
    backend, _ = _tmux(
        driver=FakeTmuxDriver(
            geometries=(
                Geometry(pane="%88", top=0, height=20),
                Geometry(pane="%7", top=20, height=10),
            )
        )
    )

    reading = backend.daemon_host(claim=_tmux_claim())

    assert "no readable foreground command" in reading.error


def test_a_tmux_pane_above_holding_only_its_shell_is_not_daemon_liveness() -> None:
    backend, _ = _tmux(
        driver=FakeTmuxDriver(
            geometries=(
                Geometry(pane="%88", top=0, height=20),
                Geometry(pane="%7", top=20, height=10),
            ),
            commands={"%88": "zsh"},
        )
    )

    reading = backend.daemon_host(claim=_tmux_claim())

    assert reading.pane_id == ""
    assert "retained shell" in reading.unresolved


def test_a_tmux_pane_above_running_something_else_is_unresolved() -> None:
    backend, _ = _tmux(
        driver=FakeTmuxDriver(
            geometries=(
                Geometry(pane="%88", top=0, height=20),
                Geometry(pane="%7", top=20, height=10),
            ),
            commands={"%88": "htop"},
        )
    )

    reading = backend.daemon_host(claim=_tmux_claim())

    assert "not the overseer daemon" in reading.unresolved


def test_a_live_daemon_above_the_tmux_pane_is_the_verified_host() -> None:
    backend, _ = _tmux(
        driver=FakeTmuxDriver(
            geometries=(
                Geometry(pane="%88", top=0, height=20),
                Geometry(pane="%7", top=20, height=10),
            ),
            commands={"%88": "overseerd"},
        )
    )

    reading = backend.daemon_host(claim=_tmux_claim())

    assert (reading.pane_id, reading.unresolved, reading.error) == ("%88", "", "")


def test_a_tmux_placement_titles_normalizes_and_resizes_the_new_top_pane() -> None:
    """The legacy layout steps are preserved, in the legacy order."""
    driver = FakeTmuxDriver(geometries=(Geometry(pane="%7", top=0, height=30),))
    backend, _ = _tmux(driver=driver)

    placement = backend.place_daemon_above(
        claim=_tmux_claim(), cwd=CORE_ROOT, command=DAEMON_COMMAND
    )

    assert placement.ok
    assert placement.pane_id == "%88"
    assert placement.effect_unknown is False
    assert driver.calls == [
        ("split_window_top", ("%7", CORE_ROOT, DAEMON_COMMAND)),
        ("set_pane_title", ("%88", tmux_bootstrap.DAEMON_PANE_TITLE)),
        ("pane_exists", "%88"),
        ("select_layout_even", "%7"),
        ("set_pane_height_percent", ("%88", tmux_bootstrap.DAEMON_PANE_HEIGHT_PERCENT)),
    ]


def test_a_refused_tmux_split_is_a_known_failure_with_nothing_created() -> None:
    driver = FakeTmuxDriver(split_result=None)
    backend, _ = _tmux(driver=driver)

    placement = backend.place_daemon_above(
        claim=_tmux_claim(), cwd=CORE_ROOT, command=DAEMON_COMMAND
    )

    assert not placement.ok
    assert placement.pane_id == ""
    assert placement.effect_unknown is False
    assert "refused to split" in placement.error
    assert "set_pane_title" not in driver.verbs()


def test_a_tmux_daemon_pane_that_closed_immediately_is_reported_as_not_alive() -> None:
    driver = FakeTmuxDriver(pane_alive=False)
    backend, _ = _tmux(driver=driver)

    placement = backend.place_daemon_above(
        claim=_tmux_claim(), cwd=CORE_ROOT, command=DAEMON_COMMAND
    )

    assert not placement.ok
    assert placement.pane_id == "%88"
    assert "did not stay alive" in placement.error
    assert "set_pane_height_percent" not in driver.verbs()
