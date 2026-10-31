"""A supervisor tick shares Herdr observations across all mapped rows."""

from __future__ import annotations

from types import SimpleNamespace

import herdr_adapter
import herdr_calls
import herdr_identity
import pane_router_reads

__all__: list[str] = []


def _target(*, pane_id: str) -> herdr_identity.HerdrPaneTarget:
    return herdr_identity.HerdrPaneTarget(
        socket_path="/run/herdr.sock",
        server_pid=71,
        server_starttime="server-start",
        pane_id=pane_id,
    )


class _Herdr:
    def __init__(self) -> None:
        self.list_calls = 0
        self.foreground_calls = 0

    def identify(self, *, socket_path: str) -> herdr_adapter.InstanceIdentification:
        assert socket_path == "/run/herdr.sock"
        return herdr_adapter.InstanceIdentification(
            ok=True,
            peer=SimpleNamespace(pid=71, starttime="server-start"),
            error="",
        )

    def list_panes(self, *, target: herdr_identity.HerdrPaneTarget) -> herdr_adapter.PaneListing:
        self.list_calls += 1
        return herdr_adapter.PaneListing(
            ok=True,
            panes=tuple(
                herdr_calls.PaneRow(
                    pane_id=f"pane-{index}",
                    tab_id="tab",
                    workspace_id="workspace",
                    cwd="",
                    foreground_cwd="",
                    focused=False,
                )
                for index in range(48)
            ),
            error="",
        )

    def capture_pane(
        self, *, target: herdr_identity.HerdrPaneTarget, retain_ansi: bool = True
    ) -> herdr_adapter.PaneCapture:
        del target, retain_ansi
        return herdr_adapter.PaneCapture(ok=True, text="", error="")

    def foreground(
        self, *, target: herdr_identity.HerdrPaneTarget
    ) -> herdr_adapter.ForegroundReading:
        self.foreground_calls += 1
        index = int(target.pane_id.removeprefix("pane-"))
        return herdr_adapter.ForegroundReading(
            ok=True,
            process=herdr_calls.ForegroundProcess(
                pane_id=target.pane_id,
                shell_pid=100 + index,
                process_group_id=200 + index,
                name="claude",
                cmdline="claude",
                cwd="/repo",
            ),
            error="",
        )


def _reads(*, herdr: _Herdr) -> pane_router_reads.PaneRoutingReads:
    return pane_router_reads.PaneRoutingReads(
        tmux=SimpleNamespace(),
        herdr=herdr,
        herdr_endpoints=lambda: (),
        tmux_run=lambda **_kwargs: "",
        coordinates=set(),
    )


def test_one_tick_reuses_one_listing_and_each_foreground_read_across_gone_rows() -> None:
    """Nineteen gone rows must not each rescan the same forty-eight panes."""
    herdr = _Herdr()
    reads = _reads(herdr=herdr)
    sessions = [
        herdr_identity.encode_herdr_target(target=_target(pane_id=f"pane-{index}"))
        for index in range(19)
    ]

    assert all(reads.session_exists(session=session) for session in sessions)
    for index, session in enumerate(sessions):
        assert (
            reads.renumbered_herdr_coordinate(
                session=session,
                observed_session_identity=f"claude:{200 + index}:start-{index}:topic-{index}",
                starttime_of=lambda *, pid: f"start-{pid - 200}",
            )
            == session
        )
    assert (
        reads.renumbered_herdr_coordinate(
            session=sessions[0],
            observed_session_identity="claude:200:start-0:topic-0",
            starttime_of=lambda *, pid: f"start-{pid - 200}",
        )
        == sessions[0]
    )

    assert herdr.list_calls == 1
    assert herdr.foreground_calls == 48
