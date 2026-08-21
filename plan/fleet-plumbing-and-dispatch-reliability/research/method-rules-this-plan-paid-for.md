# Method rules this plan paid for

Consolidated 2026-08-19; extended 2026-08-21 with rules 13-15, then 16-19,
then 20-22, then 23. These rules were each learned by being bitten, and until now they
lived scattered across a dozen ledger handoff entries — which means
reconstructing them costs reading the whole timeline in order. They are the
transferable part of this work, so they belong in the research store where a
fresh reader can find them in one place.

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

### 16. A populated field is not evidence of a CURRENT requirement

`overseer-olxhm6` was found with its top-level `acceptance_criteria` **null**
while a 1,535-character copy of a real bar sat in `metadata.acceptance_criteria`.
That is the `overseer-jkakz6` divergence, and it points the harmful way: `bd show`
renders the metadata copy, so every human reader saw a complete bar while the
factory and the projection — which read the live field — would have received
nothing. The item was `ready` and declared factory-safe.

Promoting the copy into the live field looked like the whole repair. It was not.
The item's own 2026-08-19 amendment states that its restructure **supersedes**
the single-leg framing, and the metadata copy *was* that superseded framing —
verified by searching the promoted text, which contained no occurrence of the
restructure or of either new leg. So the repair replaced a null bar with a
**retired** one.

That direction matters. A null bar fails loudly. A superseded bar passes quietly:
the amendment's own first sentence warns that an implementer working only the
null-fields branch leaves the larger classes untouched, and the superseded bar is
that branch and nothing else. A dispatch would have produced a technically
passing run addressing one of three classes.

**So the check is two-part.** Read the JSON to confirm the field is populated —
never the rendering, which shows a copy the factory does not consume. Then read
the comment timeline for anything that supersedes it. Doing only the first is how
this session nearly shipped the retired bar it had just repaired.

A sweep of the thread's nine other open carriers found exactly one further
supersession-language hit worth opening, and it was a correction to a *finding*
rather than to a bar. **The hazard is rare, which is precisely why nobody looks.**

### 17. Two probes, each blind exactly where the other sees

Deciding whether a stranded dispatch left any work behind has two standard
probes, and **each is separately documented in this fleet as "the" reliable
one.** Both claims are half right.

Measured 2026-08-21 on `overseer-7bhp`. Its run parked at the in-loop human gate
after implementing, passing janitor and passing review. From the operator seat:

```
gh pr list --head feat/overseer-7bhp --state all   ->  []
git ls-remote origin ...                           ->  refs/heads/feat/overseer-7bhp
```

The run had **pushed but never opened a PR**, because it hit the gate first. The
all-states PR query — named in `overseer-thk0`'s deliverable as "the one
host-independent leg" — returns the same empty array for *"finished work is
sitting on a branch"* as for *"nothing ever happened"*. The ref listing found
roughly fifty lines of green, reviewed work.

The converse is already on record and is equally true: an empty `ls-remote`
discriminates nothing, because a merged PR's branch is routinely auto-deleted,
so the ref probe reads empty **precisely when the work landed**.

| shape | PR query, all states | remote ref listing |
|---|---|---|
| merged, branch auto-deleted | **finds it** | empty — misleads |
| pushed, no PR opened | empty — misleads | **finds it** |
| nothing ever happened | empty | empty |

**Only both empty licenses the conclusion that no work exists.** Naming either
probe alone sends the next reader down the blind side half the time, and in the
pushed-but-no-PR direction the cost is the documented one — concluding nothing
happened, releasing the claim, re-dispatching into a collision with the run's own
published branch.

This is rule 4 applied to a pair rather than a single check: for each probe, ask
what state would have produced the *other* answer. Do it for both and the gap
between them is obvious; do it for one and the gap is invisible.

### 18. A closed carrier is not a shipped fix — verify the artifact you will execute

Rule 15 covers the case where you *have* the fix and its mechanism does not
apply to you. This is the other side: the fix is real, the item is **closed**,
and you still do not have it.

Measured 2026-08-21. `bd-ib-k2nkih` — the P0 that had every dispatch dying
`exec /bin/bash: argument list too long` in sandbox setup — went to `CLOSED`.
Dispatching on that fact alone would have failed again, for two independent
reasons:

1. **The session's resolved build predates the fix.** A session binds a plugin
   build at startup and keeps it. Ours had already gone
   `726ae2ae3499 → 1997cded11be → bdb97d1daf03 → f311b9274cdd → 4157cf17b852` —
   **five values in about four hours**. Any build id written down goes stale
   inside the hour, which is `overseer-iwu`'s claim measured from the inside.
2. **Closed names an item, not an artifact.** Nothing in the ledger row tells
   you whether the bytes you are about to execute contain the change.

The check that actually licensed the retry was reading the **mechanism** in the
resolved build's own source: `_dispatcher_gh_refresh.py` at `4157cf17b852`
chunks its base64 payload to sizes chosen to stay inside `MAX_ARG_STRLEN`,
names the regression it addresses in a comment, and asserts each chunk stays
within the base64 alphabet. The previous build passed the whole payload in one
argument. That is a positive identification of the fix, not an inference from
its carrier's status.

**So: take the build id from the tool at the moment you dispatch, then confirm
the fix's mechanism is present in that build.** Both legs are needed — the
first without the second gives you a fresh build you have not checked, and the
second without the first checks a build you will not run.

The generalisation across 15 and 18: **a fix has to clear three gates before it
helps you — it must exist, it must reach your artifact, and its mechanism must
match your instance.** Each gate has now cost this thread a separate incident.

### 19. Do not argue about what a measurement would show — take it

Rules 3 and 4 are about designing checks that *can* fail. This one is about the
analyst, and it cost a wrong recommendation on `overseer-izh7` that a maintainer
could have acted on.

That item's leg 2 asks whether the bd-guard blocked-op count for this repo
returns to zero after the remedy merged at `2026-08-20T09:23:46Z`. Every number
on the item predated that merge, so nobody had measured the window the criterion
is actually about. I reasoned about it instead, and recorded this:

> the forward window has the same expected value under both hypotheses —
> guidance effective, and guidance irrelevant. It returns zero either way …
> such a criterion cannot fail.

On that basis I recommended closing on the frank basis that leg 2 could never
attribute anything.

**One query refuted it.** Over the post-remedy window, scoped to this repo:
**4,384 bd invocations, and one blocked op** —

```
2026-08-20T10:57:45Z   bd update overseer-au3pt3.9 --status open
guard.op = status:open   exit_code = 3   bd.repo = livespec-overseer
```

Ninety-four minutes after the guidance merged. The criterion could have returned
zero and did not, so it discriminates — which was the entire content of my
objection.

**The shape of the error is the point.** I applied rule 4 — ask what state would
produce the other answer — to the *criterion*, and never to my own claim about
it. The data was one read-only query away the whole time, in a dataset the item
already names. Reasoning about a measurement is not cheaper than taking it when
the measurement is available; it is only faster to write down.

**So: before arguing that a check is vacuous, run it.** A vacuity argument is a
prediction about the result, and predictions about available results are exactly
the claims you never have to make.

A second, smaller trap surfaced in the same query and is worth carrying: the
first attempt filtered on `guard.mode = "fail"` and returned 4,382 of 4,382.
`guard.mode` is the guard's *configured mode*, not an outcome. **A ratio of
exactly 1.0 is a filter smell, not a finding.**

### 20. An instrument gap and a causal claim are two findings, and the first does not evidence the second

`overseer-zw34c3` measured, correctly and carefully, that the delimiter check
this repo prescribes misses a doubled *closing* brace. Scanned as stored, the
casualty item gives zero hits for all three opening forms and two for the
closing form, so the check really does return clean on the record it was filed
about. That half is confirmed.

It then attributed a casualty to that sequence — and **nothing had ever been
dispatched.** The item's only journal row is the foreman filing it; its
successor has none. Positive control on the same query: a known-dispatched item
returns 127 rows. So the undispatchability was inferred, never observed.

Two measurements refute the attribution outright:

- **The grammar.** The dispatcher's own escaper states that the template engine
  enters template mode ONLY at the three *opening* delimiters, and that closing
  delimiters are inert outside a tag. Its regex matches those three and nothing
  else.
- **A natural experiment.** Of 612 assembled goal files surviving on this host —
  every one classified, no cherry-picking — exactly two contain a doubled closing
  brace with no opener. **Both ran**: one for 41 minutes, one to completion with
  outcome green in another tenant. Exactly two contain a doubled opener, and both
  died at the factory-run stage in about 32 seconds.

The consequence is not academic. Implementing the item as filed would add a leg
flagging a sequence the grammar says is inert and that ordinary nested JSON
produces *by default* — and the item's own criterion 3 forbids that, since it
requires the fixed check to stay clean on ordinary JSON. **Criteria 1 and 3 are
in direct conflict as filed**, and the conflict is only visible once you stop
treating the instrument gap as evidence for the cause.

**So: when a careful measurement sits next to a causal claim, check whether the
claim was measured too.** It rides along on the credibility of its neighbour.
The tell here cost one query and would have been available at filing time: *ask
whether the thing you are calling undispatchable was ever dispatched.*

### 21. A control is a dated claim like any other — re-verify it AS a control

Rules 3 and 4 are about designing a check that can fail. This one is about the
check you designed *last month* and are still trusting.

`overseer-fs4` does the right thing: it states that a zero-hit grep is not
evidence on its own, and it names a positive control — a token that "hits at"
four specific call sites. Re-running its method today, **that token returns
zero.** Not because the search is broken: because the key was removed from the
package, which is exactly what this thread verified when it closed
`overseer-n11` as already-done. The control is now indistinguishable from the
thing it was supposed to detect.

**The same pass produced two different failures wearing one symptom, and only
the control separated them.** The first run returned zero for *every* term
including the control, because the shell expanded the include-pattern flag
before `grep` saw it and nothing was scoped at all. Had the four target terms
been run alone, the output would have been four confident zeros produced by a
broken command. Once the command was fixed, the control *still* returned zero —
for the unrelated staleness reason above. Swapping in a token known to exist
today (345 hits) is what finally made the four real zeros meaningful.

This has a family. Three instances landed in a single day:

| the control | how it decayed |
|---|---|
| a remote run id quoted as a dump fixture | removed from the remote store within hours, while its sibling survived |
| a real historical commit used as a RED fixture | absent from CI's shallow clone, so the test failed where it ran |
| a grep token named as a positive control | legitimately deleted from the package it probed |

Each fails in the **safest-looking** direction: a zero from a broken or outdated
query is indistinguishable from the zero you hoped for, and a fixture that
cannot be found reads as *the finding was wrong* rather than *the fixture
decayed*.

**So: before a control validates anything, validate the control.** And when you
write one down for someone else, prefer a property that is re-derivable — resolve
the fixture *by shape* at the time of use — over an identifier that was true on
the day you wrote it.

### 22. An acceptance criterion is a claim about the world, and can be false

Rule 16 says a populated acceptance field is not evidence of a *current*
requirement. This is the harder case: a field that is current, ratified, and
**technically wrong**.

`overseer-iwu` asks for a resolver that selects the newest plugin cache
directory **by modification time**. Measured across this host's cache — 175
directories, versions read from each directory's own manifest rather than
inferred from its name — mtime order is not release order, and two independent
pairs are anti-correlated:

```
08:28:35  0.62.10        0.62.10
07:57:48  15a4ae9aff88   0.62.9     <- newer mtime, older version
06:48:29  15b9787566a7   0.62.10    <- what ensure-plugins names as current
04:13:53  271b1f3fa14c   0.62.5     <- newest of its block by mtime
04:10:24  4157cf17b852   0.62.8     <- oldest of its block by mtime
```

The prescribed heuristic picks the staler build in **both** pairs where the two
orders disagree, and the authority the item already trusts names a directory
that is only the third newest by mtime.

**And the specified test would not have caught it.** It asserts the resolver
reaches an *existing executable* — and a stale build's entry point exists. Its
required positive control tests existence, not currency. So the acceptance as
written would green-light a resolver that can pick the wrong build: the same
check-that-cannot-fail class the item itself was filed about.

**Corrected the same day, because the first version of this rule overstated its
own evidence.** It said "reliably picks the wrong build". Re-measured four hours
later, the heuristic answers *correctly* at that moment — newest by mtime is also
the highest version. It is not reliably wrong; **it is unreliable**, which is the
stronger argument anyway and the same shape as `overseer-iwu`'s own burstiness
correction: a resolver that is right most afternoons and wrong on the afternoon
you are debugging a dispatch refusal is worse than one that is dependably broken,
because nothing observable at the moment of picking tells you which case you are
in. The re-measure also enlarged the evidence from two anti-correlated pairs to
**53 adjacent inversions**, including four consecutive builds whose versions
*descend* as their timestamps ascend.

Two more instances the same day. `overseer-thk0` inherited a criterion pinning a
specific run id as its demonstration, and that run vanished from the remote store
between the criterion being written and being read. `overseer-zw34c3` carries two
criteria that cannot both be satisfied (rule 20).

**So: measure an acceptance criterion before implementing against it**, at least
where it prescribes a mechanism rather than an outcome. All three of these were
caught in the gap between ratification and dispatch, which is the cheap moment —
a criterion that is wrong about the world produces a run that passes its own bar
and ships the defect, and the passing run is then evidence *for* the criterion.

### 23. Check what BECAME of work you routed — a routing is not a terminal state

This thread has closed eight carriers superseded-with-pointer. Every one of those
closures verified the successor **existed** at the moment of handover — correctly,
and that is where the checking stopped. Nobody ever asked what happened next.

Asked on 2026-08-21, for the first time:

| successor | state |
|---|---|
| `livespec-driver-claude-d7d` | **closed** — implemented and merged, PR 570, 08:21:41Z |
| `bd-ib-gn6hdf` | **closed** — fixed and merged, PR 1582 |
| `bd-ib-unm6co` | **closed** — dispatch landed PR 1609 |
| `bd-ib-acbp` | **closed** — dispatch landed PR 1592 |
| `bd-ib-2rolbh` | pending-approval |
| `bd-ib-ay5mtm` | blocked |

**Four defects this thread found, evidenced and routed have been repaired in their
owning repos**, and no routed work is recorded nowhere. That is good news, it is
what an archive completeness review has to rest on, and it sat uncollected for
days because a routing felt like an ending.

**The expensive half is the first row.** `overseer-n77r` exists to document an
override *before* the resolver fix makes essentially every worktree here fail with
a not-installed error. That fix is `d7d` — this thread's own routing of
`overseer-af9`. It merged at 08:21:41Z. A re-measure on `n77r` four hours earlier
had confirmed, correctly for its moment, that the window was still open.

And the fix did not arrive alone: the shipped resolver's rule 3 now maps a worktree
back to its **primary** before the registry lookup, which is precisely the
mitigation `n77r` was filed to write a workaround for. Executed rather than read —
the primary and two record-less worktrees all resolve to the same core root, none
fails. So a live carrier's central premise was invalidated **by its own thread's
routed work**, in a repo nobody here was watching.

**I then drafted that carrier's guidance from its own last-recorded state**, saying
worktrees would start failing loudly and the reader probably had not seen it yet.
Both sentences were already false when written, by about an hour. Rule 18 says a
closed carrier is not a shipped fix; this is the mirror image and it is not covered
by it — **an open carrier's premise is not still true either.** The record you are
reading describes when someone last looked, in a repo whose movement you do not see.

**So: when work leaves for another repo, put a check on what it does there.** Ask
at least at these moments — before drafting anything from the carrier that routed
it, before writing a completeness review, and before treating any carrier's urgency
as current. The question is cheap: one status read per successor. What it buys is
both directions — credit for repairs that actually shipped, and warning when a
routed fix quietly removes the reason another item exists.

## A note on where these came from

Nothing here is a general software-engineering maxim. Each rule is the residue
of a specific incident in this fleet, and several exist because the OBVIOUS
remedy was the damaging one — un-closing shipped work, granting a privilege the
specification withholds, reverting a correct fix by citing its own superseded
rationale.

That is this plan's signature: **the failure points away from its own fix.**
The rules above are mostly instruments for noticing when that is happening.
