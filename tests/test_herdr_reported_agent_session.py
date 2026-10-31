"""Herdr's per-pane Codex session report reaches the daemon's identity reader.

The daemon identifies a Codex carrier that holds no rollout file open only from the
backend-reported session id. Herdr publishes that id on each `pane.list` row's
`agent_session` member (`{source, agent, kind, value}`); these tests pin that the
pure parser keeps exactly an `id`-kind Codex report and that the production mixed
pane driver answers `pane_agent_session` from the row of the addressed pane.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from overseer import (
    herdr_adapter,
    herdr_calls,
    herdr_identity,
    pane_router,
)
from overseer.test_supervisor_fakes import FakeTmux

__all__: list[str] = []

SESSION_ID = "11111111-2222-3333-4444-555555555555"


def _row(*, pane: str, session: object = None) -> dict[str, object]:
    row: dict[str, object] = {
        "pane_id": pane,
        "tab_id": "w1:t1",
        "workspace_id": "w1",
        "cwd": "/repo",
        "foreground_cwd": "/repo",
        "focused": False,
        "agent": "codex",
    }
    if session is not None:
        row["agent_session"] = session
    return row


def _report(*, agent: str = "codex", kind: str = "id", value: str = SESSION_ID) -> dict[str, str]:
    return {"source": "herdr:codex", "agent": agent, "kind": kind, "value": value}


def _parsed(*, session: object) -> str:
    rows = herdr_calls.pane_rows(result={"panes": [_row(pane="w1:p1", session=session)]})
    assert rows is not None
    return rows[0].reported_codex_session_id


def test_an_id_kind_codex_report_is_carried_on_the_pane_row():
    assert _parsed(session=_report()) == SESSION_ID


def test_a_report_that_is_not_an_id_kind_codex_report_is_no_evidence():
    assert _parsed(session=_report(kind="path", value="/home/.codex/rollout.jsonl")) == ""
    assert _parsed(session=_report(agent="claude")) == ""
    assert _parsed(session=_report(value="")) == ""
    assert _parsed(session=_report(value="   ")) == ""


def test_a_missing_or_malformed_report_never_discards_the_pane_row():
    assert _parsed(session=None) == ""
    assert _parsed(session="not an object") == ""
    assert _parsed(session={"agent": "codex", "kind": "id", "value": 5}) == ""


@dataclass(kw_only=True)
class ListingHerdr:
    rows: dict[str, str]
    ok: bool = True
    listed: list[str] = field(default_factory=list)

    def list_panes(self, *, target: herdr_identity.HerdrPaneTarget) -> herdr_adapter.PaneListing:
        self.listed.append(target.pane_id)
        if not self.ok:
            return herdr_adapter.PaneListing(ok=False, panes=(), error="gone")
        return herdr_adapter.PaneListing(
            ok=True,
            panes=tuple(
                herdr_calls.PaneRow(
                    pane_id=pane,
                    tab_id="w1:t1",
                    workspace_id="w1",
                    cwd="/repo",
                    foreground_cwd="/repo",
                    focused=False,
                    reported_codex_session_id=session,
                )
                for pane, session in self.rows.items()
            ),
            error="",
        )


def _coordinate(*, pane: str) -> str:
    return herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path="/run/herdr.sock",
            server_pid=701,
            server_starttime="start-701",
            pane_id=pane,
        )
    )


def _driver(*, herdr: ListingHerdr) -> pane_router.MixedPaneDriver:
    return pane_router.MixedPaneDriver(tmux=FakeTmux(), herdr=herdr)


def test_the_mixed_driver_answers_with_the_addressed_panes_reported_id():
    herdr = ListingHerdr(rows={"w1:p1": SESSION_ID, "w1:p2": "other-id"})
    driver = _driver(herdr=herdr)

    assert driver.pane_agent_session(session=_coordinate(pane="w1:p1")) == SESSION_ID
    assert driver.pane_agent_session(session=_coordinate(pane="w1:p2")) == "other-id"


def test_a_pane_without_a_report_or_outside_the_listing_has_no_reported_id():
    driver = _driver(herdr=ListingHerdr(rows={"w1:p1": "", "w1:p2": SESSION_ID}))

    assert driver.pane_agent_session(session=_coordinate(pane="w1:p1")) is None
    assert driver.pane_agent_session(session=_coordinate(pane="w1:p9")) is None


def test_an_unreadable_listing_is_no_evidence():
    driver = _driver(herdr=ListingHerdr(rows={"w1:p1": SESSION_ID}, ok=False))

    assert driver.pane_agent_session(session=_coordinate(pane="w1:p1")) is None


def test_a_legacy_or_undecodable_coordinate_has_no_reported_id_and_asks_no_server():
    herdr = ListingHerdr(rows={"w1:p1": SESSION_ID})
    driver = _driver(herdr=herdr)

    assert driver.pane_agent_session(session="legacy-session") is None
    assert driver.pane_agent_session(session="herdr:malformed") is None
    assert herdr.listed == []
