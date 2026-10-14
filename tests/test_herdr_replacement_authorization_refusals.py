"""Specific diagnostics for failures at the Herdr authorization boundary."""

from __future__ import annotations

from types import SimpleNamespace

import _herdr_replacement_authorization
import herdr_identity
import signals
from _supervisor_launch_profile import ClaudeLaunchPlan
from test_supervisor_builders import FakeTmux, make_plan, make_supervisor, mapped_track


def test_bind_refusal_names_the_specific_failed_condition(*, tmp_path, monkeypatch) -> None:
    repo, topic = make_plan(tmp_path=tmp_path)
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())
    track = mapped_track(repo=repo, topic=topic, session="pane")
    target = herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path=str(tmp_path / "herdr.sock"),
            server_pid=700,
            server_starttime="server-start",
            pane_id="w1:p9",
        )
    )
    identity = f"claude:201:old-start:{topic}"
    ready = SimpleNamespace(token=signals.STATE_READY, mtime=1001.0)
    cases = {
        "round closed": (
            SimpleNamespace(at=None, malformed_reason=None, session_identity=None),
            ready,
        ),
        "round malformed": (
            SimpleNamespace(
                at=None,
                malformed_reason="missing or non-numeric injection stamp",
                session_identity=None,
            ),
            ready,
        ),
        "round identity missing": (
            SimpleNamespace(
                at=1000.0,
                malformed_reason="round record missing session identity",
                session_identity=None,
            ),
            ready,
        ),
        "declaration no longer ready": (
            SimpleNamespace(at=1000.0, malformed_reason=None, session_identity=identity),
            SimpleNamespace(token=signals.STATE_BLOCKED, mtime=1001.0),
        ),
    }
    observed = {}
    for condition, (round_record, declaration) in cases.items():
        monkeypatch.setattr(
            _herdr_replacement_authorization.registry,
            "read_round_record",
            lambda *, _record=round_record, **kwargs: _record,
        )
        monkeypatch.setattr(
            _herdr_replacement_authorization.signals,
            "read_state",
            lambda *, _declaration=declaration, **kwargs: _declaration,
        )
        transaction, reason = _herdr_replacement_authorization.bind_authorization(
            sup=sup,
            track=track,
            target=target,
            launch=ClaudeLaunchPlan(command="claude", env={}),
            snapshot=SimpleNamespace(),
        )
        assert transaction is None
        observed[condition] = reason

    assert observed == {
        "round closed": "round closed before durable binding",
        "round malformed": (
            "round malformed before durable binding: missing or non-numeric injection stamp"
        ),
        "round identity missing": "round identity missing before durable binding",
        "declaration no longer ready": "ready declaration no longer ready before durable binding",
    }
