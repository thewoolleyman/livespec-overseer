"""Report-only attention for unmet foreman convene obligations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import foreman_gather_evidence
import foreman_valve_policy
import jsonio
import registry
from _supervisor_liveness_time import age_label, append_note

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "CONSENSUS_OVERDUE_STATUS",
    "ConsensusOverdueDecision",
    "ConsensusOverdueRequest",
    "consensus_overdue_decision",
]

CONSENSUS_OVERDUE_STATUS = "consensus-overdue"
_CONVENE_BOUND_SECONDS = 30 * 60
_FOREMAN_STATE = Path("tmp") / "overseer" / "foreman"
_FLOOR_CATEGORIES = frozenset({"truly-unresolvable", "human-gated-by-design"})


@dataclass(frozen=True, kw_only=True)
class ConsensusOverdueDecision:
    status: str
    note: str
    active_conditions: set[str]


@dataclass(frozen=True, kw_only=True)
class ConsensusOverdueRequest:
    sup: Supervisor
    track: registry.Track
    session: str
    pane: str
    capture: str
    blocked_age: float | None
    note: str | None
    act: bool


def _read_json_file(*, path: Path) -> dict[str, object] | None:
    parsed = jsonio.parse_object(text=path.read_text(encoding="utf-8"))
    return None if jsonio.is_parse_failure(result=parsed) else parsed.unwrap()


def _json_files(*, root: Path) -> list[Path]:
    return [] if not root.is_dir() else [path for path in sorted(root.rglob("*.json"))]


def _record_fingerprint(*, record: dict[str, object]) -> str | None:
    value = record.get("question_fingerprint")
    if isinstance(value, str) and value != "":
        return value
    request = jsonio.as_object(value=record.get("request")) or {}
    nested = request.get("question_fingerprint")
    return nested if isinstance(nested, str) and nested != "" else None


def _matching_json_record(*, root: Path, question_fingerprint: str) -> dict[str, object] | None:
    for path in _json_files(root=root):
        record = _read_json_file(path=path)
        if record is not None and _record_fingerprint(record=record) == question_fingerprint:
            return record
    return None


def _obligation_record(
    *, repo: Path, topic: str, question_fingerprint: str
) -> dict[str, object] | None:
    return _matching_json_record(
        root=repo / _FOREMAN_STATE / "convene-obligations" / topic,
        question_fingerprint=question_fingerprint,
    )


def _consensus_artifact_exists(*, repo: Path, topic: str, question_fingerprint: str) -> bool:
    roots = (
        repo / _FOREMAN_STATE / "panels" / topic,
        repo / _FOREMAN_STATE / "consensus",
        repo / _FOREMAN_STATE / "convene-escalations" / topic,
        repo / _FOREMAN_STATE / "convene-discharges" / topic,
    )
    return any(
        _matching_json_record(root=root, question_fingerprint=question_fingerprint) is not None
        for root in roots
    )


def _observed_at(*, record: dict[str, object]) -> float | None:
    value = record.get("observed_at_epoch")
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _human_valve_category(*, record: dict[str, object]) -> str | None:
    valve = jsonio.as_object(value=record.get("human_valve")) or {}
    value = valve.get("category")
    return value if isinstance(value, str) and value != "" else None


def _obligation_applies(*, record: dict[str, object]) -> bool:
    action_id = record.get("action_id")
    category = _human_valve_category(record=record)
    return (
        isinstance(action_id, str)
        and action_id != "human_valve"
        and category not in (_FLOOR_CATEGORIES)
    )


def _consensus_overdue_note(
    *, topic: str, question_fingerprint: str, elapsed: float, note: str | None
) -> str:
    extra = (
        f"unmet convene obligation {age_label(seconds=elapsed)}: "
        f"{topic} question_fingerprint={question_fingerprint[:12]}"
    )
    return append_note(note=note, extra=extra) or extra


def _elapsed(*, request: ConsensusOverdueRequest, record: dict[str, object]) -> float:
    observed_at = _observed_at(record=record)
    return request.blocked_age or 0.0 if observed_at is None else request.sup.now() - observed_at


def consensus_overdue_decision(
    *, request: ConsensusOverdueRequest
) -> ConsensusOverdueDecision | None:
    repo = Path(request.track.repo)
    if foreman_valve_policy.effective_valve_disposition(repo=repo).get("effective") != (
        foreman_valve_policy.CONSENSUS
    ):
        return None
    question_fingerprint = foreman_gather_evidence.pane_content_hash(text=request.capture)
    obligation = _obligation_record(
        repo=repo, topic=request.track.topic, question_fingerprint=question_fingerprint
    )
    if obligation is None or not _obligation_applies(record=obligation):
        return None
    elapsed = _elapsed(request=request, record=obligation)
    if elapsed < _CONVENE_BOUND_SECONDS or _consensus_artifact_exists(
        repo=repo, topic=request.track.topic, question_fingerprint=question_fingerprint
    ):
        return None
    note = _consensus_overdue_note(
        topic=request.track.topic,
        question_fingerprint=question_fingerprint,
        elapsed=elapsed,
        note=request.note,
    )
    if request.act:  # pragma: no branch
        request.sup.alert(
            repo=request.track.repo,
            topic=request.track.topic,
            session=request.session,
            pane=request.pane,
            message=(
                f"consensus overdue ({age_label(seconds=elapsed)}): "
                f"{request.track.topic} question_fingerprint={question_fingerprint[:12]}"
            ),
            condition=CONSENSUS_OVERDUE_STATUS,
        )
    return ConsensusOverdueDecision(
        status=CONSENSUS_OVERDUE_STATUS,
        note=note,
        active_conditions={CONSENSUS_OVERDUE_STATUS},
    )
