"""_supervisor_restart — the restart and wind-down injection mechanics.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. Reached ONLY from the cascade's `ready` and low-context legs, and
RUNTIME-DISPATCHED: a Codex track routes to `codex resume <id>`, never the claude
launch command, because aiming `claude -n <topic>` at a codex pane would replace
the codex session with a claude one and destroy it.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, cast

import _supervisor_launch
import _supervisor_ready
import _supervisor_state
import registry
import signals
from _supervisor_codex_restart import do_codex_restart
from _supervisor_config import track_key
from _supervisor_prompts import (
    resume_for_track,
    supervisor_epic_path,
    supervisor_handoff_path,
    supervisor_wrapup_message,
    wrapup_message,
)

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "do_codex_restart",
    "do_restart",
    "maybe_inject",
    "missing_plan_epic_message",
    "rederive_epic_if_stale",
    "resume_prompt",
]


def missing_plan_epic_message() -> str:
    """Surface text for a ready track whose mapping row lacks the plan epic locator."""
    return "ready cannot respawn: no plan epic recorded"


def _supervisor_topic_archived_message() -> str:
    """Surface text for a supervisor ready declaration whose plan thread is archived/gone."""
    return (
        "supervisor ready declared but its plan thread is archived or gone; "
        "retiring the track, not restarting"
    )


def rederive_epic_if_stale(*, sup: Supervisor, track: registry.Track, act: bool) -> registry.Track:
    """One-shot re-derive of a null epic at the restart-interlock boundary.

    A row's epic can go stale between assignment time (``supervisor.py add``)
    and a later ``ready`` declaration (overseer-vbmq): the anchor was
    unreadable when the row was added, was written afterward, or a transient
    ledger outage hit the fallback query. The daemon tick otherwise never
    re-reads ``epic_from_plan_anchor`` itself (assignment-only, by design), so a
    stale null stays null forever without this. The caller invokes this ONLY
    after finding the track unusable for a restart (``resume_prompt`` returned
    None) — never speculatively — and only under ``act`` (never on a read-only
    ``list`` tick). Persists on success (``registry.record_derived_epic``) so a
    later tick sees the healed row directly; this never re-reads per tick.
    """
    if not act:
        return track
    derived = registry.epic_from_plan_anchor(repo=track.repo, topic=track.topic)
    if derived is None:
        return track
    _ = registry.record_derived_epic(
        repo=track.repo, topic=track.topic, epic=derived, store_path=sup.store_path
    )
    return dataclasses.replace(track, epic=derived)


def resume_prompt(*, track: registry.Track) -> str | None:
    """Return the runtime resume prompt, or None when a normal track lacks its epic.

    Thin alias for :func:`_supervisor_prompts.resume_for_track`, kept because the restart
    mechanics are this module's surface and its callers name it here. The derivation
    itself lives beside the text it builds, so the relaunch and attention paths share one
    definition with the restart rather than each carrying their own.
    """
    return resume_for_track(track=track)


def _migrated_supervisor_epic_certifies(*, track: registry.Track) -> bool:
    """Return whether the retired-file shape is replaced by a ledger-bound binder."""
    path = supervisor_epic_path(
        repo=track.repo, topic=signals.supervisor_topic(entity_topic=track.topic)
    )
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return False
    lowered = text.lower()
    names_epic = track.epic is not None and track.epic in text
    names_ledger = "ledger" in lowered
    return names_epic and names_ledger


def _supervisor_resume_artifact_certifies(*, track: registry.Track) -> bool:
    """Accept either the legacy file artifact or the migrated ledger-backed shape."""
    topic = signals.supervisor_topic(entity_topic=track.topic)
    if supervisor_handoff_path(repo=track.repo, topic=topic).exists():
        return True
    return _migrated_supervisor_epic_certifies(track=track)


def _handle_uncertified_supervisor_binder(
    *, sup: Supervisor, track: registry.Track, target: str
) -> bool:
    """Alert (and report True) when a supervisor track's binder cannot certify a restart.

    Returns False, with NO side effect, when the track is not a supervisor entity or its
    binder certifies — the ordinary case, where :func:`do_restart` proceeds to the actual
    respawn. This is the only reason for it to exist as its own function: folding its body
    back into :func:`do_restart` would push that function's return-statement count over the
    lint ceiling (PLR0911).

    **Branches on WHY the binder is absent (overseer-y26).** ``registry.archived_or_gone``
    is a DIRECTORY-level test, spec-permitted for the daemon to consult (it never opens a
    file under ``plan/``): when the plan thread was archived or deleted, the missing binder
    is EXPECTED, not anomalous, so the round is closed with a terminal, non-"missing-file"
    alert and no restart is attempted — that wording is exactly what taught a prior
    supervisor (livespec-dev-tooling, 2026-08-04) to restore a banned tombstone 13 hours
    after the ban, believing the daemon was pointing at a genuinely lost file. Only a
    genuinely LIVE plan directory with no binder keeps today's ``supervisor-handoff-missing``
    alert — that case IS anomalous, and the round is left open (unchanged) so it keeps
    reporting until a human intervenes.
    """
    if not (
        signals.topic_reserved_for_supervisor(topic=track.topic)
        and not _supervisor_resume_artifact_certifies(track=track)
    ):
        return False
    if registry.archived_or_gone(
        repo=track.repo, topic=signals.supervisor_topic(entity_topic=track.topic)
    ):
        # Close the round instead of leaving a `ready` marker that re-reaches this branch
        # every tick — archive_gc ordinarily drops the mapping row in the SAME tick before
        # `do_restart` is ever reached; this only covers that narrow same-tick race.
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=_supervisor_launch.session_of(sup=sup, track=track),
            pane=target,
            message=_supervisor_topic_archived_message(),
            condition="supervisor-topic-archived",
        )
        _supervisor_state.clear_state(sup=sup, track=track)
        return True
    sup.alert(
        repo=track.repo,
        topic=track.topic,
        session=_supervisor_launch.session_of(sup=sup, track=track),
        pane=target,
        message="supervisor ready declared but supervisor-handoff.md is missing; not restarting",
        condition="supervisor-handoff-missing",
    )
    return True


def maybe_inject(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    eff_ctx: int,
    threshold: int,
    is_codex: bool = False,
) -> None:
    """Escalating, spam-proof wrap-up injection: warn once per crossed band.

    The bands are the effective ``threshold`` plus each lower 10%-band below it
    (40 / 30 / 20 / 10). A band fires at most ONCE per round: the set of
    already-notified bands is DURABLE (the injection-stamp sidecar), so a
    daemon restart never re-spams a band it already sent. Multiple bands crossed
    in one tick coalesce into a SINGLE message but mark ALL of them notified.

    ``target`` is the resolved pane id (RB3). The round's ``at`` stamp is
    written ONLY when OPENING the round (the first band of the round) — a
    re-warn at a lower band does NOT rewrite it, so a ready marker the session
    writes still has ``mtime > at`` and certifies, and re-warns never reset the
    notified bands. On a paste failure that OPENED the round, the just-opened
    round is rolled back (stamp cleared) so the next tick retries cleanly (B5).

    ``is_codex`` selects the runtime-appropriate submit verification — this is the
    change that makes the escalating wrap-up (the daemon's ONLY lever now that
    nothing is force-killed) reach a Codex track, not just a Claude one.
    """
    repo, topic = track.repo, track.topic
    bands = sorted({threshold} | {b for b in (40, 30, 20, 10) if b < threshold}, reverse=True)
    notified = set(registry.read_notified_bands(repo=repo, topic=topic, stamp_path=sup.stamp_path))
    due = [b for b in bands if eff_ctx <= b and b not in notified]
    if not due:
        return
    round_record = registry.read_round_record(repo=repo, topic=topic, stamp_path=sup.stamp_path)
    opened_now = round_record.at is None or round_record.malformed_reason is not None
    if opened_now:
        # Stamp BEFORE the paste (design) so a marker the session writes has
        # mtime > at. Only on opening — a re-warn preserves the round's at.
        session = _supervisor_launch.session_of(sup=sup, track=track)
        runtime = "codex" if is_codex else "claude"
        identity = _supervisor_ready.session_identity(
            sup=sup, session=session, topic=topic, runtime=runtime
        )
        if identity is None:
            sup.alert(
                repo=repo,
                topic=topic,
                session=session,
                pane=target,
                message="wrap-up round NOT opened; session identity could not be determined",
                condition="round-identity-undetermined",
            )
            return
        registry.write_injection_stamp(
            repo=repo,
            topic=topic,
            ts=sup.now(),
            session_identity=identity,
            stamp_path=sup.stamp_path,
        )
    if signals.topic_reserved_for_supervisor(topic=topic):
        message = supervisor_wrapup_message(
            remaining=eff_ctx,
            repo=repo,
            topic=signals.supervisor_topic(entity_topic=topic),
            epic=track.epic,
        )
    else:
        message = wrapup_message(remaining=eff_ctx, repo=repo, topic=topic, epic=track.epic)
    if _supervisor_launch.submit_prompt(
        sup=sup, target=target, text=message, expect_codex=is_codex
    ):
        for b in due:
            registry.add_notified_band(repo=repo, topic=topic, band=b, stamp_path=sup.stamp_path)
        sup.log(message=f"injected wrap-up into {repo}::{topic} (ctx {eff_ctx}%, bands {due})")
    else:
        if opened_now:
            # Roll back the just-opened round so the next tick retries cleanly.
            registry.clear_injection_stamp(repo=repo, topic=topic, stamp_path=sup.stamp_path)
        sup.alert(
            repo=repo,
            topic=topic,
            session=_supervisor_launch.session_of(sup=sup, track=track),
            pane=target,
            message="wrap-up injection FAILED (paste did not land); will retry",
        )


def do_restart(
    *, sup: Supervisor, track: registry.Track, target: str, is_codex: bool = False
) -> None:
    """Atomic restart, RUNTIME-DISPATCHED: respawn → wait for the TUI → resume → close.

    ``target`` is the resolved pane id (RB3), STABLE across the respawn.

    There is exactly ONE caller and exactly one authorization: the session itself
    declared ``ready`` in its state file (``signals.ready_valid``). The daemon has
    no other path to a restart — it never decides a session is done (maintainer
    2026-07-14). The abrupt ``respawn-pane -k`` is safe precisely BECAUSE of that
    declaration: the session asserted it is at a clean stopping point.

    **The one destructive bug this daemon can have** is aiming the CLAUDE launch
    command at a Codex pane — it would REPLACE the codex session with a claude one.
    ``is_codex`` routes a Codex track to :meth:`_do_codex_restart` (``codex resume``)
    so the claude command is never issued to a codex pane; the sabotage-verified
    guard test (``…never issues the claude command``) pins that the routing holds.

    Every tmux step is a HARD GATE (B5). If ``respawn-pane`` fails, the daemon
    SURFACES the failure and RETURNS WITHOUT closing the round — nothing was killed,
    so the session's declaration is preserved and the restart is retried. If the
    respawn succeeds but the recognition poll times out, the one kill authorization
    has already been consumed: the daemon keeps the open round but marks
    ``resume_pending`` so the next tick can recover without a second respawn.

    **The submit is SELF-HEALING (R1, 2026-07-18).** The round is closed (state file
    deleted + injection stamp cleared — B4) ONLY when the resume line actually SUBMITS.
    A freshly-respawned TUI can DROP the Enter while still drawing its welcome screen,
    leaving the fresh session live but idle with an un-run resume prompt (proven live
    2026-07-17). On that failure this does NOT clear the marker or log "restarted" —
    it marks a round-scoped ``resume_pending`` (``registry.set_resume_pending``) and
    alerts, and the NEXT tick's ``evaluate`` retries the SUBMIT ONLY (``_resend_enter``
    — never a re-respawn; a fresh ``ready`` stays the sole respawn trigger, so the retry
    can never escalate to a kill). Separating "is the fresh Claude up?" from "did the
    resume submit?" is the fix for the discarded-marker bug where the old code cleared
    the marker and reported success regardless. On the SUCCESS path ``_clear_state``
    also pops the in-memory inject state (RB2), so the redundant explicit pop is
    belt-and-suspenders.

    **A supervisor track whose binder is absent is handled by
    :func:`_handle_uncertified_supervisor_binder` (overseer-y26)** — see that function's
    docstring for the archived-vs-live branch.
    """
    if _handle_uncertified_supervisor_binder(sup=sup, track=track, target=target):
        return
    if is_codex:
        do_codex_restart(sup=sup, track=track, target=target)
        return
    if not sup.tmux.respawn_pane(
        session=target, cwd=track.repo, command=_supervisor_launch.launch_command(track=track)
    ):
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=_supervisor_launch.session_of(sup=sup, track=track),
            pane=target,
            message="restart respawn FAILED; keeping the ready declaration so it retries",
        )
        return
    if not _supervisor_launch.await_pane(sup=sup, target=target, is_ready=signals.pane_is_claude):
        registry.set_resume_pending(repo=track.repo, topic=track.topic, stamp_path=sup.stamp_path)
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=_supervisor_launch.session_of(sup=sup, track=track),
            pane=target,
            message="respawned pane never became Claude; will retry resume without respawn",
        )
        return
    # Wait for the fresh TUI to finish its FIRST paint and render a ready (empty)
    # input box before pasting — a half-drawn welcome/news screen DROPS the Enter,
    # which is exactly what stranded resumes live (2026-07-17). Best-effort: if the
    # box never appears in time, proceed anyway and let the submit-retry below (and
    # the next tick's `resume_pending` retry) recover.
    _ = _supervisor_launch.await_input_box(sup=sup, target=target)
    # If the fresh TUI came up on a picker (a trust / update / bypass-permissions
    # gate), NEVER keystroke into it (blocker #6) — pasting + Enter would auto-accept
    # its default. Defer to the `resume_pending` retry, which reports the gate as
    # `blocked:human` and resumes once the human clears it (review SF4).
    fresh_capture = sup.tmux.capture_pane(session=target)
    if signals.is_structured_gate(capture_text=fresh_capture):
        registry.set_resume_pending(repo=track.repo, topic=track.topic, stamp_path=sup.stamp_path)
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=_supervisor_launch.session_of(sup=sup, track=track),
            pane=target,
            message="freshly-restarted pane is on a gate — not keystroking it; will retry",
        )
        return
    resume = cast(str, resume_prompt(track=track))
    registry.record_post_respawn(
        repo=track.repo,
        topic=track.topic,
        ctx=signals.parse_ctx_remaining(capture_text=fresh_capture),
        resume=resume,
        stamp_path=sup.stamp_path,
    )
    if _supervisor_launch.submit_prompt(sup=sup, target=target, text=resume):
        _supervisor_state.clear_state(sup=sup, track=track)
        _ = sup.inject.pop(track_key(repo=track.repo, topic=track.topic), None)
        sup.log(message=f"restarted {track.repo}::{track.topic} (pane {target})")
        return
    # The fresh Claude IS up, but the resume line did not submit (the fresh TUI
    # dropped the Enter). Separate the two facts the old code conflated — "is the
    # fresh Claude up?" (yes) and "did the resume submit?" (no) — and DO NOT give up:
    # keep the `ready` marker + stamp, record a round-scoped `resume_pending`, and let
    # the NEXT tick retry the SUBMIT ONLY (re-send Enter, never a re-respawn — a fresh
    # `ready` is the sole respawn trigger, so the retry can never escalate to a kill).
    # Never log a clean "restarted" here; the alert is edge-triggered and persists (the
    # row stays NEEDS-YOU) until the resume actually submits.
    registry.set_resume_pending(repo=track.repo, topic=track.topic, stamp_path=sup.stamp_path)
    sup.alert(
        repo=track.repo,
        topic=track.topic,
        session=_supervisor_launch.session_of(sup=sup, track=track),
        pane=target,
        message="resume line NOT submitted after restart — will retry the Enter (no respawn)",
    )
