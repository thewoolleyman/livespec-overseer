# Operating findings — what a drain pass meets that the mechanism note does not cover

**Ledger anchor:** epic `overseer-adclcd`. Mutable plan state — status, next action,
handoff entries — lives on that epic and its children. This note is write-once
research and is never authoritative about what remains.

Companion to `mechanism.md`, which was written from the 2026-08-19 drain itself.
Everything here was measured LATER the same day, by the session that resumed the
thread and tried to route its first carrier to the factory. That is a different
vantage point and it surfaced a different class of finding: `mechanism.md` knows
how to perform a drain, and this note is about what the pass meets at its EDGES —
the ledger it files into, the factory it hands to, and the evidence it leaves
behind when things fail.

Re-measure before trusting any count, path or timestamp.

## The create path is the drain pass's hot path, and its default poisons the tenant

`mechanism.md` records that a non-lifecycle status refuses every dispatch in the
repo, and prescribes holding items at backlog rather than reaching for the defer
flag. That is correct and it is not the whole trap, because it describes a flag
an operator has to reach for deliberately.

**The ordinary create path defaults to a non-conforming status all by itself.**
Filing a work item with no explicit status leaves it at the substrate's native
default, which is outside the seven lifecycle statuses. The row then trips the
global pre-dispatch conformance sweep and refuses EVERY dispatch in the repo,
naming an id that belongs to whoever filed it rather than to whoever is blocked.

**And it is not avoidable at creation, which is the part that makes advice about
it easy to get wrong.** Measured 2026-08-20 while filing a real item: the create
command has NO status flag. You cannot create a conforming item in one command.
The only status-ish flag it offers is the deferral flag — which sets the one
status that blocks every dispatch in the tenant. So "set an explicit lifecycle
status when filing" is not achievable as stated; the achievable form is **create,
then immediately set the status, as a pair**, and verify the row afterwards. The
create call prints the non-conforming status it just used in its own success
output, so the evidence is on screen at the moment it happens.

**This matters more for grooming than for any other operation in the fleet.**
A drain pass files work items continuously — it is most of what stage 3 and stage
4 do. An operation that files fifty items through a bare create path poisons the
tenant fifty times over, and every one of those refusals lands on some other
thread's dispatch. The trap scales with exactly the thing this operation exists
to do.

Measured on 2026-08-19: four separate non-conforming rows across three sessions in
one day, two of them appearing about twenty minutes apart while this thread was
actively trying to dispatch. One session filed such a row, caught it within about
ninety seconds, and wrote it up — and the trap still produced two more rows
afterwards, from a different thread's filing route.

**What the contract must require:** set an explicit lifecycle status at filing
time, and re-read the row afterwards rather than trusting the create call. The
create call's own success output states the status it actually used, so the
evidence is present at the moment of filing if the operation looks at it.

**And what it must NOT do:** silently repair other threads' rows as a side effect.
Correcting a status is a narrow, reversible, status-preserving action and is
appropriate when it unblocks the tenant. Reaching further — into the filing route
that produced it, which belongs to another thread — is not. Record the correction
on the item, and relay the pattern to the owning thread without judgement; the
same trap bit several seats the day it was measured, so it is a tooling defect
rather than anyone's carelessness.

## The end-of-pass conformance assertion must declare its scope, or it is worthless

This bears directly on invariant 3 of the seven, and it nearly produced a false
clean reading twice in one day.

The listing command's default scope is NOT the tenant. It caps rows at a default
limit and excludes closed rows and gate issues. A sweep run at that default can
report zero non-conforming rows while a poisoned row sits outside the window, and
**a truncated sweep that happens to return a clean answer is indistinguishable
from a complete one.** One session noticed only because the row count it got back
was suspiciously round, matching the default limit exactly.

The honest form asks for unlimited rows, all statuses, and gate issues included.
On this repo the difference was roughly nine times as many rows scanned.

**The general rule, which this thread has now recorded in three different
shapes:** a measurement is only as good as its declared scope, so state the scope
beside the result every time. The invariant checker should therefore report the
population it scanned alongside its verdict, not a bare pass or fail. A checker
that cannot say what it looked at cannot be trusted when it says it found nothing.

## The pass ends holding a queue it does not own

Stage 5 hands sessions to the repo's foreman, and stage 6 verifies. Neither stage
owns what happens next, and on 2026-08-19 what happened next was that the factory
was unavailable for the rest of the day.

**A drain pass can therefore complete every one of its own stages and still leave
the repo unable to act on anything it routed.** If the pass reports completion
without saying so, it has misreported its own outcome: the queue it created is
real, and every dispatch in it is about to fail.

The seam to name in the contract is that the drain hands the queue to the foreman
LOOP, and the loop — not the pass — owns releasing it. That is the correct
division of labour, since the pass is one-shot and the condition it is waiting on
may clear hours later. What the pass owes is an honest statement of what it
queued and what that queue is waiting on.

**There are TWO such queues, not one, and the second was missed on the first
pass through this material.** Stage 5's own hand-off is rate-limited. Measured
2026-08-20: the foreman's action seam is real — its plan-start action is
genuinely one of eleven shipped action ids, and its act executable really does
revalidate a proposal against a fresh gather document — but the foreman contract
states plainly that it performs ONE bounded action per HOURLY tick. So a pass
that creates three threads needing three sessions has queued three actions
against a drain rate of one per hour, competing with every other action class the
foreman may need that tick.

This has a direct consequence for stage 6, which verifies by reading tmux
sessions and daemon snapshot rows. Run immediately after stage 5, that
verification finds the sessions ABSENT — correctly, because they have not been
started yet. **Stage 6 must report queued session starts as QUEUED with their
expected latency, must not treat a not-yet-started session as a defect, and must
not wait for one** — waiting would block a one-shot operation on an hourly loop.

**So the honest general statement is that a drain pass CONVERGES
ASYNCHRONOUSLY.** It completes its own work synchronously and then leaves two
queues draining on other components' clocks: dispatches behind a provider
credential window, and session starts behind the foreman's tick. It owns neither
clock. Reporting completion without naming both queues and their gating
conditions misreports the outcome.

## Pre-flight cannot prove factory health when the failure is mid-turn

This is the sharpest single finding of the day, and it is a specific instance of a
hazard `mechanism.md` already names in the abstract.

Every static dispatch-safety check on the item passed: delimiter pre-flight clean,
correctly parented, no cross-repo dependency edge, target repo's master CI proven
green, tenant conformance clean. The dispatch then created a run, launched a
sandbox, cut a worktree, and **died inside the implement stage** on a provider
usage limit.

So a green pre-flight is a control that exercises a DIFFERENT LEG from the one
that fails. Reading it as evidence of factory health is exactly the
scope-of-control substitution `mechanism.md` records as the most expensive error
of the ratifying pass — the same mistake, in a new place, made by a session that
had read the warning that morning.

**A real dispatch is the only valid health signal.** The convention that follows
is to treat the first dispatch after a suspected recovery as a deliberate PROBE,
owned by one seat, with other seats holding until it survives its implement stage.
That protocol is what turns an expensive unknown into one bounded cost, and it is
worth a sentence in the contract wherever stage 5 describes handing off.

**Independence is a claim about FILE SCOPE, not about the credential pool.** Two
carriers that touch disjoint files still serialize against one provider budget. A
pass that reports them as parallelizable will overpromise its own throughput, and
the overpromise only shows up under load.

## A surface error can hide the real cause, and the classifier can be wrong about both

The failure text at the stage read as a protocol error in the agent transport
layer. The actual cause, several levels down in the run's inspect payload, was a
provider usage limit naming its own reset time in plain language.

Worse, the run classified the failure as transient infrastructure — which reads as
"retry might work" when in fact nothing would work until a stated clock time. An
operation that retries on that classification burns a full container setup per
attempt for a guaranteed failure.

**Read the structured failure payload, not the stage's one-line error**, before
deciding whether a failure is retryable, item-specific, or fleet-wide.

## The journal outlives the run — a vanished run has NOT taken its diagnosis with it

This one corrected a claim this very thread had already recorded, which is why it
is here rather than only in a handoff.

Both failed runs disappeared from the run-listing CLI entirely. Asking that CLI to
dump or inspect either one reported no such run. On that basis the session
concluded, and wrote down, that nothing was recoverable.

**That was right about the WORK and wrong about the EVIDENCE.** The work was
genuinely unrecoverable — the implement stage never reached a commit, so no patch
existed to rescue. But the complete failure payload for both runs, including the
provider error object with its reset time, was retained the whole time in the
dispatcher's own journal file at the repo-relative path under the temporary
directory, in the inspect-stage rows keyed by work item id.

**So the discriminator to carry is: the run-listing CLI reporting a run absent is
not evidence that its failure detail is gone.** Read the journal before concluding
a vanished run left nothing behind. A trap whose only tell is reachable through a
command that reports the run missing would otherwise be unrecognisable in the
field — which is precisely the failure mode the contract's trap section exists to
prevent.

## Annotating an item permanently enlarges its future dispatch brief

This one was learned by doing it. It is recorded first-hand because a drain pass
annotates work items constantly — triage and bucketing are largely annotation —
so this is not an incidental hazard for this operation, it is a hazard on its
main path.

**Ledger comments are assembled verbatim into the dispatch brief.** The goal
renderer takes item fields plus every ledger comment plus ratified lessons. The
comments are read unfiltered — no recency window, no count cap, no length cap —
and a failed read REFUSES the dispatch outright, because comments are explicitly
load-bearing operator riders rather than decoration.

**Measured 2026-08-20** against five real work items, comparing the rendered
brief with and without their comments, after one session had spent two rounds
filing verification findings onto them:

    item      comments   brief without   brief with   ratio
    hg5vw6           4            5465        15622     x2.9
    26ufok           3            7137        17987     x2.5
    lywdj4           4            4236        20739     x4.9
    r5b66g           2            4111        13435     x3.3
    mr2f2k           1            3056         7010     x2.3

Every one of those findings was real and dispatch-saving. The briefs still
doubled to quintupled in a few hours of ordinary, well-intentioned annotation.

**Nothing warns, and nothing can.** The dispatcher's item-sizing guard exists for
exactly this failure — briefs too large to finish in one unattended turn — but it
is documented as a pure function of the ITEM, and its heuristics read only title
and description. Comment growth is fully present in the payload and completely
invisible to the guard. On the worst row above the guard reasons about roughly a
fifth of what ships. Filed as a defect in the orchestrator tenant
(`bd-ib-d1mj`).

**And it is one-way.** Comments are append-only — the tooling offers add and list
and nothing else. An inflated brief cannot be trimmed back, so the guard's usual
advice to consider splitting is not even available as a remedy for this growth
path. The cost of noticing late is unrecoverable.

**What the operation should do.** Put durable per-item findings in the item's own
FIELDS, which remain editable. Put pass-level narrative on the plan epic, which
is an anchor rather than a dispatch target and therefore costs nothing at
dispatch time. Reserve item comments for what a dispatched agent genuinely must
read. The relevant question before commenting is not "is this true and useful" —
it usually is — but "must the implementing agent read this, and is it worth
permanently enlarging the brief".

## Verify a relayed operational fact, and say which part you could not verify

The session that resumed this thread was handed an operational briefing from a
peer seat. Two details in it did not survive contact:

- The stated failure wall time was roughly half what was actually measured.
- The failure was described as arriving before the sandbox launched. It arrives
  after, which is what makes it expensive.

Both halves of the briefing pointed at a real condition — the underlying diagnosis
was correct and was independently confirmed from this thread's own run records.
The relayed TELL was simply not the tell. Tracing it back, the shorter figure came
from a comment describing a probe as a cheap instrument, not from a measured
duration; it had been carried forward as though it were a measurement.

**The pattern worth carrying:** a relayed fact usually has a true core and a
degraded surface. Confirm the core from your own evidence, correct the surface,
and say which is which — rather than either accepting the whole thing or
discarding it. `mechanism.md` already requires verifying a delegated claim before
acting on it; this is the same rule applied to a peer rather than a subagent, and
the failure mode is gentler and harder to see.
