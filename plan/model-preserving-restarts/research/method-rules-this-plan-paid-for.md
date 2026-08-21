# Method rules this plan paid for

Consolidated 2026-08-21. Each rule below was learned by being bitten during
`model-preserving-restarts`, and until now they lived scattered across roughly
two dozen ledger handoff entries on epic `overseer-bc55wx` — a timeline long
enough that reconstructing them costs reading the whole thing in order. They
are the transferable part of this work, so they belong in the research store
where a fresh reader finds them in one place.

**This note is method only.** It records no carrier state; status is composed
from the ledger. Where a rule names an incident, the incident is on the epic's
timeline and on the carrier.

## The rules

### 1. Green tests over a FABRICATED shape are not evidence

**Cost: a P1 shipped to master under a full green suite.** The wrapper-capture
path was unreachable for both canonical local-llm wrappers, because each ends
in `exec` — which REPLACES the wrapper process, so no wrapper survives anywhere
in the parent chain the capture walks. The suite was green because the only
wrapper-capture test hand-fabricated a parent whose `argv[0]` IS the wrapper
path: a process shape neither shipped wrapper can produce.

Ask what shape the REAL producer emits, and build the fixture from that. A
fixture you authored to make the code pass is a restatement of the code.

### 2. A string assertion is not an execution

**Cost: every wrapper-arm relaunch was fatal — exit 127, pane destroyed.** The
env delta rendered the model assignment BEFORE the unset flags, and GNU `env`
accepts options only ahead of the first assignment, so the relaunch tried to
execute a program named after a flag. It shipped at 100% coverage because the
beside-tests assert the rendered command AS A STRING and nothing ever runs it.

Worse than losing a model: a tmux pane whose command exits is CLOSED, so a
single-pane tracked session is destroyed. Observed directly — the first attempt
removed the exercise session outright.

If a code path's product is a command, one test must EXECUTE it.

### 3. Verify a daemon's currency by what it IMPORTED, not by what its tree HOLDS

This plan first recorded the rule as "verify by artifact, not by clock": read
`/proc/PID/cwd`, confirm that tree holds the package, assert the feature is in
it. **That is necessary and INSUFFICIENT, and it produced a false positive on
this very plan** while checking whether the acting daemon carried the fix that
had just merged:

    02:41:58   checkout fast-forwarded to f7417d3
    02:42:24   daemon STARTED, importing f7417d3      <- lacks the new call
    02:59:23   checkout fast-forwarded to a37d6cc     <- the fix arrives, 17 min late

The daemon's cwd tree contained the feature to anyone who grepped it, and the
running process had never seen it. **The artifact is a MUTABLE WORKING TREE and
it moves under a running process.** The artifact test proves currency only when
PAIRED WITH REFLOG ORDERING — the fast-forward introducing the feature must
PRECEDE the process start time.

`overseerd` imports `overseer.*` once at startup and never hot-reloads, so this
is not a corner case; it is the normal state of any long-lived daemon in a repo
that moves several times an hour.

### 4. A snapshot consumed as though it were live — the general form of rules 3, and of two others

Three instances on this plan, and they are one error wearing three faces:

- **A ledger field describes the RECORD, not the WORLD.** `Updated:` does not
  move when a comment is added — proven with a self-performed write, not merely
  observed — and comments are where this fleet records nearly all its evidence.
  Separately, `status` is not a scheduling signal: a P1 reading `BACKLOG` had a
  dedicated plan open that same day.
- **A seat's injected guidance describes the file AS OF SESSION START.** Two
  seats disagreed about a hazard and both were reading the same path; the
  divergence was invisible from inside either. Grep the file on disk before
  citing a hazard from memory of it — not because your copy is probably stale,
  but because you cannot know either way.
- **A daemon's working tree describes the checkout as of NOW**, per rule 3.

In all three the failure is identical: a snapshot read as live, with nothing in
the reading to reveal the difference.

### 5. Silence is not a signal unless you have confirmed the instrument can return BOTH answers

The statusline truncates from the END, and the parser's usual anchor — the
context segment — is among the first things truncation removes, while the model
name is FIRST and always survives. So the value is on screen when the anchor is
already gone.

The availability threshold is not pane width; it is the rendered length of the
segments BEFORE the anchor relative to width. A NARROW pane in a short path
keeps the signal while a WIDE pane in a deeply nested path loses it — and paths
are longest in WORKTREES, which is where nearly all real work happens here. So
the signal goes quiet exactly where it would most often be consulted.

Never design a check whose silence means "nothing wrong" without first proving
it can speak.

### 6. ABSENT and DISAGREEING are different readings, and only one may act

Corollary of rule 5, stated separately because it is the one an implementer
skips. 5 of 37 live panes resolved no model at all, and per the sweep above
that is routine rather than exceptional. A veto that treats absence as a
negative reading fires constantly and wrongly. Absent must not skip a restart;
only a resolved-and-disagreeing read may.

The discriminating test for such a parser is a REJECT assertion — feed it
ordinary prose that merely mentions the anchor token and assert it returns
nothing. The measured defect was a false ACCEPT: the shipped parser returned a
line of transcript conversation. A conventional parser test would have passed
without catching it.

### 7. Quoting the evidence can poison the report

A good bug report quotes the failing line verbatim. For the template-delimiter
defect the failing line IS the poison: the dispatcher assembles ledger COMMENTS
into the run goal, so a comment quoting the delimiter makes that work-item
permanently undispatchable. Comments are APPEND-ONLY — there is no edit and no
delete — so the record cannot be repaired, only superseded.

It fired on prose ABOUT the hazard, twice, the second time minutes after the
author had merged fleet guidance warning of it. **Warnings do not fix this.**
Describe the byte sequence in words, and check the record AS STORED — before
filing and again after — with a mechanical grep rather than care.

### 8. Absence from the local run table discriminates NOTHING when the factory is remote

The fleet rule "an ACTIVE status is never evidence of a run; the run table is"
is LOCAL, and it silently stops holding once an item dispatches to a remote
factory. Read literally it then says "absent from the run table implies eviction
implies re-dispatch" — which is how you re-run merged work against your own
still-running sibling.

For a remote dispatch the discriminator is **the forge query over ALL states**,
not a ref probe and not the local process view: a merged PR's branch is
routinely auto-deleted, so the ref reads empty precisely when the work landed.

This plan hit the succeeded-untransitioned shape FOUR times. Each time the
remedy was to close with verified evidence, never to re-dispatch.

### 9. Harness-symmetry analysis finds what reachability counting cannot

A mechanical sweep for "public functions defined but never referenced by another
production module" produced 128 hits; the tighter filter still produced 74. It
is a false-positive generator for this codebase, because a function called only
within its own module reads as unwired.

More to the point, **it would not have found the defect that was actually
there.** The mismatch veto was wired to one of two harnesses; the function was
imported and called, and what was missing was a call on one BRANCH. Walking each
stage of a pipeline and asking whether it treats both harnesses alike found it.
Prefer that when hunting for more of the same class.

### 10. A fence names the leg you did not check — so go check it

An entry on this plan correctly fenced itself: it stated in terms that a
consequence had not been observed and was inherited from a neighbouring case
rather than reproduced. **The fence named exactly the leg that turned out to be
false**, and the entry had to be retracted after circulating.

What was missing was the cheap follow-up the fence implied — reading the code
path to see whether the consequence COULD occur. A fence is only worth what you
do about it; an unactioned fence reads to everyone else as diligence.

### 11. An adversarial review reads the files your diff did NOT touch

A spec modification was locally coherent and globally contradictory: two of the
four blockers returned against it were in files the diff never opened, where a
behavior-form twin of the narrowed clause still asserted the opposite. A
self-review would not have found them, because the author was reasoning about
the paragraph just written.

### 12. Commissioning a review in order to receive a wanted answer is not review

A BLOCKERS verdict mechanically removes delegated ratification authority, and no
redraft restores it. Iterating a proposal until the gate goes green is precisely
the failure the gate exists to prevent. The same applies to the archive gate's
completeness review: commission it only when the work is actually disposed, or a
correct INCOMPLETE is the only possible answer.

### 13. A tool failure and a reasoned refusal are indistinguishable in an aggregate outcome

A consensus panel on this plan's last open question returned `escalate`, reason
`insufficient_information`. Of the three legs producing that outcome, **two were
tool failures rather than reasoning** — one reviewer's response did not parse,
and the audit journal append was skipped — and the aggregate additionally lost
the reviewer identity for two of three reviewers.

Both reviewers who actually spoke agreed on the substance. The outcome recorded
disagreement. When an aggregate reports that a panel could not decide, check
whether it is reporting that its INSTRUMENTS could not report.

### 14. Live exercise catches the class the suite structurally cannot

Both P1s on this plan reached master under a green suite and were found only by
driving real panes. Rules 1 and 2 are the two mechanisms. The exercise is not
for the interlock and not for timing — those are covered by assertions — it
exists for the two questions assertions beg: does the rendered command actually
EXECUTE, and does the fresh process's `/proc` show what was RECORDED.

Use a scratch HOME and throwaway tracks. The isolation recipe redirects the
watch-set, mapping store and stamp sidecar in one move, so the cardinal rule is
protected STRUCTURALLY rather than by care. This plan learned that the hard way
by adopting a throwaway repo into the REAL watch-set and putting exercise rows
in front of every operator for half an hour.
