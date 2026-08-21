"""Prompt builders for supervisor-pair tracks."""

from __future__ import annotations

import signals

__all__: list[str] = [
    "supervisor_idle_nudge_message",
    "supervisor_ledger_resume",
    "supervisor_resume",
    "supervisor_wrapup_message",
]

_INSIST_AT = 30

_WRAPUP_SUGGEST_HEAD = """\
You are down to {n}% of your context. Please start wrapping up for a clean session
restart — do it now, while you still have room to do it properly."""

_WRAPUP_INSIST_HEAD = """\
STOP AND WIND DOWN NOW. You have only {n}% of your context left. Finish what is in
flight, do not start anything new, and shut down — you are close to the point where
you can no longer hand off cleanly."""

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

Writing that line is the declaration. Pane text, final-response prose, or saying
"Ready for restart" in this conversation is never a declaration channel.

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


def _wrapup_head(*, remaining: int) -> str:
    return _WRAPUP_INSIST_HEAD if remaining <= _INSIST_AT else _WRAPUP_SUGGEST_HEAD


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
