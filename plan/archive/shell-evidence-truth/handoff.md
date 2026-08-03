# shell-evidence-truth — handoff

> **ARCHIVED 2026-08-03.** This is the thread's historical opening handoff.
> Sections 2 and 3 intentionally preserve the state and next action at open;
> they are no longer instructions. Read `completion.md` for the landed result,
> deployment evidence, and live re-verification.

> Cold-open handoff. It assumes you have read nothing and remember nothing,
> and that you may be a different model than the session that wrote it.
> Everything load-bearing is either stated here or cited by a path in §5.
> Do not treat chat history as a source of truth.

## 1. The primary goal

Make the daemon's background-shell busy evidence TRUE: a shell that is
part of a session's own MCP launch chain — spawned with the runtime,
alive for the session's whole life, doing no work — must not count as
"active background work", while a genuine mid-session background command
(a `Bash(run_in_background)` shell, a Codex background terminal) MUST
keep counting. Today `has_active_subshell`
(`overseer/claude_sessions.py`) counts any descendant with a shell
`comm`. Its one consumer is the `bg_shell` fallback in
`overseer/_supervisor_observe.py` (~line 218): an ADOPTED Claude
session's registry self-report is authoritative and skips the walk, so
the live blast radius is Codex panes (`overseer/codex_sessions.py`
delegates to the walk) and any pane without a usable self-report. For
those, every session whose MCP servers launch through the fleet's
credential wrapper reads `working (background shell)` from first tick to
last: wrap-up injection permanently suppressed, keep-going nudge
unreachable, `winddown-starved` / `shell-prolonged` alarms false. The
defect record is **`overseer-3rk`**; the observed instance is
`06-resilience-acceptance` (repo `homelab`), idle at 8% context for 15+
hours while its runtime's own `/ps` showed zero background terminals.

## 2. Where this thread stands

Created 2026-08-02. The epic anchor is **`overseer-3zbwi3`**. Read live
status from the ledger — `list-work-items` / `bd show overseer-3zbwi3` —
never from this file; this handoff cites ids read-only and carries no
work queue.

Done so far: the reasoning note (§5 item 1) carries the diagnosed
mechanism, the live process-tree evidence, the regression boundary, and
the candidate discriminator (shell start time relative to the runtime's
start). NOT done: the spec-bearing-or-not verdict, any spec change, the
detector fix, and the owed re-verification of the
`beads-v1-1-2-upgrade` 54h alarms (repo
`livespec-orchestrator-beads-fabro`).

## 3. The next action (exactly one)

Decide **spec-bearing or implementation-only**, and route accordingly:
sweep this repo's `SPECIFICATION/spec.md`, `SPECIFICATION/contracts.md`,
`SPECIFICATION/scenarios.md`, and the shipped prose
(`.claude-plugin/prose/overseer.md`, `overseer/marker-protocol.md`) for
clauses that DEFINE what counts as background-shell / busy EVIDENCE
(as opposed to clauses prescribing the response to it — those belong to
`plan/supervisor-wrapup-citizenship/`). Record the verdict as a research
note in this thread. If any ratified clause must narrow, author the
proposed change via the `/livespec:propose-change` operation
(independent Fable-model review, then `/livespec:revise`) BEFORE any
code. Then file the detector-fix work item as a CHILD of
`overseer-3zbwi3` via the `capture-work-item` operation (`depends_on`
the epic, and the proposed-change ratification when spec-bearing;
autonomy tier T2), implemented through the FACTORY path — the `drive`
operation (`impl:<id>`) or the Dispatcher drain — never the in-session
`implement` operation.

Every repo artifact of this thread rides this repo's normal
worktree → PR → rebase-merge discipline, as the thread's own opening did.

## 4. The regression boundary (do not trade one lie for another)

The fix must pass BOTH: (a) the `06-resilience-acceptance` shape —
runtime → sudo/wrapper-shell → `op` → `sh` → long-lived MCP node, all
started with the session — classifies as NOT busy-on-shell; (b) the
`overseer-vyjkzw` root-incident shape — a stale task shell spawned
mid-session by a tool call — STAYS busy-on-shell. Where evidence
genuinely cannot distinguish the two, fail-soft holds: keep reading
busy. A launch chain relaunched mid-session (an MCP server crash) is the
known hard case for the start-time cut; pressure-test it before
committing to that discriminator. Choosing the concrete start-time
margin (clock: `/proc` starttime jiffies, already read by
`claude_sessions.proc_starttime`) is part of the fix's own work — state
it, test it, and add the `starttime_of` injection seam beside the walk's
existing `children_of`/`comm_of` pattern.

## 5. Read-first chain (all committed in this repo, livespec-overseer)

1. `plan/shell-evidence-truth/false-busy-mechanism.md` — the diagnosed
   mechanism, live process tree, discriminator candidates, relations.
2. `overseer/claude_sessions.py` — `has_active_subshell`, the detector
   under change. The false premise appears TWICE (the function
   docstring AND the module comment above `_SHELL_COMMS`, ~lines
   136-137); correct both. Its one consumer is
   `overseer/_supervisor_observe.py` (`bg_shell`, ~line 218; adopted
   Claude sessions skip it — registry self-report is authoritative);
   `overseer/codex_sessions.py` documents the deliberate Codex
   delegation; beside-tests live in
   `overseer/test_claude_sessions.py`.
3. `SPECIFICATION/spec.md` §"Fail-soft posture" — the over-fire-busy
   posture the fix must respect (and §"The keep-going nudge" if the
   sweep reaches evidence definitions there).
4. `plan/supervisor-wrapup-citizenship/handoff.md` — the complementary,
   deliberately separate suppression-narrowing thread (epic
   `overseer-blccme`); neither thread blocks the other.

Ledger ids to read live (never stored here): `overseer-3zbwi3` (this
thread's epic), `overseer-3rk` (the defect), `overseer-vyjkzw`,
`overseer-blccme`.
