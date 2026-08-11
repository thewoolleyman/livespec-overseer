# adoptable-launch-discipline — handoff

> Cold-open handoff. It assumes you have read nothing and remember nothing,
> and that you may be a different model than the session that wrote it.
> Everything load-bearing is either stated here or cited by a path in §5.
> Do not treat chat history as a source of truth.

## 1. The primary goal

Every launch of a Claude or Codex agent session — by hand, by a
charter, by a bootstrap — must produce a session the daemon can ADOPT,
by construction. Adoption is exact: Claude joins by registry name
(`~/.claude/sessions/<pid>.json` `name`), Codex by
`session_index.jsonl` thread name. A launch that omits the per-runtime
idiom yields a live, working, UNWATCHED agent — no context tracking, no
wrap-up protocol, no restart, no `NEEDS YOU`. The 2026-08-11 fleet
audit found **20 such agents at once** (18 Claude on default `<dir>-XX`
names, argv-confirmed missing `-n`; 2 unnamed Codex threads). The
daemon's own launch paths are already correct; the fix belongs to the
charter/protocol layer plus an enforcement gate. The defect record is
**`overseer-daj`** (its comments carry all evidence).

The idioms, verbatim (stated separately per runtime — never as one
"harness-neutral" form, per the `overseer-816` precedent):
Claude fresh launch `claude --dangerously-skip-permissions -n <topic>`,
Claude live repair `/rename <topic>`; Codex restart `codex resume
--dangerously-bypass-approvals-and-sandbox <session-id> "<kick>"` (id
recoverable from the index by topic), Codex fresh launch immediate
`/rename <topic>`.

## 2. Where this thread stands

Created 2026-08-11. The epic anchor is **`overseer-fjhsj3`**. Read live
status from the ledger — `list-work-items` / `bd show overseer-fjhsj3` —
never from this file; this handoff cites ids read-only and carries no
work queue.

Done so far: the reasoning note (§5 item 1) carries the audit-sized
problem, the per-runtime idioms, the two fronts, and the deliberate
non-rule. NOT done: the grooming of `overseer-daj` into slices, the
charter/generator content changes, the conformance gate, and any spec
sweep.

## 3. The next action (exactly one), then the follow-on sequence

THE next action: **groom `overseer-daj` into ready slices with the
maintainer** — this thread exists to pull that bug forward, and the
maintainer OWNS the cut (grooming is a drafting conversation; nothing
is filed without approval). Draft the slice proposal from the two
fronts in the reasoning note: (a) charter/supervisor-protocol content —
the per-runtime idiom text landing in the generator and the shared
`.ai/supervisor-protocol.md` layer of each target repo; (b) the
charter-gate conformance check that FAILS a charter whose
launch/restart legs omit the idiom (mechanics plug into the
`plan/charter-gate-ratchet/` thread's gate machinery — cross-link,
do not duplicate); optionally (c) productizing the audit as a standing
cause-side check, which is a maintainer scope call. File approved
slices as CHILDREN of `overseer-fjhsj3` via the `capture-work-item`
operation (`depends_on` the epic; autonomy tier T2 — the fleet's
dispatch-after-ratification tier), implemented through the FACTORY
path — the `drive` operation (`impl:<id>`) or the Dispatcher drain —
never the in-session `implement` operation.

The follow-on sequence: sweep whether any RATIFIED clause states launch
idioms (`SPECIFICATION/spec.md` §"The restart",
`overseer/marker-protocol.md`, `.claude-plugin/prose/overseer.md`,
`.claude-plugin/prose/supervise-plan.md`); if yes, route that clause's
amendment via the `/livespec:propose-change` operation → independent
Fable-model review → `/livespec:revise` before the affected slice
dispatches. Close by folding `overseer-daj` (superseded-by or child
linkage, maintainer's call at groom time).

Every repo artifact of this thread rides this repo's normal
worktree → PR → rebase-merge discipline.

## 4. The regression boundary

- Adoption stays EXACT: no fuzzy matching, no daemon-side guessing to
  compensate for bad launches. The daemon's own launch paths are
  correct and unchanged.
- The tmux session name is NOT required to equal the registry name:
  adoption keys on registry-name == plan topic. A deliberately
  topic-named agent inside a differently-named tmux session (live
  precedent: tmux `homelab` holding claude `01-homelab-aws-account`)
  is a WORKING mapping the gate must not flag.
- Live-repair keystrokes (`/rename`) are never sent into a pane
  showing a structured gate (a picker consumes keystrokes) — the
  2026-08-11 audit's gated-skip discipline.
- The conformance gate fails charters at GENERATION/check time; it
  never blocks or kills a live mis-launched session (those surface
  through the daemon's existing `session-gone` / `codex-unindexed`
  attention, which stays).

## 5. Read-first chain (all committed in this repo, livespec-overseer)

1. `plan/adoptable-launch-discipline/launch-idioms-and-gate.md` — the
   audit-sized problem, the idioms, the two fronts, the non-rule.
2. `overseer/claude_sessions.py` and `overseer/codex_sessions.py` — the
   exact adoption joins the discipline serves (registry name;
   session-index thread name).
3. `plan/charter-gate-ratchet/handoff.md` — the adjacent thread owning
   charter-gate MECHANICS this thread's enforcement front plugs into.
4. `overseer/_supervisor_launch.py` — the daemon's own correct launch
   commands (the reference implementations of both idioms).

Ledger ids to read live (never stored here): `overseer-fjhsj3` (this
thread's epic), `overseer-daj` (the defect record being groomed),
`overseer-816` (the harness-neutral-idiom precedent), `overseer-mgg`
(sibling delivery-leg defect, separate thread).
