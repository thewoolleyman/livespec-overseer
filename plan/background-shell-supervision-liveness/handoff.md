# Background-shell supervision liveness — handoff

## Purpose

Investigate and close the condition in which a stale or failed background
shell can keep a low-context overseer track green and outside `NEEDS YOU`
indefinitely. Preserve the cardinal rule: only a fresh session-written
`ready` declaration may authorize restart.

This file is the thread's sole resumption point. A new session should receive
exactly:

```text
read /data/projects/livespec-overseer/plan/background-shell-supervision-liveness/handoff.md and follow it
```

## Where the thread stands

The investigation is COMPLETE and the contract is SELECTED. What remains is
ratification, then implementation.

- The causal chain is reproduced and documented in `research/root-cause.md`.
- The behavior matrix, the candidate comparison, the rejected alternatives,
  and the recommended contract are in `research/policy-options.md`. That note
  is the design of record for this thread.
- Two maintainer decisions are RATIFIED (2026-07-28) and already baked into
  the recommendation: the episode floor is **2 hours**, and the new row status
  token is **`shell-prolonged`** (yellow, added to `ATTENTION_STATUSES`, alert
  condition key `prolonged-background-shell`).
- The required specification amendment is FILED and PENDING at
  `SPECIFICATION/proposed_changes/background-shell-liveness-attention.md`. It
  amends `spec.md` §"Fail-soft posture" and `contracts.md` §"Attention
  surface" only, in implementation-neutral prose (spec.md's scope statement
  puts the status vocabulary outside the governed contract, so no token or
  constant is named in governed prose).

## Read first

Read, in order:

1. `plan/background-shell-supervision-liveness/research/root-cause.md`
2. `plan/background-shell-supervision-liveness/research/policy-options.md`
   — the selected contract, its exact predicate, and its clearing/re-arm rule
3. `SPECIFICATION/proposed_changes/background-shell-liveness-attention.md`
   (if still pending; once revised it moves under
   `SPECIFICATION/history/vNNN/proposed_changes/`)
4. `SPECIFICATION/spec.md`, especially "The cardinal rule", "The supervision
   round", "The escalating wrap-up", "The keep-going nudge" (whose in-memory
   continuous-idle clock is the ratified precedent this contract mirrors), and
   "Fail-soft posture" — the last is the clause the incident falsified.
   (Corrected 2026-07-28: this line cited "Resilience and fail-soft behavior",
   a section that does not exist in this tree and never has.)
5. `SPECIFICATION/contracts.md`, especially "The restart interlock", "The
   wrap-up injection", and "Attention surface"
6. `overseer/marker-protocol.md`
7. `overseer/AGENTS.md`, especially busy detection, Claude registry status,
   state precedence, and attention
8. `overseer/_supervisor_observe.py`, `overseer/_supervisor_evaluate.py`,
   `overseer/_supervisor_view.py`, `overseer/_supervisor_config.py`,
   `overseer/_supervisor_records.py`
9. The background-shell and registry-status beside-tests:
   `overseer/test_supervisor_daemon_wide_warn.py` and
   `overseer/test_supervisor_auto_link_repo.py`

Do not read chat history as a source of truth. The measured incident evidence,
the safety constraints, and the selected contract are in the two research
notes.

## Ledger anchors

- Planning epic: `overseer-4xfmez`
- Implementation bug: `overseer-vyjkzw`

Read their current state from the beads-backed ledger before acting; do not
copy status into this handoff as a shadow queue. Reach `bd` through the fleet
credential wrapper (`with-livespec-env.sh bd …`) — a bare `bd` is denied by the
tenant database. The bug description cites the epic, but the requested native
dependency edge was rejected because Beads forbids a task-to-epic `blocks`
edge. Do not bypass the store to invent one.

## Next action

One path, in order:

1. Run `/livespec:revise` to process the pending proposed change. Accept or
   reject it; a rejection returns this thread to `research/policy-options.md`
   §"Candidate comparison", not to a fresh investigation.
2. Once the revision is cut and `overseer-vyjkzw` is admitted, dispatch the
   implementation through the factory route — `drive` action
   `impl:overseer-vyjkzw` or the Dispatcher drain. Do NOT implement it inline
   from this planning session.
3. The implementing slice owes, atomically with the product change: the
   `## Scenario` in `SPECIFICATION/scenarios.md`, its integration test under
   `tests/integration/`, and that scenario's `tests/heading-coverage.json` row
   — every scenario heading in this tree is mechanically required to name a
   real integration test, which is why the proposal deliberately adds no
   scenario ahead of the code.
4. Two existing tests named by `tests/heading-coverage.json` MUST be grown by
   the same slice, because the contract they pin changes:
   `overseer.test_supervisor.test_needs_attention_predicate_covers_every_attention_status`
   (pins `contracts.md` §"Attention surface") and
   `overseer.test_supervisor.test_ctx_unknown_never_injects` (pins `spec.md`
   §"Fail-soft posture").

## Required outcome constraints

- No paste, Enter, respawn, shell kill, or declaration write may be added to
  the stale-shell attention path.
- `ready` remains the sole restart authorization.
- A fresh real background command remains protected.
- The alert is coordinate-rich and edge-triggered.
- The condition clears and can re-arm on a later episode.
- Daemon restart behavior is explicit and fails in the safe direction.
- Claude and Codex behavior is explicitly tested or explicitly distinguished
  from measured evidence.
- The specification, protocol docs, maintenance guide, status coloring,
  attention membership, and tests agree.
- The implementation gate is `uv run pytest overseer -q`, then `just check`.
  Do not weaken, remove, skip, or exempt an existing check.

## Repository discipline

Every tracked-file change goes through a provisioned secondary worktree, PR,
review, and rebase merge. Create worktrees with:

```sh
just worktree-create <branch> [base_ref]
```

Use `mise exec -- git ...` for git writes so hooks fire. Never pass
`--no-verify`. Product `.py` changes require the repo's red-green-replay commit
ritual. Stop and report any hook failure rather than bypassing it. Never touch
another session's worktree or branch, and never kill the acting overseer daemon
in tmux `livespec-overseer:1.1`.

## Handoff refresh rule

Keep this file self-sufficient. Put durable reasoning in `research/`, cite the
live ledger ids rather than copying their status, and keep exactly one next
execution path here. Before declaring the handoff ready, verify every path in
the read-first chain exists and is tracked on the merged default branch.
