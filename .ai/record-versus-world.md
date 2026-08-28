# A field describes the RECORD, not the WORLD

Moved verbatim from `AGENTS.md`.

## A ledger field describes the RECORD, not the WORLD — `Updated:` is not activity, `status` is not scheduling

Measured 2026-08-19 with a live positive control. This one is cheap to get
wrong because the field sits directly under `Created:`, exactly where a reader
expects a last-touched date, and reads like one.

**IT DOES NOT MOVE ON A COMMENT WRITE.** A ledger item can be actively
investigated, argued over, and annotated at length while `bd show` keeps
reporting a months-old `Updated:` date. Comments are where this fleet records
nearly all of its evidence, so the field is blind to most of what actually
happens to an item.

**The control, and why the obvious one is not enough.** The first
counter-example found was `livespec-dev-tooling-qrunmn`: a comment dated
2026-07-20 against `Updated: 2026-07-19`. That is suggestive and **not
sufficient** — a migrated or backdated comment would produce the same reading
on a field that works correctly. The discriminating test is a **write you
perform yourself**:

    bd comment <id> "..."     # then immediately:
    bd show <id> | grep '^Created:'

Done on `overseer-mim`, whose `Updated:` stayed at `2026-07-26` across a
comment added seconds earlier. A sibling item touched by a genuine field
mutation the same day *did* show that day's date, so the field tracks record
mutations and not the comment stream.

**Why it matters beyond tidiness.** Staleness judgements route real decisions
here: whether a blocker is likely to move, whether to dedup onto an existing
record or file fresh, whether a "successor" is a genuine handoff or a parking
space. Reading `Updated:` as an activity signal makes a live item look
abandoned and — the more expensive direction — makes a **parked** item look
merely quiet when it is neither.

**What to do instead: verify behaviorally.** Ask what would be TRUE IN THE
WORLD if the item had progressed, and check that. For a code item, whether the
change is present on the owning repo's `origin/master`. For a forge item, the
PR state — GitHub's own `updated_at` *is* a real activity field, unlike this
one. Comment count is a useful secondary signal precisely because the
`Updated:` field ignores it.

This is a close cousin of the "check that cannot fail" hazard, with one
difference worth holding: there the check was RUN and could only return one
answer; here a field is READ and means something narrower than it appears.
Both end the same way — a confident claim resting on evidence that could not
have contradicted it.

### The same trap wears a second field name: `status` is not a scheduling signal

**The section above was originally written about `Updated:` alone, and that
framing was too narrow — proven the same day, by its own author, minutes after
landing it.** Having switched off `Updated:` and onto comment counts, the same
session then read a work item's **`status`** as evidence about whether anyone
was working, and recorded that four routed items were "not scheduled". One of
them, a P1 reading `BACKLOG`, had a **dedicated plan opened that very
day** in the owning repo — a published branch, a committed research note naming
that item as its anchor, and a live session on it.

**In this fleet the ledger row is the LAST thing to move, not the first.** Work
is planned in threads and branches, measured, and often half-done before any
row changes. So a row's status tells you what the record says about itself, and
nothing about whether a person or a factory run is on it right now.

**Check the world, not the row:** branches in the owning repo (including plan
branches), plan directories on its master, open PRs, running sessions, and the
state of the code the item describes.

**And weigh a negative correctly.** A search across another repo's planning
surface that finds nothing is *not* a negative result — the plan above
would have been missed entirely but for a coincidentally-noticed session name.
Say "I found no evidence of in-flight work", never "it is not scheduled". The
two sound alike and only the first is supportable from outside the owning repo.

**Why this generalization is the durable form.** Both instances are one error:
reading a field that describes a RECORD as though it described the WORLD. The
narrow rule did not prevent the second instance even in the mind that had just
written it, which is the strongest available evidence that the general rule is
the one worth carrying.

### And a THIRD field name, which is not a field at all: a FILE's history is not a FEATURE's history

Measured 2026-08-21, and it earns its place here because it defeated a reader who
had just re-read the two rules above and was actively applying them.

The question was whether a long-running `overseerd` predated a fix. `git log
--diff-filter=A -- <path>` showed the module carrying the behaviour was **created
hours after the daemon started**, which looks like proof. It was not. `git log -S
<symbol>` over the same tree showed the function had existed for **three weeks**;
the recent commit was a soft-band **split** that moved it into a file of its own
without changing a line of it.

**A refactor moves code without changing behaviour, so file history is the wrong
instrument for behaviour age.** This repo splits modules constantly — the LLOC
soft band makes that a routine, encouraged operation — so the wrong instrument is
wrong *often* here, not rarely.

    git log -S '<symbol>' --all -- <dir>     # when did this BEHAVIOUR appear
    git log --diff-filter=A -- <path>        # when did this PATH appear

**The expensive part is that the wrong instrument AGREED.** The conclusion being
tested — that the daemon was stale — happened to be TRUE, for an entirely
different reason. So the bad measurement produced a correct answer and a false
account of why, which is strictly worse than being wrong: nothing about the
result invites a second look. It was caught only because the live status file
plainly showed the supposedly-absent behaviour working.

Same family as the two rules above, one level down: there the hazard was reading a
RECORD's field as the WORLD's state; here it is reading a PATH's age as a
BEHAVIOUR's age. When a claim rests on "this did not exist yet", name which
instrument established that, and prefer the one keyed on the thing itself.

### And a FOURTH: a search result is not evidence about the PAST — date the information before you retract

Measured 2026-08-21. This one closes the family, because its victim is the very
habit the three rules above are meant to instil: checking yourself.

A completeness review found that a plan had deferred a concern to an owner that
turned out to be CLOSED, so the concern had no owner. Hours later, a broader
search found a live, well-groomed epic owning exactly that concern, with six P1
children. The obvious reading — the reviewer searched badly and the owner was
there all along — was about to be written up as a correction.

**It was wrong.** The owning plan's directory landed at 23:14:44Z and its scope
event was stamped 22:43. The review ran at 15:00Z. The owner did not exist then;
it was created roughly seven and a half hours later, plausibly *because* of the
finding.

**Both readings look identical today, and only a timestamp separates them.** A
present-tense query answers "what is true now" and is silent about when it became
true — so using it to audit a past claim reads the record's current state as the
world's history, exactly as the three rules above warn.

**An unnecessary retraction is not free.** It puts a false admission of error into
the permanent record, and it undermines a sound finding — here, one that had
already caused a P1 to be filed and may have prompted the cure. Over-correction
looks like diligence and costs the same as being wrong.

So before retracting on new information, ask **when the new information became
true**, and prefer the instrument that carries a date: the commit that added the
file, the stamped scope event, the run's `createdAt`. If the new evidence
post-dates the claim, you have an UPDATE — "correct when written, since cured" —
not a correction. Say so in those words; the two are different facts and the
record needs the difference.

### A FIFTH, AND THE FIELD IS ONE THE SESSION WROTE ITSELF: a timestamp a session WROTE is not a time that was MEASURED

Measured 2026-08-21, twice in one hour, by two seats independently — which is the
evidence that it is a method defect rather than carelessness.

**A session that never calls the clock estimates it, and the estimate runs ahead.**
One seat labelled a peer message `16:48Z` from its own sense of elapsed time; the
reading under that label had been taken meaningfully earlier, and it reported a PR
as open that had merged at `16:38:35Z`. The other seat published a
`plan-handoff-entry` declaring `timestamp: 17:10:00Z` while the ledger stored the
comment at **16:47** — a self-declared time twenty-three minutes in its own future.
Neither had run `date -u` at any point in the session.

**The two are not equally expensive, and the difference is the point.** A
mislabelled message costs a re-read; the value under it was never wrong. A
fabricated timestamp inside a handoff entry corrupts the **ordering key**: entries
in this fleet declare that they supersede the one below, and a resuming session
reads the newest. So the second one does not mislabel a reading, it reorders the
record a resume depends on.

**THE RULE: STAMP THE READ, NOT THE MESSAGE.** Bracket the call and quote what it
returns beside the value. Never estimate, never carry a stamp forward from earlier
in a session, and never let composition time stand in for measurement time.

    date -u +%Y-%m-%dT%H:%M:%SZ    # before the read, and again beside the value

**The independent check, when a declared stamp looks wrong:** the ledger records
its own storage time for every comment. A declared `timestamp:` that disagrees with
the stored time is settled by the stored one, and the disagreement is worth naming
in an appended correction rather than left for a reader to trip over.

Same family as the four rules above, and closest to the first: `Updated:` is not
activity, a PATH's age is not a BEHAVIOUR's age, and a timestamp a session WROTE is
not a time that was MEASURED. In each, a field that describes the RECORD gets read
as though it described the WORLD — here the record is the session's own prose, which
is why nothing external contradicts it. It also pairs directly with the rule
immediately above: that one says to date the information before retracting, and this
one is about the dates themselves being trustworthy.

Deliberately no mechanical enforcement is proposed here: a check that parses declared
stamps out of handoff entries and diffs them against storage times is a real idea and
a SEPARATE proposal, and folding it in would turn a guidance fix into a gate.

### A SIXTH, AND IT IS THE ABSENCE OF A FIELD RATHER THAN ITS CONTENT: a silent log is not a silent subsystem

Measured 2026-08-22 during the `overseer-6s3pk6` cutover, and recorded because the
error was committed by a session that had spent the day applying the five rules
above.

**The shape.** A daemon was moved to run from an isolated runtime prefix. Asked
whether its release-currency check was firing, the session read the log it had always
read, found **no currency events at all**, and wrote that a clean adoption "is silent
by design" — offering a plausible mechanism for the silence and closing the question.

Both halves were wrong. The check was firing on **every** tick, and the log had simply
**stopped being written**: moving the package relocated the log to a path derived from
the daemon's own module location, so the file being read had been dead for ninety
minutes. The live log was full of the very events reported as absent.

**Why this is the worst member of the family.** The five rules above are about reading
a field that describes the RECORD as though it described the WORLD. Here there was no
field to misread — there was *nothing*, and nothing is the most accommodating evidence
there is. A present value can contradict your expectation; an absent one never does.
Worse, the session did not merely note the gap, it **explained** it, and the
explanation was reasonable enough to survive its own review. An inference that makes a
dead instrument look like a finding is harder to catch than a wrong number.

**The rule: before concluding a subsystem is quiet, prove its instrument is live.**
The same applies to an empty query result, a metric with no datapoints, and a status
file nobody is updating.

**But do NOT reach for the obvious check, because it is wrong here.** Comparing the
log's mtime against the writer's tick rate looks like the one-command answer and is a
trap: this is an **event-history** log — `daemon.py`'s own docstring says so — and it
advances on EVENTS, not on ticks. Measured 2026-08-23T00:10Z on a completely healthy
daemon: the status snapshot read `tick_generation` 36, written 10 seconds earlier,
while the log's mtime was **17 minutes** old. An mtime rule reports that daemon as
dead, and it does so precisely when the fleet is quiet — which is when nobody is
watching. (A first draft of this very entry prescribed that check. It was caught in
review before it landed.)

**Two checks that do work.** For liveness and cadence, use a genuinely per-tick
heartbeat — here the status snapshot's `tick_generation` and `written_at`, which
advance every tick regardless of whether anything is worth logging. For "is this the
file the writer is actually writing to", identify the writer and enumerate what it
holds open, rather than trusting the path you happen to know:

    ls -l /proc/<pid>/fd            # every open descriptor, not just the one you expect

Note the second is stronger than checking `fd 2` alone: a process can redirect its own
stderr to a path it computes at startup, so the descriptor you set on the command line
is not necessarily the file it logs to. That was exactly the case here.

**And normalize the clocks, or the check reports the opposite of the truth.** This host
runs CEST (+0200), so `stat` and `find -printf` render local time while the ledger, the
status file and `date -u` are all `Z`. A reviewer checking this same defect compared
`find -printf` output against a UTC stamp and was two hours out **in the direction that
would have confirmed a fixed defect as still broken**. This file already records that
trap for `ps -o lstart`; it applies to `stat` and `find` identically. Put both sides in
UTC or the comparison is a guess.

**And distrust agreement most.** The session's own account of why it skipped the check:
*the silence already agreed with a story I liked.* That is the whole mechanism. A
measurement that confirms what you expect gets spent, not audited — so the cheap
verification is skipped precisely when the conclusion is about to be written down. When
an absence supports your hypothesis, that is the moment to check the instrument, not
the moment to stop.
