"""Report-only attention for wait-premise targets that can no longer be found."""
# livespec-lloc-soft-band-owner: overseer-1a31.2.1

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import _supervisor_launch
import _supervisor_liveness
import _supervisor_wait_target_evidence
import _supervisor_wait_target_lifecycle
import _supervisor_wait_target_sources
import registry
import wait_premises
from _supervisor_view import MAX_REASON_IN_ALERT, elide
from _supervisor_wait_target_status import (
    WAIT_TARGET_EXPIRED_STATUS,
    WAIT_TARGET_MISSING_CONDITION,
    WAIT_TARGET_MISSING_STATUS,
    WAIT_TARGET_SATISFIED_STATUS,
)

if TYPE_CHECKING:
    from _supervisor_core import Supervisor
    from _supervisor_records import Observation, WaitTargetCacheEntry

__all__: list[str] = [
    "WAIT_TARGET_MISSING_CONDITION",
    "WAIT_TARGET_MISSING_STATUS",
    "WaitTargetMissingRequest",
    "WaitTargetMissingResult",
    "apply_wait_target_missing_attention",
]


@dataclass(frozen=True, kw_only=True)
class WaitTargetMissingResult:
    status: str
    note: str | None
    active_conditions: set[str]


@dataclass(frozen=True, kw_only=True)
class WaitTargetMissingRequest:
    sup: Supervisor
    track: registry.Track
    session: str
    pane: str
    status: str
    note: str | None
    obs: Observation
    active_conditions: set[str]
    act: bool


@dataclass(frozen=True, kw_only=True)
class _MissingPremise:
    """One premise that verified missing WITH a note, and where it was read.

    ``order`` is the premise's position in the directory read, kept only to
    break a tie between two premises recorded at the same instant so the choice
    of what to report stays deterministic.
    """

    record: dict[str, object]
    key: str
    note: str
    recorded_at: str
    order: int


def _unchanged(*, request: WaitTargetMissingRequest) -> WaitTargetMissingResult:
    return WaitTargetMissingResult(
        status=request.status,
        note=request.note,
        active_conditions=set(request.active_conditions),
    )


def _surface(*, request: WaitTargetMissingRequest, note: str) -> None:
    request.sup.alert(
        repo=request.track.repo,
        topic=request.track.topic,
        session=request.session,
        pane=request.pane,
        message=(
            f"{elide(text=note, limit=MAX_REASON_IN_ALERT)} - inspect the waiting "
            "session; report-only, no restart authorized"
        ),
        condition=WAIT_TARGET_MISSING_CONDITION,
    )


def _deliver_relay(
    *,
    request: WaitTargetMissingRequest,
    record: dict[str, object],
    key: str,
    note: str,
    repo: Path,
) -> None:
    if (
        key in request.obs.istate.wait_target_relayed_keys
        or not _supervisor_wait_target_lifecycle.relay_allowed(
            idle=request.obs.idle, busy=request.obs.busy, gate=request.obs.gate
        )
    ):
        return
    evidence_source = _supervisor_wait_target_sources.string_field(
        record=record, key="evidence_source"
    )
    path = _supervisor_wait_target_evidence.write_evidence(
        repo=repo,
        topic=request.track.topic,
        key=key,
        record=record,
        status=WAIT_TARGET_MISSING_STATUS,
        note=note,
    )
    if path is None:
        return
    text = _supervisor_wait_target_lifecycle.relay_text(
        record=record, note=note, evidence_path=path, evidence_source=evidence_source
    )
    if not _supervisor_launch.submit_prompt(
        sup=request.sup, target=request.pane, text=text, expect_codex=request.obs.is_codex
    ):
        return
    request.obs.istate.wait_target_relayed_keys.add(key)


def _lifecycle_status(
    *,
    request: WaitTargetMissingRequest,
    record: dict[str, object],
    entry: WaitTargetCacheEntry,
) -> str | None:
    if entry.status == WAIT_TARGET_SATISFIED_STATUS:
        return WAIT_TARGET_SATISFIED_STATUS
    if (
        entry.status == WAIT_TARGET_MISSING_STATUS
        and _supervisor_wait_target_lifecycle.expired_and_no_longer_waiting(
            status=request.status, observed_at=request.obs.observed_at, record=record
        )
    ):
        return WAIT_TARGET_EXPIRED_STATUS
    return None


def _cleared_by_lifecycle(
    *,
    request: WaitTargetMissingRequest,
    repo: Path,
    record: dict[str, object],
    key: str,
    entry: WaitTargetCacheEntry,
) -> bool:
    status = _lifecycle_status(request=request, record=record, entry=entry)
    if status is None:
        return False
    request.obs.istate.wait_target_relayed_keys.discard(key)
    _supervisor_wait_target_lifecycle.clear_premise_with_evidence(
        repo=repo,
        topic=request.track.topic,
        record=record,
        key=key,
        status=status,
        write_evidence=_supervisor_wait_target_evidence.write_evidence,
    )
    return True


def _evict_orphan_cache_entries(
    *, cache: dict[str, WaitTargetCacheEntry], live_keys: set[str]
) -> None:
    """Drop cache entries for premises that are no longer on disk.

    The key is the record's whole JSON, so ANY field change mints a new one, and
    the lifecycle now REMOVES a satisfied or expired premise from disk outright
    — nothing else ever evicted an entry, so a long-lived daemon accumulated one
    per distinct record it had ever seen, including records deleted long ago.
    Evicting in the same pass that reads the premise directory bounds the cache
    by the premise set: the keys kept are exactly the premises this pass read
    and did not clear.
    """
    for key in [key for key in cache if key not in live_keys]:
        del cache[key]


def _verify_every_premise(
    *, request: WaitTargetMissingRequest, repo: Path, records: list[dict[str, object]]
) -> list[_MissingPremise]:
    """Verify EVERY premise on the track and return the ones that are missing.

    This pass used to RETURN at the first premise that verified missing with a
    note, and three things followed. A second evaporated target was never
    verified at all that tick, so it got no cache entry and no evidence record;
    the relay could only ever fire for the first one; and because every
    ``wait_target_relayed_keys.discard`` call sits inside this walk, a premise
    that recovered while an earlier one was still missing kept its relayed mark
    forever — there is no other clearing path in the module. Walking every
    premise first, and deciding what to REPORT afterwards, makes all three
    independent of the order the premise directory happens to be read in.
    """
    cache = request.obs.istate.wait_target_cache
    live_keys: set[str] = set()
    missing: list[_MissingPremise] = []
    for order, record in enumerate(records):
        key = _supervisor_wait_target_sources.cache_key(record=record)
        entry = _supervisor_wait_target_sources.verify_wait_target_record(
            repo=repo, record=record, cache=cache.get(key), now=request.obs.observed_at
        )
        cache[key] = entry
        if _cleared_by_lifecycle(request=request, repo=repo, record=record, key=key, entry=entry):
            continue
        live_keys.add(key)
        if entry.status != WAIT_TARGET_MISSING_STATUS or entry.note is None:
            request.obs.istate.wait_target_relayed_keys.discard(key)
            continue
        missing.append(
            _MissingPremise(
                record=record,
                key=key,
                note=entry.note,
                recorded_at=_supervisor_wait_target_sources.string_field(
                    record=record, key="recorded_at"
                )
                or "",
                order=order,
            )
        )
    _evict_orphan_cache_entries(cache=cache, live_keys=live_keys)
    return missing


def _reported_premise(*, missing: list[_MissingPremise]) -> _MissingPremise:
    """Choose the ONE missing premise the row's single status and note name.

    THE RULE IS OLDEST-RECORDED-FIRST, ties broken by read order. A row carries
    one status and one note, so exactly one premise can be named there — but the
    premise that won used to be whichever the directory listing reached first,
    and ``wait_premise_path`` names files ``<kind>-<target>-<digest>.json``, so
    that was a digest of the target id: arbitrary, not the oldest, the most
    urgent, or the first declared. The oldest declaration is the wait that has
    gone unanswered longest, which is the one an operator most needs named.

    ``read_wait_premises`` drops any record whose ``recorded_at`` is not a valid
    timestamp, so the empty-string fallback below is a type guard rather than a
    rule about undated premises; it cannot be reached from a record this pass
    was given.
    """
    return min(missing, key=lambda premise: (premise.recorded_at, premise.order))


def apply_wait_target_missing_attention(
    *, request: WaitTargetMissingRequest
) -> WaitTargetMissingResult:
    repo = Path(request.track.repo)
    records = wait_premises.read_wait_premises(repo=request.track.repo, topic=request.track.topic)
    missing = _verify_every_premise(request=request, repo=repo, records=records)
    if not missing:
        return _unchanged(request=request)
    reported = _reported_premise(missing=missing)
    if request.act:  # pragma: no branch
        _surface(request=request, note=reported.note)
        for premise in missing:
            _deliver_relay(
                request=request,
                record=premise.record,
                key=premise.key,
                note=premise.note,
                repo=repo,
            )
    return WaitTargetMissingResult(
        status=WAIT_TARGET_MISSING_STATUS,
        note=_supervisor_liveness.append_note(note=request.note, extra=reported.note),
        active_conditions={*request.active_conditions, WAIT_TARGET_MISSING_CONDITION},
    )
