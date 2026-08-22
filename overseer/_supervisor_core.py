"""supervisor.py — the overseer daemon: poll loop, state machine, table, CLI.

Stdlib-only, host-only (see ``registry.py`` header — the whole skill folder is
outside the livespec product gates). This module *acts and renders*; it holds
NO semantic judgment. Every "am I done / blocked?" decision is made by the
tracked session's own LLM and DECLARED out-of-band on the filesystem (the ONE
``.overseer-state`` file); this daemon only pattern-matches deterministic tmux
signals and that declaration — it never infers readiness for itself.

It builds on the already-merged pure-logic core:
  - ``registry.py`` — discovery ⋈ mapping, the JSONL store, injection stamps.
  - ``signals.py``  — pane parsing (busy / gate / idle / ctx%) + the ONE indicator
    file (``read_state`` / ``ready_valid``).
  - ``tmuxio.py``   — the single tmux subprocess boundary (injectable, faked in
    tests).

THE CARDINAL RULE (maintainer 2026-07-14): **the daemon NEVER restarts a session
that has not declared itself ready.** A tracked session declares its own state by
writing ONE line to ONE file (``<repo>/tmp/overseer/<topic>/.overseer-state``):

    ready                       at a clean stopping point — restart me
    blocked: <one-line reason>  needs a human decision the session cannot make
    winding-down                acknowledged the wrap-up; wrapping up now

``ready`` is the SOLE authorization for a restart. The daemon never infers it from a
timer, from idleness, or from anything else: "idle + settled" is NOT "safe to kill" —
a session can be idle while a background build runs, while a sub-agent works, or while
it waits on a human in another pane. Only the session knows, so only the session may
say so. A session that declares NOTHING is reported to the human as not responding and
is left alone — that is a bug in the session, never a licence for the daemon to guess.

One file with a VALUE, not two presence-markers: two files could both exist, and their
precedence was incidental rather than designed.

Per-tick state machine (precedence, top to bottom — working / blocked:human are
detected FIRST so injection is suppressed there):

    working        is_busy (incl. a live background shell)  → leave alone
    blocked:human  is_structured_gate OR state == blocked   → surface; suppress inject
    restarting     state == ready (fresh) AND idle-input    → respawn + resume + clear state
    winding-down   fresh ACK                                → wait; suppress re-warn
    warned/danger  ctx ≤ threshold AND idle-input           → escalating wrap-up; danger SURFACES
    idle           ctx > threshold                          → leave alone
    settling       pane present but not verified idle       → wait

``restarting`` is checked BEFORE ``warned``: a fresh ``ready`` means the session
already declared it is done, so it supersedes any re-warn. The wrap-up ESCALATES by
10% band (50/40 suggest → 30/20/10 insist), and a fresh ``winding-down`` suppresses it
so the daemon never keystrokes into a session that is already wrapping up.

**This module is the daemon's CLASS, extracted from `supervisor.py`.** `supervisor.py`
crossed the 250-LLOC hard ceiling by more than five times, so it became a FACADE that
re-exports this surface and keeps the one-shot track-management CLI; the constants,
prompts, view projection and per-tick records moved to `_supervisor_config`,
`_supervisor_prompts`, `_supervisor_view` and `_supervisor_records`. Consumers are
untouched: `import supervisor` still resolves `Supervisor` and everything else.

This file is STILL over the ceiling on its own — decomposing `Supervisor`'s method
groups into `_supervisor_<topic>.py` collaborators of free functions is the remaining
work (overseer-bg2.3). Import a constant FROM the module that defines it, never through
the `supervisor` facade: a facade re-export can be monkeypatched successfully while the
reader here keeps its own binding.
"""
# livespec-lloc-soft-band-owner: overseer-temi26.2

from __future__ import annotations

import os
import shutil
import sys
import time
import uuid
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO

import _seams
import _supervisor_currency
import _supervisor_diagnostics
import _supervisor_discovery
import _supervisor_evaluate
import _supervisor_launch
import _supervisor_lifecycle
import _supervisor_nudge
import _supervisor_observe
import _supervisor_recovery
import _supervisor_render
import _supervisor_restart
import _supervisor_snapshot
import _supervisor_state
import _supervisor_tick
import claude_sessions
import codex_sessions
import registry
import tmuxio
from _supervisor_config import (
    LOOP_INTERVAL_SECONDS,
    default_gitignore_check,
    installed_claude_version,
)
from _supervisor_records import InjectState, PairStallState
from _supervisor_view import RowView

__all__: list[str] = ["Supervisor"]

CodexSessionMap = dict[tuple[str, str], codex_sessions.CodexSession]
MaybeStr = str | None
CurrencyCheck = Callable[[], Mapping[str, object] | None]


def _process_execv(*, path: str, argv: list[str]) -> None:  # pragma: no cover
    os.execv(path, argv)  # noqa: S606


# --------------------------------------------------------------------------- #
# The daemon.
# --------------------------------------------------------------------------- #


@dataclass
class Supervisor:
    """The deterministic multi-track supervisor.

    All external state is injectable so tests drive it with a fake ``tmux`` and
    ``tmp_path`` stores — no real tmux, no touching ``~``. ``watch_repos`` may
    be given explicitly (tests) or read from the ``$HOME`` watch-set declaration
    (daemon CLI).
    """

    tmux: tmuxio.PaneDriver = field(default_factory=tmuxio.TmuxIO)
    store_path: str | os.PathLike[str] | None = None
    stamp_path: str | os.PathLike[str] | None = None
    watch_repos: list[str] | None = None
    watch_set_path: str | os.PathLike[str] | None = None
    status_snapshot_path: str | os.PathLike[str] | None = None
    status_path: str | os.PathLike[str] | None = None
    status_writer: _seams.StatusWriter = _supervisor_snapshot.default_status_writer
    status_snapshot_writer: Callable[..., None] = _supervisor_snapshot.write_status_snapshot
    currency_check: CurrencyCheck | None = None
    reexec_target: Callable[[], Path | None] = field(default_factory=lambda: lambda: None)
    argv: Callable[[], list[str]] = field(default_factory=lambda: lambda: sys.argv)
    execv: Callable[..., None] = _process_execv
    reexec_min_interval_seconds: float = 3600.0
    extra_repos: list[str] = field(default_factory=list)
    # Daemon-wide default warn threshold (remaining-% at which the FIRST wrap-up
    # fires) for any track WITHOUT a per-track ``ctx_threshold`` override. Set from
    # ``overseerd --warn-percent`` via ``run_daemon``; a track's own override wins.
    warn_percent: int = registry.DEFAULT_CTX_THRESHOLD
    # Resolved at CONSTRUCTION rather than at import, so a caller (or a test)
    # that redirects sys.stdout first still gets the stream it expects.
    out: IO[str] = field(default_factory=lambda: sys.stdout)
    now: Callable[[], float] = time.time
    sleep: Callable[[float], None] = time.sleep
    # Claude session-registry adoption seams (default: real ~/.claude/sessions + /proc;
    # the beside-tests inject a tmp registry dir + fake /proc readers).
    sessions_dir: str | os.PathLike[str] | None = None
    ppid_of: _seams.PidToOptionalInt = claude_sessions.proc_ppid
    starttime_of: _seams.PidToOptionalStr = claude_sessions.proc_starttime
    cmdline_of: _seams.PidToOptionalBytes = claude_sessions.proc_cmdline
    environ_of: _seams.PidToOptionalBytes = claude_sessions.proc_environ
    # Background-subshell detection seams (default: real /proc; the beside-tests
    # inject fake process-tree readers). A tracked session sitting at an empty
    # prompt but with a later `Bash(run_in_background)` command still running has a
    # DESCENDANT shell under its pane process; startup wrapper shells are ignored
    # only when their /proc starttime proves they were born with the runtime.
    children_of: _seams.PidToIntList = claude_sessions.proc_children
    comm_of: _seams.PidToOptionalStr = claude_sessions.proc_comm
    # Codex session-discovery seams (default: real /proc scan + ~/.codex; the beside-tests
    # inject fakes). Unlike Claude — whose candidate pids come from the injected registry
    # dir (`sessions_dir`) — Codex discovers its pids by a live `/proc` `comm==codex` scan
    # and reads `~/.codex/session_index.jsonl` for the topic, so its host coupling is a
    # DISTINCT reader set. It MUST be injectable or every adopt/refresh test would read the
    # host's real /proc and ~/.codex (test-isolation defect #6). `codex_home=None` means the
    # codex_sessions functions resolve the real `~/.codex` themselves, so it is threaded
    # through as-is (no `_sessions_dir`-style helper needed). `ppid_of` (the tmux-join walk)
    # is shared with the Claude seam above.
    codex_home: str | os.PathLike[str] | None = None
    codex_pids_of_comm: _seams.CommToPidList = codex_sessions.proc_pids_of_comm
    codex_fd_targets_of: _seams.PidToStrList = codex_sessions.proc_fd_targets
    # Host-precondition seams (default: the real `/proc` + a real PATH lookup; the
    # beside-tests' `_sup` factory defaults them to a SUPPORTED-looking host so the
    # suite never depends on the RUNNER having tmux). Linux + tmux is a DECLARED
    # REQUIREMENT, deliberately NOT an abstraction boundary: the session readers read
    # `/proc/<pid>/stat`, which macOS does not have AT ALL, and every acting mechanic
    # drives a real tmux. `which` is asked about the literal `tmux` NAME rather than a
    # caller's injected `tmux_bin`, because this gate asks "is this host supported at
    # all?" — not "is that particular binary resolvable", which a fake tmux would
    # wrongly satisfy.
    proc_root: str | os.PathLike[str] = "/proc"
    which: Callable[[str], str | None] = shutil.which
    codex_cwd_of: _seams.PidToOptionalStr = codex_sessions.proc_cwd
    # Startup gate: `<repo>/tmp/overseer/` MUST be gitignored (the overseer only
    # writes temp files, never tracked ones). Injectable so tests fake the check.
    gitignore_check: _seams.RepoPredicate = default_gitignore_check
    claude_version_of: Callable[[], str | None] = installed_claude_version
    # Assignment-time epic lookup re-used once at the restart boundary when a stored row
    # still has ``epic=None``. Tests inject this so ready-certification paths never reach
    # a host Beads ledger through ``bd``.
    epic_lookup: _seams.EpicLookup = field(default_factory=lambda: registry.epic_from_plan_anchor)
    # The daemon's OWN pane (its `$TMUX_PANE`, inherited because `overseerd` is launched
    # inside the top pane). Used only to badge the attention count onto the tmux WINDOW
    # name — the one overseer surface visible from a session the operator is attached to.
    # None (not in tmux, or a test) simply disables the badge.
    own_pane: str | None = None
    daemon_instance_id: str = field(default_factory=lambda: uuid.uuid4().hex, init=False)
    tick_generation: int = field(default=0, init=False)
    last_reexec_attempt_at: float = field(default=float("-inf"), init=False)
    status_snapshot_failed: bool = field(default=False, init=False)
    inject: dict[tuple[str, str], InjectState] = field(default_factory=dict, init=False)
    pair_stalls: dict[tuple[str, str], PairStallState] = field(default_factory=dict, init=False)
    mapping_epics: dict[tuple[str, str], str] = field(default_factory=dict, init=False)
    # Edge-trigger memory for `alert`: track key + condition → the last alert line
    # emitted for it. Keeps the log an EVENT HISTORY (one line per condition entered)
    # instead of the same line re-emitted every tick. Re-armed in `evaluate` when the
    # track goes healthy.
    alerted: dict[tuple[str, str, str], str] = field(default_factory=dict, init=False)
    currency_blocked_message: str | None = field(default=None, init=False)
    # Last window name written, so the badge is only re-sent when the count CHANGES
    # (a tmux call every tick for an unchanged name is pure noise).
    last_window_name: str | None = field(default=None, init=False)
    # `{tmux_session: claude_registry_status}` for this tick, recomputed at the top of
    # every `build_rows`. Claude's own live self-report ("busy"/"idle"/"waiting") is an
    # AUTHORITATIVE busy signal that catches in-process sub-agents the process-tree walk
    # cannot see. Empty for Codex sessions (not in Claude's registry) and in direct-
    # `evaluate` beside-tests that don't set it.
    claude_status_by_session: dict[str, str] = field(default_factory=dict, init=False)
    # `{tmux_session: {claude_registry_name, ...}}` for this tick, recomputed beside
    # `claude_status_by_session`. The identity gate (`_pane_is_managed_claude`) checks that the
    # track's
    # TOPIC is among the live Claude names in the pane's tmux session — parity with the Codex
    # gate's `name == topic` check — so a generic reused tmux window the store maps to topic A
    # but now running topic B's Claude is not mis-driven (R2, 2026-07-18). It is a SET (not a
    # last-wins single) so a helper Claude sharing the tmux session cannot shadow the track's
    # own name and flap it to `session-gone` (review SF5). Empty for Codex sessions (not in
    # Claude's registry) and in direct-`evaluate` beside-tests that don't set it — an unknown
    # tmux session preserves the prior repo+process gate (fail-soft).
    claude_names_by_session: dict[str, set[str]] = field(default_factory=dict, init=False)
    claude_identity_by_session: dict[tuple[str, str], str] = field(default_factory=dict, init=False)
    # {tmux_session: CodexSession} for every live NAMED codex session, recomputed each
    # tick beside claude_status_by_session. Membership IS the exact answer to "is this pane
    # Codex?" — the pane command says `bun` (the launcher), which is too generic to
    # trust. Typed loosely to keep the dataclass free of a codex_sessions import cycle.
    live_codex: CodexSessionMap = field(default_factory=dict, init=False)
    # Topics that appear in >=2 watched repos this tick, recomputed at the top of
    # `build_rows` (before adopt/auto_link/evaluate run, so every session-name
    # derivation this tick sees the same set). `registry.tmux_id` repo-qualifies
    # ONLY these — so a session is named after its bare plan topic unless that topic
    # genuinely collides across repos (maintainer-declared 2026-07-19). Empty in
    # direct-`evaluate` beside-tests that don't run `build_rows` — which yields the
    # bare-topic name, the correct default for a single-repo fixture.
    colliding_topics: frozenset[str] = field(default_factory=frozenset, init=False)
    # ----------------------------------------------------------------- #
    # Diagnostics.
    # ----------------------------------------------------------------- #

    def log(
        self,
        *,
        message: str,
        event: str = "daemon-log",
        repo: str | None = None,
        topic: str | None = None,
        fields: Mapping[str, object] | None = None,
    ) -> None:
        _supervisor_diagnostics.log(
            sup=self,
            message=message,
            event=event,
            repo=repo,
            topic=topic,
            fields=fields,
        )

    def log_claude_build(self, *, phase: str) -> None:
        _supervisor_diagnostics.log_claude_build(sup=self, phase=phase)

    def surface(
        self,
        *,
        message: str,
        event: str = "daemon-alert",
        repo: str | None = None,
        topic: str | None = None,
        fields: Mapping[str, object] | None = None,
    ) -> None:
        """Surface a DAEMON-level alert to the operator (stderr; the bottom pane reads it).

        For anything scoped to a TRACK, use :meth:`alert` instead — it guarantees the
        tmux coordinates the operator needs in order to act.
        """
        _supervisor_diagnostics.surface(
            sup=self,
            message=message,
            event=event,
            repo=repo,
            topic=topic,
            fields=fields,
        )

    def alert(
        self,
        *,
        repo: str,
        topic: str,
        session: str | None,
        pane: str | None,
        message: str,
        condition: str = "default",
    ) -> None:
        """Surface a TRACK-scoped alert that always names WHERE to act."""
        _supervisor_diagnostics.alert(
            request=_supervisor_diagnostics.AlertRequest(
                sup=self,
                repo=repo,
                topic=topic,
                session=session,
                pane=pane,
                message=message,
                condition=condition,
            )
        )

    # ----------------------------------------------------------------- #
    # Watch-set + discovery ⋈ mapping.
    # ----------------------------------------------------------------- #

    def _resolve_watch(self) -> list[str]:
        """See :func:`_supervisor_discovery.resolve_watch`."""
        return _supervisor_discovery.resolve_watch(sup=self)

    def archive_gc(self) -> int:
        """See :func:`_supervisor_discovery.archive_gc`."""
        return _supervisor_discovery.archive_gc(sup=self)

    def auto_link(self, *, track: registry.Track) -> registry.Track | None:
        """See :func:`_supervisor_discovery.auto_link`."""
        return _supervisor_discovery.auto_link(sup=self, track=track)

    def adopt_sessions(self) -> list[registry.Track]:
        """See :func:`_supervisor_discovery.adopt_sessions`."""
        return _supervisor_discovery.adopt_sessions(sup=self)

    def _refresh_codex_sessions(self) -> None:
        """See :func:`_supervisor_discovery.refresh_codex_sessions`."""
        _supervisor_discovery.refresh_codex_sessions(sup=self)

    def refresh_codex_sessions(self) -> None:
        return self._refresh_codex_sessions()

    def _refresh_claude_status(self) -> None:
        """See :func:`_supervisor_discovery.refresh_claude_status`."""
        _supervisor_discovery.refresh_claude_status(sup=self)

    def refresh_claude_status(self) -> None:
        return self._refresh_claude_status()

    def build_rows(self, *, act: bool = True) -> list[registry.Track]:
        """See :func:`_supervisor_discovery.build_rows`."""
        return _supervisor_discovery.build_rows(sup=self, act=act)

    # ----------------------------------------------------------------- #
    # Per-track evaluation (the state machine).
    # ----------------------------------------------------------------- #

    def _session_of(self, *, track: registry.Track) -> str:
        """See :func:`_supervisor_launch.session_of`."""
        return _supervisor_launch.session_of(sup=self, track=track)

    def _is_codex_track(
        self, *, session: MaybeStr, repo: str, topic: str, target: MaybeStr = None
    ) -> bool:
        """See :func:`_supervisor_observe.is_codex_track`."""
        return _supervisor_observe.is_codex_track(
            sup=self, session=session, repo=repo, topic=topic, target=target
        )

    def _clear_state(self, *, track: registry.Track) -> None:
        """See :func:`_supervisor_state.clear_state`."""
        _supervisor_state.clear_state(sup=self, track=track)

    def _expire_aged_ready(self, *, track: registry.Track) -> bool:
        """See :func:`_supervisor_state.expire_aged_ready`."""
        return _supervisor_state.expire_aged_ready(sup=self, track=track)

    def _void_stale_blocked(
        self, *, track: registry.Track, blocked: MaybeStr, generating: bool
    ) -> MaybeStr:
        """See :func:`_supervisor_state.void_stale_blocked`."""
        return _supervisor_state.void_stale_blocked(
            sup=self, track=track, blocked=blocked, generating=generating
        )

    def _write_idle_nudge_state(self, *, track: registry.Track) -> None:
        """See :func:`_supervisor_nudge.write_idle_nudge_state`."""
        _supervisor_nudge.write_idle_nudge_state(sup=self, track=track)

    def evaluate(self, *, track: registry.Track, act: bool) -> RowView:
        """See :func:`_supervisor_evaluate.evaluate`."""
        return _supervisor_evaluate.evaluate(sup=self, track=track, act=act)

    def _do_codex_restart(self, *, track: registry.Track, target: str) -> None:
        """See :func:`_supervisor_restart.do_codex_restart`."""
        _supervisor_restart.do_codex_restart(sup=self, track=track, target=target)

    _launch_command = staticmethod(_supervisor_launch.launch_command)
    _codex_launch_command = staticmethod(_supervisor_launch.codex_launch_command)

    def _submit_prompt(self, *, target: str, text: str, expect_codex: bool = False) -> bool:
        """See :func:`_supervisor_launch.submit_prompt`."""
        return _supervisor_launch.submit_prompt(
            sup=self, target=target, text=text, expect_codex=expect_codex
        )

    # ----------------------------------------------------------------- #
    # Reboot recovery (startup-only, never per-tick).
    # ----------------------------------------------------------------- #

    def recover_missing_sessions(self) -> list[str]:
        """See :func:`_supervisor_recovery.recover_missing_sessions`."""
        return _supervisor_recovery.recover_missing_sessions(sup=self)

    def _do_codex_launch(self, *, track: registry.Track, session: str, session_id: str) -> bool:
        """See :func:`_supervisor_recovery.do_codex_launch`."""
        return _supervisor_recovery.do_codex_launch(
            sup=self, track=track, session=session, session_id=session_id
        )

    def do_launch(self, *, track: registry.Track, session: str, start: bool = False) -> bool:
        """See :func:`_supervisor_recovery.do_launch`."""
        return _supervisor_recovery.do_launch(sup=self, track=track, session=session, start=start)

    def do_launch_result(
        self, *, track: registry.Track, session: str, start: bool = False
    ) -> _supervisor_recovery.LaunchResult:
        """See :func:`_supervisor_recovery.do_launch_result`."""
        return _supervisor_recovery.do_launch_result(
            sup=self, track=track, session=session, start=start
        )

    # ----------------------------------------------------------------- #
    # Table rendering.
    # ----------------------------------------------------------------- #

    def render(self, *, rows: Iterable[RowView]) -> None:
        """Paint the live table + the ``NEEDS YOU`` block. See :mod:`_supervisor_render`."""
        _supervisor_render.render_table(sup=self, rows=rows)

    def _refresh_window_name(self, *, attention: int) -> None:
        """Badge the attention count onto the tmux window name. See :mod:`_supervisor_render`."""
        _supervisor_render.refresh_window_name(sup=self, attention=attention)

    # ----------------------------------------------------------------- #
    # Tick + loop.
    # ----------------------------------------------------------------- #

    def tick(self, *, act: bool = True) -> list[RowView]:
        """One loop iteration: build rows, evaluate each, render the table + attention block."""
        return _supervisor_tick.run_tick(sup=self, act=act)

    def currency_row(self) -> RowView | None:
        """Surface release-currency failures without stopping supervision."""
        return _supervisor_currency.currency_row(sup=self)

    # ----------------------------------------------------------------- #
    # Singleton daemon lock (per store).
    # ----------------------------------------------------------------- #

    def _singleton_lock_path(self) -> Path:
        """See :func:`_supervisor_lifecycle.singleton_lock_path`."""
        return _supervisor_lifecycle.singleton_lock_path(sup=self)

    def _acquire_singleton_lock(self) -> IO[str] | None:
        """See :func:`_supervisor_lifecycle.acquire_singleton_lock`."""
        return _supervisor_lifecycle.acquire_singleton_lock(sup=self)

    @staticmethod
    def _release_singleton_lock(*, handle: IO[str] | None) -> None:
        """See :func:`_supervisor_lifecycle.release_singleton_lock`."""
        _supervisor_lifecycle.release_singleton_lock(handle=handle)

    def unignored_tmp_repos(self) -> list[str]:
        """See :func:`_supervisor_lifecycle.unignored_tmp_repos`."""
        return _supervisor_lifecycle.unignored_tmp_repos(sup=self)

    def unsupported_host_reasons(self) -> list[str]:
        """See :func:`_supervisor_lifecycle.unsupported_host_reasons`."""
        return _supervisor_lifecycle.unsupported_host_reasons(sup=self)

    def run(
        self, *, interval: float = LOOP_INTERVAL_SECONDS, once: bool = False, recover: bool = False
    ) -> None:
        """See :func:`_supervisor_lifecycle.run_loop`."""
        _supervisor_lifecycle.run_loop(sup=self, interval=interval, once=once, recover=recover)
