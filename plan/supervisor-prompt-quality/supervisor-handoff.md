# Supervisor Handoff - supervisor-prompt-quality (TERMINAL)

## STOP. THIS TRACK IS COMPLETE AND ARCHIVED. THERE IS NOTHING TO SUPERVISE.

You were handed this path by a respawn prompt. That prompt is stale by design —
it names a fixed path, and this thread archived on **2026-08-02**. This file
exists ONLY so that prompt resolves to something true instead of a missing file.

**Do not resume this thread. Do not invent work for it. Do not adopt its
successors.** Your correct action is at the bottom of this file and it is short.

The real thread now lives at **`plan/archive/supervisor-prompt-quality/`** —
both records, `handoff.md` and `supervisor-handoff.md`, moved there by merge
`0464d6eb6` and verified present in `origin/master`. Read them if you want
history; nothing there is pending.

## What this track delivered, so you can recognise it as finished

Phase 1 (epic `overseer-byvxlp`, nine slices) and phase 2 (epic `overseer-yho`)
both delivered. Every defect class the cut named has an executable gate in
`tests/prompts/`; releases 0.14.0 and 0.15.0 shipped; and the chain
fix → gate → release → adopter cache refresh → the running generator was observed
working end to end.

**The limit this track never closed, restated at the end rather than quietly
dropped:** nothing observes a supervisor READING a charter clause and doing
otherwise. Rung 3 — observed conduct — is uncovered. It was DEMONSTRATED rather
than conceded on 2026-08-02 (charter correction **C20**): the picker rule is
policed by six of the contract's thirty-one requirements, the gate asserting them
is green, and a supervisor broke it anyway after applying it correctly three
times in the same session. Everything outside the hook-backed rows is ADVISORY.

## Where the surviving work went — each has its own thread and its own owner

| work | now lives at | ledger | state |
|---|---|---|---|
| fleet charter remediation | `plan/fleet-charter-remediation/` | `overseer-yho.3` | OPEN — the maintainer's cut; scope and costing already decided (phased, `livespec-orchestrator-beads-fabro` first, 56 of 117 defects). **Do not self-assign it.** |
| rung-3 conduct gate | `plan/daemon-liveness-truth/` | `overseer-oydugu` | OPEN, `blocked: needs-human` — that verdict is correct, not an oversight |
| watcher gate (false-busy pins the idle exit) | `plan/fleet-charter-remediation/` | `overseer-c45` | OPEN — routed 2026-08-02, see the correction below |

`plan/daemon-liveness-truth/` has a **live worker** and open PRs of its own
(`overseer-j1r`, `overseer-mkx`). It is not yours. Do not touch its branches,
worktrees or items.

## The one decision left open, and why it was NOT taken unilaterally

Epic `overseer-yho` is **still open**, and that is deliberate. The ledger refused
to close it — *"cannot close epic: 2 open child issue(s)"*. They are:

- `overseer-yho.3`, re-homed in prose but still carrying the parent-child edge;
- **`overseer-c45`**, which the MAINTAINER filed at 2026-08-02T03:07Z — a
  watcher-gate defect where a content-based busy heuristic pins the idle exit, so
  a supervisor pane reports "working (background shell)" forever.

`--force` would have ORPHANED a live maintainer-filed item, so it was left alone.
Its disposition was a maintainer call, and it has since been made.

> **CORRECTED 2026-08-02, AFTER THIS FILE FIRST LANDED.** The sentence here used
> to read that `overseer-c45` "fits `plan/daemon-liveness-truth/` well — it is the
> same family as `j1r`/`mkx`". **That routing was wrong, and it was wrong in an
> instructive way: it matched on the SYMPTOM.** A pane whose reported state
> diverges from reality really is the `j1r`/`mkx` family, so the analogy reads
> well. But measured against the item's own text, both of its asks are
> charter-generator work — a `tests/prompts/` detector for the watcher idle-exit,
> and a membership check against `overseer-yho.3`'s 117-defect sweep. It names no
> daemon module and states that the daemon reports TRUTHFULLY, so there is no
> daemon fix in it. `overseer-x29`'s own description draws that boundary and warns
> against absorbing generator-quality work.
> **It is homed in `plan/fleet-charter-remediation/`**, beside `overseer-yho.3`,
> which also means `overseer-yho`'s two open children now share one live thread.
> The routing rationale is recorded on the item itself, not only here.

**`overseer-yho` stays open, and that is now a positive statement rather than a
deferral.** Both its children are open work with a live thread: it closes when
that thread finishes. Closing it sooner would hide 56 unremediated charter defects
and an ungated watcher class behind a tidy epic.

## Two hazards worth carrying out of this track

These are role-level and now live in `.ai/supervisor-protocol.md` as **C21** and
**C22**; they are repeated here because they bite a supervisor immediately:

- **Confirming a paste by grepping the pane for its text cannot work.** Claude
  Code renders a multi-line paste as a placeholder and a single-line paste
  inline, so a content search returns zero on a paste that landed perfectly.
  Confirm by the placeholder or a non-empty prompt line, accept either shape, and
  re-capture rather than re-sending — the render lags.
- **zsh does not word-split unquoted parameter expansions**, so splitting a
  captured line into fields the bash way yields ONE field. A watcher built that
  way slept through a green CI run for fourteen minutes and then reported "still
  not terminal". Same family as C14.

## Repo state at close, measured rather than assumed

- `origin/master` carries the archive; master CI was green on merge `0464d6eb6`.
- **Nothing of this track's is open anywhere.** The open PRs in this repo belong
  to the daemon-liveness track and to release-please.
- No background jobs from this track remain armed.
- The supervisor's narrative record is at
  `tmp/overseer/supervisor-prompt-quality/.supervisor-state` (gitignored, so a
  fresh clone has none of it — treat every line in it as a claim with a
  timestamp).

## YOUR ACTION

There is no supervision work on this track. Do not start any.

1. Confirm the archive is real: `plan/archive/supervisor-prompt-quality/` exists
   in `origin/master` and the live directory holds only this file.
2. Report to the maintainer, in one or two sentences, that this track is complete
   and archived and that you are standing down.
3. Declare `ready` in this supervisor's own state file and stop.

If the maintainer wants work done instead, they will say so — and the right home
is one of the successor threads above, entered through its own handoff, not
through this one.
