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

from __future__ import annotations

import os
import shutil
import sys
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO

import _supervisor_discovery
import _supervisor_launch
import _supervisor_lifecycle
import _supervisor_nudge
import _supervisor_observe
import _supervisor_offer
import _supervisor_recovery
import _supervisor_render
import _supervisor_restart
import _supervisor_state
import claude_sessions
import codex_sessions
import registry
import signals
import streams
import tmuxio
from _supervisor_config import (
    DANGER_CTX_REMAINING,
    IDLE_NUDGE_AFTER,
    LOOP_INTERVAL_SECONDS,
    SUPERVISION_CONDITIONS,
    default_gitignore_check,
    iso_now,
    track_key,
)
from _supervisor_records import InjectState
from _supervisor_view import (
    MAX_REASON_IN_ALERT,
    RESUME_PENDING_NOTE,
    RowView,
    elide,
    needs_attention,
)

__all__: list[str] = ["Supervisor"]


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
    ppid_of: Callable[[int], int | None] = claude_sessions.proc_ppid
    starttime_of: Callable[[int], str | None] = claude_sessions.proc_starttime
    # Background-subshell detection seams (default: real /proc; the beside-tests
    # inject fake process-tree readers). A tracked session sitting at an empty
    # prompt but with a `Bash(run_in_background)` command still running has a
    # DESCENDANT shell under its pane process — that means active background work,
    # so the session is BUSY, not idle (never respawn-pane -k a session with live
    # background work).
    children_of: Callable[[int], list[int]] = claude_sessions.proc_children
    comm_of: Callable[[int], str | None] = claude_sessions.proc_comm
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
    codex_pids_of_comm: Callable[[str], list[int]] = codex_sessions.proc_pids_of_comm
    codex_fd_targets_of: Callable[[int], list[str]] = codex_sessions.proc_fd_targets
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
    codex_cwd_of: Callable[[int], str | None] = codex_sessions.proc_cwd
    # Startup gate: `<repo>/tmp/overseer/` MUST be gitignored (the overseer only
    # writes temp files, never tracked ones). Injectable so tests fake the check.
    gitignore_check: Callable[[str], bool] = default_gitignore_check
    # The daemon's OWN pane (its `$TMUX_PANE`, inherited because `overseerd` is launched
    # inside the top pane). Used only to badge the attention count onto the tmux WINDOW
    # name — the one overseer surface visible from a session the operator is attached to.
    # None (not in tmux, or a test) simply disables the badge.
    own_pane: str | None = None
    inject: dict[tuple[str, str], InjectState] = field(default_factory=dict, init=False)
    # Edge-trigger memory for `alert`: track key + condition → the last alert line
    # emitted for it. Keeps the log an EVENT HISTORY (one line per condition entered)
    # instead of the same line re-emitted every tick. Re-armed in `evaluate` when the
    # track goes healthy.
    alerted: dict[tuple[str, str, str], str] = field(default_factory=dict, init=False)
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
    # {tmux_session: CodexSession} for every live NAMED codex session, recomputed each
    # tick beside claude_status_by_session. Membership IS the exact answer to "is this pane
    # Codex?" — the pane command says `bun` (the launcher), which is too generic to
    # trust. Typed loosely to keep the dataclass free of a codex_sessions import cycle.
    live_codex: dict[tuple[str, str], codex_sessions.CodexSession] = field(
        default_factory=dict, init=False
    )
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

    def log(self, message: str) -> None:
        streams.write_stderr(text=f"{iso_now()} overseer: {message}\n")

    def surface(self, message: str) -> None:
        """Surface a DAEMON-level alert to the operator (stderr; the bottom pane reads it).

        For anything scoped to a TRACK, use :meth:`alert` instead — it guarantees the
        tmux coordinates the operator needs in order to act.
        """
        streams.write_stderr(text=f"{iso_now()} overseer[SURFACE]: {message}\n")

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
        """Surface a TRACK-scoped alert that always names WHERE to act.

        Every track alert carries the plan topic, its repo, the tmux SESSION and PANE
        holding it, and a copy-pasteable jump command. ``repo::topic`` alone tells the
        operator WHAT is stuck but never WHERE to go — they were left to hunt for the
        session by hand (maintainer 2026-07-14).

        This is load-bearing for the notify-never-block contract (invariant 8): because
        the overseer NEVER prompts on a track's behalf, this line is the operator's ONLY
        handover, so it MUST be self-sufficient. Every new track-scoped alert goes
        through here — never a bare ``surface`` with an f-string of ``repo::topic``.

        EDGE-TRIGGERED: emitted when a track ENTERS a condition (or the condition's text
        changes), NOT once per tick. The log is the daemon's EVENT HISTORY — the surface
        the bottom pane reads to answer "what happened, and when?" — while CURRENT state
        is owned by the re-rendered table + its ``NEEDS YOU`` block. Re-emitting an
        unchanged alert every tick buried that history in thousands of identical lines (a
        track blocked overnight logged ~3,000 of them) and answered a question the table
        already answers better. The re-arm is in :meth:`evaluate`: when a track returns to
        a healthy status its entry is dropped, so the NEXT time it goes bad it reports
        again.
        """
        where = f"tmux session '{session}' pane {pane}" if session else "no live tmux session"
        jump = f" — jump: tmux switch-client -t {session}" if session else ""
        line = f"{topic} ({registry.repo_slug(repo)}) — {message} [{where}]{jump}"
        key = (*track_key(repo, topic), condition)
        if self.alerted.get(key) == line:
            return
        self.alerted[key] = line
        self.surface(line)

    # ----------------------------------------------------------------- #
    # Watch-set + discovery ⋈ mapping.
    # ----------------------------------------------------------------- #

    def _resolve_watch(self) -> list[str]:
        """See :func:`_supervisor_discovery.resolve_watch`."""
        return _supervisor_discovery.resolve_watch(self)

    def archive_gc(self) -> int:
        """See :func:`_supervisor_discovery.archive_gc`."""
        return _supervisor_discovery.archive_gc(self)

    def auto_link(self, track: registry.Track) -> registry.Track | None:
        """See :func:`_supervisor_discovery.auto_link`."""
        return _supervisor_discovery.auto_link(self, track)

    def adopt_sessions(self) -> list[registry.Track]:
        """See :func:`_supervisor_discovery.adopt_sessions`."""
        return _supervisor_discovery.adopt_sessions(self)

    def _refresh_codex_sessions(self) -> None:
        """See :func:`_supervisor_discovery.refresh_codex_sessions`."""
        _supervisor_discovery.refresh_codex_sessions(self)

    def _refresh_claude_status(self) -> None:
        """See :func:`_supervisor_discovery.refresh_claude_status`."""
        _supervisor_discovery.refresh_claude_status(self)

    def build_rows(self, *, act: bool = True) -> list[registry.Track]:
        """See :func:`_supervisor_discovery.build_rows`."""
        return _supervisor_discovery.build_rows(self, act=act)

    # ----------------------------------------------------------------- #
    # Per-track evaluation (the state machine).
    # ----------------------------------------------------------------- #

    def _session_of(self, track: registry.Track) -> str:
        """See :func:`_supervisor_launch.session_of`."""
        return _supervisor_launch.session_of(self, track)

    def _is_codex_track(
        self, session: str | None, repo: str, topic: str, target: str | None = None
    ) -> bool:
        """See :func:`_supervisor_observe.is_codex_track`."""
        return _supervisor_observe.is_codex_track(self, session, repo, topic, target)

    def _clear_state(self, track: registry.Track) -> None:
        """See :func:`_supervisor_state.clear_state`."""
        _supervisor_state.clear_state(self, track)

    def _void_if_stale(self, track: registry.Track, *, ready: bool) -> bool:
        """See :func:`_supervisor_state.void_if_stale`."""
        return _supervisor_state.void_if_stale(self, track, ready=ready)

    def _void_stale_blocked(
        self, track: registry.Track, blocked: str | None, *, generating: bool
    ) -> str | None:
        """See :func:`_supervisor_state.void_stale_blocked`."""
        return _supervisor_state.void_stale_blocked(self, track, blocked, generating=generating)

    def _write_idle_nudge_state(self, track: registry.Track) -> None:
        """See :func:`_supervisor_nudge.write_idle_nudge_state`."""
        _supervisor_nudge.write_idle_nudge_state(self, track)

    def evaluate(  # noqa: C901,PLR0911,PLR0912,PLR0915 — see "On the size of this function"
        self, track: registry.Track, *, act: bool
    ) -> RowView:
        """Derive a track's status and (when ``act``) perform its side effects.

        ``act=False`` is the read-only path used by the ``list`` command: it
        captures the pane and reads markers but performs NO paste / respawn /
        stamp write. The daemon loop calls with ``act=True``.

        **On the size of this function.** What remains after :meth:`_observe` was
        split out is the DECISION CASCADE: an ordered sequence of guards, each of
        which either returns a row or falls through to the next. Its length is the
        number of distinct states a track can be in, and its ordering IS the
        design — the cardinal rule (never restart a session that has not declared
        itself ready) is enforced by which guard comes first, not by any single
        guard in isolation.

        Extracting the fact-gathering was a real seam and is done; it took the
        function from 106 statements / 38 branches / complexity 34 down to 83 / 33
        / 31. Going further would mean cutting the cascade itself into per-state
        helpers, which was considered and rejected (maintainer-declared
        2026-07-19): it would scatter the precedence order across call sites where
        no reader can check it in one pass, and precedence is exactly what a
        reviewer of this function needs to verify. The four complexity rules are
        therefore suppressed HERE, on this one function, rather than for the file
        or the folder — every other function in this module is still held to them.
        """
        if track.is_unassigned:
            return RowView(
                topic=track.topic, repo=track.repo, tmux=None, ctx=None, status="unassigned"
            )

        repo, topic = track.repo, track.topic
        session = self._session_of(track)
        key = track_key(repo, topic)

        if not self.tmux.session_exists(session):
            # The mapped TMUX session is gone — but the work may not be. A Claude
            # session for the same plan can keep running in a NON-tmux terminal (a bare
            # SSH shell), which the tmux-only daemon cannot capture, inject, or respawn.
            # Distinguish that live-but-unmanageable case from a genuinely gone track so
            # the operator is not falsely alarmed that finished-looking work was lost.
            return _supervisor_offer.no_managed_pane_row(self, repo=repo, topic=topic)

        # Resolve the pane id ONCE and target every subsequent pane op by it (RB3).
        # A pane id is exact and never prefix/fnmatch-matched, so if the tracked
        # session dies mid-tick the ops fail-soft instead of a bare `-t <name>`
        # falling back to a live SIBLING session (e.g. dead `livespec--overseer`
        # resolving to live `livespec--overseer-rewrite`) and, worst case,
        # `respawn-pane -k` killing it. Stable across respawn.
        target = self.tmux.pane_id(session)
        if target is None:
            return _supervisor_offer.no_managed_pane_row(self, repo=repo, topic=topic)

        # Identity gate (B3): the mapped session exists, but before reading its pane
        # for any ACT we confirm it is really OUR Claude in OUR repo — never
        # keystroke into a shell / wrong session / human split-pane.
        if not _supervisor_observe.pane_is_managed(self, target, repo, topic, session):
            # The gate stays exactly what it was — an ACT guard (never keystroke into a
            # pane not proven ours). What changed is that its answer is no longer a row
            # STATUS of its own. Whether the pane is a bare shell (our session exited) or
            # something foreign, the fact for the operator is identical and simple: this
            # track's session is NOT IN THIS TMUX. It was assigned to something once, so
            # it is `session-gone` — never `unassigned`, which is reserved for a plan
            # whose session we have NEVER seen (maintainer-declared 2026-07-17: "KEEP
            # session-gone if you've ever seen the session, only use unassigned if you've
            # never seen it"). The MAPPING ROW is precisely that memory of having seen it,
            # which is why it is kept rather than pruned.
            #
            # `not-claude` is DELETED (maintainer-declared 2026-07-17: "What the hell is
            # not-claude?"). It was this gate's return value leaking into the UI — it named
            # a check's output, not anything an operator needs — and it made a bare
            # terminal (`livespec1`) look like a tracked pane while no OTHER bare terminal
            # appears at all. The daemon lists PLANS, not panes: a tmux name reaches the
            # table only as a mapping's column value, and `_no_managed_pane_row` already
            # reports `tmux=None` so no dead terminal is named.
            return _supervisor_offer.no_managed_pane_row(self, repo=repo, topic=topic)

        # Phase 1 — OBSERVE. Every fact the guard cascade below decides on is
        # gathered in one place, so the cascade reads as a single top-to-bottom
        # precedence order. Unpacked into locals so each guard reads the same way
        # it always has.
        obs = _supervisor_observe.observe(self, track, session=session, target=target, key=key)
        capture, busy, gate, idle = obs.capture, obs.busy, obs.gate, obs.idle
        is_codex, runtime, codex_fallback = obs.is_codex, obs.runtime, obs.codex_fallback
        claude_status, eff_ctx, istate = obs.claude_status, obs.eff_ctx, obs.istate
        declared, malformed, blocked, acked, ready = (
            obs.declared,
            obs.malformed,
            obs.blocked,
            obs.acked,
            obs.ready,
        )

        # Phase 2 — DECIDE.

        # R1 — self-healing resume retry. A prior tick respawned the fresh Claude but its
        # resume line did not submit (the fresh TUI dropped the Enter, or the daemon died
        # mid-restart). The round is still open (marker + stamp kept), so `ready` is still
        # valid — but re-entering the `elif ready:` branch below would RE-RESPAWN and kill
        # the live fresh session. This branch intercepts first and retries the SUBMIT ONLY:
        # re-send Enter, never a respawn (a fresh `ready` is the sole respawn trigger,
        # invariant 7). It also runs BEFORE the busy/idle cascade because a box holding the
        # un-submitted resume text reads as "not idle" → would otherwise fall to `settling`
        # and never retry. Codex never sets `resume_pending` (its `codex resume` auto-submits
        # the kick), so this is Claude-only by construction.
        if act and registry.read_resume_pending(repo, topic, self.stamp_path):
            if gate:
                # A fresh TUI showing a picker (trust / update / bypass-permissions confirm):
                # NEVER keystroke into a gate (blocker #6). Report it and keep the round open;
                # the retry resumes once the human clears the gate (review SF4).
                self.alert(
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
                    ctx=eff_ctx,
                    status="blocked:human",
                    note="structured gate on freshly-restarted pane",
                    runtime=runtime,
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
                if signals.input_box_ready(capture)
                else _supervisor_launch.resend_enter(self, target)
            )
            if resolved:
                self._clear_state(track)
                self.log(f"restart resume submitted for {repo}::{topic} (pane {target})")
                return RowView(
                    topic=topic,
                    repo=repo,
                    tmux=session,
                    ctx=eff_ctx,
                    status="restarting",
                    runtime=runtime,
                )
            # Still un-submitted: keep the round open (retry again next tick) and report it.
            self.alert(
                repo=repo,
                topic=topic,
                session=session,
                pane=target,
                message=(
                    "resume line STILL not submitted after restart — "
                    "retrying the Enter (no respawn)"
                ),
            )
            return RowView(
                topic=topic,
                repo=repo,
                tmux=session,
                ctx=eff_ctx,
                status="restarting",
                note=RESUME_PENDING_NOTE,
                runtime=runtime,
            )

        # A per-track override (an int ``ctx_threshold``) wins; otherwise inherit
        # the daemon-wide default (``warn_percent``, set from ``--warn-percent``).
        threshold = track.ctx_threshold if track.ctx_threshold is not None else self.warn_percent

        # The row note defaults to the blocked reason (if any); the busy branch
        # overrides it to "background shell" when a live background shell is the SOLE
        # reason the pane isn't idle, so the operator can see WHY.
        note: str | None = blocked if blocked else None
        if malformed and declared is not None:
            note = f"BAD state file: {declared.token!r}"
            if act:
                self.alert(
                    repo=repo,
                    topic=topic,
                    session=session,
                    pane=target,
                    message=(
                        f"MALFORMED state file: {declared.token!r} is not one of "
                        f"{', '.join(signals.STATE_TOKENS)} — treated as no declaration "
                        f"(the track will NOT be restarted)"
                    ),
                    condition="malformed-state",
                )

        # Precedence, top to bottom. Single-capture `busy` and the human gates
        # are checked first. For an apparently-idle track that would ACT
        # (restart / inject), the daemon first confirms the pane is SETTLED
        # (`_pane_settled`) — a single frame can't see active token-streaming, so
        # a changing pane is treated as `working` and skipped this tick.
        if busy:
            status = "working"
            if act:
                # A GENERATING session is not waiting on a human, so a `blocked:` it has
                # outlived is provably dead — retire it before the note is derived, or the
                # dead reason rides this row (it is the note default) and later fires a
                # false `blocked:human`. Busy via a BACKGROUND SHELL alone does NOT qualify:
                # that session is at its prompt and may genuinely still be waiting.
                blocked = self._void_stale_blocked(
                    track,
                    blocked,
                    generating=signals.is_busy(capture) or claude_status == "busy",
                )
                note = blocked if blocked else None  # re-derive: the default came from `blocked`
            # When the PANE itself looks idle, the row note explains WHY it is `working`,
            # or the operator would read the idle-looking pane and distrust the status.
            if not signals.is_busy(capture):
                if claude_status == "shell" or codex_fallback:
                    note = "background shell"  # a live `Bash(run_in_background)` command
                # Provably always True where it stands: reaching here needs `busy` True
                # with `is_busy(capture)` False and the `shell`/codex-fallback arm above
                # already excluded, which leaves `claude_busy` as the only disjunct that
                # can be carrying `busy` — and `CLAUDE_BUSY_STATUSES` holds exactly
                # {"busy", "shell"}. So the else-exit is dead and branch coverage can
                # never close it.
                #
                # KEPT as an `elif` rather than demoted to `else` precisely because that
                # proof depends on the CURRENT contents of `CLAUDE_BUSY_STATUSES`, which
                # exists to be extended. Add a third status and `else` would silently
                # label it "sub-agent (Claude busy)" — wrong; the `elif` correctly leaves
                # the note unset. The dead arc is the cost of that safety, so it is
                # annotated rather than removed.
                elif claude_status == "busy":  # pragma: no branch
                    note = "sub-agent (Claude busy)"  # in-process sub-agent, no shell
            if act:
                # Void the certification ONLY if it is past the grace — a young
                # marker is the certifying turn's own busy tail and must survive
                # (RB1); an old one means the session resumed work after certifying.
                ready = self._void_if_stale(track, ready=ready)
                # The session took a turn — clear any idle-with-context-left nudge marker
                # so the NEXT idle-with-context episode re-nudges (re-arm on non-idle).
                _supervisor_nudge.clear_idle_nudge_state(self, track)
        elif gate or blocked is not None:
            status = "blocked:human"
            if act:
                ready = self._void_if_stale(track, ready=ready)
                # A gate / block is also "non-idle" — drop a stale nudge marker (safe: the
                # helper re-reads and leaves a session-written `blocked` untouched).
                _supervisor_nudge.clear_idle_nudge_state(self, track)
                detail = blocked if blocked else "structured gate on pane"
                # The decision belongs to the TRACKED session, which is already showing
                # it in its own pane. The overseer NOTIFIES and hands over coordinates;
                # it never re-asks the question itself (invariant 8).
                self.alert(
                    repo=repo,
                    topic=topic,
                    session=session,
                    pane=target,
                    message=(
                        f"blocked on human: {elide(detail, MAX_REASON_IN_ALERT)} "
                        "— answer it IN THAT PANE"
                    ),
                )
        elif not idle:
            # Pane present but not a verified idle-input state and not busy —
            # a transient/settling capture. Wait; never act.
            status = "settling"
        elif act and not _supervisor_launch.pane_settled(self, target):
            # One frame looks idle, but the pane is actively changing (streaming).
            status = "working"
        elif act and not _supervisor_observe.pane_is_managed(self, target, repo, topic, session):
            # TOCTOU re-check (Codex re-review #1): the identity gate ran at the top
            # of the tick, but capturing + the settle delay opened a window in which
            # the pane could have exited to a shell (or cd'd out of the repo). Re-
            # verify identity IMMEDIATELY before any act, so a wrap-up is never
            # pasted into — nor a respawn aimed at — a pane no longer proven ours.
            #
            # `settling` (a one-tick "wait and re-read"), NOT a status of its own: the
            # pane changed UNDER US mid-tick, which is exactly what settling means. The
            # act is suppressed either way, and the next tick re-enters at the top gate,
            # which classifies the settled truth (`session-gone` if it really has gone).
            status = "settling"
        elif ready:
            # The session DECLARED `ready`. This is the ONLY path to a restart — the
            # daemon never infers it (maintainer 2026-07-14). RUNTIME-DISPATCHED: for a
            # Codex track `_do_restart` routes to `codex resume <id>`, NEVER the claude
            # launch command — aiming `claude -n <topic>` at a codex pane would REPLACE
            # the codex session with a claude one and destroy it. That routing (not a
            # separate monitor-only refusal) is what preserves the one place a bug here is
            # destructive rather than merely wrong; the sabotage-verified guard test pins
            # it. A Codex track is now a full citizen (maintainer-declared 2026-07-17):
            # it is restarted on its own `ready` exactly like a Claude one.
            status = "restarting"
            if act:
                _supervisor_restart.do_restart(self, track, target, is_codex=is_codex)
        elif eff_ctx is not None and eff_ctx <= threshold:
            # A FRESH `winding-down` ACK buys patience: the session heard us and is
            # wrapping up, so stop re-warning (never keystroke into a session that is
            # actively winding down). A STALE ACK resumes escalating — an ACK must not
            # become an infinite stall — but still never authorizes an act.
            if act and not acked:
                _supervisor_restart.maybe_inject(
                    self, track, target, eff_ctx, threshold, is_codex=is_codex
                )
            if acked:
                status = "winding-down"
            elif eff_ctx <= DANGER_CTX_REMAINING:
                status = "danger"
                if act:
                    _supervisor_nudge.alert_non_responder(
                        self,
                        track,
                        session=session,
                        pane=target,
                        eff_ctx=eff_ctx,
                        declared=declared,
                    )
            else:
                status = "warned"
        else:
            _supervisor_offer.surface_supervision_offer(self, track, act=act)
            # Idle at an empty prompt with the context ABOVE the wind-down threshold. If
            # the session has declared nothing, nudge it ONCE this episode to keep going
            # rather than stop early (the inverse of the wrap-up). The daemon-written
            # `idle-with-context-left` marker makes it single-prompt; it clears when the
            # session next goes non-idle, re-arming a fresh nudge for the next episode.
            nudged_already = (
                declared is not None and declared.token == signals.STATE_IDLE_WITH_CONTEXT_LEFT
            )
            has_context_left = eff_ctx is not None and eff_ctx > threshold
            # Claude's own `waiting` = at a gate/prompt for the human. Even when no
            # structured gate is visible in the capture (it scrolled, or it is a prose
            # question a YOLO session cannot raise as a prompt), that IS "a blocking
            # question for the human" — so it must NOT be nudged to keep going.
            waiting_on_human = claude_status == "waiting"
            # `eff_ctx is not None` is spelled out here as well as inside
            # `has_context_left` so the type checker can narrow it for the
            # `_nudge_idle_with_context` call below. It is not redundant to a reader
            # either: a nudge needs a KNOWN remaining-context percentage to quote.
            if (
                eff_ctx is not None
                and has_context_left
                and not waiting_on_human
                and (declared is None or nudged_already)
            ):
                status = "idle-with-context-left"
                # Fire the nudge ONLY after the session has been continuously idle for at
                # least `IDLE_NUDGE_AFTER` (maintainer 2026-07-18: the nudge was "too
                # aggressive, TOO SOON", interrupting sessions merely between turns). The
                # status still reads `idle-with-context-left` immediately (it is descriptive,
                # not an attention row); only the keystroke waits for the 1-hour floor.
                idle_long_enough = (
                    istate.idle_since is not None
                    and (self.now() - istate.idle_since) >= IDLE_NUDGE_AFTER
                )
                if act and not nudged_already and idle_long_enough:
                    _supervisor_nudge.nudge_idle_with_context(
                        self, track, target, eff_ctx, threshold, is_codex=is_codex
                    )
            else:
                status = "idle"

        view = RowView(
            topic=topic,
            repo=repo,
            tmux=session,
            ctx=eff_ctx,
            status=status,
            note=note,
            runtime=runtime,
        )
        # Re-arm the edge-triggered alert once the track is healthy again, so the NEXT
        # time it goes bad it reports afresh rather than being suppressed as a duplicate
        # of the condition it was in hours ago.
        if act and not needs_attention(view):
            prefix = track_key(repo, topic)
            self.alerted = {
                key: value
                for key, value in self.alerted.items()
                if key[:2] != prefix or key[2] in SUPERVISION_CONDITIONS
            }
        return view

    def _do_codex_restart(self, track: registry.Track, target: str) -> None:
        """See :func:`_supervisor_restart.do_codex_restart`."""
        _supervisor_restart.do_codex_restart(self, track, target)

    @staticmethod
    def _launch_command(track: registry.Track) -> str:
        """See :func:`_supervisor_launch.launch_command`."""
        return _supervisor_launch.launch_command(track)

    @staticmethod
    def _codex_launch_command(session_id: str, resume: str) -> str:
        """See :func:`_supervisor_launch.codex_launch_command`."""
        return _supervisor_launch.codex_launch_command(session_id, resume)

    def _submit_prompt(self, target: str, text: str, *, expect_codex: bool = False) -> bool:
        """See :func:`_supervisor_launch.submit_prompt`."""
        return _supervisor_launch.submit_prompt(self, target, text, expect_codex=expect_codex)

    # ----------------------------------------------------------------- #
    # Reboot recovery (startup-only, never per-tick).
    # ----------------------------------------------------------------- #

    def recover_missing_sessions(self) -> list[str]:
        """See :func:`_supervisor_recovery.recover_missing_sessions`."""
        return _supervisor_recovery.recover_missing_sessions(self)

    def _do_codex_launch(self, track: registry.Track, session: str, session_id: str) -> bool:
        """See :func:`_supervisor_recovery.do_codex_launch`."""
        return _supervisor_recovery.do_codex_launch(self, track, session, session_id)

    def do_launch(self, track: registry.Track, session: str) -> bool:
        """See :func:`_supervisor_recovery.do_launch`."""
        return _supervisor_recovery.do_launch(self, track, session)

    # ----------------------------------------------------------------- #
    # Table rendering.
    # ----------------------------------------------------------------- #

    def render(self, rows: Iterable[RowView]) -> None:
        """Paint the live table + the ``NEEDS YOU`` block. See :mod:`_supervisor_render`."""
        _supervisor_render.render_table(self, rows)

    def _refresh_window_name(self, attention: int) -> None:
        """Badge the attention count onto the tmux window name. See :mod:`_supervisor_render`."""
        _supervisor_render.refresh_window_name(self, attention)

    # ----------------------------------------------------------------- #
    # Tick + loop.
    # ----------------------------------------------------------------- #

    def tick(self, *, act: bool = True) -> list[RowView]:
        """One loop iteration: build rows, evaluate each, render the table + attention block."""
        views = [self.evaluate(track, act=act) for track in self.build_rows(act=act)]
        self.render(views)
        # Only the DAEMON badges the window. `list` is advertised read-only, so it must
        # not rename the maintainer's window as a side effect of printing a table.
        if act:
            self._refresh_window_name(sum(1 for view in views if needs_attention(view)))
        return views

    # ----------------------------------------------------------------- #
    # Singleton daemon lock (per store).
    # ----------------------------------------------------------------- #

    def _singleton_lock_path(self) -> Path:
        """See :func:`_supervisor_lifecycle.singleton_lock_path`."""
        return _supervisor_lifecycle.singleton_lock_path(self)

    def _acquire_singleton_lock(self) -> IO[str] | None:
        """See :func:`_supervisor_lifecycle.acquire_singleton_lock`."""
        return _supervisor_lifecycle.acquire_singleton_lock(self)

    @staticmethod
    def _release_singleton_lock(handle: IO[str] | None) -> None:
        """See :func:`_supervisor_lifecycle.release_singleton_lock`."""
        _supervisor_lifecycle.release_singleton_lock(handle)

    def unignored_tmp_repos(self) -> list[str]:
        """See :func:`_supervisor_lifecycle.unignored_tmp_repos`."""
        return _supervisor_lifecycle.unignored_tmp_repos(self)

    def unsupported_host_reasons(self) -> list[str]:
        """See :func:`_supervisor_lifecycle.unsupported_host_reasons`."""
        return _supervisor_lifecycle.unsupported_host_reasons(self)

    def run(
        self, *, interval: float = LOOP_INTERVAL_SECONDS, once: bool = False, recover: bool = False
    ) -> None:
        """See :func:`_supervisor_lifecycle.run_loop`."""
        _supervisor_lifecycle.run_loop(self, interval=interval, once=once, recover=recover)
