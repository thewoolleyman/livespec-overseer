"""_supervisor_prompts — every word the daemon ever puts into a tracked session.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. This module owns the wrap-up escalation text, the keep-going nudge, and the
read-first locator builders — single-sourced here so `overseer/marker-protocol.md`, the
tracked sessions' plan state, and the daemon all quote the SAME strings.

A worker track's read-first source is its plan's LEDGER-HELD PLAN STATE — the entries on
the governed plan's ledger epic, located by repository path and recorded epic id. It is
NOT a path under the plan tree: a path-shaped pointer can go stale, can name a file that
was never written, and cannot be resolved by a cold-open successor that has no prior
context. The daemon holds the epic id as an OPAQUE LOCATOR and never reads those entries.

Nothing here decides anything: these are pure string builders over (repo, topic, epic) and
a remaining-context percent. The escalation THRESHOLD (`_INSIST_AT`) is a property of
the text, so it lives here rather than in `_supervisor_config`, and stays private
because only :func:`wrapup_message` reads it.

:func:`supervisor_handoff_path` is public despite the private module because the
daemon reads it across the module boundary, where pyright-strict's
`reportPrivateUsage` rejects an `_`-prefixed name.
"""

from __future__ import annotations

from pathlib import Path

import registry
import signals

__all__: list[str] = [
    "charter_authorized_unblock_nudge_message",
    "expiry_notice_message",
    "idle_nudge_message",
    "launch_resume",
    "pair_stall_nudge_message",
    "plan_epic_resume",
    "plan_state_locator",
    "resume_for_track",
    "supervisor_epic_path",
    "supervisor_handoff_path",
    "supervisor_idle_nudge_message",
    "supervisor_ledger_resume",
    "supervisor_resume",
    "supervisor_wrapup_message",
    "wrapup_message",
]


# --------------------------------------------------------------------------- #
# The read-first locator + resume line. Single-sourced here so Build C's
# convention doc and tracked-session plan state reference the SAME text.
# --------------------------------------------------------------------------- #


def plan_state_locator(*, repo: str, epic: str | None) -> str:
    """The track's ledger-held plan state, named by repository path and epic id.

    A track with NO recorded epic has no locator to hand out. That is not a silent case:
    the restart interlock refuses to respawn such a track and surfaces it instead, so the
    text says exactly that rather than naming a plausible-looking pointer nobody can
    resolve.
    """
    if epic is None:
        return (
            f"this track's ledger-held plan state in repository {repo} — but NO plan epic "
            "id is recorded for this track, so ask the operator to record one"
        )
    return f"the plan state held on ledger epic {epic} in repository {repo}"


def plan_epic_resume(*, repo: str, epic: str) -> str:
    """The first prompt pasted into a restarted plan session: resolve its ledger epic."""
    return f"resume plan epic {epic} in repository {repo}; read its ledger-held plan state"


def _resume_line(*, repo: str, epic: str | None) -> str:
    """The exact prompt the fresh session will be handed, quoted back in the wrap-up."""
    if epic is None:
        return (
            "(no resume prompt can be built — this track records NO plan epic id, so it "
            "is surfaced for a human instead of respawned)"
        )
    return plan_epic_resume(repo=repo, epic=epic)


def resume_for_track(*, track: registry.Track) -> str | None:
    """The runtime resume prompt for a track, or None when a plan track lacks its epic.

    ONE definition for every path that hands a session its first prompt — the restart
    after a `ready`, the reboot-recovery relaunch, and the attention check that asks
    whether a respawned pane ever ran what it was handed. Two definitions would let the
    daemon respawn onto one source and then judge the pane against another.

    A supervisor pair member resumes by repository + ledger epic too, but with the
    supervisor entity's attributed handoff entries rather than the worker's plan state.
    Both branches resolve cold-open state from the ledger rather than from a path-shaped
    pointer that may have gone stale — or that may name a file nobody ever wrote.

    A track's stored `resume` is deliberately NOT consulted here. Assignment surfaces used
    to auto-populate that field with a derived handoff line, so a non-empty value on an
    existing row is far more likely to be that stale derivation than an operator's
    deliberate override, and honoring it would resurrect exactly the pointer this chain
    exists to retire.
    """
    if signals.topic_reserved_for_supervisor(topic=track.topic):
        return supervisor_resume(
            repo=track.repo,
            topic=signals.supervisor_topic(entity_topic=track.topic),
            epic=track.epic,
        )
    if track.epic is None:
        return None
    return plan_epic_resume(repo=track.repo, epic=track.epic)


def launch_resume(*, track: registry.Track) -> str:
    """The first prompt for a track being LAUNCHED — `start`, or reboot recovery.

    A launch is never refused for a missing epic, and that asymmetry with the restart is
    deliberate. The restart spends a session's own `ready` declaration and destroys a
    live process, so it must refuse rather than respawn onto a prompt nobody can resolve.
    A launch destroys nothing: `start` is an attended operator act, and reboot recovery
    is restoring a session the operator already had.

    So a track with no recorded epic is handed the truth — there is no ledger-held plan
    state to resume from — instead of a plausible-looking path into its plan directory.
    Naming a file the daemon cannot vouch for is what sent sessions to read pointers that
    had gone stale, or that named a file nobody ever wrote.
    """
    derived = resume_for_track(track=track)
    if derived is not None:
        return derived
    return (
        f"no plan epic id is recorded for the track {track.topic} in repository "
        f"{track.repo}, so there is no ledger-held plan state to resume from; report that "
        "to the operator before starting any work"
    )


# --------------------------------------------------------------------------- #
# The wrap-up message.
# --------------------------------------------------------------------------- #

# At/below this remaining-%, the wrap-up STOPS suggesting and DEMANDS shutdown. The
# escalation the maintainer asked for (2026-07-14): a gentle nudge at the first bands
# (50/40), then insistent at 30/20/10. Re-sending identical text five times is
# repetition, not escalation — and with the force-restart gone, this escalation IS the
# lever, so it has to actually get sharper.
_INSIST_AT = 30

_WRAPUP_SUGGEST_HEAD = """\
You are down to {n}% of your context. Please start wrapping up for a clean session
restart — do it now, while you still have room to do it properly."""

_WRAPUP_INSIST_HEAD = """\
STOP AND WIND DOWN NOW. You have only {n}% of your context left. Finish what is in
flight, do not start anything new, and shut down — you are close to the point where
you can no longer hand off cleanly."""

_WRAPUP_BODY = """\
You WILL be restarted — but ONLY when YOU say so. The overseer never kills a session
that has not declared itself ready. When you stop, this pane is restarted according to
its runtime and handed exactly ONE prompt. A Claude restart launches a new conversation.
A Codex restart uses `codex resume`, reattaches this same Codex rollout, and auto-submits
the prompt:
    {resume}
So {read_first} is the ONLY durable resume state inherited by the restarted runtime. Do
NOT leave your resume state anywhere else (a scratchpad file, this transcript, a file
under plan/) — it will be LOST. If your real pending work has drifted from what those
entries say, APPEND a fresh entry that corrects them; never withhold your declaration over
drift.

Declare your state by writing ONE line to the single state file
{state_file} — one of exactly these three values:

    winding-down                  I got this message and am wrapping up now.
    ready                         I am at a clean stopping point — restart me.
    blocked: <one-line reason>    I need a human decision I cannot make myself.

ACKNOWLEDGE FIRST, right now, before anything else:
    mkdir -p {marker_dir} && echo winding-down > {state_file}

Then:
 1. Bring your OWN work to a clean, resumable stopping point and commit it through your
    repository's own gates. Never pass --no-verify. If a gate rejects you, fix the cause
    or declare `blocked: <reason>` — do not bypass it and do not discard the work.
 2. APPEND your resume state to {read_first}, through your orchestrator's sanctioned plan
    surface. Writing it down locally is NOT saving it — an entry that was never appended
    has no attribution, no timestamp, and the next session cannot see it at all. Do NOT
    write it into a file under plan/, and do NOT write to the ledger directly.
 3. Stop every background sub-agent and subprocess you started.
 4. Declare done, and stop. The command that declares ready is your FINAL act:
        overseer-declare ready

After `overseer-declare ready`, stop immediately.
if you are still in this conversation, no restart happened - never conclude otherwise.

`ready` is the ONLY thing that restarts you. If you write nothing at all, you are NOT
restarted and NOT killed — you are reported to the human as not responding, and your
track sits there until a person intervenes. Do not do that to them: write the file."""


def _wrapup_head(*, remaining: int) -> str:
    return _WRAPUP_INSIST_HEAD if remaining <= _INSIST_AT else _WRAPUP_SUGGEST_HEAD


def wrapup_message(*, remaining: int, repo: str, topic: str, epic: str | None) -> str:
    """The wrap-up text injected when a track crosses a ctx warn band.

    ESCALATES with the band (maintainer 2026-07-14): a suggestion while there is still
    room (above ``_INSIST_AT``), then an insistent shut-down demand at 30/20/10.
    ``remaining`` fills ``{n}`` with the CURRENT remaining-context percent, so each
    re-warn reflects the live value.

    ``repo``/``topic`` build the TEMP dir (``<repo>/tmp/overseer/<topic>/``) holding the
    single ``.overseer-state`` file the session writes — never anything under ``plan/``.
    ``epic`` names the LEDGER-HELD PLAN STATE the restart resumes FROM. Building that
    locator is pure string work (:func:`plan_state_locator`): the overseer POINTS at the
    plan state, exactly as the resume line does, and never reads those entries.

    Three failures shaped this text. A tracked session once REFUSED to declare anything —
    reasoning that the resume line pointed at a handoff which no longer matched its real
    pending work (which it had stashed in a scratchpad) — and wedged its track at 13%
    forever; so the message says plainly that the plan state is the ONLY inherited
    artifact and that drift is fixed by APPENDING, never by withholding the declaration.
    Because the daemon must never guess a session is safe to kill, the message also makes
    the session's declaration the sole authorization: no ``ready``, no restart. And
    because a file written to disk was repeatedly mistaken for a saved handoff, step 2
    says outright that an un-appended entry is invisible to the successor.
    """
    return f"{_wrapup_head(remaining=remaining)}\n\n{_WRAPUP_BODY}".format(
        n=remaining,
        marker_dir=str(signals.marker_dir(repo=repo, topic=topic)),
        state_file=str(signals.state_path(repo=repo, topic=topic)),
        read_first=plan_state_locator(repo=repo, epic=epic),
        resume=_resume_line(repo=repo, epic=epic),
    )


_CHARTER_AUTHORIZED_UNBLOCK_NUDGE = """\
Your supervisor charter already says:

A wait is not a question. A mechanical unblock is not a question.
If the SUPERVISOR can perform the unblock, PERFORM IT.

The overseer is not choosing from this picker and will not answer it for you. Re-read
the pending picker, perform only charter-authorized mechanical unblocks yourself, and
declare `blocked: <reason>` only when the unblock genuinely requires a human decision."""


def charter_authorized_unblock_nudge_message() -> str:
    """Reminder pasted into a stalled supervisor picker without submitting an answer."""
    return _CHARTER_AUTHORIZED_UNBLOCK_NUDGE


_EXPIRY_NOTICE = """\
Your ready declaration EXPIRED: it stood past its maximum age without a verified
settled-idle observation, so it no longer authorizes a restart.

Declare your state by writing ONE line to the single state file
{state_file} — one of exactly these three values:

    winding-down                  I got the wind-down message and am wrapping up now.
    ready                         I am at a clean stopping point — restart me.
    blocked: <one-line reason>    I need a human decision I cannot make myself.

A restart requires a fresh ready. The declaration that just expired will not restart
this session; write `ready` again only after you are truly at a clean stopping
point."""


def expiry_notice_message(*, repo: str, topic: str) -> str:
    """The bounded notice sent after a ready declaration expires past its maximum age."""
    return _EXPIRY_NOTICE.format(state_file=str(signals.state_path(repo=repo, topic=topic)))


def supervisor_handoff_path(*, repo: str, topic: str) -> Path:
    """The retired supervisor-handoff artifact path, for legacy certification only.

    Supervise-plan no longer AUTHORS this file: its binder is appended to the plan's
    ledger epic, and supervisor resume prompts now resolve that ledger state directly.
    Existing files can still certify old supervisor restart rounds while live plans are
    migrating. Callers on the daemon's discovery path must never open, read, hash, or
    depend on its content or mtime.
    """
    return Path(repo) / "plan" / topic / "supervisor-handoff.md"


def supervisor_epic_path(*, repo: str, topic: str) -> Path:
    """The migrated plan-shape file that names the governed ledger epic."""
    return Path(repo) / "plan" / topic / "epic.md"


def _supervisor_state_locator(*, repo: str, topic: str, epic: str | None) -> str:
    """The supervisor entity's ledger-held resume state."""
    entity = signals.supervisor_entity_topic(topic=topic)
    if epic is None:
        return (
            f"the supervisor handoff entries attributed to {entity} in repository {repo} — "
            "but NO plan epic id is recorded for this track, so ask the operator to record one"
        )
    return (
        f"the supervisor handoff entries attributed to {entity} on ledger epic {epic} "
        f"in repository {repo}"
    )


def _supervisor_resume_line(*, repo: str, topic: str, epic: str | None) -> str:
    """The exact prompt the fresh supervisor session will be handed."""
    if epic is None:
        return (
            "(no resume prompt can be built — this supervisor track records NO plan epic id, "
            "so it is surfaced for a human instead of respawned)"
        )
    return supervisor_ledger_resume(repo=repo, topic=topic, epic=epic)


_SUPERVISOR_WRAPUP_BODY = """\
You WILL be restarted — but ONLY when YOU say so. The overseer never kills a session
that has not declared itself ready. When you stop, this pane is restarted according to
its runtime and handed exactly ONE prompt:
    {resume}
So {read_first} is the ONLY durable resume state inherited by the restarted runtime. Do
NOT leave your resume state anywhere else (a scratchpad file, this transcript, a file
under plan/) — it will be LOST. If your real pending work has drifted from what those
entries say, APPEND a fresh entry that corrects them; never withhold your declaration over
drift.

Declare your state by writing ONE line to the single state file
{state_file} — one of exactly these three values:

    winding-down                  I got this message and am wrapping up now.
    ready                         I am at a clean stopping point — restart me.
    blocked: <one-line reason>    I need a human decision I cannot make myself.

ACKNOWLEDGE FIRST, right now, before anything else:
    mkdir -p {marker_dir} && echo winding-down > {state_file}

Then:
 1. Bring your OWN supervision work to a clean, resumable stopping point and commit any
    repository changes you already made through your repository's own gates. Never pass
    --no-verify. If a gate rejects you, fix the cause or declare `blocked: <reason>` —
    do not bypass it and do not discard the work.
 2. APPEND your supervisor resume state to {read_first}, through your orchestrator's
    sanctioned plan surface. Writing it down locally is NOT saving it — an entry that was
    never appended has no attribution, no timestamp, and the next session cannot see it
    at all. Do NOT write it into a file under plan/, and do NOT write to the ledger
    directly.
 3. Stop every background sub-agent and subprocess you started.
 4. Declare done, and stop. The command that declares ready is your FINAL act:
        overseer-declare ready

After `overseer-declare ready`, stop immediately.
if you are still in this conversation, no restart happened - never conclude otherwise.

`ready` is the ONLY thing that restarts you. If you write nothing at all, you are NOT
restarted and NOT killed — you are reported to the human as not responding, and your
track sits there until a person intervenes. Do not do that to them: write the file."""


def supervisor_ledger_resume(*, repo: str, topic: str, epic: str) -> str:
    """Resume prompt for a migrated supervisor pair member."""
    entity = signals.supervisor_entity_topic(topic=topic)
    return (
        f"resume supervisor entity {entity} for plan epic {epic} in repository {repo}; "
        "read the supervisor handoff entries attributed to that entity"
    )


def _supervisor_plan_state_locator(*, repo: str, topic: str, epic: str | None) -> str:
    """The dual resume-state locator for a migrated supervisor pair member."""
    entity = signals.supervisor_entity_topic(topic=topic)
    shared = f"the shared supervisor protocol .ai/supervisor-protocol.md in repository {repo}"
    if epic is None:
        return (
            f"{shared} and this supervisor entity's ledger-held handoff entries — but NO "
            "plan epic id is recorded for this track, so ask the operator to record one"
        )
    return (
        f"{shared}, plus the supervisor handoff entries attributed to {entity} on ledger "
        f"epic {epic}"
    )


def supervisor_resume(*, repo: str, topic: str, epic: str | None = None) -> str:
    """Resume prompt for a supervisor pair member."""
    if epic is None:
        return (
            "(no resume prompt can be built — this supervisor track records NO plan epic id, "
            "so ask the operator to record one)"
        )
    return supervisor_ledger_resume(repo=repo, topic=topic, epic=epic)


def supervisor_wrapup_message(
    *, remaining: int, repo: str, topic: str, epic: str | None = None
) -> str:
    """Wrap-up text for a supervisor pair member.

    The supervisor entity's state and round key use ``<topic>-supervisor``, while its
    durable resume state is the attributed supervisor-entry stream on the worker plan's
    ledger epic. This is a whole text VARIANT rather than parameter substitution on the
    worker body: the supervisor entity names its attributed entries, but both entities now
    use the sanctioned plan surface rather than authoring files under ``plan/``.
    """
    entity_topic = signals.supervisor_entity_topic(topic=topic)
    return f"{_wrapup_head(remaining=remaining)}\n\n{_SUPERVISOR_WRAPUP_BODY}".format(
        n=remaining,
        marker_dir=str(signals.marker_dir(repo=repo, topic=entity_topic)),
        state_file=str(signals.state_path(repo=repo, topic=entity_topic)),
        read_first=_supervisor_state_locator(repo=repo, topic=topic, epic=epic),
        resume=_supervisor_resume_line(repo=repo, topic=topic, epic=epic),
    )


_IDLE_NUDGE = """\
You are idle at {n}% context — ABOVE the {threshold}% wind-down line, so you have room to
keep going. Do NOT stop, and do NOT offer to stop, while you are above {threshold}%.

Pick your work back up and continue — your task is in
    {read_first}
Keep going until you are near {threshold}%; the overseer will then send the wind-down.

The overseer has marked your track `idle-with-context-left` in
    {state_file}
That marker clears as soon as you take another turn (the daemon clears it when it sees you
working again); you may also `rm {state_file}` yourself.

If you are NOT free to continue — you are WAITING ON A HUMAN (you asked a question or hit a
decision you cannot make, and cannot raise a prompt, e.g. Codex in YOLO mode) — then say so
out-of-band so the operator is alerted, INSTEAD of sitting idle:
    echo 'blocked: <one-line reason>' > {state_file}"""


def idle_nudge_message(
    *, remaining: int, threshold: int, repo: str, topic: str, epic: str | None
) -> str:
    """The single "keep going" nudge injected into an idle session that still has context
    left (``remaining`` > ``threshold``).

    The inverse of :func:`wrapup_message`: instead of "wind down", it says "you have room,
    do not stop above the wind-down line". It is sent at most ONCE per idle episode — the
    ``idle-with-context-left`` marker the daemon writes edge-triggers it, and that marker
    clears when the session next goes non-idle, re-arming a fresh nudge for the next
    episode. It points the session back at the same ledger-held plan state the restart
    would resume it from, so the two messages can never name different sources.

    It also carries the out-of-band escape for the case the daemon cannot see: a session
    genuinely WAITING on a human that expressed it only in prose (Codex in YOLO mode cannot
    raise a structured gate) is told to declare ``blocked: <reason>`` — the existing token —
    so the operator is alerted rather than the track being nudged to keep going.
    """
    return _IDLE_NUDGE.format(
        n=remaining,
        threshold=threshold,
        read_first=plan_state_locator(repo=repo, epic=epic),
        state_file=str(signals.state_path(repo=repo, topic=topic)),
    )


def supervisor_idle_nudge_message(
    *, remaining: int, threshold: int, repo: str, topic: str, epic: str | None = None
) -> str:
    """Keep-going nudge for a supervisor pair member.

    ``topic`` is the worker topic. The supervisor entity's state marker still lives
    under ``<topic>-supervisor``, and the durable state the supervisor resumes from is
    the shared supervisor protocol plus ledger-held supervisor handoff entries on the
    worker plan's epic.
    """
    entity_topic = signals.supervisor_entity_topic(topic=topic)
    return _IDLE_NUDGE.format(
        n=remaining,
        threshold=threshold,
        read_first=_supervisor_plan_state_locator(repo=repo, topic=topic, epic=epic),
        state_file=str(signals.state_path(repo=repo, topic=entity_topic)),
    )


def pair_stall_nudge_message(
    *,
    repo: str,
    topic: str,
    epic: str | None,
    worker_session: str,
    worker_pane: str | None,
    stalled_seconds: float,
) -> str:
    """Nudge a stalled supervisor/worker pair through the supervisor pane."""
    state_file = signals.state_path(repo=repo, topic=signals.supervisor_entity_topic(topic=topic))
    duration = f"{stalled_seconds / 3600:.1f}h"
    return f"""\
Your worker/supervisor pair has shown no progress for {duration}.

You own direction for this pair. Resume driving the worker now, or if the pair is
actually waiting on a human question, surface that explicitly by declaring it out-of-band:
    echo 'blocked: <one-line reason>' > {state_file}

Worker coordinates: tmux session '{worker_session}', pane {worker_pane}.
Worker plan state: {plan_state_locator(repo=repo, epic=epic)}"""
