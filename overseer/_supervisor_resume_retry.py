"""_supervisor_resume_retry — R1, the cascade's first leg: the self-healing resume retry.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. This module is ONE function, called from :func:`_supervisor_evaluate.evaluate`
at exactly the position the leg's inline block occupied.

**Why this leg has a module of its own.** It was extracted from
:mod:`_supervisor_evaluate` (maintainer-declared 2026-07-26) and, at first, into a
function directly below `evaluate` in that same file. That arrangement stopped
clearing the LLOC ceilings: `bg2.9`'s keyword-only conversion re-wrapped the module's
signatures and call sites, taking it from 239 to 255 LLOC — past the 250 HARD
ceiling, which `overseer-bg2.4`'s `file_lloc_hard_gate` turns from a warning into a
build failure. Nothing could be moved WITHIN the module to reduce it: relocating a
function inside one file changes no line count. Moving this leg is the only
arrangement measured to put every file in the package under the 200 soft ceiling —
folding it into :mod:`_supervisor_restart`, where R1 belongs by subject, lands THAT
file at 203 and merely relocates the offence (supervisor-declared 2026-07-27, on the
255-over-250 measurement).

**What that costs, and what it does not.** The 2026-07-19 and 2026-07-26 rulings both
protect ONE property: that `evaluate`'s PRECEDENCE ORDER reads top-to-bottom in a
single pass. That survives untouched — the call still sits at the leg's exact
position, so no reader of the cascade loses anything. What worsens is the secondary
cost the 2026-07-26 ruling already accepted by name: a reader enumerating every way
`evaluate` can return early opens a FILE rather than scrolling down within one. That
is the same cost, one notch worse — not a new kind of cost, and not the protected
property. NO OTHER leg may be cut out on this precedent; the test for any future
extraction is whether the precedence order still reads in one pass in `evaluate`, not
whether it resembles this one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_launch
import _supervisor_state
import registry
import signals
from _supervisor_records import Observation
from _supervisor_view import RESUME_PENDING_NOTE, RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["resume_retry"]


def resume_retry(
    *,
    sup: Supervisor,
    track: registry.Track,
    obs: Observation,
    act: bool,
    session: str,
    target: str,
) -> RowView | None:
    """R1 — self-healing resume retry: the cascade's first leg, or None to fall through.

    A prior tick respawned the fresh Claude but its resume line did not submit (the
    fresh TUI dropped the Enter, or the daemon died mid-restart). The round is still
    open (marker + stamp kept), so ``ready`` is still valid — but re-entering
    :func:`_supervisor_evaluate.evaluate`'s ``elif ready:`` branch would RE-RESPAWN and
    kill the live fresh session. This leg intercepts first and retries the SUBMIT ONLY:
    re-send Enter, never a respawn (a fresh ``ready`` is the sole respawn trigger,
    invariant 7). Codex never sets ``resume_pending`` (its ``codex resume`` auto-submits
    the kick), so this is Claude-only by construction.

    Why this leg is a function at all — and why no other leg may become one — is on
    this module's header, together with what the arrangement costs. The short form:
    the call sits at exactly the position the inline block occupied, so the cascade's
    PRECEDENCE ORDER still reads top-to-bottom in one pass, which is the property both
    the 2026-07-19 and 2026-07-26 rulings protect.

    The cost, named rather than hidden: this leg's THREE early exits live here rather
    than in the cascade, so a reader enumerating every way
    :func:`_supervisor_evaluate.evaluate` can return early opens this file. Returning
    None means "not this leg"; every other path returns the row that ends the tick.
    """
    repo, topic = track.repo, track.topic
    if not (
        act and registry.read_resume_pending(repo=repo, topic=topic, stamp_path=sup.stamp_path)
    ):
        return None
    if obs.gate:
        # A fresh TUI showing a picker (trust / update / bypass-permissions confirm):
        # NEVER keystroke into a gate (blocker #6). Report it and keep the round open;
        # the retry resumes once the human clears the gate (review SF4).
        sup.alert(
            repo=repo,
            topic=topic,
            session=session,
            pane=target,
            message="gate on freshly-restarted pane — answer it IN THAT PANE",
        )
        return RowView(
            topic=topic,
            repo=repo,
            tmux=session,
            ctx=obs.eff_ctx,
            status="blocked:human",
            note="structured gate on freshly-restarted pane",
            runtime=obs.runtime,
        )
    # Branch on the BOX STATE, not on `busy` (review SF3): a freshly-respawned session
    # can read busy for reasons unrelated to the resume (SessionStart hooks), so a
    # top-level `busy` shortcut would false-close the round while the resume is still
    # un-submitted. An EMPTY box means the resume left the box (submitted / never
    # pasted) — the round is done here; the rare paste-failure re-engages via the
    # idle-with-context nudge, not a double-kick. A box holding TEXT means the Enter
    # was dropped — re-send Enter ONLY (never re-paste; the text is already there).
    resolved = (
        True
        if signals.input_box_ready(capture_text=obs.capture)
        else _supervisor_launch.resend_enter(sup=sup, target=target)
    )
    if resolved:
        _supervisor_state.clear_state(
            sup=sup,
            track=track,
            diagnostic_token=signals.STATE_RESTARTED,
            diagnostic_detail="restart completed; consumed ready declaration",
        )
        sup.log(message=f"consumed ready declaration for {repo}::{topic}")
        sup.log(message=f"restart resume submitted for {repo}::{topic} (pane {target})")
        return RowView(
            topic=topic,
            repo=repo,
            tmux=session,
            ctx=obs.eff_ctx,
            status="restarting",
            runtime=obs.runtime,
        )
    # Still un-submitted: keep the round open (retry again next tick) and report it.
    sup.alert(
        repo=repo,
        topic=topic,
        session=session,
        pane=target,
        message=("resume line STILL not submitted after restart — retrying the Enter (no respawn)"),
    )
    return RowView(
        topic=topic,
        repo=repo,
        tmux=session,
        ctx=obs.eff_ctx,
        status="restarting",
        note=RESUME_PENDING_NOTE,
        runtime=obs.runtime,
    )
