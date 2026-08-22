"""Typed-ruling relay mechanics for foreman consensus acts."""

from __future__ import annotations

import re
from pathlib import Path

import jsonio
import signals
import tmuxio
from foreman_act_revalidate import revalidate_identity, str_field
from foreman_act_types import HUMAN_VALVE, ActResult

__all__: list[str] = [
    "act_typed_ruling",
    "ruling_kind_defined",
]

_RULING_KIND_RE = re.compile(r"^\|\s*`([^`]+)`\s*\|")


def ruling_kind_defined(*, kind: str) -> bool:
    return kind in governed_ruling_kinds()


def governed_ruling_kinds() -> frozenset[str]:
    prose = _foreman_contract_path()
    if prose is None:  # pragma: no cover
        return frozenset()
    return _ruling_kinds_from_contract(text=prose.read_text(encoding="utf-8"))


def _foreman_contract_path() -> Path | None:
    here = Path(__file__).resolve()
    candidates = (
        here.parents[1] / "prose" / "foreman.md",
        here.parents[1] / ".claude-plugin" / "prose" / "foreman.md",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None  # pragma: no cover


def _ruling_kinds_from_contract(*, text: str) -> frozenset[str]:
    in_table = False
    kinds: set[str] = set()
    for line in text.splitlines():  # pragma: no branch
        if line.strip() == "| Ruling kind | Required structured fields | Execution |":
            in_table = True
            continue
        if not in_table:  # pragma: no branch
            continue
        if not line.startswith("|"):  # pragma: no cover
            break
        match = _RULING_KIND_RE.match(line)
        if match is not None:
            kind = match.group(1)
            if kind != "Ruling kind":  # pragma: no branch
                kinds.add(kind)
    return frozenset(kinds)


def act_typed_ruling(
    *,
    ruling: dict[str, object],
    proposal: dict[str, object],
    document: dict[str, object],
    repo: str,
) -> ActResult:
    _ = proposal
    action_id = HUMAN_VALVE
    kind = _str_field(payload=ruling, key="kind")
    if kind is None or not ruling_kind_defined(kind=kind):
        return _refused(  # pragma: no cover
            action_id=action_id, reason="consensus_ruling_not_enumerated"
        )
    if kind != "relay-to-session":  # pragma: no cover
        return _refused(action_id=action_id, reason="consensus_ruling_not_supported")
    refusal = _relay_refusal(ruling=ruling, proposal=proposal, document=document, repo=repo)
    if refusal is not None:
        return _refused(action_id=action_id, reason=refusal)  # pragma: no cover
    return _relay(action_id=action_id, ruling=ruling, repo=repo)


def _relay_refusal(
    *,
    ruling: dict[str, object],
    proposal: dict[str, object],
    document: dict[str, object],
    repo: str,
) -> str | None:
    if revalidate_identity(proposal=proposal, document=document) is not None:  # pragma: no cover
        return "session_identity_changed"
    shape_refusal = _ruling_shape_refusal(ruling=ruling)
    if shape_refusal is not None:  # pragma: no cover
        return shape_refusal
    return _ruling_target_refusal(ruling=ruling, proposal=proposal, document=document, repo=repo)


def _ruling_shape_refusal(*, ruling: dict[str, object]) -> str | None:
    missing = (
        _str_field(payload=ruling, key="message") is None
        or _str_field(payload=ruling, key="record_path") is None
    )
    return "malformed_typed_ruling" if missing else None  # pragma: no cover


def _ruling_target_refusal(
    *,
    ruling: dict[str, object],
    proposal: dict[str, object],
    document: dict[str, object],
    repo: str,
) -> str | None:
    if _str_field(payload=ruling, key="target_topic") != str_field(  # pragma: no cover
        payload=proposal, key="topic"
    ):
        return "typed_ruling_target_changed"
    if _str_field(payload=ruling, key="target_session_name") != str_field(  # pragma: no cover
        payload=proposal, key="session_name"
    ):
        return "typed_ruling_target_changed"
    row = _matching_row(
        document=document, repo=repo, topic=str_field(payload=proposal, key="topic")
    )
    if row is None:  # pragma: no cover
        return "session_identity_changed"
    if _str_field(payload=ruling, key="target_session_identity") != str_field(  # pragma: no cover
        payload=row, key="session_identity"
    ):
        return "session_identity_changed"
    return None


def _relay(*, action_id: str, ruling: dict[str, object], repo: str) -> ActResult:
    session = _str_field(payload=ruling, key="target_session_name") or ""
    message = _str_field(payload=ruling, key="message") or ""
    tmux = tmuxio.TmuxIO()
    pane = tmux.pane_id(session=session)
    if pane is None:  # pragma: no cover
        return _refused(action_id=action_id, reason="pane_unavailable")
    if not _runtime_matches(command=tmux.pane_current_command(session=pane)):  # pragma: no cover
        return _refused(action_id=action_id, reason="runtime_identity_changed")
    if not signals.path_in_repo(  # pragma: no cover
        pane_current_path=tmux.pane_current_path(session=pane), repo=repo
    ):
        return _refused(action_id=action_id, reason="cwd_identity_changed")  # pragma: no cover
    if not tmux.bracketed_paste(session=pane, text=message):  # pragma: no cover
        return _failed(action_id=action_id, reason="paste_failed")
    if not tmux.send_keys(session=pane, keys="Enter"):  # pragma: no cover
        return _failed(action_id=action_id, reason="submit_failed")
    return _acted(action_id=action_id, reason="typed_ruling_relayed")


def _matching_row(
    *, document: dict[str, object], repo: str, topic: str | None
) -> dict[str, object] | None:
    snapshot = jsonio.as_object(value=document.get("snapshot"))
    rows = jsonio.as_list(value=None if snapshot is None else snapshot.get("rows"))
    if rows is None or topic is None:  # pragma: no cover
        return None
    for raw in rows:
        row = jsonio.as_object(value=raw)
        if (  # pragma: no branch
            row is not None and row.get("repo") == repo and row.get("topic") == topic
        ):
            return row
    return None  # pragma: no cover


def _runtime_matches(*, command: str | None) -> bool:
    return signals.pane_is_claude(
        pane_current_command=command
    ) or signals.pane_is_codex(  # pragma: no branch
        pane_current_command=command
    )


def _str_field(*, payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value != "" else None


def _result(*, action_id: str, outcome: str, reason: str, mutated: bool) -> ActResult:
    return {
        "action_id": action_id,
        "mutated": mutated,
        "outcome": outcome,
        "reason": reason,
    }


def _refused(*, action_id: str, reason: str) -> ActResult:  # pragma: no cover
    return _result(action_id=action_id, outcome="refused", reason=reason, mutated=False)


def _acted(*, action_id: str, reason: str) -> ActResult:
    return _result(action_id=action_id, outcome="acted", reason=reason, mutated=True)


def _failed(*, action_id: str, reason: str) -> ActResult:  # pragma: no cover
    return _result(action_id=action_id, outcome="failed", reason=reason, mutated=False)
