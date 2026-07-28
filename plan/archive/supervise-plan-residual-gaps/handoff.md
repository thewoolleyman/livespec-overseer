# Plan — supervise-plan-residual-gaps

**Owning repo:** `livespec-overseer`. **Status: read it from the ledger**
(`list-work-items` / `next`); nothing here stores status.

**Ledger anchor:** epic **`overseer-7lv`**. Created 2026-07-26 at maintainer
direction.

## Read this first — this thread is a RESIDUE, not a rival

`plan/supervisor-prompt-quality/` and its epic `overseer-byvxlp` already own
the generated-supervisor-prompt quality bar (eight requirement families). This
thread **extends** that work and **forks none of it**.

The distinction worth holding: `overseer-byvxlp` governs what the generated
prompt CONTAINS and whether it EXECUTES — cold-open gate, placeholder lint,
adopter parameterization. This thread governs the supervisor's own **runtime
liveness and obligations**: what wakes it, what it owes, and to whom. Same
artifact, different failure axis.

**If the maintainer would rather fold this residue in as `overseer-byvxlp`
children at groom, that is a strictly better outcome than two anchors.** This
thread's only real claim is that the residue must not be lost.

## Provenance

A cold-open supervisor session — `console-happy-path-mvp-supervisor`, driving
`livespec-console-beads-fabro` — read the shipped `supervise-plan` prose
contract (plugin cache `e239ff4dcc93`) and tested it against its own recorded
failures from that session. Six candidate holes came out; a coverage check
against `overseer-byvxlp` found five already covered or partly covered. Only
the residue is carried here.

That session is also the evidence source: every failure below was OBSERVED,
not hypothesized, and several reached durable records on master before a human
caught them.

**The coverage map lives in `overseer-7lv`'s description. Do NOT re-derive it —
but DO re-run it before grooming, because `overseer-byvxlp` may have moved.**

## The residue — five requirements

**R1. The armed-re-entry trigger is scoped too narrowly.** The shipped prose
says "Before ending ANY turn **while the worker is mid-flight**, ARM a
re-entry." Observed: the worker was correctly PARKED, gated on an external
event the SUPERVISOR owned. Worker-idle plus supervisor-holds-an-obligation
matches no trigger, and the thread sat 8h05m until the maintainer intervened.
The trigger must fire on ANY open obligation regardless of holder, and the wake
condition must be able to be a non-pane event — the shipped watcher can only
diff a tmux pane, and cannot watch a PR merge.

**R2. The supervisor has no durable obligation record.** The supervised worker
has `.overseer-state`, and it works: the 8h stall was diagnosed FROM it,
because the worker's marker correctly named its gate. The supervisor has no
equivalent — nothing survives context compaction or session death stating what
it waits on, what wakes it, and what to do if nothing does. Family 1 of
`overseer-byvxlp` deliberately keeps live status out of the generated prompt
and routes it to the ledger and thread handoff; that is right for THREAD status
and leaves the supervisor's own in-flight obligations homeless.

> Preserve the irony rather than sanding it off: that same session enforced the
> marker discipline on its worker three times — catching three false "the marker
> exists" claims — while never applying it to itself.

**R3. No cross-track handoff protocol.** "A lane owned by another track is not
a thread-wide blocked state" is necessary and not sufficient. Observed: an
obligation was handed to a peer supervisor, and a second was accepted from the
maintainer on another track's behalf; one sat unrouted for over an hour inside
the worker's marker with the supervisor's name on it. Needed: how to hand an
obligation to a peer, confirm receipt, confirm the peer REMOVED it from their
own plan so it cannot live in two places, and track it so it cannot die in the
gap. Reusable precedent: `livespec-console-beads-fabro-6ma`, a correctly
diagnosed P1 that sat six days in a tenant whose owners could not fix it.

**R4. Verification discipline beyond blocked-claims.** Family 8 already
requires blocked-claims to carry verifiable referents and adds a startup
stale-state audit. Two observed shapes remain uncovered:

- **A filed item is a claim with a timestamp.** Five P1 bug titles were relayed
  as present-tense blockers; two were dead — one fixed the same day it was
  filed, one obsoleted by a sandbox change — and the framing reached a merged
  handoff on master before the maintainer challenged it.
- **An exit code through a pipe is the last command's.** `… | tail -35; echo
  "EXIT=$?"` was read as the CLI succeeding. The fleet's existing "establish
  outcomes from artifacts, never exit codes" lore is defeated by the pipeline
  case in a way its current wording does not name.

**R5. The watcher expires into an intention.** The shipped watcher ceilings at
~180 iterations then echoes "re-arm", leaving re-arming to the supervisor's
intention — the exact failure the same section forbids ("'I'll check back' is
an INTENTION, not a mechanism"). Expiry must itself be a wake, or the watcher
must self-perpetuate.

## Next action

**Nothing is started.** In order:

1. **Re-run the coverage map** in `overseer-7lv` against the CURRENT
   `overseer-byvxlp` and `overseer-hbr.16`/`overseer-hbr.4`. Anything that has
   since been absorbed should be struck here rather than built twice.
2. **Put the fold-in question to the maintainer** — residue as `overseer-7lv`
   slices, or as `overseer-byvxlp` children. One question, recommendation
   first.
3. **Then groom** whichever anchor survives. The maintainer owns the cut.

Do not start writing template prose before step 1. The whole point of this
thread is that the residue is small and precisely bounded; re-deriving it wide
would recreate the duplication it exists to avoid.

## Standing bounds

- `overseer-hbr.16` (both stall modes + tell-them-apart fixtures) and
  `overseer-hbr.4` (executable-commands bar) are the FLOOR and land first.
  Beads forbids task-blocks-epic edges, so those dependencies are PROSE-ONLY
  and must be re-checked by hand before calling anything ready.
- Every requirement here must become REQUIRED GENERATED CONTENT in the
  `supervise-plan` prose contract — not advice in a hand-written charter. A
  charter that says the right thing while the generator omits it is the exact
  gap this thread documents.
- Every fixture asserts over GENERATED output and must be demonstrated RED
  under an injected defect. R1's red: a generated charter that arms nothing
  when the worker is idle and the supervisor holds an open obligation.
- Do not weaken or remove an existing check to make a new one pass.

## Operational map

Supervision runs against the live fleet: daemon in tmux `livespec-overseer:1.1`
— never kill it. The `supervise-plan` contract under repair is this repo's
`prose/supervise-plan.md`; the version this thread was written against is
plugin cache `e239ff4dcc93`. Sibling threads: `plan/supervisor-prompt-quality/`
(the tie-together for `overseer-byvxlp`, still LIVE) and
`plan/archive/ship-overseer-to-fleet/` — **CLOSED and archived 2026-07-27**,
all six goals met (goal 1 was fleet availability; this thread strengthens the
behavioral bar and never gated it).

**Told, and it landed.** As of 2026-07-26 the `supervise-plan` skill RESOLVED
in a session that is not this repo's (`livespec-console-beads-fabro`), read
cold from the plugin cache — their goal-1 acceptance condition, observed from
the outside. That thread recorded it in its §"Independent corroboration of goal
1", valuing it precisely because it came from a thread with no stake in scoring
the goal met. Nothing further is owed to it; it is closed.

This thread's supervisor charter: `supervisor-handoff.md` beside this file.
