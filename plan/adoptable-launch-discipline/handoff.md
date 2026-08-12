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
status from the ledger — `list-work-items`, or the credential-wrapped
ledger read `source /data/projects/1password-env-wrapper/with-livespec-env.sh
bd -C /data/projects/livespec-overseer show overseer-fjhsj3` (a BARE `bd`
fails with Access denied in these tenants) — never from this file; this handoff cites ids read-only and carries no
work queue.

Done so far: the reasoning note (§5 item 1) carries the audit-sized
problem, the per-runtime idioms, the two fronts, and the deliberate
non-rule. The maintainer approved the cut on 2026-08-12 and it is now filed.
The original defect `overseer-daj` is closed as superseded by the two local
slices below; the epic anchor remains `overseer-fjhsj3`.

Local livespec-overseer slices:

- `overseer-rf6qg3` — core generator/protocol content — **closed** after
  merged PR #811 and the follow-up handoff PR #813.
- `overseer-464iib` — existing charter-gate-ratchet enforcement — **closed**
  after merged PR #816 (`7ba74c7`).

Repo-local protocol slices, each filed in its own tenant with ordering kept
in prose rather than a cross-tenant dependency edge:

- `hl-ekvd22` in homelab — `pending-approval` (homelab uses its own
  `/usr/local/bin/with-homelab-env.sh` credential wrapper).
- `livespec-y4xn2k` in livespec — `ready`.
- `bd-ib-e7qesr` in livespec-orchestrator-beads-fabro — `ready`.
- `livespec-dev-tooling-tqu55m` in livespec-dev-tooling — `ready`.

The core and enforcement slices are implemented and merged from the worktree branch
`implement-adoptable-launch-discipline`; its generator/protocol changes add the
runtime-specific launch/restart contract to both prose layers and generated-
output tests. The maintainer explicitly directed in-session implementation of
the enforcement slice after the factory `CLAUDE_CODE_OAUTH_TOKEN` remained
exhausted/rate-limited before sandbox launch; no factory run was created. The
enforcement commit `50156a6` extends the existing charter-defect registry with
class `(m)`, including red/green controls for an incomplete contract,
reformatted correct content, a differently named tmux session, and structured-
gate `/rename` safety. `just check` passed all 70 targets, with 1112 tests
passing in the aggregate suite. PR #816 merged by rebase and its ledger item is
closed. No daemon behavior or spec sweep was changed.
The defect's live comment remains the evidence anchor: 51 panes, 20
unadoptable agents (18 Claude launches missing `-n`, 2 unnamed Codex threads).

## 3. The next action (exactly one), then the follow-on sequence

THE next action on resume: **admit and drive the three already-ready foreign
protocol slices**. The homelab slice needs its normal tenant admission step
before dispatch; record each foreign PR and ledger closure in its own tenant.
Then perform the planned ratified-clause sweep before any additional rollout
work. This thread exists to pull the approved replacement work forward; do not
re-groom or re-file `overseer-daj`.

The approved dependency layers are:

1. **Core content, target `livespec-overseer` — DONE:** update the actual charter
   generator, `.claude-plugin/prose/supervise-plan.md`, and this repo's
   `.ai/supervisor-protocol.md` with separate Claude fresh/live-repair and
   Codex resume/fresh-launch idioms. Preserve the exact adoption join, the
   `/rename` structured-gate safety check, and the rule that tmux names are
   not adoption keys. Add generated-output controls.
2. **Protocol adoption, four repo-local slices:** update the shared
   `.ai/supervisor-protocol.md` in `homelab`, `livespec`,
   `livespec-orchestrator-beads-fabro`, and `livespec-dev-tooling`. The
   console has supervisor handoffs but no shared protocol file. Each foreign
   tenant must mint its own id; do not add a `depends_on` edge to an
   `overseer-` id. Record ordering in each slice's text.
3. **Enforcement, cross-linked to `plan/charter-gate-ratchet/` — DONE for
   `livespec-overseer`:** extend
   its existing detector machinery, rather than creating a second gate, so
   a launch/restart leg omitting the runtime-specific idiom fails. Require
   a must-flag defect, a must-pass differently-written correct form, a
   topic-named agent in a differently-named tmux session, and the known
   structured-gate `/rename` safety control.
4. **Rollout:** amend the existing charter-gate-ratchet adopter slices to
   carry this detector; do not duplicate their cross-repo work in this
   epic. The optional standing cause-side audit is excluded from this cut
   and should be filed separately if the maintainer wants it.

Important measured path correction: `overseer/_supervisor_prompts.py` is
daemon wrap-up/resume text and contains no charter launch generator. The
generator source is `.claude-plugin/prose/supervise-plan.md`; the daemon
launch paths remain correct and unchanged.

The slices were filed through the shared intake Definition-of-Ready path.
Foreign slices obey the tenant rule above and should use the FACTORY path —
the `drive` operation (`impl:<id>`) or Dispatcher drain. For
`overseer-rf6qg3`, the maintainer explicitly authorized the in-session route
because the factory credential was exhausted; record that exception in the
completion reason. Do not generalize this exception to the remaining slices.

The follow-on sequence: sweep whether any RATIFIED clause states launch
idioms (`SPECIFICATION/spec.md` §"The restart",
`overseer/marker-protocol.md`, `.claude-plugin/prose/overseer.md`,
`.claude-plugin/prose/supervise-plan.md`); if yes, route that clause's
amendment via the `/livespec:propose-change` operation → independent
Fable-model review → `/livespec:revise` before the affected slice
dispatches. `overseer-daj` is already folded out with an explicit
supersession reason naming `overseer-rf6qg3` and `overseer-464iib`.

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
  is a WORKING mapping the gate must not flag. Any detector on this
  axis needs BOTH a must-pass exemplar (the case above) and a
  must-flag counterpart, per the charter-gate corpus's
  three-way-control discipline — all four false positives that gate
  family has ever produced flagged already-correct content.
- Live-repair keystrokes (`/rename`) are never sent into a pane
  showing a structured gate (a picker consumes keystrokes) — the
  2026-08-11 audit's gated-skip discipline. The detection predicate is
  `signals.is_structured_gate` (`overseer/signals.py`): a `❯ N.` /
  `› N.` numbered cursor or the literal permission question; check the
  capture BEFORE typing.
- The conformance gate fails charters at GENERATION/check time; it
  never blocks or kills a live mis-launched session (those surface
  through the daemon's existing `session-gone` / `codex-unindexed`
  attention, which stays).

## 5. Read-first chain (all committed in this repo, livespec-overseer)

1. `plan/adoptable-launch-discipline/launch-idioms-and-gate.md` — the
   audit-sized problem, the idioms, the two fronts, the non-rule.
2. `overseer/claude_sessions.py` (a re-export facade — the registry
   join itself lives in `overseer/_claude_sessions_registry.py`, read
   that too) and `overseer/codex_sessions.py` — the exact adoption
   joins the discipline serves (registry name; session-index thread
   name).
3. `plan/charter-gate-ratchet/handoff.md` — the adjacent thread owning
   charter-gate MECHANICS this thread's enforcement front plugs into.
4. `overseer/_supervisor_launch.py` — the daemon's own correct launch
   commands (the reference implementations of both idioms).

Reference ledger ids to re-read live (the statuses in §2 are a resume
checkpoint, not a substitute for live reads): `overseer-fjhsj3` (this
thread's epic), `overseer-816` (the harness-neutral-idiom precedent), and
`overseer-mgg` (sibling delivery-leg defect, separate thread). The replacement
and superseded ids are recorded in §2 so a fresh session can resume the
approved cut without reconstructing the grooming conversation.
