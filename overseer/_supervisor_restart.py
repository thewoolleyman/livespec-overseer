"""_supervisor_restart — the restart and wind-down injection mechanics.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. Reached ONLY from the cascade's `ready` and low-context legs, and
RUNTIME-DISPATCHED: a Codex track routes to `codex resume <id>`, never the claude
launch command, because aiming `claude -n <topic>` at a codex pane would replace
the codex session with a claude one and destroy it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_launch
import _supervisor_state
import registry
import signals
from _supervisor_config import track_key
from _supervisor_prompts import default_resume, wrapup_message

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "do_codex_restart",
    "do_restart",
    "maybe_inject",
]


def maybe_inject(
    sup: Supervisor,
    track: registry.Track,
    target: str,
    eff_ctx: int,
    threshold: int,
    *,
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
    notified = set(registry.read_notified_bands(repo, topic, sup.stamp_path))
    due = [b for b in bands if eff_ctx <= b and b not in notified]
    if not due:
        return
    opened_now = registry.read_injection_stamp(repo, topic, sup.stamp_path) is None
    if opened_now:
        # Stamp BEFORE the paste (design) so a marker the session writes has
        # mtime > at. Only on opening — a re-warn preserves the round's at.
        registry.write_injection_stamp(repo, topic, sup.now(), sup.stamp_path)
    message = wrapup_message(remaining=eff_ctx, repo=repo, topic=topic)
    if _supervisor_launch.submit_prompt(sup, target, message, expect_codex=is_codex):
        for b in due:
            registry.add_notified_band(repo, topic, b, sup.stamp_path)
        sup.log(f"injected wrap-up into {repo}::{topic} (ctx {eff_ctx}%, bands {due})")
    else:
        if opened_now:
            # Roll back the just-opened round so the next tick retries cleanly.
            registry.clear_injection_stamp(repo, topic, sup.stamp_path)
        sup.alert(
            repo=repo,
            topic=topic,
            session=_supervisor_launch.session_of(sup, track),
            pane=target,
            message="wrap-up injection FAILED (paste did not land); will retry",
        )


def do_restart(
    sup: Supervisor, track: registry.Track, target: str, *, is_codex: bool = False
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

    Every tmux step is a HARD GATE (B5). If ``respawn-pane`` fails, or the pane
    never becomes a live Claude, the daemon SURFACES the failure and RETURNS
    WITHOUT closing the round — so the session's declaration is preserved and the
    restart is retried, never silently destroyed.

    **The submit is SELF-HEALING (R1, 2026-07-18).** The round is closed (state file
    deleted + injection stamp cleared — B4) ONLY when the resume line actually SUBMITS.
    A freshly-respawned TUI can DROP the Enter while still drawing its welcome screen,
    leaving the fresh session live but idle with an un-run handoff (proven live
    2026-07-17). On that failure this does NOT clear the marker or log "restarted" —
    it marks a round-scoped ``resume_pending`` (``registry.set_resume_pending``) and
    alerts, and the NEXT tick's ``evaluate`` retries the SUBMIT ONLY (``_resend_enter``
    — never a re-respawn; a fresh ``ready`` stays the sole respawn trigger, so the retry
    can never escalate to a kill). Separating "is the fresh Claude up?" from "did the
    resume submit?" is the fix for the discarded-marker bug where the old code cleared
    the marker and reported success regardless. On the SUCCESS path ``_clear_state``
    also pops the in-memory inject state (RB2), so the redundant explicit pop is
    belt-and-suspenders.
    """
    if is_codex:
        do_codex_restart(sup, track, target)
        return
    if not sup.tmux.respawn_pane(
        session=target, cwd=track.repo, command=_supervisor_launch.launch_command(track)
    ):
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=_supervisor_launch.session_of(sup, track),
            pane=target,
            message="restart respawn FAILED; keeping the ready declaration so it retries",
        )
        return
    if not _supervisor_launch.await_pane(sup, target, signals.pane_is_claude):
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=_supervisor_launch.session_of(sup, track),
            pane=target,
            message="respawned pane never became Claude; keeping the ready declaration",
        )
        return
    # Wait for the fresh TUI to finish its FIRST paint and render a ready (empty)
    # input box before pasting — a half-drawn welcome/news screen DROPS the Enter,
    # which is exactly what stranded resumes live (2026-07-17). Best-effort: if the
    # box never appears in time, proceed anyway and let the submit-retry below (and
    # the next tick's `resume_pending` retry) recover.
    _ = _supervisor_launch.await_input_box(sup, target)
    # If the fresh TUI came up on a picker (a trust / update / bypass-permissions
    # gate), NEVER keystroke into it (blocker #6) — pasting + Enter would auto-accept
    # its default. Defer to the `resume_pending` retry, which reports the gate as
    # `blocked:human` and resumes once the human clears it (review SF4).
    if signals.is_structured_gate(sup.tmux.capture_pane(session=target)):
        registry.set_resume_pending(track.repo, track.topic, sup.stamp_path)
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=_supervisor_launch.session_of(sup, track),
            pane=target,
            message="freshly-restarted pane is on a gate — not keystroking it; will retry",
        )
        return
    resume = track.resume or default_resume(track.repo, track.topic)
    if _supervisor_launch.submit_prompt(sup, target, resume):
        _supervisor_state.clear_state(sup, track)
        _ = sup.inject.pop(track_key(track.repo, track.topic), None)
        sup.log(f"restarted {track.repo}::{track.topic} (pane {target})")
        return
    # The fresh Claude IS up, but the resume line did not submit (the fresh TUI
    # dropped the Enter). Separate the two facts the old code conflated — "is the
    # fresh Claude up?" (yes) and "did the resume submit?" (no) — and DO NOT give up:
    # keep the `ready` marker + stamp, record a round-scoped `resume_pending`, and let
    # the NEXT tick retry the SUBMIT ONLY (re-send Enter, never a re-respawn — a fresh
    # `ready` is the sole respawn trigger, so the retry can never escalate to a kill).
    # Never log a clean "restarted" here; the alert is edge-triggered and persists (the
    # row stays NEEDS-YOU) until the resume actually submits.
    registry.set_resume_pending(track.repo, track.topic, sup.stamp_path)
    sup.alert(
        repo=track.repo,
        topic=track.topic,
        session=_supervisor_launch.session_of(sup, track),
        pane=target,
        message="resume line NOT submitted after restart — will retry the Enter (no respawn)",
    )


def do_codex_restart(sup: Supervisor, track: registry.Track, target: str) -> None:
    """Atomic restart of a CODEX track: respawn with ``codex resume <id> "<kick>"``.

    The Codex analogue of the Claude restart, and SIMPLER (proven live 2026-07-17):
    ``codex resume`` takes the kick as an ARGUMENT and AUTO-SUBMITS it, so there is
    no separate resume-line paste and no fresh-TUI submit race. It resumes the SAME
    session by its exact UUID — codex appends to the same rollout, so the
    ``thread_name`` (hence adoptability) survives the restart by construction. Resume
    by UUID, never by name: "UUIDs take precedence", and a name could be ambiguous or
    drop to a picker.

    The session id comes from the live per-tick Codex map (``self.live_codex``), looked up
    by ``(tmux, topic)`` so a second codex sharing this tmux session cannot supply the
    WRONG session id (#4); if the session vanished between the map refresh and here,
    the declaration is KEPT and the restart retried next tick (B5), exactly like a
    failed respawn.
    """
    session = _supervisor_launch.session_of(sup, track)
    live = sup.live_codex.get((session, track.topic))
    if live is None:
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=session,
            pane=target,
            message="codex session vanished before restart; keeping the ready declaration",
        )
        return
    resume = track.resume or default_resume(track.repo, track.topic)
    command = _supervisor_launch.codex_launch_command(live.session_id, resume)
    if not sup.tmux.respawn_pane(session=target, cwd=track.repo, command=command):
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=session,
            pane=target,
            message="restart respawn FAILED; keeping the ready declaration so it retries",
        )
        return
    if not _supervisor_launch.await_pane(sup, target, signals.pane_is_codex):
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=session,
            pane=target,
            message="respawned pane never became Codex; keeping the ready declaration",
        )
        return
    # The kick was submitted BY the `codex resume` argument — no separate paste step.
    _supervisor_state.clear_state(sup, track)
    _ = sup.inject.pop(track_key(track.repo, track.topic), None)
    sup.log(f"restarted (codex) {track.repo}::{track.topic} (pane {target})")
