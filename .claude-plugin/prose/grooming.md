---
name: grooming
description: Run one bounded repo-wide drain pass for accumulated livespec work.
---

# grooming - bounded repository drain pass

You are running the per-repository grooming operation for this checkout. This is
not the foreman loop. Foreman is the bounded operator loop: it runs on a recurring
tick and may propose one bounded action per tick. Grooming is a bounded drain pass:
it runs once on demand against a repo whose proposed changes and work items have
accumulated, routes that work into live plan threads, hands the driving to the
foreman and the factory, reports what it queued, and exits.

This operation takes no work-item id. Use it for an accumulated backlog with
unparented items, stale proposed changes, missing acceptance criteria, and missing
plan sessions. Do not confuse it with the shipped single-item `groom` operation in
the livespec-orchestrator-beads-fabro plugin. That operation takes one work-item id
and drafts a maintainer-approved decomposition for a single oversized or
non-converging item. If this drain pass finds one item too large for any plan
thread to hold, route that item to the single-item operation instead of cutting it
inline.

## Boundary

You route work. You do not implement work items. You do not dispatch them. You do
not drive approval valves, acceptance valves, rejection valves, resolved-blocked
valves, policy valves, capacity valves, or move valves. You do not archive plan
threads. You do not restart or force any tracked session. The cardinal ready-file
restart rule remains untouched.

The pass creates or updates ledger and plan-routing state only where that is the
operation's own output: plan buckets, parent-child membership, acceptance criteria,
triage state, scope events, opening handoffs, and foreman proposals for missing
sessions. When work must be implemented, dispatched, approved, accepted, archived,
or restarted, the pass records the route and hands it to the component that owns
that lifecycle.

The pass converges asynchronously. Its own work completes synchronously, but it can
leave two queues draining on clocks it does not own:

- Session starts wait behind the foreman's one-action hourly tick.
- Implementation dispatches wait behind the shared provider credential pool and
  the factory's run queue.

Report both queues explicitly. A clean drain report that hides either queue
misstates completion.

## Surfaces This Contract Governs

All behavior lives in this harness-neutral prose. Thin bindings may expose the
operation to particular runtimes, but they must only resolve the plugin root, read
this file completely, and execute it. They do not carry independent behavior.

The operation's full thread has six carriers, all of which this contract must keep
coherent:

1. The shared prose contract, this file.
2. The six-stage drain pipeline and plan-budget rule.
3. The thin operation bindings and manifest descriptions that expose the contract.
4. The supervised grooming entity, including adoption, wrap-up, and restart text.
5. The operator and marker-protocol documentation that must describe that entity.
6. The tests and release gates that prove the surfaces stay wired and clean.

This file is carrier 1 and the spine for carriers 2 through 6. Later carriers must
reference it rather than restating its behavior.

## Plan Budget

Resolve the budget during stage 1, before bucket decisions.

Resolution order:

1. An explicit integer `plan_budget` under the repo's `grooming` configuration key
   pins the ceiling.
2. If that key is absent, unreadable, malformed, or not an integer, use AUTO.

AUTO is derived from the drainable population at pass start:

```text
drainable population =
  pending proposed changes under the spec proposed-changes directory, excluding README
  plus non-closed, non-done work items, excluding plan-anchor epics

budget = clamp(ceil(drainable population / items per plan), minimum plans, maximum plans)
```

Default `items per plan` is 12, default minimum is 2, and default maximum is 8.
Each value may be overridden under the same configuration key. Existing live plan
threads count against the budget, so the pass may create at most:

```text
new thread allowance = max(0, budget - live thread count)
```

Live threads are the non-archived directories under `plan/`, cross-checked against
plan-anchor epics carrying plan-slug metadata. Use both sources because they drift.

The budget is a ceiling, not a target. Prefer the smallest number of coherent
buckets that keeps each thread about one subject. Do not pad to the budget. If a
pre-existing or later split pushes the repo over budget, report the overflow with
the numbers. Do not fold a real thread back into another one; merged plan files,
live sessions, and in-flight runs make that a maintainer decision.

## Six Stages

### 1. Measure

Measure the whole tenant, not the default listing window. Use the merged
work-item projection exposed by the orchestrator plugin named in the governed
repo's `.livespec.jsonc` `implementation.plugin` key: the `list-work-items
--json` operation. Runtime neutrality comes from resolving the governed repo's
plugin and invoking that operation by capability, not from hard-coding a
substrate command. Use an all-records, all-statuses, machine-readable ledger
view, including gate records when the local ledger supports them. A default
ledger listing is not enough: it omits records and has already produced false
clean readings.

Compose and record:

- the true open set;
- the untriaged subset;
- the unparented subset;
- pending proposed changes;
- live plan threads from filesystem and plan-anchor metadata;
- the resolved plan budget, its governing path, and new-thread allowance;
- the exact population scanned for each conformance claim.

If a result is clean, state its scope beside the claim. A clean result with no
scanned population is not evidence.

The automatic plan budget is the drainable population divided into plan-sized
buckets, then clamped by the configured minimum and maximum. With the shipped
defaults (`items_per_plan = 12`, `min_plans = 2`, `max_plans = 20`), populations
from 13 through 240 are population-derived; below 13 the minimum decides, and
above 240 the maximum decides. A config-pinned `plan_budget` overrides the
automatic value. Whenever you report a budget, name the governing path with the
number: `explicit`, `population-derived`, `min-clamped`, or `max-clamped`.

Register the grooming seat at entry, or use the shipped registration wrapper when
one exists. The reserved entity topic is the repo slug plus the grooming suffix.
It has no supervised worker. Its wrap-up asks the session to finish the single
ledger write in progress, write down any formed judgement on the relevant plan
epic or item, then declare ready. It must not ask the session to finish the whole
drain, because stage 1 re-measures everything after restart and the pass is
idempotent by design.

### 2. Drain The Spec Lane

Run the repo's revise operation over the intended pending proposed changes, then
file any implementation work required by the newly ratified letter through the
repo's ordinary capture path.

This can be selective. The revise operation walks every pending proposal it is
given, so name the proposal topics being consumed and leave unrelated or freshly
raised proposals alone.

Do not hand-assemble the history snapshot unless no reviewed path exists. A
consumed proposal needs the paired revision record: decision, rationale, resulting
files, and ratification-review block. A snapshot containing only changed spec
files can pass a one-way pairing check while missing the actual decision record.

### 3. Triage

Run the shared intake Definition-of-Ready checklist over every backlog item lacking
the triaged label. Do not re-derive the gates.

When a gate needs information the item is missing, fix the item first and then run
the checklist. Do not mark an item blocked because it lacks the acceptance criteria
this operation exists to write. That is circular.

A blocked verdict is valid when the item is genuinely waiting on a maintainer
ruling, fleet policy, ratification, or sibling repo decision. Such an item still
needs acceptance criteria. The first line must name the gating decision and the
decision-maker, so the item is implementable when the gate lifts.

When filing new items, treat create and status-set as a single operation. The
ordinary create path may use the substrate's native intake status, which is outside
the lifecycle set and can poison the tenant. Immediately set a lifecycle status,
then re-read the row. If you repair another thread's non-conforming row to unblock
the tenant, record the correction on the item and relay the pattern to the owning
thread; do not silently repair unrelated fields.

### 4. Bucket

Group every unparented non-done item into coherent plan threads within the budget.

Create each new thread through the plan operation's create-thread path: one
research note plus one ledger epic anchor, and nothing else. Before admitting
children, record a scope event naming requirement carriers and explicit deferrals:
what is deferred, why it is not in this thread, and where it will be reconsidered.
Then append an opening handoff with exactly one next action, the factory route, and
a read-first chain.

Assign membership by parent-child edge. Never use a dependency edge for thread
membership. A dependency edge participates in dispatch eligibility and can make
the child permanently undispatchable.

A pre-existing epic that is not a plan anchor may be folded in as a sub-epic rather
than promoted to its own thread. That is how the budget is respected without
orphaning real work.

Keep item comments rare. Ledger comments are assembled verbatim into future
dispatch briefs and are append-only. Put durable per-item facts in editable fields.
Put pass-level narrative on the plan epic. Comment on a dispatched item only when
the implementing agent must read that comment and the permanent brief growth is
worth it.

### 5. Start

Hand missing sessions to the repo's foreman through its `plan_start` action,
revalidated through `foreman-act`. Do not start sessions by hand outside that path.

Register the seat before proposing. A plan-start proposal cannot start a topic the
daemon has never seen, because revalidation needs an existing snapshot row. The
working order is: register the topic with its repo, topic, and epic; then submit
the plan-start proposal. Register the epic from birth. An epic-null seat can later
produce a respawn refusal; birth registration avoids the repair.

Compose and submit every foreman-act proposal inside one daemon generation. Gather
and act are one operation, not two. If you read a gather document, pause to reason,
and act moments later, the proposal may be refused because the generation changed.
The tell is a refusal naming generation change or stale gather evidence, not the
pause that caused it. Report that ordering failure and retry only through a fresh
single gather-and-act pass.

The foreman performs one bounded action per hourly tick. If this pass creates
three threads needing three sessions, it queued roughly three ticks of work before
competition from dispatch reconciliation, blocked-session answers, human valves,
or other foreman duties. Stage 6 must report not-yet-started sessions as queued,
not as defects, and must not wait for the hourly loop.

Minimum launch briefing content, in order:

1. The route first: factory dispatch for dispatch-safe product work; in-session
   implementation only for genuinely factory-ineligible work.
2. The read-first chain.
3. The ledger access method for that repo, naming the credential wrapper when the
   tenant requires one.
4. Exactly one next action.
5. Conditional repo mechanics, explicitly scoped to steps that are not
   factory-eligible.

Do not front-load worktree mechanics in a launch briefing. That reads as an
instruction to open a worktree even when the correct route is factory dispatch and
opens none.

### 6. Verify, Then Drain

Verify what this pass itself did:

- every non-done item rolls up to a plan;
- every open item carries acceptance criteria;
- status vocabulary is conforming;
- no dispatchable item contains the template delimiter hazard described in words
  below;
- acceptance split labels and acceptance shape agree both ways;
- cross-repo dependency edges resolve;
- routing fields name the repo where the deliverable lands;
- new plan scope events and opening handoffs exist;
- foreman proposals for missing sessions were accepted or refused with recorded
  reasons.

Read content and source, never proxy reports. For sessions, read the tmux session
list and the daemon snapshot rows directly. For work items, read the
orchestrator plugin's `list-work-items --json` projection resolved from the
governed repo's `.livespec.jsonc` `implementation.plugin` key; that is the
referent for this contract's "merged projection" language. For dispatches, read
the run listing for the same server the dispatcher used, then read the dispatcher
journal when the run listing cannot explain the outcome.

As measured on 2026-08-22 against merged master `08b2afd` and a 669-row
projection, that sanctioned projection can answer the three implemented
invariants that need no optional evidence: plan-rollup, acceptance-present, and
lifecycle-status. It can answer dispatchable-delimiter only with item detail text
supplied for comments and notes, and cross-repo-dependencies only with sibling id
sets supplied for every referenced sibling repo; otherwise the checker reports
the narrower evidence base in the invariant scope. The remaining two invariants,
split-acceptance-label and routing-field, are not implemented yet; their scanned
population is zero because the checker has no canonical field to read, not
because the tenant is clean. Revisit this paragraph when `bd-ib-m36re3` or its
successor changes the projection. Until then, any raw ledger read used to
investigate an unimplemented invariant must carry the record-shape traps below
beside the claim.

The run-existence check must name the server the dispatcher used. The run-listing
client may default to a local server while the dispatcher submitted elsewhere. The
tell is a confident empty run list whose newest entry is stale, while process
ancestry shows the dispatch path used an explicit server. A run list from the wrong
server is worse than no evidence because it points at releasing the claim and
re-dispatching real queued work.

Confirm the run exists and confirm the frozen criteria in the same step. The goal
file snapshots acceptance criteria when the run is created, not when it starts.
Editing the ledger after run creation does not reach a queued run. Once a run
exists, the remedies for stale criteria are to remove the run before execution and
dispatch again, or let it build to the stale bar and correct at acceptance.

Do not treat `active` as evidence of a run. Do not treat absence from the live run
listing as evidence no run ever existed. Check the all-runs view and the dispatcher
journal before releasing a claim. A vanished run may be absent from inspect and
dump commands while its full failure payload remains in the journal keyed by work
item.

## Ledger Invariants

The pass must leave these seven invariants true, or report the breach with the
population scanned:

1. Every non-done item rolls up to a plan epic. Only plan anchors are unparented.
2. Every open item carries acceptance criteria, read through the merged projection.
3. Only lifecycle statuses exist: backlog, ready, pending-approval, active,
   blocked, acceptance, and closed.
4. No item in a dispatchable state carries an opening template delimiter:
   two opening braces, an opening brace followed by a percent sign, or an
   opening brace followed by a hash sign.
5. An item labelled for human-verified acceptance has split acceptance criteria,
   and an item with split acceptance carries the label.
6. Every cross-repo dependency edge resolves against a real id in a repo the
   consuming manifest lists.
7. An item's routing field names the repo its deliverable lands in, not the repo
   where the filer happened to sit.

## Measured Traps

Each trap below includes its tell. A trap without a tell cannot be recognized in
the field.

**Non-lifecycle status poisons the tenant.** Tell: the global pre-dispatch ledger
check refuses all dispatches in the repo, often with a conformance message rather
than a defect in the item being dispatched. The create path can print the
non-conforming status in its own success output. Remedy: create, immediately set a
lifecycle status, re-read, and record any repair.

**The default ledger listing can hide the poison.** Tell: a clean conformance
answer from a listing whose count is capped, round, or missing closed and gate
records. Remedy: scan all records, all statuses, and gate records; report the
population.

**Comments are not in the record.** Measured 2026-08-21 over the 523 records of
the `livespec-dev-tooling` tenant using the raw all-statuses JSON read. A record
read returns `comment_count` and no `comments` key, and the raw show shape is a
one-element array rather than an object. Tell: a read-back after a successful
comment write reports zero comments, which reads as a lost write. Remedy: read
comments through the substrate's comments operation and keep comment evidence
separate from record fields.

**Records are omitempty-sparse.** Measured 2026-08-21 over the same 523-record
population: 25 distinct keys appeared, and only 10 appeared on every record.
Tell: a field is absent on a large minority of records and it looks like the
listing dropped it. The listing did not drop it; those records hold the zero
value. Remedy: inspect key presence as record shape before drawing a tenant
conclusion from absence.

**`dependencies` is one heterogeneous array.** Measured 2026-08-21 over the same
523-record population: 261 dependency rows shared one array, keyed their target
as `depends_on_id`, and used six relation types: `parent-child` 116, `blocks`
93, `relates-to` 26, `discovered-from` 23, `related` 2, and `duplicates` 1. That
means 168 of 261 rows, 64 percent, were not blockers. Tell: every target reads
as `None`, the tenant looks full of dangling edges, or blockers appear that do
not exist. Remedy: read the target key and relation type before treating any row
as a blocker.

**A bounded query's negative result is a statement about the bound.** Measured
2026-08-21 in one livespec-overseer grooming pass: a forge query window of 250
rows reported two acceptance items as having no PR, while their merged PRs were
below that window. The same pass caught three more ordinary bounds: keyword
choice, 900-character text window, and 600-character text window. Tell: a
surprising absence, where the tenant looks like it is missing a field, PR, fix,
or other artifact that ought to obviously be present. Remedy: measure the
instrument before believing its verdict, and state the row limit, text window,
file set, or match term beside any negative claim.

**An opening template delimiter makes an item undispatchable.** Tell: dispatch graph
construction fails on an undefined template variable whose name appears only in
the item text or comments, not in the workflow. The hazardous forms are two
opening braces, an opening brace followed by a percent sign, and an opening
brace followed by a hash sign. A stray pair made from two closing braces is
literal text; discriminate before remediating. Do not reproduce the opening
forms in item text, comments, this contract, tests, or commit messages. Describe
them in words. Because comments are append-only, the durable
remedy for a contaminated comment is a clean-text successor or a non-dispatchable
hold, not evidence deletion.

**Acceptance criteria can diverge between fields.** Tell: human-facing item output
shows one acceptance bar while the implement brief or plugin projection uses
another. Remedy: read the merged projection, where the later native field wins
over the creation-time metadata copy.

**Cross-repo dependency edges fail closed.** Tell: dispatch refuses the item as not
in the ready set, yet the status is dispatchable. Resolve the edge id against both
tenants before unsetting anything. If the edge is thread membership, remove it and
use a parent-child edge. If the dependency is genuine and the sibling repo is
missing from the manifest, list the sibling. If the pointer is wrong, repoint it.

**A freshly filed item can be backlog, not ready.** Tell: dispatch says the item is
not in the ready set and there is no dependency edge. Check the first line of the
item before inspecting edges. Remedy: promote to ready only when the item is meant
to be dispatchable.

**Run success can leave an active phantom claim.** Tell: the item is active and
assigned to the factory, live run listing is empty, but the all-runs view shows a
succeeded run and the forge has a merged PR naming the item. Remedy: close the
item with verification. Do not re-dispatch.

**A queued run can vanish before execution.** Tell: dispatch returned success and
the run first appeared as queued or runnable, later disappeared from all-runs
views, and no merged PR or succeeded run exists. Remedy: release the claim and
dispatch again after recording the eviction.

**A failed run can still contain recoverable work.** Tell: the run failed after
the implement stage reached a commit, and an exported run dump contains a
diff.patch under a stage directory. Remedy: recover the patch before redoing the
work. If no patch exists because commit capture failed, the work is not
recoverable through that path.

**A vanished run has not taken its diagnosis with it.** Tell: run inspect and dump
report no such run, but the dispatcher journal still carries an inspect-stage row
keyed by work item id with the provider or transport error payload. Remedy: read
the journal before concluding no evidence remains.

**Provider usage limits are not proven clear by pre-flight.** Tell: every static
dispatch-safety check passes, the sandbox launches, and the run dies inside the
agent turn with a provider limit or reset-time payload. A real dispatch is the
only valid health signal. After a suspected reset, one foreman-owned dispatch is
the probe; other seats hold until its implement stage survives. Dispatch
independence is a file-scope claim, not a credential-pool claim.

**A surface error can hide the provider cause.** Tell: the stage reports a
transport or protocol error while the structured payload names a provider usage
limit and reset time. Remedy: read structured failure detail before deciding
whether to retry, mark item-specific failure, or report a fleet-wide wait.

**Foreman start proposals are ordered.** Tell: a plan-start proposal for a new
topic refuses because no snapshot row exists, or a proposal refuses because the
daemon generation changed between gather and act. Remedy: register with epic
first; compose and submit inside one generation.

**Stage 6 can falsely fail healthy queued starts.** Tell: immediately after stage
5, tmux and daemon rows still lack sessions the foreman accepted as future
actions. Remedy: report queued session starts with hourly-tick latency and do not
wait.

**Auto-merge races the author.** Tell: a PR opens and merges before all intended
commits or fixes are pushed. Remedy: push every commit intended to ship before
opening the PR, then treat the branch as frozen. Follow-up work goes on a new
branch.

**Worktree mechanics can point at the wrong path.** Tell: the worktree creation
recipe fails silently, or a worktree is created inside the primary checkout path.
Use the repo's current documented rescue only when the route is genuinely not
factory-eligible.

**Rate-limit guard hooks can deny forge commands on ordinary words.** Tell: forge
commands are rejected because a title or inline body contains loop-like wording.
Remedy: keep sensitive words out of PR titles and pass long bodies through files.

**Relayed facts degrade at the surface.** Tell: a peer briefing names the right
underlying condition but gives the wrong wall time, stage, or launch boundary.
Remedy: verify the core from local evidence, correct the surface, and state which
part remains unverified.

## Patterns That Worked

Delegate independent long legs, keep the bucketing. The spec drain and triage
sweep can run independently while the driver cuts plan buckets. The bucketing
stays with the driver because it is the coherence decision.

Verify delegated and relayed claims before acting on them. Treat peer reports and
subagent reports as leads, not evidence. Re-measure load-bearing claims from the
authoritative source.

State a control's scope before its claim. A green control over one leg is not proof
about another leg. Demand the same scope statement when receiving evidence.

Never type into another session's pane. Route valve answers, decisions, and session
starts through the foreman and its revalidated action path. Before overriding an
answer already visible in a pane, establish who entered it.

Do not manufacture a subject for a live mutation. If a finding needs a real stuck
record, wait for one. Operating on plausibly live work to satisfy curiosity can
destroy the thing under investigation.

Merge duplicates, never delete them. Append the losing item's unique measurements
to the winner first, then close the loser as a duplicate citing the winner.

A handoff must let a fresh session continue with no chat history: exactly one next
action, every cited path committed, the factory route named, the ledger access
method named, and no parallel checklist.

## Deliberate Non-Goals

This operation does not implement work items. It does not dispatch them. It does
not drive approval, acceptance, rejection, resolved-blocked, policy, capacity, or
move valves. It does not archive plan threads. It does not restart or force any
tracked session. It does not collapse plan overflow. It does not repair unrelated
filing routes while grooming. It does not prove factory health through pre-flight.

It routes accumulated work into coherent, supervised plan threads, records enough
evidence for the next operator to continue, hands queued starts to the foreman, and
exits.
