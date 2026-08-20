# Method rules this plan paid for

Consolidated 2026-08-19; extended 2026-08-21 with rules 13-15. These rules
were each learned by being bitten, and until now they lived scattered across a
dozen ledger handoff entries — which means reconstructing them costs reading
the whole timeline in order. They are the transferable part of this work, so
they belong in the research store where a fresh reader can find them in one
place.

**This note is method only.** It records no carrier state; status is composed
from the ledger. Where a rule names an incident, the incident is on the epic's
timeline and on the carrier.

## The rules

### 1. State the SCOPE of a control when you hand one over, and demand it when you receive one

**Cost: a wrongly-closed P1.** A control was published that could not have
failed; another session closed a carrier on it within 22 minutes, in good
faith, because it was presented as a control with rows and verdicts.

Name the leg you exercised and the leg you did not.

### 2. And state the DOMAIN — the STATES a remedy is correct for

Separately paid for. A finding about a valve that clears a stuck claim was
relayed as the way to clear assignee residue on **closed** rows, which would
have un-closed merged, shipped work. The valve is correct for a stuck `active`
claim and forbidden on a closed row, because its clear is transition-coupled.

A remedy has a domain. Handing one over without it is handing over a loaded
tool.

### 3. Probe the case a gate must REFUSE, not the case it must admit

An admit-only probe passes identically on a working gate and on an absent one.

### 4. When a check returns the answer you expected, ask what state would have produced the OTHER answer

If you cannot construct one, the check is not evidence. Six instances caught
across this plan's life, including:

- an ancestry check that asked whether a branch was merged into `HEAD` — trivially
  yes, because the clone was checked out on that branch;
- a closed-sibling probe that returned `True` on builds predating sibling
  enforcement;
- a rendered `bd show` omitting an `Assignee:` line, which is equally consistent
  with a cleared field and an empty-string field. Only the JSON separated them.

### 5. A citation match is not a fix

Require the diff that PERFORMS the change plus current state agreeing — never
the commit subject.

Two instances. One carrier had a commit whose message matched the symptom and
nothing else. Later, two upstream commits appeared to resolve a blocker until
their dates were read: both authored five months before the item was filed,
making them the baseline the fix builds on rather than the fix.

### 6. When an action is in flight across a session boundary, SAY SO, and say what would constitute completion

A performed-but-not-completed next action reads as unstarted while a duplicate
is one command away.

### 7. A ledger field describes the RECORD, not the WORLD

**Learned twice in one session, the second time by the author of the first.**

- `Updated:` does not move on a comment write, so it is not an activity signal.
  Proven with a live write on a row whose date did not change.
- `status` is not a scheduling signal. A P1 reading `BACKLOG` had a dedicated
  plan opened that same day in the owning repo — published branch, committed
  research note naming it as the anchor, live session on it.

In this fleet the row is the LAST thing to move. Work is planned in branches and
threads, measured, and often half-done before any row changes. Check branches,
plan directories, open PRs, running sessions, and the code itself.

The narrow form of this rule ("`Updated:` is unreliable") did not prevent the
second instance even in the mind that had just written it. That is the argument
for carrying the general form.

### 8. Weigh a negative correctly, especially across a repo boundary

A search across another repo's planning surface that finds nothing is **not** a
negative result. The plan in rule 7 would have been missed entirely but
for a coincidentally-noticed session name.

Say "I found no evidence of in-flight work". Never "it is not scheduled".

### 9. Record the measurement that does NOT support your item

A carrier here argued a release train was CONTINUOUS. A later window showed six
hours and zero releases — a sample that appears to refute it, and which any
reader could have taken.

Recording it corrected the premise to **bursty**, which is *worse* for a human
(a reliably-wrong habit gets noticed; an unpredictable one does not) and makes
the item robust to the sample that would otherwise discredit it.

A right conclusion resting on a wrong mechanism is never re-tested by anyone
downstream. Supporting-evidence-only records are how that happens.

### 10. A null result, properly conducted, still rules something out

Re-checking a blocker via history rather than via its PR record returned the
same answer — but it closed the "fixed by another route" possibility that the
PR record could not speak to.

The rule in 7 does not claim records are usually wrong. It claims you cannot
know which case you are in without looking. Rule 9's carrier is the case where
looking changed something; this is the case where it did not. Only one of those
was predictable in advance.

### 11. Fence a claim at the moment you make it, not at review time

The operative discipline behind several rules above. Five findings were
self-refuted during one session — a prior-art lead, a control, a scheduling
claim, an inference from help text, and a published trap entry — and every one
was cheap **because it had been written down with its own weakest leg named.**

A finding recorded without that fence is a finding nobody re-tests, including
its author.

### 11b. But a fence is only worth what you DO about it

**The fifth self-refutation is the one that earns this clause, because fencing
did not save it.** A trap entry was published in `AGENTS.md` claiming a
particular row status blocked dispatch tenant-wide. It was fenced exactly as
rule 11 asks: it stated in terms that the refusal had *not* been observed, and
marked the blast-radius claim as INHERITED from a neighbouring trap rather than
reproduced.

**The fence named precisely the leg that turned out to be false.** The claim was
wrong: the dispatcher auto-heals that status before the conformance check ever
runs, and only key-misses block. One read of the dispatch path — the cheap check
the fence itself pointed at — would have caught it before publication.

**And the fence made the wrong claim travel further, not less far.** It was
routed to another repo's foreman, who did everything right: verified both code
links independently, folded it into a tracked item as a third defect channel,
and carried the not-observed caveat *verbatim*. Correct handling of a fenced
claim, and the claim was still false. **An unactioned fence reads to everyone
else as diligence**, which is exactly why it propagates.

So rule 11 has a second clause: **fencing a claim makes being wrong cheap; it
does not make the claim true.** Where the fence names a check that is cheap to
run, RUN IT BEFORE PUBLISHING. Where it names one that is genuinely expensive —
here, reproducing a tenant-wide outage on a shared ledger — publishing behind
the fence is still right, but say what would settle it and who can afford to.

**Retract visibly, not silently.** Once a fenced claim has been published and
routed, deleting it leaves the claim circulating with nothing to find. The
retraction has to go where the claim went — the document, and every seat that
received it.

### 11c. Price a fence before declaring the check too expensive

**The converse failure, and it happened the same night, to the same author, in
the same artifact.** Two checks were fenced as "genuinely not cheap from here",
explicitly contrasted with the earlier case where the fence should have been
actioned. One of them was **two `find` invocations and about a second.**

**Over-fencing is the same failure as under-checking, wearing better manners.**
Rule 11b says run the cheap check a fence names. It does not say *verify that a
check is expensive before declaring it so* — and that estimate is a claim like
any other. Rule 4 applies to it: what state would have produced the other
answer? Usually the cheapest way to find out is to run the thing.

**Two fences mispriced in opposite directions in one session** — one check that
should have been run and was not, one declared expensive that took a second.
The second is the more insidious, because a fence that misprices its own check
reads to everyone as diligence while deferring the work indefinitely. Nobody
ever comes back to it, since it is documented as costly.

**And the measurement reversed a conclusion that had been left open.** The
unpriced census, once run, excluded one of three dispositions that had been
handed to another item's owner as an open choice — on evidence, in a second.
The cost of not running it was a wrong instruction standing for an hour.

**The tell for this failure is a fence written in the same breath as a
disposition.** If you are recording "the answer depends on X, which I did not
measure", stop and ask what measuring X actually costs. That sentence is doing
two jobs — deferring the check and shaping someone else's decision — and only
one of them is legitimate when the check is a one-liner.

**Deferring is not automatically the humble choice.** This clause was itself
initially withheld as something to "offer rather than add unilaterally", to an
artifact its own author had written, in that author's own plan. That is the same
over-caution one layer up.

### 12. A code path describes ITSELF, not the system — ask WHICH SURFACE

The sharper form of rule 7. That rule says a ledger FIELD describes the record
rather than the world. This one says the same of CODE: verifying one call site
tells you about that call site, and generalizing from it is how a correct
measurement becomes a false claim.

**Four instances in a single night, and every correction that night came from
this rule rather than from finding a wrong fact.** In each case the facts were
right and the generalization was not:

- A guard exempts a flag from normalization — true at the guard layer, and the
  dispatcher heals the same value one layer down, so the consequence drawn from
  the exemption was false.
- The pre-push gate heals before checking — true, and the bare check subcommand
  does not, so "auto-healed before the check" was true of some surfaces and not
  others.
- Another repo recorded a status re-triggering a refusal mid-repair; a
  retraction here said it could not. **Both were correct** — a repairer
  verifying between commands runs the non-healing surface, while the dispatch
  that would have healed it never ran.
- The same shared check registry is consulted by four callers. Three normalize
  first; one does not. The invariant has one source of truth and the CALLERS
  disagree, which is a caller-contract gap and reads exactly like a duplicated
  invariant.

**The diagnostic question is "which surface produced this?", asked before
concluding anything.** A finding, a refusal, a green check, a clean census —
each is a statement about the path that produced it. Two people measuring the
same subject on different surfaces will produce contradictory reports and both
be right, which is unfalsifiable-looking until someone names the surfaces.

**And it changes how acceptance criteria must be written.** An acceptance
phrased as "the status no longer appears" is satisfiable against a path that
already heals while changing nothing on the path anyone actually complained
about. **Name the surface in the acceptance**, or an implementer can satisfy it
honestly and fix nothing.

**A corollary for shared invariants.** Single-sourcing the RULE does not
single-source the PREPARATION each caller does before consulting it. When a
check is reused across surfaces, the divergence will live in what callers do
first, and it will look like the invariant is inconsistent when the invariant is
the one thing that is fine.

### 13. A measurement whose window PREDATES the remedy cannot attribute — and a good denominator does not rescue it

`overseer-izh7` leg 2 asks for the bd-guard blocked-op count to return to zero
over a window longer than the trigger's 60-minute lookback. Measured 2026-08-20:
zero, across every caller path in this repo, over about 34 hours. The criterion
reads satisfied.

It is worthless as written, because the guidance it exists to test merged at
`09:23:46Z` and this repo's last blocked op was some 34 hours *earlier*. The
whole window sits before the remedy. The measurement returns the same value
whether or not the fix landed — so it can confirm a condition's absence and can
never attribute it.

**A corollary about how the objection was answered.** The first draft of this
finding gave two reasons to reject the measurement: no denominator, and the
window predates the fix. Only one survived contact. The denominator was then
measured — 8,437 invocations from this repo in the same window, zero
blocked — so "the repo was merely quiet" is refuted and the zero is a real
signal. **Split a compound objection and re-test each half**, or a refuted
half drags a sound half down with it. Here the sound half was the one that
mattered.

What it leaves behind deserves naming: `izh7` leg 1 is **prophylactic**. Its
value lies with callers who have not yet made the mistake, and the absence of a
mistake that had already stopped cannot demonstrate it. An acceptance asking for
a zero will keep being satisfiable without ever testing the remedy.

### 14. A signature that cannot separate healthy from broken must never be acted on

`overseer-1hv`'s execution leg needs a genuinely stuck claim, and the standing
agreement is to take one met in the normal course rather than manufacture it. A
sweep found five items reading `active` with a `fabro` assignee and a null run
id — the item's surface signature exactly.

None qualified. All carried same-day record mutations, whereas the measured
instance had `updated_at` **frozen** at the dispatch instant. A null run id is
not a stuck signal at all: this thread's own `izh7` dispatch carried null both
while running *and* after it merged. And those items dispatch to a **remote**
factory, where absence from the local process view is evidence of nothing.

The rule is what follows from that. The signature classifies **live remote
runs** as stuck, so acting on it — moving such a row to clear its claim —
destroys work in flight, and does so most confidently at the moment the run is
healthiest. All five were left untouched. **Before acting on a signature, ask
what a healthy system looks like through it.**

### 15. Having the fix is not the same as the fix applying to you

`overseer-n04`'s warning has a real upstream fix: beads `3068bc428`, PR 3568,
"skip auto-backup file-URL register on external Dolt server", dated 2026-04-28.
The maintainer's correction reasonably anticipated the remedy was an upgrade not
yet taken.

Measured 2026-08-21: **we already have it.** The earliest tag containing the fix
is `v1.0.5` and the installed binary *is* `v1.0.5` — established by an
is-ancestor test against the installed commit, not by comparing version strings.
And it cannot fire here: its guard skips the registration only when the server
sits on a *different* filesystem, returning true for loopback hosts, and this
tenant is configured at `127.0.0.1`. Same warning text, different mechanism —
ours is a privilege denial, the fixed one is a meaningless URL.

An upgrade undertaken on that expectation would consume real effort and change
nothing observable. **Check that the fix's MECHANISM matches your instance, not
merely that its symptom does.** This is rule 5 one turn further on: there the
citation matched and no change had been made; here the change is genuinely made,
genuinely correct, and genuinely irrelevant to us.

## A note on where these came from

Nothing here is a general software-engineering maxim. Each rule is the residue
of a specific incident in this fleet, and several exist because the OBVIOUS
remedy was the damaging one — un-closing shipped work, granting a privilege the
specification withholds, reverting a correct fix by citing its own superseded
rationale.

That is this plan's signature: **the failure points away from its own fix.**
The rules above are mostly instruments for noticing when that is happening.
