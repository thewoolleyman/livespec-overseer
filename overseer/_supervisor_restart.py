"""_supervisor_restart — the restart and wind-down injection mechanics.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. Reached ONLY from the cascade's `ready` and low-context legs, and
RUNTIME-DISPATCHED: a Codex track routes to `codex resume <id>`, never the claude
launch command, because aiming `claude -n <topic>` at a codex pane would replace
the codex session with a claude one and destroy it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import _supervisor_launch
import _supervisor_state
import _supervisor_wrapup_injection
import registry
import signals
from _supervisor_claude_restart import claude_respawn_verified
from _supervisor_codex_restart import do_codex_restart
from _supervisor_config import track_key
from _supervisor_launch_profile import ClaudeLaunchPlan
from _supervisor_prompts import resume_for_track
from _supervisor_prompts import wrapup_message as _wrapup_message
from _supervisor_restart_binder import (
    handle_uncertified_restart_binder,
    missing_foreman_epic_message,
    missing_plan_epic_message,
    missing_restart_epic_message,
)
from _supervisor_statusline_model import restart_blocked_by_statusline_mismatch
from _supervisor_wrapup_injection import maybe_inject

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "do_codex_restart",
    "do_restart",
    "maybe_inject",
    "missing_foreman_epic_message",
    "missing_plan_epic_message",
    "missing_restart_epic_message",
    "rederive_epic_if_stale",
    "resume_prompt",
]

wrapup_message = _wrapup_message


def _restart_wrapup_message(*, remaining: int, repo: str, topic: str, epic: str | None) -> str:
    return wrapup_message(remaining=remaining, repo=repo, topic=topic, epic=epic)


_supervisor_wrapup_injection.wrapup_message_provider = _restart_wrapup_message


def rederive_epic_if_stale(
    *, sup: Supervisor, track: registry.PlanTrack, act: bool
) -> registry.PlanTrack:
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
    derived = sup.epic_lookup(repo=track.repo, topic=track.topic)
    if derived is None:
        return track
    _ = registry.record_derived_epic(
        repo=track.repo, topic=track.topic, epic=derived, store_path=sup.store_path
    )
    return registry.track_with_epic(track=track, epic=derived)


def resume_prompt(*, track: registry.Track) -> str | None:
    """Return the runtime resume prompt, or None when a normal track lacks its epic.

    Thin alias for :func:`_supervisor_prompts.resume_for_track`, kept because the restart
    mechanics are this module's surface and its callers name it here. The derivation
    itself lives beside the text it builds, so the relaunch and attention paths share one
    definition with the restart rather than each carrying their own.
    """
    return resume_for_track(track=track)


def _do_claude_restart(*, sup: Supervisor, track: registry.Track, target: str) -> None:
    launch = _supervisor_launch.claude_launch_plan(track=track, daemon_restart=True)
    if not isinstance(launch, ClaudeLaunchPlan):
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=_supervisor_launch.session_of(sup=sup, track=track),
            pane=target,
            message=f"{launch.message}; keeping the ready declaration so it retries",
            condition="stale-launch-profile",
        )
        return
    if restart_blocked_by_statusline_mismatch(
        sup=sup,
        track=track,
        target=target,
        session=_supervisor_launch.session_of(sup=sup, track=track),
    ):
        return
    sup.log_claude_build(phase="respawn")
    if not sup.tmux.respawn_pane(
        session=target,
        cwd=track.repo,
        command=launch.command,
        env=launch.env,
    ):
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=_supervisor_launch.session_of(sup=sup, track=track),
            pane=target,
            message="restart respawn FAILED; keeping the ready declaration so it retries",
            condition="claude-restart-respawn-failed",
        )
        return
    if not claude_respawn_verified(sup=sup, track=track, target=target):
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
            condition="claude-fresh-gate-after-restart",
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
        _supervisor_state.clear_state(
            sup=sup,
            track=track,
            diagnostic_token=signals.STATE_RESTARTED,
            diagnostic_detail="restart completed; consumed ready declaration",
        )
        _ = sup.inject.pop(track_key(repo=track.repo, topic=track.topic), None)
        sup.log(message=f"consumed ready declaration for {track.repo}::{track.topic}")
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
        condition="claude-resume-submit-failed",
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
    if handle_uncertified_restart_binder(sup=sup, track=track, target=target):
        return
    if is_codex:
        do_codex_restart(sup=sup, track=track, target=target)
        return
    _do_claude_restart(sup=sup, track=track, target=target)
