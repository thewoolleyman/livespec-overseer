"""Beside-tests for `_supervisor_foreman_escalation.unbind_escalation`.

The daemon unbinds a live escalation from its seat when it performs a restart, so
the successor inherits an outstanding human decision instead of reading its
predecessor's marker as superseded. The integration tier owns the scenario; this
module owns the REFUSALS — the cases where unbinding must leave the marker exactly
as it is, each of which would otherwise silently rewrite an operator's file.

``import _supervisor_foreman_escalation`` resolves via conftest.py.
"""

import json

import _supervisor_foreman_escalation as foreman_escalation

__all__: list[str] = []


def _write(*, repo, topic, payload):
    path = foreman_escalation.escalation_path(repo=str(repo), topic=topic)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return path


def test_unbind_reports_no_change_for_an_absent_marker(*, tmp_path):
    assert foreman_escalation.unbind_escalation(repo=str(tmp_path), topic="no-such-topic") is False


def test_unbind_leaves_a_resolved_marker_alone(*, tmp_path):
    """A resolved marker is not a live escalation, so there is nothing to carry over."""
    payload = {"reason": "answered", "resolved": True, "session_identity": "claude:seat"}
    path = _write(repo=tmp_path, topic="resolved-topic", payload=payload)

    assert foreman_escalation.unbind_escalation(repo=str(tmp_path), topic="resolved-topic") is False
    assert json.loads(path.read_text(encoding="utf-8")) == payload


def test_unbind_leaves_an_unreadable_marker_alone(*, tmp_path):
    """Fail-soft: a marker we cannot parse is surfaced elsewhere, never rewritten here.

    Rewriting it would destroy whatever the operator actually wrote, which is the one
    copy of the reason a human still has to act on.
    """
    path = foreman_escalation.escalation_path(repo=str(tmp_path), topic="malformed-topic")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")

    assert (
        foreman_escalation.unbind_escalation(repo=str(tmp_path), topic="malformed-topic") is False
    )
    assert path.read_text(encoding="utf-8") == "{not json"


def test_unbind_is_idempotent_for_an_already_unbound_marker(*, tmp_path):
    """Already unbound is already correct — report no change rather than rewrite."""
    payload = {"reason": "still outstanding"}
    path = _write(repo=tmp_path, topic="unbound-topic", payload=payload)

    assert foreman_escalation.unbind_escalation(repo=str(tmp_path), topic="unbound-topic") is False
    assert json.loads(path.read_text(encoding="utf-8")) == payload


def test_unbind_drops_only_the_binding_and_keeps_the_reason(*, tmp_path):
    """The reason is the thing a human must still answer; only the seat binding goes."""
    payload = {"reason": "sixteen unanswered items", "session_identity": "claude:old-seat"}
    path = _write(repo=tmp_path, topic="bound-topic", payload=payload)

    assert foreman_escalation.unbind_escalation(repo=str(tmp_path), topic="bound-topic") is True

    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored == {"reason": "sixteen unanswered items"}
    assert (
        foreman_escalation.read_escalation(
            repo=str(tmp_path), topic="bound-topic", live_session_identity="claude:successor"
        )
        is not None
    )
