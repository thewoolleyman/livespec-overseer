"""Mechanics for answering an existing blocked pane prompt under a foreman claim."""

from __future__ import annotations

import foreman_gate_state
import foreman_pane_claim
import jsonio
import signals
import tmuxio
from foreman_act_revalidate import str_field
from foreman_act_types import BLOCKED_SESSION_ANSWER, ActResult

__all__: list[str] = ["act_blocked_session_answer"]

_CLAIM_TTL_SECONDS = foreman_pane_claim.CLAIM_TTL_SECONDS


def _result(*, outcome: str, reason: str, mutated: bool) -> ActResult:
    return {
        "action_id": BLOCKED_SESSION_ANSWER,
        "mutated": mutated,
        "outcome": outcome,
        "reason": reason,
    }


def _refused(*, reason: str) -> ActResult:
    return _result(outcome="refused", reason=reason, mutated=False)


def _acted(*, reason: str) -> ActResult:
    return _result(outcome="acted", reason=reason, mutated=True)


def _failed(*, reason: str) -> ActResult:  # pragma: no cover
    return _result(outcome="failed", reason=reason, mutated=False)


def _matching_row(
    *, document: dict[str, object], repo: str, topic: str
) -> dict[str, object] | None:
    snapshot = jsonio.as_object(value=document.get("snapshot"))
    rows = jsonio.as_list(value=None if snapshot is None else snapshot.get("rows"))
    if rows is None:  # pragma: no cover
        return None
    for raw in rows:  # pragma: no branch
        row = jsonio.as_object(value=raw)
        if (  # pragma: no branch
            row is not None and row.get("repo") == repo and row.get("topic") == topic
        ):
            return row
    return None  # pragma: no cover


def _answer_payload(*, proposal: dict[str, object]) -> dict[str, object] | None:
    return jsonio.as_object(value=proposal.get(BLOCKED_SESSION_ANSWER))


def _answer_text(*, payload: dict[str, object]) -> str | None:
    value = payload.get("answer_text")
    return value if isinstance(value, str) and value.strip() else None


def _question_fingerprint(*, payload: dict[str, object]) -> str | None:
    value = payload.get("question_fingerprint")
    return value if isinstance(value, str) and value.strip() else None


def _runtime_matches(*, runtime: str, command: str | None) -> bool:
    if runtime == "claude":
        return signals.pane_is_claude(pane_current_command=command)
    if runtime == "codex":  # pragma: no cover
        return signals.pane_is_codex(pane_current_command=command)
    return False  # pragma: no cover


def _answer_refusal(
    *, proposal: dict[str, object], document: dict[str, object], repo: str
) -> tuple[str | None, dict[str, object] | None, dict[str, object] | None]:
    topic = str_field(payload=proposal, key="topic")
    session = str_field(payload=proposal, key="session_name")
    payload = _answer_payload(proposal=proposal)
    reason = None
    row = None if topic is None else _matching_row(document=document, repo=repo, topic=topic)
    if topic is None or session is None or payload is None or row is None:  # pragma: no cover
        reason = "malformed_blocked_answer"
    elif payload.get("mode") == "dismiss_and_represent":
        reason = "marker_protocol_unratified"
    elif payload.get("mode") != "answer_existing_prompt":  # pragma: no cover
        reason = "unsupported_blocked_answer_mode"
    elif row.get("status") != "blocked:human":  # pragma: no cover
        reason = "pane_not_blocked_human"
    elif _answer_text(payload=payload) is None:  # pragma: no cover
        reason = "malformed_blocked_answer"
    elif _question_fingerprint(payload=payload) != row.get(
        "question_fingerprint"
    ):  # pragma: no cover
        reason = "question_fingerprint_changed"
    return reason, payload, row


def _pane_refusal(*, tmux: tmuxio.PaneDriver, pane: str, runtime: str, repo: str) -> str | None:
    if not _runtime_matches(  # pragma: no cover
        runtime=runtime, command=tmux.pane_current_command(session=pane)
    ):
        return "runtime_identity_changed"
    if not signals.path_in_repo(  # pragma: no cover
        pane_current_path=tmux.pane_current_path(session=pane), repo=repo
    ):
        return "cwd_identity_changed"
    if tmux.capture_pane(session=pane) != tmux.capture_pane(session=pane):  # pragma: no cover
        return "pane_not_settled"
    return None


def _claim(
    *, session: str, pane: str, runtime: str, session_identity: str, question_fingerprint: str
) -> foreman_pane_claim.PaneClaim:
    now = foreman_pane_claim.time_time()
    return foreman_pane_claim.PaneClaim(
        owner="foreman",
        session=session,
        pane=pane,
        runtime=runtime,
        session_identity=session_identity,
        question_fingerprint=question_fingerprint,
        acquired_at=now,
        expires_at=now + _CLAIM_TTL_SECONDS,
    )


def _persist_gate_state(*, repo: str, topic: str, state: foreman_gate_state.GateState) -> None:
    foreman_gate_state.persist_gate_state(
        repo=repo,
        topic=topic,
        state=state,
    )


def act_blocked_session_answer(
    *, proposal: dict[str, object], document: dict[str, object], repo: str
) -> ActResult:
    reason, payload, row = _answer_refusal(proposal=proposal, document=document, repo=repo)
    if reason is not None or payload is None or row is None:
        return _refused(reason=reason or "malformed_blocked_answer")
    topic = str_field(payload=proposal, key="topic") or ""
    session = str_field(payload=proposal, key="session_name") or ""
    runtime = str_field(payload=row, key="runtime") or ""
    answer_text = _answer_text(payload=payload) or ""
    fp = _question_fingerprint(payload=payload) or ""
    session_identity = str_field(payload=row, key="session_identity") or ""
    tmux = tmuxio.TmuxIO()
    pane = tmux.pane_id(session=session)
    if pane is None:  # pragma: no cover
        return _refused(reason="pane_unavailable")
    pane_refusal = _pane_refusal(tmux=tmux, pane=pane, runtime=runtime, repo=repo)
    if pane_refusal is not None:  # pragma: no cover
        return _refused(reason=pane_refusal)
    foreman_pane_claim.write_pane_claim(
        repo=repo,
        topic=topic,
        claim=_claim(
            session=session,
            pane=pane,
            runtime=runtime,
            session_identity=session_identity,
            question_fingerprint=fp,
        ),
    )
    try:
        _persist_gate_state(
            repo=repo,
            topic=topic,
            state=foreman_gate_state.GateState(
                runtime=runtime,
                pane=pane,
                capture=tmux.capture_pane(session=pane),
                question_text=answer_text,
                question_fingerprint=fp,
            ),
        )
        if not tmux.bracketed_paste(session=pane, text=answer_text):  # pragma: no cover
            return _failed(reason="paste_failed")
        if not tmux.send_keys(session=pane, keys="Enter"):  # pragma: no cover
            return _failed(reason="submit_failed")
        return _acted(reason="answered_existing_prompt")
    finally:
        foreman_pane_claim.clear_pane_claim(repo=repo, topic=topic)
