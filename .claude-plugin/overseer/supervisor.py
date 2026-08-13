"""supervisor.py — the overseer facade + the one-shot track-management CLI.

Stdlib-only, host-only. This module is the operator's and every consumer's single
entry point to the overseer daemon, in two roles:

  * **the FACADE.** `import supervisor` resolves the whole surface — `Supervisor`,
    `RowView`, `needs_attention`, the prompt builders, the tuning constants the
    public API names — so no consumer had to change when the implementation split.
  * **the one-shot CLI.** `uv run --no-project python overseer/supervisor.py <cmd>`
    is the `/overseer` skill's bottom-pane surface (`list` / `add` / `remove` /
    `unassign` / `start`), which is why `main` and the `__main__` guard live HERE and
    not in a collaborator. There is deliberately no `daemon` subcommand: the daemon
    is the dedicated `overseerd` executable, which calls :func:`run_daemon`.

The implementation lives in five private sibling modules, split when this file
crossed the 250-LLOC hard ceiling by more than five times:

  - :mod:`_supervisor_core`    — `class Supervisor`: the poll loop, the per-tick
                                 precedence cascade, recovery/launch, the table.
  - :mod:`_supervisor_config`  — the tuning constants, the start-up gitignore probe,
                                 and the shared `track_key` / `iso_now` helpers.
  - :mod:`_supervisor_prompts` — every word injected into a tracked session, plus the
                                 read-first locator + resume builders.
  - :mod:`_supervisor_view`    — `RowView`, the per-status row tint, note elision, the
                                 annotated tmux cell, the `NEEDS YOU` test.
  - :mod:`_supervisor_records` — `InjectState` and `Observation`, the per-track records
                                 one tick works with.

The siblings are `_`-prefixed because a private-helper MODULE is exempt from the
mirror-test pairing rule, while their shared members are PUBLIC — pyright-strict's
`reportPrivateUsage` rejects importing an `_`-prefixed name across modules, so a
helper shared between siblings cannot stay underscore-named once it moves out of one
file. That is the same shape `registry.py` and its `_registry_*` collaborators use.

THE CARDINAL RULE and the per-tick state machine are documented on
:mod:`_supervisor_core`, beside the code that implements them.

**Do not reach a tuning constant through this facade in order to patch it.** A
re-export here can be `monkeypatch.setattr`-ed successfully while the real reader in
`_supervisor_core` keeps its own binding — that exact failure appended rows to a
maintainer's live `~/.livespec-overseer.jsonl` during the registry split. Patch the
module that DEFINES the constant.
"""

from __future__ import annotations

import argparse
import io
import json
import os

import _supervisor_snapshot
import registry
import signals
import streams
import tmuxio
from _seams import SubcommandHandler
from _supervisor_config import DANGER_CTX_REMAINING as DANGER_CTX_REMAINING
from _supervisor_config import LOOP_INTERVAL_SECONDS as LOOP_INTERVAL_SECONDS
from _supervisor_config import default_gitignore_check as default_gitignore_check
from _supervisor_config import iso_now as iso_now
from _supervisor_core import Supervisor as Supervisor
from _supervisor_prompts import idle_nudge_message as idle_nudge_message
from _supervisor_prompts import plan_epic_resume as plan_epic_resume
from _supervisor_prompts import plan_state_locator as plan_state_locator
from _supervisor_prompts import wrapup_message as wrapup_message
from _supervisor_view import ATTENTION_STATUSES as ATTENTION_STATUSES
from _supervisor_view import RowView as RowView
from _supervisor_view import needs_attention as needs_attention
from version import APP_VERSION as APP_VERSION

__all__: list[str] = [
    "APP_VERSION",
    "DANGER_CTX_REMAINING",
    "LOOP_INTERVAL_SECONDS",
    "RowView",
    "Supervisor",
    "idle_nudge_message",
    "main",
    "plan_epic_resume",
    "plan_state_locator",
    "wrapup_message",
]


# --------------------------------------------------------------------------- #
# CLI. The daemon NEVER calls `start` — launching a session is surface-only.
# --------------------------------------------------------------------------- #


def build_supervisor() -> Supervisor:
    """Build the daemon's ``Supervisor`` for the CLI — with NO tunable surface.

    The invocation surface carries no watch-set / store / stamp knobs (they were
    de-gold-plated 2026-07-13): the watch-set is declared in ``$HOME``
    (``~/.livespec-overseer-repos.json``), and the mapping store + the
    injection-stamp sidecar are the hard-coded ``registry`` defaults
    (``~/.livespec-overseer.jsonl`` / ``~/.livespec-overseer-stamps.json``). The
    ``Supervisor`` dataclass keeps ``store_path`` / ``stamp_path`` / ``watch_repos``
    injectable, but ONLY the beside-tests inject them — never the CLI.

    ``own_pane`` is read from the environment rather than passed: ``overseerd`` runs
    INSIDE the daemon pane, so tmux has already exported that pane's id as ``$TMUX_PANE``.
    It is used only to badge the attention count onto the window name, so when it is
    absent (not under tmux) the badge simply never fires.
    """
    return Supervisor(
        watch_set_path=registry.DEFAULT_WATCH_SET_PATH,
        own_pane=os.environ.get("TMUX_PANE"),
    )


def _cli_colliding() -> frozenset[str]:
    """Cross-repo topic-collision set for one-shot CLI naming (``add`` / ``start``).

    Reads the SAME watch-set the daemon uses (the ``$HOME`` declaration at
    ``~/.livespec-overseer-repos.json``) and computes :func:`registry.colliding_topics`
    over its discovery, so a CLI-created session is named EXACTLY as the daemon would
    name it: the bare plan topic, or ``<slug>-<topic>`` only when the topic collides
    across repos.
    """
    watch = registry.watch_set_from_config(
        config_path=registry.DEFAULT_WATCH_SET_PATH, extra_repos=[]
    )
    return registry.colliding_topics(discovered=registry.discover_plans(watch_repos=watch))


def _upsert(*, track: registry.Track) -> None:
    """Replace any existing (repo, topic) mapping row in the hard-coded store, then
    append (one row each)."""
    _ = registry.remove_mapping(repo=track.repo, topic=track.topic, store_path=None)
    registry.append_mapping(track=track, store_path=None, added_at=iso_now())


def _track_for_assignment(*, repo: str, topic: str, session: str) -> registry.Track:
    """Build the mapping row written by attended assignment surfaces.

    No ``resume`` is written. That field is the OPERATOR's optional per-track override of
    the respawn prompt, and auto-populating it with a derived line made every row look
    like an override — which is why the derived value has to be ignored on read. The
    daemon derives the prompt from ``repo``, ``epic``, and the entity name instead.
    """
    return registry.Track(
        topic=topic,
        repo=repo,
        tmux=session,
        epic=registry.epic_from_plan_anchor(repo=repo, topic=topic),
    )


def run_daemon(*, warn_percent: int | None = None) -> int:
    """Start the fleet daemon with fixed defaults — the ``overseerd`` entrypoint.

    Called by the dedicated ``overseerd`` executable: watch every fleet member
    (discovered from the manifest, resolved relative to THIS file so it works from
    any cwd), with the hard-coded store + stamp paths and the default loop
    interval. ``warn_percent`` (from ``overseerd --warn-percent N``) is the
    daemon-wide default remaining-% at which the first wrap-up fires; None means
    the built-in ``registry.DEFAULT_CTX_THRESHOLD``. A per-track ``ctx_threshold``
    override still wins over it. ``recover=False`` keeps the daemon a pure
    surface-only watcher — it never auto-spawns/revives a session at startup;
    (re)launching a mapped-but-dead session is a deliberate ``start`` via the
    skill. This function does not return (the loop runs until the process is
    killed); the ``int`` is a formality so ``overseerd`` can ``raise SystemExit``.
    """
    supervisor = build_supervisor()
    # Set the field after building (rather than threading it through
    # `build_supervisor`) so the daemon keeps its single no-arg builder.
    supervisor.warn_percent = (
        warn_percent if warn_percent is not None else registry.DEFAULT_CTX_THRESHOLD
    )
    supervisor.run(interval=LOOP_INTERVAL_SECONDS, once=False, recover=False)
    return 0


def _cmd_list(*, args: argparse.Namespace) -> int:
    sup = build_supervisor()
    if args.json:
        original_out = sup.out
        sup.out = io.StringIO()
        try:
            rows = sup.tick(act=False)  # read-only classify: no injection/restart
        finally:
            sup.out = original_out
        body = json.dumps(
            _supervisor_snapshot.document_payload(sup=sup, rows=rows),
            indent=2,
            sort_keys=True,
        )
        streams.write_stdout(text=f"{body}\n")
    else:
        _ = sup.tick(act=False)  # read-only render: no injection/restart
    return 0


def _cmd_adopt(*, args: argparse.Namespace) -> int:
    del args  # `adopt` takes no options; the dispatch shape supplies one anyway
    adopted = build_supervisor().adopt_sessions()
    for track in adopted:
        streams.write_stdout(text=f"adopted {track.tmux} → {track.repo}::{track.topic}\n")
    streams.write_stdout(text=f"adopted {len(adopted)} existing session(s)\n")
    return 0


def _refuse_reserved_topic(*, repo: str, topic: str) -> bool:
    if not signals.topic_reserved_for_supervisor(topic=topic):
        return False
    streams.write_stderr(
        text=(
            f"refusing reserved supervisor topic {repo}::{topic}; "
            "worker topics may not end in -supervisor\n"
        )
    )
    return True


def _derive_tmux_or_refuse(*, repo: str, topic: str) -> str | None:
    try:
        return registry.tmux_id(repo=repo, topic=topic, colliding=_cli_colliding())
    except ValueError as exc:
        streams.write_stderr(text=f"{exc}\n")
        return None


def _cmd_add(*, args: argparse.Namespace) -> int:
    repo = os.path.normpath(args.repo)
    if _refuse_reserved_topic(repo=repo, topic=args.topic):
        return 1
    session = _derive_tmux_or_refuse(repo=repo, topic=args.topic)
    if session is None:
        return 1
    track = _track_for_assignment(repo=repo, topic=args.topic, session=session)
    _upsert(track=track)
    streams.write_stdout(text=f"added mapping {repo}::{args.topic} (tmux {track.tmux})\n")
    return 0


def _cmd_remove(*, args: argparse.Namespace) -> int:
    repo = os.path.normpath(args.repo)
    if _refuse_reserved_topic(repo=repo, topic=args.topic):
        return 1
    removed = registry.remove_mapping(repo=repo, topic=args.topic, store_path=None)
    streams.write_stdout(text=f"removed {removed} mapping row(s) for {args.repo}::{args.topic}\n")
    return 0


def _cmd_start(*, args: argparse.Namespace) -> int:
    """Surface-only, user-initiated launch. The daemon never invokes this.

    Guarded (B8): if the session already runs a LIVE Claude, ``start`` does NOT
    ``respawn-pane -k`` it (that would kill a mid-work session with no interlock —
    the exact "never force-kill mid-work" violation the whole design exists to
    prevent, reachable via a repeated bottom-pane ``start``). It just upserts the
    mapping and reports. ``--force`` is required to actually respawn a live one.
    """
    repo = os.path.normpath(args.repo)
    topic = args.topic
    if _refuse_reserved_topic(repo=repo, topic=topic):
        return 1
    session = _derive_tmux_or_refuse(repo=repo, topic=topic)
    if session is None:
        return 1
    force = getattr(args, "force", False)
    io = tmuxio.TmuxIO()
    sup = Supervisor(tmux=io)
    track = _track_for_assignment(repo=repo, topic=topic, session=session)
    if io.session_exists(session=session) and not force:
        # Fail CLOSED (RB4): refuse to respawn-kill an existing session unless we
        # POSITIVELY know it is DEAD. Only a bare SHELL proves that — a dead session
        # reports its shell name positively, so demanding proof costs nothing, while an
        # unreadable `pane_current_command` (None) or ANY other program might be live
        # work mid-flight.
        #
        # This asks "is it proven dead?", NOT "is it a live Claude?" (adversarial review,
        # probe-proven, 2026-07-17). The old test was `cmd is None or pane_is_claude(cmd)`,
        # which knew only ONE runtime: a live CODEX pane reports `bun`, failed the
        # Claude test, and was treated exactly like a dead shell — so a bare `start`
        # respawn-KILLED a live Codex TUI and replaced it with a claude one. The guard's
        # own stated purpose was already "fail closed on anything unproven-dead"; it just
        # enumerated the live runtimes instead of the dead one, which does not scale to a
        # second runtime and never did.
        cmd = io.pane_current_command(session=session)
        if not signals.pane_is_shell(pane_current_command=cmd):
            _upsert(track=track)
            streams.write_stdout(
                text=(
                    f"{repo}::{topic}: session {session} already running (or its identity is "
                    f"unreadable) — mapping upserted, NOT respawned. Pass --force to respawn "
                    f"(kills the running session).\n"
                )
            )
            return 0
    if not io.session_exists(session=session):
        _ = io.new_session(name=session, cwd=repo)
        # Require the EXACT session to exist before launching (Codex re-review #3):
        # a failed `new-session` must not let `_do_launch` respawn a prefix-matched
        # sibling.
        if not io.session_exists(session=session):
            streams.write_stderr(
                text=(
                    f"start FAILED: could not create tmux session {session} "
                    f"for {repo}::{topic}\n"
                )
            )
            return 1
    if not sup.do_launch(track=track, session=session):
        streams.write_stderr(
            text=f"start FAILED to launch {repo}::{topic} in tmux session {session}\n"
        )
        return 1
    _upsert(track=track)
    streams.write_stdout(text=f"started {repo}::{topic} in tmux session {session}\n")
    return 0


def _add_track_args(*, parser: argparse.ArgumentParser) -> None:
    """The shared ``--repo`` / ``--topic`` keyword flags for the track subcommands.

    Keyword (not positional) so the ``/overseer`` skill is the operator surface:
    it prompts for whichever is omitted and passes both. Required here so a stray
    bare invocation fails loudly rather than acting on a half-specified track.
    """
    _ = parser.add_argument("--repo", required=True, help="repo checkout path the plan lives in")
    _ = parser.add_argument(
        "--topic", required=True, help="plan topic (the plan/<topic>/ dir name)"
    )


def main(*, argv: list[str] | None = None) -> int:
    """The track-management CLI (`list` / `add` / `remove` / `unassign` / `start`).

    This is the MODULE's one-shot surface, invoked from the `/overseer` skill's
    bottom pane. It deliberately carries NO `daemon` subcommand: the daemon is the
    dedicated `overseerd` executable (which calls `run_daemon`), not a subcommand
    here — a daemon that IS the executable has no business being a subcommand of a
    track-management CLI. No watch-set / store / stamp knobs either; those are
    fixed (see `build_supervisor`).
    """
    parser = argparse.ArgumentParser(
        prog="overseer", description="livespec overseer track-management CLI"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="print the current joined table once (read-only)")
    _ = p_list.add_argument(
        "--json",
        action="store_true",
        help=(
            "emit observation-only snapshot JSON instead of the table; acting remains "
            "disabled because freshness is unproved"
        ),
    )
    p_list.set_defaults(func=_cmd_list)

    p_adopt = sub.add_parser(
        "adopt", help="adopt existing worker sessions matching active plan topics"
    )
    p_adopt.set_defaults(func=_cmd_adopt)

    p_add = sub.add_parser("add", help="add a (repo, topic) mapping row")
    _add_track_args(parser=p_add)
    p_add.set_defaults(func=_cmd_add)

    p_remove = sub.add_parser("remove", help="remove a (repo, topic) mapping row")
    _add_track_args(parser=p_remove)
    p_remove.set_defaults(func=_cmd_remove)

    # unassign is a synonym for remove: drop the mapping so the plan reverts to
    # `unassigned` (never force-kills the session — surface-only).
    p_unassign = sub.add_parser("unassign", help="detach a plan's mapping (revert to unassigned)")
    _add_track_args(parser=p_unassign)
    p_unassign.set_defaults(func=_cmd_remove)

    p_start = sub.add_parser("start", help="surface-only: launch a session for a plan and map it")
    _add_track_args(parser=p_start)
    _ = p_start.add_argument(
        "--force",
        action="store_true",
        help="respawn even if the session already runs a live Claude (kills it)",
    )
    p_start.set_defaults(func=_cmd_start)

    args = parser.parse_args(argv)
    handler: SubcommandHandler = args.func
    return int(handler(args=args))


if __name__ == "__main__":
    raise SystemExit(main())
