# Why every agent launch must be adoptable by construction

Reasoning note for the `adoptable-launch-discipline` plan thread (repo:
`livespec-overseer`). The defect record is **`overseer-daj`** (read its
live state and comments from the ledger — the 2026-08-04 foreman
instance and the 2026-08-11 fleet-audit evidence live there; cite, do
not re-file).

## The problem, sized by the audit

The daemon's adoption is exact, never heuristic: a Claude session is
joined to its plan topic by its registry name
(`~/.claude/sessions/<pid>.json` `name`), a Codex session by its
`session_index.jsonl` thread name. A session launched WITHOUT the
per-runtime naming/identity idiom is invisible to the daemon — alive
and working, but unwatched: no context tracking, no wrap-up protocol,
no restart, no `NEEDS YOU` membership.

The 2026-08-11 fleet audit (maintainer-directed, run from the overseer
bottom pane) found **20 unadoptable agents at once** across 51 panes:
18 Claude sessions carrying default `<dir>-XX` names — launch argv
confirmed missing `-n` (`claude --dangerously-skip-permissions
--model …` with no `-n` flag) — and 2 named-tmux Codex sessions with no
thread name. Repos spanned `homelab`, `livespec-overseer`, `livespec`,
`livespec-console-beads-fabro`, `livespec-driver-claude`, `vps-info`.
All were repaired live by hand; the repair does not prevent the next
twenty.

The daemon's OWN launch paths are already correct (Claude:
`claude --dangerously-skip-permissions -n <topic>`; Codex:
`codex resume <uuid>` preserving the thread name). Every observed
instance came from a launch OUTSIDE the daemon — hand launches and
charter/bootstrap-driven launches by workers and supervisors.

## The per-runtime idioms (the content the charter layer must carry)

- **Claude, fresh launch**: `claude --dangerously-skip-permissions -n <topic>`
  — `-n` writes the registry name at birth. **Claude, already-running
  repair**: `/rename <topic>` in the TUI (verified live: syncs to the
  registry immediately on current builds).
- **Codex, restart of an existing thread**: `codex resume
  --dangerously-bypass-approvals-and-sandbox <session-id> "<kick>"` —
  reattaches the SAME rollout, thread name survives. **Codex, fresh
  launch**: immediately `/rename <topic>` in the TUI so
  `session_index.jsonl` gains the record (verified live 2026-08-11 on
  `beads-v1-1-2-upgrade`: the rename registered in the index and the
  session's own statusline within seconds — with the one caveat that
  the submit Enter can be swallowed, the `overseer-mgg` family, so
  verify the composer cleared). The session id for a resume
  is recoverable from the index by topic
  (`codex_sessions.latest_session_for_thread_name`).
- The idioms are RUNTIME-SPECIFIC and must be stated separately;
  `overseer-816` already showed what happens when a Claude-specific
  idiom is written as harness-neutral.

## The two fronts

1. **Charter/protocol content**: the supervisor-protocol layer
   (`.ai/supervisor-protocol.md` in each target repo) and the charter/
   supervisor-handoff generator in THIS repo
   (`overseer/_supervisor_prompts.py`) state the per-runtime
   adoptable-launch idiom verbatim wherever they instruct launching or
   restarting an agent session — worker restarts by supervisors, sub
   session spawns, bootstrap launches. `overseer-daj`'s acceptance
   already sketches this; the thread grooms it into ready slices.
2. **Enforcement**: a conformance gate that can FAIL a charter whose
   launch/restart legs omit the idiom — the natural home is the
   existing charter-gate machinery (see `plan/charter-gate-ratchet/`,
   the adjacent thread that owns gate MECHANICS; this thread owns the
   launch-idiom CONTENT the gate checks). Whether a live-audit check
   (the 2026-08-11 audit script productized as a daemon attention
   condition or a `just` target) is in scope is a grooming decision —
   the daemon already surfaces the RESULTING states (`session-gone`,
   `codex-unindexed`); the audit adds the cause-side view.

## Constraints

- Adoption stays exact — no fuzzy matching, no daemon-side guessing to
  compensate for bad launches; the fix is at the launch layer.
- The daemon's own launch paths are correct and unchanged.
- Renaming a live session is the sanctioned repair idiom and must stay
  safe: never type into a gated pane (a picker consumes keystrokes);
  the 2026-08-11 audit's gated-skip discipline is the precedent.
- One deliberate non-rule: a tmux session name need NOT equal the
  registry name — adoption keys on the registry name matching a PLAN
  TOPIC, and a deliberately topic-named claude inside a
  differently-named tmux session (observed: tmux `homelab` holding
  claude `01-homelab-aws-account`) is a WORKING mapping the discipline
  must not "fix".

## Relations

- **`overseer-daj`** — the defect record; groomed into slices under
  this thread's epic.
- **`plan/charter-gate-ratchet/`** — the charter-gate machinery this
  thread's enforcement front plugs into (cross-link, do not fold).
- **`overseer-mgg` / `plan/resume-submit-integrity/`** — the sibling
  restart-leg defect (delivery); instance #4 (2026-08-11,
  16-fleet-provisioning-usb-supervisor) proved the two classes are
  cleanly separable: naming correct, submit stranded.
- **`overseer-816`** — the harness-neutral-idiom precedent.
- Sweep surfaces at proposed-change time (if any ratified clause
  states launch idioms): `SPECIFICATION/spec.md` §"The restart",
  `overseer/marker-protocol.md`, `.claude-plugin/prose/overseer.md`,
  `.claude-plugin/prose/supervise-plan.md`, and the generator surfaces.
