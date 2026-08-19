# Mechanism — what the grooming operation does, and every pattern it must carry

**Ledger anchor:** epic `overseer-adclcd`. All mutable plan state — status, next
action, handoff entries — lives on that epic and its child items; this note is
write-once research and is never authoritative about what remains.

Everything here was measured on 2026-08-19 during a live, autonomous drain of this
repo. Re-measure before trusting any path or count.

## Why this thread exists

On 2026-08-19 a single session took this repo from 55 un-planned work items and 2
stale proposed changes to: every non-done item assigned to a live plan, six plan
threads each with a working tmux session, two proposals ratified into the spec,
and 60 acceptance criteria authored. It worked. It also produced a measured
catalogue of the ways it goes wrong — several of which cost real damage before
they were caught, including a tenant-wide dispatch outage.

None of that is written down as an operation. It lived in one session's judgement
and in a chat transcript. The next repo that needs draining starts from zero and
re-derives it, including the traps.

This thread ships it as `/livespec-overseer:grooming` — a peer of `foreman`,
usable by any repo that installs this plugin.

## What the operation IS, and what it is NOT

`foreman` is the per-repository bounded operator LOOP: it runs forever on a tick
and takes at most one action per tick.

`grooming` is a per-repository bounded DRAIN PASS: it runs once, on demand,
against a repo whose proposed changes and work items have accumulated, and leaves
every non-done item assigned to a live plan thread with a working session. Then it
exits. It is the thing you run when a backlog has silted up; the foreman is the
thing that keeps it moving afterwards.

It does NOT implement work. It routes work and then hands the driving to the
foreman and the factory.

## Shape — four surfaces, mirroring the three skills already shipped here

Measured from the shipped `foreman` / `overseer` / `supervise-plan` trio:

- `.claude-plugin/prose/grooming.md` — the harness-neutral contract. ALL behavior
  lives here.
- `.claude-plugin/skills/grooming/SKILL.md` — thin Claude binding.
- `.claude-plugin/.codex-plugin/skills/grooming/SKILL.md` — thin Codex binding.
  Codex does NOT substitute a plugin-root token into SKILL prose, so this binding
  resolves the root explicitly.
- `.claude-plugin/.pi-plugin/skills/livespec-overseer-grooming/SKILL.md` — thin pi
  binding, named with the `livespec-overseer-` prefix as its siblings are.

Both `plugin.json` manifests must gain the operation in their `description`, in
LOCKSTEP — `tests/test_plugin_manifest_lockstep.py` asserts `name`, `version` and
`description` match across the Claude manifest and the nested Codex one, and that
codex `skills` stays `./.codex-plugin/skills/`.

## The plan budget — CONFIGURABLE AND AUTO-SCALED

The ratifying pass ran under a hand-given instruction: "no more than 3-5 plans
total, lower the better." That was the right answer for THIS repo at THAT size,
and it is exactly the kind of number that must not be hard-coded into an operation
other repos run.

**Resolution order:**

1. An explicit `plan_budget` under a `grooming` key in the governed repo's
   `.livespec.jsonc` pins the ceiling. An integer.
2. Absent — the default, and what an unreadable or malformed value falls back to —
   means AUTO, derived from the repo's own drainable population.

**The auto derivation.** Let D be the DRAINABLE POPULATION at the moment the pass
starts:

    D = (pending proposed changes under <spec_root>/proposed_changes/, excluding README)
      + (work items whose status is not closed and not done, excluding plan-anchor epics)

Then:

    budget = clamp( ceil(D / items_per_plan), min_plans, max_plans )

with defaults `items_per_plan = 12`, `min_plans = 2`, `max_plans = 8`, each
overridable under the same `grooming` key. The divisor is the load-bearing one: it
encodes "how many carriers can one plan thread hold before its worker cannot keep
the whole thread in context", and 12 is where this repo's threads landed when cut
by hand.

**Existing live plan threads count against the budget.** The pass may create at
most:

    new_thread_allowance = max(0, budget - live_thread_count)

Live threads are the non-archived directories under `plan/`, cross-checked against
plan-anchor epics carrying `plan_slug` metadata. Both sources, because they drift:
this repo has an epic that was a thread anchor for a directory that was never
created.

**The budget is a CEILING, not a target.** Fewer, larger, coherent buckets beat
more, thinner ones. The operation must prefer the smallest number of buckets that
keeps each thread's members genuinely about one subject, and must never pad to the
budget.

**Worked example, from the ratifying pass.** D was 55 unparented open items plus
2 pending proposed changes = 57. ceil(57/12) = 5, clamped to 5. Two threads were
already live, so the allowance was 3. The pass created exactly 3, hand-chosen. So
the auto derivation reproduces the hand-picked answer on the case it was derived
from. That is a necessary sanity check and NOT evidence it generalises — the
acceptance requires checking it against at least one other repo's real population
before the default is trusted.

**Overflow is reported, never auto-corrected.** After the pass, a plan worker may
legitimately split its own thread and push the repo over budget — that happened
here within hours, and the new thread was real, coherent work. The operation must
NOT fold such a thread back: it has merged filesystem artifacts, a live session
and possibly in-flight dispatches, so collapsing it is destructive and is a
maintainer decision. Report the overflow with the numbers and stop.

## The pipeline — six stages, in order

### 1. Measure

`bd list --all --json`. NOT bare `bd list`, which omits records and has already
caused a gate to false-fail every armed run. Compose the true open set, the
untriaged subset, the unparented subset, and the live plan threads. Resolve the
plan budget here.

### 2. Drain the spec lane

Run the `revise` operation over pending proposed changes, then file work items for
any implementation the newly ratified letter requires, via `capture-spec-drift` or
`capture-work-item`.

Two things measured the hard way:

- `revise` walks EVERY pending proposal. If some are unreviewed, this is a
  SELECTIVE pass — name the topics being consumed and leave the rest. A proposal
  raised minutes earlier by another agent must not be swept in.
- The history snapshot is NOT just a copy of the spec files. Each consumed
  proposal needs a paired revision record carrying the decision, rationale,
  resulting-files list and ratification-review block. Every version from v001 has
  them. A hand-cut snapshot omitted them and the gate did not notice: the
  pairing check walks one direction only (for every revision record, does its
  proposal exist), so a MISSING revision record is not a finding. Prefer the CLI
  over hand-assembly for exactly this reason.

### 3. Triage

Run the intake Definition-of-Ready checklist over every backlog item lacking the
triaged label, through the shared `intake_dor` primitive. Never re-derive the
gates.

**The rule that makes this pass useful rather than destructive:** when a gate needs
something the item is MISSING, fix the item first and then run the checklist.
Marking an item blocked because it lacks the acceptance criteria that grooming was
supposed to write is circular — it uses the absence of grooming as the reason not
to groom. In the ratifying pass this error parked 19 items before it was caught.

Conversely: a `blocked` verdict is a legitimate and useful outcome. Do not force
items onward. Items genuinely gated on a maintainer ruling, a fleet policy, a
ratification, or a sibling repo's decision belong blocked — but each must still
carry acceptance criteria stating what DONE looks like once the gate lifts, with
the specific gating decision and its decision-maker on the FIRST line.

### 4. Bucket

Group every unparented non-done item into plan threads, within the budget.

Create each thread through the plan operation's `create_thread`: exactly one
research note plus one ledger epic anchor, and nothing else. Then, BEFORE admitting
children, record a scope event naming the requirement carriers and the EXPLICIT
deferrals — what is deferred, why it is not in this thread, and where it will be
reconsidered. Then append an opening handoff naming exactly ONE next action, the
factory route, and a read-first chain.

Assign membership by PARENT-CHILD edge. Never by a dependency edge — that makes
the item permanently undispatchable.

A pre-existing epic that is not a plan anchor can be folded in as a sub-epic
rather than promoted to its own thread; that is how the budget is respected
without orphaning anything.

### 5. Start

Hand the missing sessions to the repo's foreman via its `plan_start` action,
revalidated through `foreman-act`. Do NOT start sessions by hand outside that path.

Session naming is not free-form: the worker tmux session is the BARE TOPIC, per
the ratified session-name derivation rule; repo-qualification applies only on a
genuine cross-repository collision.

### 6. Verify, then drain

Verify by content and source, never by proxy: read `tmux list-sessions` and the
daemon's own snapshot rows, not the foreman's report of them. Then confirm every
non-done item rolls up to a plan, every item carries acceptance criteria, and the
conformance invariants below hold.

## Ledger invariants the pass must leave TRUE

Each of these was violated during the ratifying pass, and each is mechanically
checkable. The operation asserts them at the end and reports any breach.

1. **Every non-done item rolls up to a plan epic.** Only plan anchors are
   unparented.
2. **Every open item carries acceptance criteria.** Read them through the MERGED
   projection, not one field — see the divergence trap below.
3. **Only lifecycle statuses exist.** The seven are backlog, ready,
   pending-approval, active, blocked, acceptance, closed. Anything else refuses
   every dispatch in the tenant.
4. **No item in a dispatchable state carries a template delimiter.**
5. **An item labelled for human-verified acceptance has a SPLIT acceptance**, and
   the converse. Both directions.
6. **Every cross-repo dependency edge resolves** against a real id in a repo the
   consuming manifest lists.
7. **An item's routing field names the repo its deliverable LANDS in**, not the
   repo the filer happened to be sitting in.

## Traps measured, each with the tell that identifies it

**A non-lifecycle status blocks the WHOLE TENANT.** The `--defer` flag writes bd's
native deferred status; the dispatcher's global pre-dispatch conformance sweep then
refuses every dispatch in the repo. Clearing the deferral is ALSO non-conforming —
it leaves the item at bd-native open — so the remedy passes back through the
blocking state. Hold an item out of the ready set with `backlog`, never `--defer`.
Tell: "pre-dispatch ledger checks failed; dispatch blocked", with no item named.

**A doubled-brace template delimiter anywhere in an item's text makes it
permanently undispatchable**, and the trap fires on prose ABOUT the trap, because
naming the hazard accurately means reproducing it. Describe delimiters in WORDS.
The delimiter reaches ledger COMMENTS too, where it is terminal — comments are
append-only, so the only remedy is a clean-text successor. Do NOT edit the
offending text out of an evidence-carrying item; hold it at backlog instead. And
note that a routine re-triage will promote such an item back into the ready set on
the merits of its content, because no gate looks for delimiters — so backlog is a
hold that will not hold, and the durable fix is a gate.

**Acceptance criteria can diverge between two fields.** The creation-time copy
lives in metadata; later edits land in the native top-level field; the plugin reads
a merged view where the top-level wins, while the human-facing show command renders
the metadata one. Consequence: the accepter and the implementer can be working to
different bars. A sweep reading only one field is wrong in BOTH directions — it
reports items as missing acceptance that in fact have it, and reports agreement
where there is none. Read the merged view.

**A cross-repo edge naming a nonexistent id fails CLOSED forever**, and it presents
identically to a mis-filed membership edge. Before unsetting one, resolve the id
against both tenants' full id sets. If the dependency is genuine and only the
pointer is wrong, REPOINT — unsetting destroys the record of a real prerequisite
and leaves the item looking dispatchable. Note also that an unresolvable sibling
failing closed is BY DESIGN and load-bearing; it must not be "fixed" by making the
unknown case permissive.

**Auto-merge races the author.** Push every commit intended to ship BEFORE opening
the PR, and treat the branch as frozen once the PR is open. Discovering follow-up
work after opening is the common way this bites; put it on a new branch.

**The worktree recipe is dead in this repo and fails silently.** Use the documented
rescue: raw worktree add, then install the worktree pack inside it, then discard
the config key that command writes. Also: the workspace path is the SAME directory
as the primary checkout, so a worktree created there lands inside the repo.

**A rate-limit guard hook denies forge commands on ordinary English words.** Keep
loop-ish words out of PR titles; pass bodies via a file.

## Patterns that worked, and are worth carrying

**Delegate the independent long legs; keep the bucketing.** The spec drain and the
triage sweep are self-contained and were run as subagents in parallel while the
driving session did the plan cutting. Both returned better work than the driver
would have produced serially.

**Verify a delegated claim before acting on it.** Every load-bearing claim a
subagent or peer returned was re-measured. Three of them were wrong, and one of
those had already produced a closed P1 before the correction arrived.

**State a control's SCOPE before its claim, and demand that scope when receiving
one.** The single most expensive error of the pass was accepting a control that
exercised the working code path and reported it as proof about the failing one.
Neither more care nor more diligence would have caught it — the fix is procedural:
say which leg the evidence exercises and which it does not.

**Never type into another session's pane.** Route valve answers and decisions
through the foreman. A keystroke sent to answer a picker landed on a different
step, submitted a maintainer's real ruling as though it were an accident, and
caused a worker to start unauthorized work. Before overriding an answer already
recorded in a pane, establish WHO entered it — "I touched this pane recently" is
not evidence that you caused what you see in it.

**Do not manufacture a subject for a live mutation.** When a finding needs a real
stuck record to prove, wait for one. Operating on a plausibly-live record to
satisfy curiosity risks destroying real work, and the damage would look exactly
like the defect under investigation.

**Merge duplicates, never delete them.** When two items describe one defect, append
the loser's unique measurements to the winner FIRST, then close the loser as a
duplicate citing it. Several of the pass's best evidence came from items that were
closed.

**A handoff must let a fresh session continue with no chat history:** exactly one
next action, every cited path committed, the factory route named, and no parallel
checklist — status is composed from the ledger.

## Making the grooming session ITSELF supervised — a first-class leg, not a follow-up

**Measured 2026-08-19, and it is the sharpest gap this thread closes:** the session
that produced everything above ran in tmux session `grooming` for hours, and was
NEVER TRACKED. The daemon's snapshot carried seven rows for this repo and not one
of them was it. It received no wrap-up at any threshold, it had no restart
interlock, and it held the only copy of a great deal of un-written-down judgement.
Every finding in this note was one exhausted context window away from being lost.

That is not peculiar to this run. The daemon adopts exactly three shapes today —
plan-track workers (bare `<topic>`), supervisors (`<topic>-supervisor`), and the
foreman (`<repo-name>-foreman`). A grooming pass is none of them, so nothing
adopts it, and the gap is silent: an untracked session looks identical to no
session at all.

**The reserved entity topic: `<repo-name>-grooming`**, mirroring the foreman seat's
`<repo-name>-foreman` shape.

In `overseer/_signals_topics.py`: add a grooming suffix constant, add it to
`_RESERVED_WORKER_SUFFIXES` so a plan topic can never collide with it, and add an
`is_grooming_topic` predicate beside `is_foreman_topic`. Like the foreman, and
UNLIKE a plan track, a grooming entity has NO supervised worker: `supervisor_topic`
must refuse it exactly as it refuses a foreman topic today, and
`topic_supervised_worker` must return None for it rather than a mis-stripped
string. Both are already-tested behaviors for the foreman suffix and the grooming
suffix must join them rather than be special-cased.

**The wrap-up.** `overseer/_supervisor_prompts.py` ships three builders today —
`wrapup_message`, `foreman_wrapup_message`, `supervisor_wrapup_message`. Add a
fourth for grooming and route it in `_supervisor_restart.py`, whose branch
currently reads foreman, then supervisor, then plain worker.

**The wrap-up must ask for something DIFFERENT, and getting this wrong wastes the
restart.** A worker's wrap-up asks it to land or park in-flight code. A grooming
pass has no in-flight edit — its writes are individually atomic ledger mutations.
Its wrap-up should ask it to: complete the single ledger write it is mid-way
through, record onto the relevant plan epic or item any judgement it has formed but
not yet written down, and then declare ready. It must NOT ask it to "finish the
drain", because the drain resumes on its own.

**Restart is CHEAPER AND SAFER here than for any other tracked shape, and this is
the design's strongest property.** The pipeline's first stage is MEASURE: it
re-derives the open set, the untriaged subset, the unparented subset, the live
threads and the plan budget from the ledger and the filesystem on every entry. A
restarted grooming session therefore needs to remember NOTHING. Unlike a worker
restarted mid-implementation there is no in-flight edit to lose and no resume
payload to reconstruct — the relaunch prompt is simply "re-enter the grooming
operation for this repository". Restart is idempotent by construction, and the
operation must be written to KEEP it so: every stage re-derives its inputs rather
than carrying state forward in the session.

**Adoption must not depend on the foreman noticing.** A grooming pass can be
started directly by a maintainer, so the operation registers its own track on entry
(or ships a documented registration step it performs first). A session that has to
wait for a foreman tick to be adopted is unsupervised for exactly the window in
which it is doing its heaviest work.

**The cardinal rule is untouched.** A grooming session is restarted only after it
writes its own `ready` declaration, exactly like every other tracked session. This
leg changes WHAT is adopted and WHAT it is told at threshold — never WHEN a
restart is authorized.

**Two sibling surfaces need the same entity.** `.claude-plugin/prose/overseer.md`
(the interactive operator contract) must render and describe the grooming entity
alongside foreman and supervisor rows, and `overseer/marker-protocol.md` must
document the new reserved topic and its declaration obligation, or the protocol
document goes stale the day this ships.

## Deliberate non-goals

This operation does not implement work items, does not dispatch them, does not
drive approval or acceptance valves, and does not archive plan threads. It does not
restart or force any tracked session — the cardinal rule is untouched. It creates
plan threads and hands driving to the foreman.
