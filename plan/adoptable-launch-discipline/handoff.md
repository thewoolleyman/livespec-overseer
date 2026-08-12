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
non-rule. On 2026-08-12, the live ledger confirmed `overseer-daj` and
`overseer-fjhsj3` are both still `backlog`, with no children filed under the
epic. The defect's live comment confirms the maintainer-directed audit:
51 panes, 20 unadoptable agents (18 Claude launches missing `-n`, 2 unnamed
Codex threads).

The grooming draft is now prepared but NOT approved or filed. No charter or
gate implementation has started, and no spec sweep has been performed.

## 3. The next action (exactly one), then the follow-on sequence

THE next action on resume: **obtain the maintainer's explicit approval of
the grooming draft, then file only the approved slices**. This thread exists
to pull `overseer-daj` forward, and the maintainer OWNS the cut and acceptance.
The draft is read-only until approval.

The proposed dependency layers are:

1. **Core content, target `livespec-overseer`:** update the actual charter
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
3. **Enforcement, cross-linked to `plan/charter-gate-ratchet/`:** extend
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

After approval, file the approved slices through `capture-work-item` with
T2/factory routing as applicable. Foreign slices must obey the tenant rule
above. They land through the FACTORY path — the `drive` operation
(`impl:<id>`) or Dispatcher drain — never the in-session `implement`
operation.

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

Ledger ids to read live (never stored here): `overseer-fjhsj3` (this
thread's epic), `overseer-daj` (the defect record being groomed),
`overseer-816` (the harness-neutral-idiom precedent), `overseer-mgg`
(sibling delivery-leg defect, separate thread).
