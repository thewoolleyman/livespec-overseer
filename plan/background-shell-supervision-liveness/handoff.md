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

## Read first

Read, in order:

1. `plan/background-shell-supervision-liveness/research/root-cause.md`
2. `SPECIFICATION/spec.md`, especially "The cardinal rule", "The supervision
   round", "The escalating wrap-up", and "Resilience and fail-soft behavior"
3. `SPECIFICATION/contracts.md`, especially "The restart interlock", "The
   wrap-up injection", and "Attention surface"
4. `overseer/marker-protocol.md`
5. `overseer/AGENTS.md`, especially busy detection, Claude registry status,
   state precedence, and attention
6. `overseer/_supervisor_observe.py`
7. `overseer/_supervisor_evaluate.py`
8. `overseer/_supervisor_view.py`
9. The background-shell and registry-status beside-tests:
   `overseer/test_supervisor_daemon_wide_warn.py` and
   `overseer/test_supervisor_auto_link_repo.py`

Do not read chat history as a source of truth. The measured incident evidence,
open questions, and safety constraints are in the research note.

## Ledger anchors

- Planning epic: `overseer-4xfmez`
- Implementation bug: `overseer-vyjkzw`

Read their current state from the beads-backed ledger before acting; do not
copy status into this handoff as a shadow queue. The bug was intake-triaged to
`pending-approval`. Its description cites the epic, but the requested native
dependency edge was rejected because Beads forbids a task-to-epic `blocks`
edge. Do not bypass the store to invent one.

## Next action

Work the investigation before implementation:

1. Build a deterministic behavior matrix for Claude registry `shell` and
   Codex descendant-shell fallback across:
   - prompt empty versus generating/gated;
   - above threshold versus threshold/30/20/10 bands;
   - young versus prolonged shell episode;
   - daemon restart;
   - shell/status transition and re-entry.
2. Identify the smallest evidence set that can surface an operator-only,
   non-destructive attention condition without treating time as
   authorization. Compare at least:
   - low-context plus empty prompt plus a bounded continuous shell episode;
   - low-context plus shell age regardless of prompt;
   - a status-preserving attention note versus a new explicit status.
3. Write the comparison and recommended contract to:
   `plan/background-shell-supervision-liveness/research/policy-options.md`.
   Include rejected alternatives and the exact clearing/re-arm rule.
4. Because the current specification explicitly allows busy false positives
   to suppress action and excludes `working` from attention, route the
   selected behavior through the `livespec:propose-change` lifecycle before
   changing product code.
5. Once the contract is accepted and `overseer-vyjkzw` is admitted, use the
   factory dispatch route — `drive` action `impl:overseer-vyjkzw` or the
   Dispatcher drain. Do not implement it inline from this planning session.

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
