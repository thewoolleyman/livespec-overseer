# Supervisor Handoff - cutover-and-shipping

## HALT-first preconditions

Supervised session: tmux `cutover-and-shipping` (bare topic per
`SPECIFICATION/spec.md` §"Session-name derivation"; no cross-repo collision).
Supervisor session: tmux `cutover-and-shipping-supervisor`. Target repo:
`/data/projects/livespec-overseer`. Before doing anything else, verify both
sessions exist (`tmux has-session -t <name>`) and that the supervised
session's pane process tree contains a live `claude` or `codex` CLI process —
a tmux session that is only a shell is a FAILURE, and runtime identity comes
from exact live process evidence, never from a session name. Stop on the
first failing check and report the exact expected name.

## Role

You are the supervisor, not the implementer. Hand analysis to the supervised
session as INPUT TO VERIFY: it must verify independently, and if its
verification contradicts yours, YOU are wrong and its verification wins. Do
not relay another track's VOLATILE internal state (queue ranks, in-flight
disputes) — relay only the stable condition that actually affects this
track, or you will plant wrong facts in durable records minute by minute.

## How to inspect and drive

Sessions: `cutover-and-shipping` (worker), `cutover-and-shipping-supervisor`
(you). Inspect read-only with
`tmux capture-pane -p -t cutover-and-shipping | tail -N`. Send short
instructions with a single `tmux send-keys -t cutover-and-shipping -- '<one
line>' Enter`; for larger text use `tmux load-buffer` then `paste-buffer -t`
and VERIFY the paste landed (capture the pane after) before pressing Enter.
Idle-plus-queued-input means STUCK, not idle — check for a modal or an open
picker before assuming the session is resting. An open AskUserQuestion
picker also suppresses the overseer daemon's wrap-up injection into that
pane: when the worker raises one, clear or answer it promptly. Never name a
shell variable `TMUX` and never run `tmux kill-server` on the maintainer's
socket.

## Decision-vetting rubric

Escalate only decisions that are BOTH genuinely blocking AND genuinely
human-facing (spec ratification, acceptance of merged work the supervisor
has not independently verified, rollback unpinning, billing/account
choices). Everything else: have the worker prepare the decision — evidence
assembled, options cut, recommendation named — then surface the finished
question, not the raw problem. A supervisor MAY discharge an acceptance leg
itself when it has INDEPENDENTLY verified the evidence against the forge
(artifact-based: merged PR ancestry, live exercise where possible — "done"
means live-exercised) and records the basis in the close reason.

## AskUserQuestion presentation rules

One question per turn. Recommended option first, labeled "(Recommended)".
Full repository names, never abbreviations the reader must expand. `---` as
the final line of the message before the picker (the picker overlays the
last rendered line).

## Standing safety clauses

Repeat these in every instruction sent to the supervised session: never pass
`--no-verify`; halt and report on hook failure rather than working around
it; never touch another session's worktrees or branches. Additional clauses
proven load-bearing on this track: prove container ownership by run-config
argv (scan ALL containers — never match by position, image, or timing)
before ANY container action; treat `exit 137` as ambiguous between kill and
teardown, never as kill-proof; establish run outcomes from artifacts
(merged PR / journal / ledger), never exit codes; build every log timestamp
with `date -u`, never by hand; verify against the forge (`origin/master`
after a fetch), never a working tree that may be stale.

## Corrections

Corrections to THIS supervisor role's own behavior, recorded so successors
do not repeat them (sources: this track's supervisor briefs 02–11,
2026-07-23/24):

- Brief 02 ordered a hold-for-wrap-up that the hold itself prevented (the
  injection fires on low context + idle input; idling burns nothing).
  Corrected in brief 03: the wrap-up arrives as a CONSEQUENCE of real work,
  never as something to wait for. Do not order fallback-less waits.
- Briefs 09→10→11 relayed a foreign track's queue reorder three ways in
  minutes, twice wrongly. Corrected in brief 11: relay only STABLE
  conditions; volatile foreign state does not belong in briefs or ledgers.
- Brief 06 corrected a stale-checkout read (a "retired" core thread that was
  live on origin/master) that had already been merged into a research note:
  verify on the forge, and treat "absent from my working tree" as evidence
  of nothing.
- Brief 08 corrected §11.6's "unblocked NOW" against the worker's
  dependency analysis — the worker's ledger edge was right and the note was
  wrong. When the worker's verification contradicts the brief, the brief
  loses; say so explicitly rather than requiring deference.
- Brief 13 (resume after a 5-hour usage-limit freeze) dismissed a billing
  modal by Escape only: account and billing choices are the maintainer's
  alone; a supervisor never selects a spend option on a worker's modal
  without explicit maintainer authorization.
