"""Guard the index and pane boundaries of a fresh Herdr Codex successor."""

from __future__ import annotations

from types import SimpleNamespace

import _supervisor_herdr_codex
import _supervisor_herdr_codex_carrier
import _supervisor_herdr_codex_successor
import herdr_identity
import pane_router_replacement
from _supervisor_launch_profile import CodexLaunchPlan

OLD = "019f548d-0000-7000-8000-000000000001"
STALE = "019f548d-0000-7000-8000-000000000002"


def test_launch_records_every_preexisting_thread_before_proving_the_successor(
    *, monkeypatch
) -> None:
    """A thread renamed after launch is not evidence that this launch created it."""
    target = "herdr:target"
    track = SimpleNamespace(repo="/repo", topic="topic", tmux=target)
    sup = SimpleNamespace(
        live_codex={(target, "topic"): SimpleNamespace(pid=101, session_id=OLD)},
        codex_home="/codex",
        starttime_of=lambda **_kwargs: "start",
    )
    captured = []
    sentinel = object()
    monkeypatch.setattr(
        _supervisor_herdr_codex.codex_sessions,
        "read_thread_names",
        lambda **_kwargs: {OLD: "topic", STALE: "unrelated-name"},
    )
    monkeypatch.setattr(_supervisor_herdr_codex, "resume_for_track", lambda **_kwargs: "resume")
    monkeypatch.setattr(
        _supervisor_herdr_codex,
        "codex_fresh_launch_plan",
        lambda **_kwargs: CodexLaunchPlan(command="codex", env={}),
    )
    monkeypatch.setattr(_supervisor_herdr_codex, "statusline_mismatch", lambda **_kwargs: False)
    monkeypatch.setattr(
        _supervisor_herdr_codex._supervisor_herdr_replacement,
        "begin_herdr_replacement",
        lambda **kwargs: captured.append(kwargs["binding"]) or sentinel,
    )

    assert (
        _supervisor_herdr_codex.begin_codex_replacement(sup=sup, track=track, target=target)
        is sentinel
    )
    assert captured[0].predecessor_named_threads == (OLD, STALE)


def test_rolloutless_proof_refuses_multiple_fresh_codex_carriers() -> None:
    snapshot = SimpleNamespace(
        foreground_group=300,
        processes=(
            SimpleNamespace(pid=301, executable="/usr/bin/codex"),
            SimpleNamespace(pid=302, executable="/usr/bin/codex"),
        ),
    )
    sup = SimpleNamespace(tmux=SimpleNamespace(report_agent_session=lambda **_kwargs: None))

    carrier, reason = _supervisor_herdr_codex_carrier.carrier_without_rollout(
        sup=sup, snapshot=snapshot
    )

    assert carrier is None
    assert reason == "fresh Codex successor is not uniquely observable in the retained shell"


def test_successor_proof_refuses_a_carrier_that_is_not_fresh(*, monkeypatch) -> None:
    carrier = SimpleNamespace(pid=301, starttime="new")
    snapshot = SimpleNamespace()
    sup = SimpleNamespace(
        tmux=SimpleNamespace(herdr_replacement_snapshot=lambda **_kwargs: snapshot),
        refresh_codex_sessions=lambda: None,
        live_codex={("pane", "topic"): object()},
    )
    track = SimpleNamespace(topic="topic")
    monkeypatch.setattr(
        _supervisor_herdr_codex_successor._supervisor_launch,
        "session_of",
        lambda **_kwargs: "pane",
    )
    monkeypatch.setattr(
        _supervisor_herdr_codex_successor._supervisor_herdr_codex_carrier,
        "carrier_from_live_rollout",
        lambda **_kwargs: (carrier, None),
    )
    monkeypatch.setattr(
        _supervisor_herdr_codex_successor._herdr_replacement_process,
        "proven_successor",
        lambda **_kwargs: None,
    )

    successor, reason = _supervisor_herdr_codex_successor._prove_successor(
        sup=sup, track=track, target="pane", current={}
    )

    assert successor is None
    assert reason == "Codex successor is not a fresh process in the retained shell"


def test_successor_stays_unproven_when_the_post_wait_index_lookup_is_empty(
    *, tmp_path, monkeypatch
) -> None:
    sup = SimpleNamespace(
        tmux=SimpleNamespace(capture_pane=lambda **_kwargs: "Codex idle"),
        sleep=lambda _seconds: None,
    )
    track = SimpleNamespace(topic="topic")
    monkeypatch.setattr(
        _supervisor_herdr_codex_successor.signals,
        "is_structured_gate",
        lambda **_kwargs: False,
    )
    monkeypatch.setattr(
        _supervisor_herdr_codex_successor.signals,
        "is_codex_idle_input",
        lambda **_kwargs: True,
    )
    monkeypatch.setattr(
        _supervisor_herdr_codex_successor._supervisor_herdr_codex_naming,
        "name_fresh_successor",
        lambda **_kwargs: True,
    )
    monkeypatch.setattr(
        _supervisor_herdr_codex_successor._supervisor_herdr_codex_naming,
        "named_thread",
        lambda **_kwargs: None,
    )

    reason = _supervisor_herdr_codex_successor._rename_successor(
        sup=sup,
        track=track,
        target="pane",
        current={"phase": "launch-attempted", "predecessor_rollout": OLD},
        record_path=tmp_path / "record.json",
        rollout=OLD,
    )

    assert reason == "fresh Codex successor was never named for this plan topic"


def test_agent_session_report_routes_only_to_the_coordinate_backend() -> None:
    target = herdr_identity.HerdrPaneTarget(
        socket_path="/tmp/herdr.sock",
        server_pid=700,
        server_starttime="start",
        pane_id="w1:p9",
    )
    calls = []
    writer = SimpleNamespace(
        report_agent_session=lambda **kwargs: calls.append(kwargs) or "reported"
    )
    host = SimpleNamespace(herdr_writer=writer)

    outcome = pane_router_replacement.report_agent_session(
        host,
        session=herdr_identity.encode_herdr_target(target=target),
        source="overseerd",
        agent_session_id=STALE,
    )

    assert outcome == "reported"
    assert calls == [{"target": target, "source": "overseerd", "agent_session_id": STALE}]
