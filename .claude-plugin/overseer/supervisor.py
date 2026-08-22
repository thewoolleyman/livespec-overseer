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
import os

import _supervisor_assignment
import _supervisor_cli_actions
import _supervisor_cli_parser
import _supervisor_cli_start
import _supervisor_cli_topic
import _supervisor_cli_update
import _supervisor_snapshot
import registry
import streams
import tmuxio
from _seams import SubcommandHandler
from _signals_topics import reserved_seat_accepts_explicit_epic
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
        status_path=_supervisor_snapshot.DEFAULT_STATUS_PATH,
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
    return _supervisor_cli_topic.cli_colliding()


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
    return _supervisor_cli_actions.list_once(args=args, build_supervisor=build_supervisor)


def _cmd_adopt(*, args: argparse.Namespace) -> int:
    return _supervisor_cli_actions.adopt(args=args, build_supervisor=build_supervisor)


def _refuse_reserved_topic(*, repo: str, topic: str) -> bool:
    return _supervisor_cli_topic.refuse_reserved_topic(repo=repo, topic=topic)


def _derive_tmux_or_refuse(*, repo: str, topic: str, allow_reserved: bool = False) -> str | None:
    try:
        return registry.tmux_id(
            repo=repo, topic=topic, colliding=_cli_colliding(), allow_reserved=allow_reserved
        )
    except ValueError as exc:
        streams.write_stderr(text=f"{exc}\n")
        return None


def _inheritable_supervisor_epic_source(*, repo: str, topic: str) -> str | None:
    """The worker topic a ``-supervisor`` entity topic should inherit its epic from.

    None when ``topic`` is not a ``-supervisor`` entity, or when it is one but has
    no supervised counterpart (no ``plan/<worker>/`` directory) — the
    reserved-suffix guard still refuses those cases exactly as before, unchanged.
    A supervisor entity has no plan directory of its own by design, so this is
    the only way it can ever carry an epic.
    """
    epic_source = registry.plan_liveness_topic(repo=repo, topic=topic)
    if epic_source == topic:
        return None
    return epic_source


def _cmd_add(*, args: argparse.Namespace) -> int:
    repo = os.path.normpath(args.repo)
    epic = _supervisor_cli_update.optional_str_value(value=args.epic)
    allow_reserved = (
        epic_source_topic := _inheritable_supervisor_epic_source(repo=repo, topic=args.topic)
    ) is not None or reserved_seat_accepts_explicit_epic(repo=repo, topic=args.topic, epic=epic)
    if not allow_reserved and _refuse_reserved_topic(repo=repo, topic=args.topic):
        return 1
    session = _derive_tmux_or_refuse(repo=repo, topic=args.topic, allow_reserved=allow_reserved)
    if session is None:
        return 1
    try:
        track = _supervisor_assignment.assignment_track(
            repo=repo,
            topic=args.topic,
            session=session,
            epic_source_topic=epic_source_topic,
            epic=epic,
            ctx_threshold=_supervisor_cli_update.ctx_threshold_value(value=args.ctx_threshold),
        )
    except ValueError as exc:
        streams.write_stderr(text=f"{' '.join(str(arg) for arg in exc.args)}\n")
        return 1
    _supervisor_cli_update.upsert_track(
        track=track,
        update_fields=_supervisor_cli_update.add_update_fields(
            epic=args.epic, ctx_threshold=args.ctx_threshold
        ),
    )
    streams.write_stdout(text=f"added mapping {repo}::{args.topic} (tmux {track.tmux})\n")
    return 0


def _cmd_remove(*, args: argparse.Namespace) -> int:
    repo = os.path.normpath(args.repo)
    removed = registry.remove_mapping(repo=repo, topic=args.topic, store_path=None)
    streams.write_stdout(text=f"removed {removed} mapping row(s) for {args.repo}::{args.topic}\n")
    return 0


def _start_handler(*, args: argparse.Namespace) -> int:
    return _supervisor_cli_start.start_command(
        args=args,
        derive_tmux_or_refuse=_derive_tmux_or_refuse,
        tmux_factory=tmuxio.TmuxIO,
        supervisor_factory=Supervisor,
    )


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
    parser = _supervisor_cli_parser.build_parser(
        handlers=_supervisor_cli_parser.ParserHandlers(
            list_handler=_cmd_list,
            adopt_handler=_cmd_adopt,
            add_handler=_cmd_add,
            remove_handler=_cmd_remove,
            start_handler=_start_handler,
        ),
        add_track_args=_add_track_args,
        add_mapping_write_args=_supervisor_cli_update.add_mapping_write_args,
    )
    args = parser.parse_args(argv)
    handler: SubcommandHandler = args.func
    return int(handler(args=args))


if __name__ == "__main__":
    raise SystemExit(main())
