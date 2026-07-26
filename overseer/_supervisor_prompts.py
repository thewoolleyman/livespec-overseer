"""_supervisor_prompts — every word the daemon ever puts into a tracked session.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. This module owns the wrap-up escalation text, the keep-going nudge, and the
handoff/resume path builders — single-sourced here so `overseer/marker-protocol.md`,
the tracked sessions' handoffs, and the daemon all quote the SAME strings.

Nothing here decides anything: these are pure string builders over (repo, topic) and
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
    "default_handoff",
    "default_resume",
    "idle_nudge_message",
    "supervisor_handoff_path",
    "wrapup_message",
]


# --------------------------------------------------------------------------- #
# The wrap-up message + resume line. Single-sourced here so Build C's
# convention doc and tracked-session handoffs reference the SAME text.
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
that has not declared itself ready. When you stop, this pane is respawned into a fresh
session handed exactly ONE prompt:
    read {handoff} and follow it
So {handoff} is the ONLY thing the next session inherits. Do NOT leave your resume state
anywhere else (a scratchpad file, this transcript) — it will be LOST. If your real
pending work has drifted from what that file says, REWRITE that file.

Declare your state by writing ONE line to the single state file
{state_file} — one of exactly these three values:

    winding-down                  I got this message and am wrapping up now.
    ready                         I am at a clean stopping point — restart me.
    blocked: <one-line reason>    I need a human decision I cannot make myself.

ACKNOWLEDGE FIRST, right now, before anything else:
    mkdir -p {marker_dir} && echo winding-down > {state_file}

Then:
 1. Bring your OWN work to a clean, resumable stopping point, and UPDATE {handoff} to
    match. Your session owns its handoff and everything under plan/; the overseer never
    reads or writes those.
 2. COMMIT {handoff}. Writing it to disk is NOT saving it — an uncommitted handoff has
    no history, no attribution, and is one `git checkout` from gone. You cannot commit
    at the primary checkout (the commit-refuse hook rejects it), and a fresh worktree
    will NOT contain your edits, so copy them across:
        W="$HOME/.worktrees/{slug}/wrapup-{topic}"
        mise exec -- git -C {repo} worktree add -b wrapup-{topic} "$W" master
        cp {handoff} "$W/plan/{topic}/handoff.md"
        cd "$W" && mise exec -- git add plan/ && mise exec -- git commit
        mise exec -- git push && gh pr create --fill && gh pr merge --auto --rebase --delete-branch
    Doc-only commits take your repo's reduced doc-only gate at both commit and push, so
    this is quick. Never pass --no-verify. If a hook rejects you, fix the cause or declare
    `blocked: <reason>` — do not bypass it and do not discard the file.
 3. Stop every background sub-agent and subprocess you started.
 4. Declare done, and stop:
        echo ready > {state_file}

`ready` is the ONLY thing that restarts you. If you write nothing at all, you are NOT
restarted and NOT killed — you are reported to the human as not responding, and your
track sits there until a person intervenes. Do not do that to them: write the file."""


def wrapup_message(*, remaining: int, repo: str, topic: str) -> str:
    """The wrap-up text injected when a track crosses a ctx warn band.

    ESCALATES with the band (maintainer 2026-07-14): a suggestion while there is still
    room (above ``_INSIST_AT``), then an insistent shut-down demand at 30/20/10.
    ``remaining`` fills ``{n}`` with the CURRENT remaining-context percent, so each
    re-warn reflects the live value.

    ``repo``/``topic`` build the TEMP dir (``<repo>/tmp/overseer/<topic>/``) holding the
    single ``.overseer-state`` file the session writes — never anything under ``plan/`` —
    and the ``plan/<topic>/handoff.md`` path the restart resumes FROM. Constructing that
    path is pure string work (``default_handoff``): the overseer POINTS at the handoff,
    exactly as the resume line does, and never opens it.

    Two failures shaped this text. A tracked session once REFUSED to declare anything —
    reasoning that the resume line pointed at a handoff which no longer matched its real
    pending work (which it had stashed in a scratchpad) — and wedged its track at 13%
    forever; so the message now says plainly that the handoff is the ONLY inherited
    artifact and that drift is fixed by REWRITING it. And because the daemon must never
    guess a session is safe to kill, the message also makes the session's declaration the
    sole authorization: no ``ready``, no restart.
    """
    head = _WRAPUP_INSIST_HEAD if remaining <= _INSIST_AT else _WRAPUP_SUGGEST_HEAD
    return f"{head}\n\n{_WRAPUP_BODY}".format(
        n=remaining,
        marker_dir=str(signals.marker_dir(repo, topic)),
        state_file=str(signals.state_path(repo=repo, topic=topic)),
        handoff=default_handoff(repo=repo, topic=topic),
        repo=repo,
        topic=topic,
        slug=registry.repo_slug(repo=repo),
    )


def default_handoff(*, repo: str, topic: str) -> str:
    """``<repo>/plan/<topic>/handoff.md`` — the discovery-convention handoff path."""
    return str(Path(repo) / "plan" / topic / "handoff.md")


def supervisor_handoff_path(*, repo: str, topic: str) -> Path:
    """The single supervision artifact the daemon may existence-test.

    This is the narrow spec allowance: for a track already proven to have a live matching
    managed session, the daemon may ask whether this exact file exists. Callers must never
    open, read, hash, or depend on its content or mtime.
    """
    return Path(repo) / "plan" / topic / "supervisor-handoff.md"


def default_resume(*, repo: str, topic: str) -> str:
    """The first prompt pasted into a (re)started session: read the handoff."""
    return f"read {default_handoff(repo=repo, topic=topic)} and follow it"


_IDLE_NUDGE = """\
You are idle at {n}% context — ABOVE the {threshold}% wind-down line, so you have room to
keep going. Do NOT stop, and do NOT offer to stop, while you are above {threshold}%.

Pick your work back up and continue — your task is in
    {handoff}
Keep going until you are near {threshold}%; the overseer will then send the wind-down.

The overseer has marked your track `idle-with-context-left` in
    {state_file}
That marker clears as soon as you take another turn (the daemon clears it when it sees you
working again); you may also `rm {state_file}` yourself.

If you are NOT free to continue — you are WAITING ON A HUMAN (you asked a question or hit a
decision you cannot make, and cannot raise a prompt, e.g. Codex in YOLO mode) — then say so
out-of-band so the operator is alerted, INSTEAD of sitting idle:
    echo 'blocked: <one-line reason>' > {state_file}"""


def idle_nudge_message(*, remaining: int, threshold: int, repo: str, topic: str) -> str:
    """The single "keep going" nudge injected into an idle session that still has context
    left (``remaining`` > ``threshold``).

    The inverse of :func:`wrapup_message`: instead of "wind down", it says "you have room,
    do not stop above the wind-down line". It is sent at most ONCE per idle episode — the
    ``idle-with-context-left`` marker the daemon writes edge-triggers it, and that marker
    clears when the session next goes non-idle, re-arming a fresh nudge for the next
    episode.

    It also carries the out-of-band escape for the case the daemon cannot see: a session
    genuinely WAITING on a human that expressed it only in prose (Codex in YOLO mode cannot
    raise a structured gate) is told to declare ``blocked: <reason>`` — the existing token —
    so the operator is alerted rather than the track being nudged to keep going.
    """
    return _IDLE_NUDGE.format(
        n=remaining,
        threshold=threshold,
        handoff=default_handoff(repo=repo, topic=topic),
        state_file=str(signals.state_path(repo=repo, topic=topic)),
    )
