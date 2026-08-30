# Dispatch traps whose error messages point AWAY from the fix

Moved verbatim from `AGENTS.md`. Every shape here was measured live in this repo; the discriminator tables are the fast path.

## Dispatch traps whose error messages point AWAY from the fix

## THE TEN SHAPES — one table, all of them

Every shape below was measured live in this repo. **Identify the shape before you act:
several are one step apart, and the remedy for a neighbour is routinely destructive** —
releasing a claim over merged work re-runs it, and re-dispatching against a live publish
branch collides with your own sibling.

| shape | the observation that identifies it | work landed | remedy |
|---|---|---|---|
| double-brace token | `template_undefined_variable` naming a token that came from the item's own text | no | fix the dispatcher defect; do **NOT** edit the item |
| queue eviction | `drive.py` exits **0**, run listed `runnable`, then absent from `fabro ps -a` **entirely** | no | release the claim and re-dispatch |
| anchor-as-dependency | `not in the ready set`, **no** phantom claim, an unresolvable `depends_on` | no | resolve the edge against both tenants; unset only if it is mere thread membership |
| succeeded-untransitioned | `fabro ps -a` says `succeeded` and the forge shows a **merged** PR | **yes — merged** | **close it** — never re-dispatch |
| interview-destroyed | `Interview ended without an answer`; `ps -a` `failed` with wall = the full ceiling | no — done but never pushed | `fabro dump` the run and land the recovered patch; release the claim |
| publish-branch collision | **two** runs: one `succeeded`, one `blocked` refusing to overwrite its sibling's branch | **yes — PR open** | close the duplicate; touch nothing else |
| factory-host ENOSPC | immediate failure at stage `fabro-run`, ENOSPC `detail` naming the factory's storage path, `fabro_run_id` null | no | release the claim and re-try `hp` — the condition is intermittent |
| janitor-post-merge red | stage `janitor-post-merge`, `pr_number` **and** `merge_sha` both populated, several unrelated items failing at once | **yes — merged** | close it, then fix master |
| merge-poll | stage `merge-poll`, `pr_number` populated with `merge_sha` **null** | not yet — PR open | fix the gate holding the merge and let auto-merge land it; do not touch the claim |
| acceptance-valve rework | envelope **green** through `done`, PR merged — and the row reads `active` with label **`rework:pending`** | **yes — merged** | read the FAIL reason in the journal and fix the acceptance TEXT; do **NOT** re-dispatch first |

**Two rules the table cannot carry.** The absence of a phantom claim discriminates
nothing by itself — several shapes leave none. And when the envelope's `detail`
describes a TRANSPORT failure (a timeout, a body read, a connection), the envelope is
reporting on the DISPATCHER's health rather than the run's: go to `fabro ps` on the
owning factory and to the forge instead, using the `fabro_run_id` the failing envelope
itself carries.

Each shape's full measurement, with the controls that established it, follows below.


Measured 2026-08-02 and 2026-08-04 while dispatching from this repo. Each fails in
a way that makes the correct remedy look wrong, which is why they are here rather
than only in a plan.

**Check the target repo's MASTER CI before diagnosing any dispatch failure.** The
Dispatcher refuses before any sandbox work with `latest master CI is not proven
green at required check ci-green`, naming the failing run. A red master blocks
EVERY dispatch in that repo and the refusal says nothing about your item, so it
reads as a problem with the item. Measured 2026-08-04: this repo's master was red
for hours — one plan handoff declared its ledger anchor as prose ("The epic anchor
is `x`") where the gate's regex requires the literal "ledger anchor" phrase before
the backticked id, so `test_plan_records_agree` failed. One line fixed it.

**THE SAME GATE HAS AN IN-PROGRESS VARIANT WHOSE REMEDY IS THE OPPOSITE — WAIT, DO NOT
GO LOOKING FOR A BROKEN GATE.** Measured 2026-08-30 dispatching `overseer-ow7c.4`. The
refusal reads almost identically to the red-master one above, and the paragraph above is
exactly what a reader pattern-matches it onto — sending them hunting a repo defect that
does not exist:

```
ERROR: the latest `master` run of workflow `CI` is not proven green at aggregate job
 `ci-green`; refusing dispatch before sandbox work.
Run databaseId: 33317477525
Reason: the latest run 33317477525 is still in_progress
Remedy: retry the dispatch when the run concludes.
```

**The gate is not "master CI is green". It is "the LATEST master CI run has CONCLUDED,
and green".** An in-progress run fails it exactly as a red one does. Read the `Reason:`
line — it is the only thing distinguishing the two, and it names the actual condition.

**Checking the most recent COMPLETED run is the wrong check and will mislead you**, because
it is green precisely when the gate is refusing. On the day this was measured the newest
completed run was green while two newer commits sat queued and in-progress; the dispatch
was refused three seconds in, having created no run and left no claim.

**This costs more here than it looks, because master churns.** Every merge in this repo is
followed by a release-please commit whose own CI must conclude before the next dispatch
passes the gate. Three dispatches on 2026-08-30 each waited on a release commit's CI, and
master moved four times in one afternoon. Budget a wait after every merge rather than
treating it as an anomaly, and re-check that the run you waited for is still the LATEST
before launching.

### A `{{...}}` token anywhere in a work-item's text makes it UNDISPATCHABLE

`drive.py --action impl:<id>` interpolates the work-item's text into the fabro
workflow's **templated** `goal` attribute. A literal `{{name}}` in that text is
parsed as a *fabro* template variable, finds no binding, and the graph is rejected
before any agent runs:

```
workflow.fabro:294:32: undefined template variable `test_nprocs`
  in graph attribute `goal` (template_undefined_variable)
```

**The token is not the workflow's** — `grep test_nprocs` over the workflow file
returns nothing. It arrives from the ledger record. In this fleet that shape is
common: quoting a justfile recipe as evidence is routine and **every** `just`
recipe variable looks exactly like this (`pytest -n {{test_nprocs}}`).

Measured with controls: `overseer-jdo` carried the token and failed every time;
`overseer-0pc` and `overseer-mir` carried no `{{...}}` and both dispatched
normally. So it is item-text-specific, not a dispatcher outage.

**It also leaves a PHANTOM CLAIM** — afterwards the item reads
`status=active, assignee=fabro` while `fabro ps` reports no running processes.
Release it by hand before re-dispatching. `ACTIVE` is never evidence of a run;
`fabro ps` is.

**Do NOT fix this by editing the work item.** Escaping or deleting the offending
text corrupts the item's own evidence and hides a defect that recurs on the next
item that quotes a recipe. Tracked as `bd-ib-vv9y` (P1, orchestrator tenant).

### A PHANTOM CLAIM HAS A SECOND CAUSE, and this section used to imply only one

The `{{...}}` trap above is not the only way an item ends up `status=active,
assignee=fabro` with nothing behind it. **A QUEUED RUN CAN BE EVICTED WITHOUT EVER
EXECUTING**, and it leaves exactly the same wreckage.

Measured 2026-08-03 dispatching `overseer-x29.1`: `drive.py` exited **0**, and
`fabro ps` showed the run as `runnable` — queued behind three in-flight runs.
It never started. Some minutes later it was absent from `fabro ps -a`
**entirely** — not `failed`, not `succeeded`, no record at all — while the item
still read `active`/`fabro`. A sibling queued run in the same window
(`livespec-dev-tooling-uzwqm6`) disappeared identically, so it is a queue
property, not an item property.

**Tell the two causes apart before diagnosing**, because the remedies differ. (These
are the two causes of a phantom claim known when this entry was written; others leave
one too — the nine-shape table at the top of this file is the complete set.)

| symptom | `{{...}}` trap | queue eviction |
|---|---|---|
| `drive.py` exit code | non-zero, immediate | **0** |
| error text | `template_undefined_variable` naming a token | none |
| `fabro ps` right after | never lists the run | lists it as `runnable` |
| `fabro ps -a` later | never lists the run | run is **absent entirely** |
| remedy | fix the dispatcher defect; do NOT edit the item | release the claim and re-dispatch |

**A `drive.py` exit of 0 is NOT evidence that work started** — it means the
request was accepted. Confirm with `fabro ps` that a run exists, and confirm again
that it reaches `running`; a run parked at `runnable` has not begun and may never.

The rule the two share is the one already stated above: `ACTIVE` is never evidence
of a run, `fabro ps` is. Release the claim by hand (`--status ready`, clear the
assignee) before re-dispatching, and record WHY in the item so the next reader does
not attribute an eviction to the `{{...}}` defect and go looking for a token that
was never there.

### A THIRD CAUSE, and unlike the two above it leaves NO phantom claim

Measured 2026-08-04. An item whose THREAD MEMBERSHIP was filed as a cross-repo
`depends_on` is permanently undispatchable:

```
ERROR: requested work-item(s) not in the ready set: <id>
```

`drive.py` exits **1** and the dispatcher exits **3**. No fabro run is created at
all, so there is nothing to find in `fabro ps` and — unlike both traps above — the
item is left with NO phantom claim. That absence is the discriminator.

The cause is that `store._depends_on_from_edges` reconstructs
`metadata.non_local_depends_on` into `WorkItem.depends_on`, and the ranker excludes
any candidate with a dep that does not resolve CLOSED —
`_dispatcher_loop_selection.is_dispatch_candidate` applies the same test to a
`pending-approval` item by projecting it to `ready` first. So an anchor link pointing
at the item's own PARENT EPIC is circular by construction: an epic cannot close
before its children. It is also unresolvable independent of status whenever the
consuming repo's `cross_repo_targets` manifest has no entry for the sibling repo —
and an unresolvable sibling FAILS CLOSED.

Measured with a three-way control against the plugin's own selector: as-filed → not
a candidate; the identical item with the single `depends_on` entry stripped →
candidate; a known-ready item → candidate.

**Thread membership belongs in the item TEXT, never in a dependency edge.** The
`Read first` block already carries it. Remedy: `bd update <id> --unset-metadata
non_local_depends_on`, and record why. A GENUINE cross-repo dependency is fine — but
check the consuming repo's `cross_repo_targets` actually lists the sibling, or it
will fail closed forever.

Measured 2026-08-19 while repairing `overseer-vfz5v5`: the same `not in the
ready set` symptom has a third case. A dependency can be genuine, and the sibling
repo can be correctly listed in `cross_repo_targets`, while the edge's
`work_item_id` is simply wrong. In that case, unsetting the edge destroys the
record of a real prerequisite and makes the item look dispatchable while its real
blocker is invisible.

**Before unsetting any cross-repo edge, resolve its `work_item_id` against BOTH
tenants' full id sets.** If it resolves and the edge is only thread membership,
unset it as above. If it resolves and the sibling repo is missing from
`cross_repo_targets`, list the sibling. If it resolves nowhere, treat the pointer
as broken: look for the real counterpart and REPOINT the edge. Unset only when no
real counterpart exists. In the measured case, the broken edge named
`overseer-llz4xi`, which existed in neither tenant and even carried an
`overseer-` prefix while declaring `livespec-dev-tooling` as its repo. The real
counterpart was unambiguous: `livespec-dev-tooling-3nt9`, whose description named
livespec-overseer's `justfile:127-142` and the same three hard-coded
marketplaces that `overseer-vfz5v5` was replacing. Repointing kept the item
correctly gated until that blocker lands, instead of deleting the truth.

There is a separate false-positive source for that third case:
`bd update --set-metadata non_local_depends_on=<json>` silently stores the value
as a string, not as a JSON array. A stringified edge can later look like a broken
reference, inviting someone to unset a healthy dependency. The working form is
`bd update <id> --metadata @<file.json>` with the COMPLETE metadata object; it
replaces the whole object, so preserve sibling keys such as `rank`. Then read the
item back and verify `non_local_depends_on` is a list, not a string.

### A `not in the ready set` refusal with NO dependency edge at all — check the STATUS first

Measured 2026-08-19 dispatching `overseer-y3xhlh.1` and `.2`. Two dispatches refused,
under a minute each, neither leaving a phantom claim:

    ERROR: requested work-item(s) not in the ready set: overseer-y3xhlh.1

`drive.py` exits **1**, the dispatcher **3** — the identical signature to the
anchor-as-dependency case above. **The cause was neither a dependency edge nor a
broken pointer. `bd create` lands a new item in `BACKLOG`, and the dispatcher's ready
set excludes backlog.** One `bd update <id> --status ready` per item fixed both, and
they re-dispatched cleanly on the same build minutes later.

**The reason this is easy to miss is that the status CHANGES BEHIND THE CREATE.**
`bd create` prints `Status: open` truthfully — beads' own intake default — and the
fleet's dispatcher then normalizes `open` onto the livespec lifecycle equivalent
`backlog` (`_dispatcher_ledger_close.py`, `_NATIVE_STATUS_REMAP`, reason
`"beads-native intake default"`). Both halves are behaving as designed. The filing
session is simply never told that the status it was shown has been superseded:

    $ bd create "..." --type bug --parent <epic>
    ✓ Created issue: overseer-y3xhlh.7 — ...
      Priority: P3
      Status: open
    $ bd show overseer-y3xhlh.7
    ◇ overseer-y3xhlh.7 [BUG] · ...   [● P3 · BACKLOG]

So the session that filed the item has been told it is open. Nothing prompts it to
suspect the status, and the refusal names the ready set rather than the status.

**CHECK THE STATUS BEFORE INSPECTING ANY EDGE.** The preceding guidance sends you to
resolve a `work_item_id` across both tenants' id sets before unsetting anything — sound
advice for a real edge, and a dead end here, because there is no edge to resolve. A
freshly-filed item typically has no `depends_on` at all, so a reader following the
edge-first path finds nothing, concludes the metadata is fine, and is left with a
refusal they cannot explain.

    bd show <id> | head -1     # BACKLOG? -> bd update <id> --status ready

Costs a second, and it discriminates the status member of this symptom family:
**no edge and `BACKLOG`** is this case; an edge that resolves nowhere is the
broken-pointer case; an edge that resolves but names the parent epic is
thread-membership; an edge whose sibling repo is absent from `cross_repo_targets`
fails closed. A further no-edge case exists immediately below, and the status read
does not identify it by itself.

**File items ready when you mean them to be dispatchable**, or promote them in the same
breath as filing. Do not batch-file a plan's children and dispatch later assuming they
are startable — they are not, and the create output says otherwise.

### A `not in the ready set` refusal with READY status and NO edge — check for a live sibling claim

Measured 2026-08-22 on `overseer-b6q2`: the central autonomous loop claimed the
item between a session's pre-flight and its manual dispatch command. The loop wrote
`loop-pick` with budget 1 at 2026-08-22T02:29:31Z, then `ledger-admit`, then
`dispatch-id` at 2026-08-22T02:29:38Z
(`dc73fddda8c14817b80ba1031505b94e`, factory `hp`) in
`tmp/fabro-dispatch-journal.jsonl`. A manual dispatch 36 seconds later refused:

    ERROR: requested work-item(s) not in the ready set: overseer-b6q2

`drive.py` exited **1**, the dispatcher **3**, no fabro run was created, and **NO
phantom claim** was left. That is character-for-character the anchor-as-dependency
signature above, and the same visible shape as a stale plugin build recorded below.
It was neither: the item had no dependency edge of any kind, it was `ready` at the
moment of the attempt, its acceptance guard returned ok, and `just ensure-plugins`
had confirmed the current build minutes earlier.

This is the ready-set claim **working**. It prevented two runs from publishing to
the same branch for the same item, the collision shape already documented below.
The remedy is to do **nothing**: do not release the claim, do not re-dispatch, and
do not start editing edges or status. First grep the dispatch journal for a recent
`dispatch-id` on the same item. If one exists and no later outcome proves it ended,
the live sibling owns the work; leave it alone and inspect the factory run instead.

### A FOURTH SHAPE: the run SUCCEEDED and the item was never transitioned

Measured 2026-08-05 on `overseer-5oap`. **This is the dangerous member of the
family, because its symptom is IDENTICAL to a queue eviction while its remedy is
the EXACT OPPOSITE.** The item reads `status=active, assignee=fabro` and
`fabro ps` does not list it — the textbook eviction signature. Following the
eviction remedy there (release the claim, re-dispatch) would RE-RUN work that had
already merged and shipped.

What actually happened: run `01KZ84FG43SF` ran 56m57s, **succeeded**, its PR
merged, and the change went out in a release. Only the ledger transition never
happened.

**`fabro ps -a` IS THE DISCRIMINATOR, and it is the only one.** An evicted run is
absent from `ps -a` entirely; a completed one is listed there as `succeeded`. The
live `fabro ps` view cannot separate them, because both are simply gone from it.

So the rule "`ACTIVE` is never evidence of a run, `fabro ps` is" needs one more
turn of the screw: **the ABSENCE of a run from `fabro ps` is not evidence that no
run happened.** Check `ps -a`, and check the forge for a merged PR naming the
item, before releasing any claim. The remedy here is to CLOSE the item with the
verification recorded — never to re-dispatch.

### A FIFTH SHAPE: the work was DONE and GREEN, and the run destroyed it

Measured 2026-08-05 on `overseer-0fy`, run `01KZ87W6RNDMNSGBT7YKWZDM8N`. **This is
the most expensive member of the family, because the dispatcher reports `failed`
about work that had already succeeded.**

    05:56Z  dispatched
    ~06:33Z the AGENT FINISHED: `just check` 68/68 at 100% coverage, commit-msg
            hook re-ran the full suite green, committed as 4de441e.
            Then, verbatim: "No push/PR performed."
            Then: "Needs human: the loop cannot auto-resolve this work-item"
                  [R] Retry / [I] Re-implement from scratch / [A] Abandon
            Then: "Interview ended without an answer."  Dispatcher exits `failed`.
    ~09:56Z the RUN hits its 4-hour ceiling still waiting for input.

Afterwards the commit is unreachable — `git cat-file -t 4de441e` returns "Not a
valid object name", the run's scratch directory holds only logs, and fabro
executes remotely.

**THE WORK IS NOT GONE, AND THIS ENTRY SAID OTHERWISE FOR A WEEK. `fabro dump`
RECOVERS IT — TRY THAT BEFORE REDOING ANYTHING.**

    fabro dump <run-id> -o <dir> [--server <factory-url>]

The commit is unreachable, but the run's exported state carries the full
implementation as a patch. Measured 2026-08-12 on two independent runs:

| run | item | recovered | outcome |
|---|---|---|---|
| `01KZSPSTPFX6` | `livespec-dev-tooling-q3emww` | 244-line patch, 2 files | applied cleanly to master and was LANDED from the dump |
| `01KZ87W6RNDMNSGBT7YKWZDM8N` | `overseer-0fy` (this entry's own incident) | **1,248-line patch, 11 files** | preserved intact |

The second row is this entry's own "roughly four hours of green work, gone" — it
was recoverable the whole time. It no longer applies cleanly only because the
work was redone by hand afterwards and `overseer-0fy` closed; two of its files
already exist. That redo was avoidable.

The dump also works on old runs (used here on a run from three days earlier and
one from a week earlier), so retention is not the constraint — knowing the
command is. `stages/*/output.log` is exported too, which is how a janitor log
previously written off as "a content-addressed blob not locatable under
`~/.fabro/storage`" was later read.

**KNOW THE BOUNDARY — RECOVERY IS NOT UNIVERSAL, AND A DUMP WITHOUT A PATCH IS
NOT A COUNTER-EXAMPLE.** The patch exists only when the run got far enough to
capture a commit. Measured on a third run, `01KZBJNKGQXM6XWZ06EC7T8KQR`
(`overseer-1gig`, the `livespec-dev-tooling-sc0z` incident): its Green amend
itself failed — `git checkpoint commit failed` — so its dump holds
`output.log`, `prompt.md` and `response.md` but **no `diff.patch` at all**. That
work is genuinely unrecoverable, and `overseer-1gig` is still `ready`, never
redone.

So the discriminator is whether `stages/*/diff.patch` exists:

| run reached | dump holds | action |
|---|---|---|
| a captured commit, then blocked/reaped | `diff.patch` | recover and land it |
| commit itself failed | logs only, no `diff.patch` | genuinely lost; re-dispatch |

So the remedy below is still right about PREVENTION, but its premise about
recovery was wrong: **dump first, redo only if the dump is genuinely empty.**

**REMOTE FACTORY RUNS NEED THE FACTORY ENDPOINT.** Measured 2026-08-23 on
run `01M0PJNQAT5X2M6AGX28XSNFN4`: a local `fabro dump <run-id> -o <dir>`
reported no matching run because it queried the local server. The same command
with the remote endpoint exported 74 files immediately:

    fabro dump <run-id> -o <dir> --server https://hp-xubuntu.perch-rudd.ts.net:32276

The same `--server` applies to `fabro attach` and `fabro ps`. For a run known to
have been launched on a remote factory, "No run found" from a local `fabro` is a
wrong-server tell, not evidence that the work is absent.

**DO NOT TAKE THE LAST STAGE'S `diff.patch` AS THE DELIVERABLE.** On the same
run, `stages/011-pr@1/diff.patch` was a 3,694-line diff against a stale base and
included unrelated master work. The item-scoped deliverable was the union of
`002-implement@1`, `004-fix@1`, and `008-review_fix@1`: eleven files, about 737
lines. Recovery means reading every `stages/*/diff.patch` and selecting by file
list against the item scope, not by stage order.

**THE DISPATCHER'S EXIT IS NOT A REAP, AND THAT GAP IS THE RESCUE WINDOW.** The
dispatcher gave up at ~37 minutes; the run stayed live and blocking for another
**3.4 hours**. `fabro attach <run>` accepts "a running or finished workflow run",
so the interview was answerable that whole time by anyone who knew it existed.
Retry / Re-implement / Abandon are **supervisor-grade** choices, not
maintainer-grade ones. So the failure was not the loop asking — it was that
nothing was listening.

**WHAT TO DO.** Watch for the interview, not just for the terminal state: a
terminal-state watcher wakes you at the END of the rescue window, which is exactly
too late. Grep the dispatch log for `Needs human`, `Interview ended`, or `cannot
auto-resolve` and treat a hit as urgent. Annotate dispatched items to PUSH AND OPEN
A PR (draft if need be) BEFORE raising any blocking question — unpushed work behind
an unanswered question is unrecoverable. Filed as `bd-ib-6o6h` (orchestrator).

**A SIZING WARNING ON THE ITEM IS NOT THE CAUSE HERE.** The dispatcher warned this
item was 1959 chars with 5 enumerated parts and might exceed one unattended turn;
the agent completed it in ~37 minutes anyway. It was not too big to implement, it
was too big to FINISH UNATTENDED. Splitting fixes neither defect.

**These five are the shapes known when this entry was written; the complete set is
the nine-shape table at the top of this file.** Succeeded-untransitioned and
interview-destroyed are the pair to keep straight here:

Both ran and both are absent
from the live `fabro ps`, but one merged its work and must be CLOSED while the
other left its work unpushed and must be RECOVERED — `fabro dump`, not redone.
`fabro ps -a` separates them — `succeeded` versus `failed` — and the forge
confirms it.

### A SIXTH SHAPE: TWO runs for ONE item, the second colliding with the FIRST'S OWN published branch

Measured 2026-08-13 on `livespec-runtime-0u8`. **This one mimics
"interview-destroyed" — `blocked`, a human question, nothing obviously landed —
while its correct remedy is the exact opposite: do NOTHING to the work, because
the work is already published.**

The second run redid the implementation, then failed at its `pr` stage:

    push blocked: pre-push hook passed, but origin already has
    refs/heads/feat/<item> with commits not present locally; per instructions i
    did not overwrite or retry on this non-workflow-permission rejection.
    human decision needed

The remote branch was its **own sibling's output**. The agent refused to
force-overwrite and escalated to `blocked(human_input_required)`. That refusal is
CORRECT behavior and must never be "fixed" by teaching agents to force-push.

**THE DISCRIMINATOR IS ONE COMMAND, AND IT IS CHEAPER THAN EVERY OTHER CHECK IN
THIS SECTION — RUN IT FIRST, and run the FORGE query, not the ref probe:**

    gh pr list --head <publish-branch> --state all
    git ls-remote origin 'refs/heads/<publish-branch>'

The order was inverted here until 2026-08-20, and it matters (three-way control
recorded on the foreman plan epic): an EMPTY `ls-remote` discriminates NOTHING —
a merged PR's branch is routinely auto-deleted, so the ref probe reads empty
precisely when the work landed. Only the forge query over ALL states separates
never-pushed from merged-and-cleaned-up. A live publish branch, or a PR in any
state, means the work EXISTS. Releasing the claim
and re-dispatching on the "interview-destroyed" reading would have re-run work
that was already open as a PR and auto-merging.

Remedy: confirm the PR, `fabro dump` the blocked run and DIFF its patch against
what is published (here they were substantively identical — two words of
reason-string wording), then `fabro rm <run> --force`. Plain `rm` refuses a
blocked run and tells you to pass `--force`.

**Keep that order — release, inspect, remove — everywhere this remedy
generalizes** (measured twice on 2026-08-19, once by a thread that destroyed its
own run's evidence this way): claim-release and run-removal are SEPARATE acts.
Release the claim immediately, since a held claim blocks the ready set; `fabro
dump`/`fabro inspect` BEFORE any removal, because `rm --force` destroys the only
readable record of a swallowed cause; remove last. The commonly-practiced
recovery recipe ends with force-remove and trains the mistake.

**HOW TWO RUNS HAPPEN, and the correction it forces on the rule above.** The
first dispatch was killed by the CALLER's own timeout; `fabro ps -a` immediately
afterwards showed NO run for the item, so a second dispatch was issued. A run
existed anyway. So "`ACTIVE` is never evidence of a run, `fabro ps` is" needs its
final turn: **after you kill a dispatcher, absence from `fabro ps -a` is not
evidence that no run exists or will exist.** Do not re-dispatch on that basis —
check the publish branch and the forge first.

**Do not kill `drive.py` on a timeout, and do not put multi-minute dispatches in
the harness background-task tracker from a loop-parked session.** A 20-minute
foreground timeout produced both the phantom claim and the collision above; the
old replacement advice was `run_in_background: true` plus waiting for a
task-notification. That pattern is retired for any Claude Code session that may
end its turn with `ScheduleWakeup` / dynamic `/loop`: measured 2026-08-16
(`overseer-za32`), the harness reaps still-running background Bash tasks about
6-15s after parking, silently killing the dispatcher.

For loop-parked multi-minute dispatches, detach the dispatcher from the harness
process tree and read the verdict from disk:

```
run_dir="$PWD/tmp/overseer/detached-dispatch/<item>-$(date -u +%Y%m%dT%H%M%SZ)"
scripts/detached-dispatch.sh "$run_dir" -- \
  python3 /absolute/path/to/drive.py --action impl:<id> ...
```

The helper uses `setsid` + `nohup`, writes combined output to
`$run_dir/output.log`, writes the launcher pid to `$run_dir/pid`, and atomically
replaces `$run_dir/verdict.env` with `status=succeeded|failed` and `exit_code=N`
when the command exits. End the turn only after arming a wake; on wake, inspect
the disk files, `fabro ps`, `fabro ps -a`, and the publish branch/forge checks
above. The task-notification stream is no longer the record of completion for
loop-parked dispatch.

Two `verdict.env` refinements, measured 2026-08-19: the helper also writes it
with `status=running` AT LAUNCH, so wait on the value CHANGING, never on the
file existing; and its two-word verdict cannot distinguish refused-before-launch
from ran-and-failed — the dispatcher's own JSON envelope in `output.log` is the
authoritative record, so read that, not the verdict line. And across every shape
in this section: the ABSENCE of a phantom claim discriminates nothing by itself —
several shapes leave none.

**A THIRD REFINEMENT, MEASURED 2026-08-22, AND IT RETIRES "READ THE ENVELOPE" AS A
SUFFICIENT RULE: THE ENVELOPE'S OWN `status` FIELD CAN ALSO BE WRONG.** The
paragraph above sends you from the two-word verdict to the dispatcher's JSON
envelope, which is the right move and is not enough. Dispatching
`overseer-6s3pk6.6`, `verdict.env` read `status=failed exit_code=1` **and** the
envelope reported `"stage": "fabro-run", "status": "failed"`, `pr_number` null,
`merge_sha` null, summary "Dispatcher did not report green". Both records agreed,
and both were wrong. The run was still executing at the time, ran 54m23s, succeeded,
and merged as PR 1703.

**Only the envelope's `detail` string discriminated**, and it names a client-side
read, not a run outcome:

    error decoding response body
    error reading a body from connection
    timed out

The dispatcher lost the HTTP response; it never observed the run stop. So the rule
is now: **read the envelope's `detail`, not merely its `status`** — and when the
detail describes a TRANSPORT failure (a timeout, a body read, a connection), the
envelope is reporting on the DISPATCHER's health, not the run's. Treat it as no
evidence about the run at all and go straight to `fabro ps` on the owning factory
and to the forge.

This matters because it defeats the discriminator table above from the inside. That
table is keyed on `fabro ps -a` plus whether work landed, which still separates the
shapes correctly — but a reader who has already accepted a `failed` verdict from two
agreeing records is unlikely to run those checks at all. Here the item sat at
`active`/`fabro` with its work merged: the **succeeded-untransitioned** row, whose
remedy is to CLOSE it, while the failure report pointed at release-and-re-dispatch.

**CONFIRMED INDEPENDENTLY THE SAME DAY, AND THE ENVELOPE HANDS YOU THE KEY TO THE
CHECK IT TELLS YOU TO RUN.** Dispatching `overseer-8nxb` about an hour earlier, a
different seat hit this shape identically: `verdict.env` read `status=failed
exit_code=1`, the envelope reported stage `fabro-run` status `failed` with
`pr_number` and `merge_sha` null, and the detail carried the same three transport
lines. The run was executing the whole time, ran 26m16s, succeeded, and merged as
PR 1700. Two instances, two seats, different durations, one day — so treat this as
a recurring shape rather than a one-off.

What that second instance adds is practical: **the failing envelope's
`fabro_run_id` was NON-NULL** (`01M0N73AGRXQG1CBC7RBNPS8JR`) even though
`pr_number` and `merge_sha` were null. That field is the run to look for, so the
"go to the factory process view" step above does not require guessing which run is
yours — read the id out of the very envelope that reported the failure, then match
it on the factory. A non-null `fabro_run_id` beside a transport `detail` is also
the sharpest positive discriminator in this family: the ENOSPC shape fails at the
same stage with **no** run id, and a queue eviction never produces one either.

That instance also shows the mis-remedy is not hypothetical. The item sat
`active`/`fabro` over merged work; releasing the claim and re-dispatching — which
is what the table's nearest-neighbour row prescribes for a run absent from local
`fabro ps` — would have started a second run against a branch its own sibling had
already published, which is the **publish-branch collision** shape documented
above. The two shapes are one step apart, and the transport `detail` plus the run
id is what separates them.

**ONE MORE ORDERING RULE, FROM A NEAR-MISS THE SAME DAY, AND IT GENERALIZES PAST
DISPATCH.** Preparing the `overseer-6s3pk6.10` cutover, the plan required stopping
the acting `overseerd` and re-running the bootstrap. Provisioning the runtime prefix
FIRST — with the old daemon deliberately left running — revealed that
`ensure_current_runtime()` returns `None` on this host (`ensurepip` absent), and that
`start.py` answers that with `return 1` and **launches no daemon at all**. Performing
the steps in the documented order would have left every tracked session in the repo
unsupervised.

**When a procedure has an irreversible step and a step that can fail, run the
failing-capable step first, even when you expect it to pass.** The cost is one
command; here the alternative cost was the fleet's supervisor. Note that the
discovery was a side effect — the reordering was chosen only to de-risk a restart,
not because anything was suspected.

**UPDATE, SAME DAY — THE PROVISIONING FAILURE ABOVE IS CURED; THE ORDERING RULE IS
NOT AFFECTED.** The paragraph above says `ensure_current_runtime()` "returns `None`
on this host", which was measured at 18:25Z and is **no longer true**. It was fixed
hours later by `overseer-6s3pk6.12` (PR 1723): provisioning moved off the stdlib
module onto `uv venv` plus `uv pip install --python <venv>`, and a failed provision
now removes its own partial prefix. Verified live at 19:56Z — the call returns a
real executable that runs.

This is an **UPDATE, not a correction**: the measurement was correct when written
and has since been cured, which is a different fact from having been wrong. It is
left in place rather than deleted because the near-miss is the whole point of the
entry, and the ordering rule it produced stands on its own — it is about the shape
of a procedure, not about `ensurepip`.

**Read the cured half as history and the rule as current.** A reader who takes the
present-tense sentence at face value today will conclude the daemon cannot be
provisioned here, which is the exact record-versus-world error that
`.ai/record-versus-world.md` documents at length — committed, this time, by the
entry that was written to warn about a neighbouring one.

**Six shapes were known when this entry was written; see the nine-shape table at the
top of this file for the current set.**

A **seventh** shape is documented further down, and it is discriminated by something
the cumulative tables of that era did not hold: the factory
host running out of disk, which fails at stage `fabro-run` with an ENOSPC `detail`
naming a path on a machine this one cannot see. Local `df` and `fabro ps` both read
clean while every dispatch fails.

### `fabro ps` IS NOT THE EVIDENCE WHEN THE FACTORY IS REMOTE — READ THE JOURNAL

Every rule above leans on "`ACTIVE` is never evidence of a run, `fabro ps` is". **That
discriminator is LOCAL, and it silently stops working once an item is dispatched to a
remote factory.** Measured 2026-08-20: a live, executing run showed *nothing* in local
`fabro ps` because its item carried `dispatch_factory=hp` and the work was running on
another host. Read literally, the table above then says "absent from `fabro ps -a` ⇒
queue eviction ⇒ release the claim and re-dispatch" — which is how you manufacture the
publish-branch collision documented immediately above, against your own still-running
sibling.

**Check the item's dispatch factory before applying any local `fabro ps` reasoning.**
When it is remote, the local process view is blind. The journal is the first record
of truth because it names the run, but it is not the only instrument.

**THE JOURNAL IS APPEND-ONLY AND CUMULATIVE, SO MATCHING BY ID ALONE ALWAYS FINDS THE
PAST.** Two entry kinds matter: `stage: "dispatch-id"` carries `work_item_id`,
`dispatch_id` and `at`; `stage: "outcome"` carries a nested `outcome` object with
`work_item_id`, `status` and its own failing `stage`. An item dispatched more than once
has one entry per attempt, and a naive "latest outcome for this id" search happily
returns **yesterday's**.

That is not hypothetical: it produced a confident "the probe FAILED, do not dispatch"
verdict from an outcome that was 11 hours stale, while the current run was still
executing normally. **Floor every outcome query on the CURRENT run's own `dispatch-id`
timestamp** — take the latest `dispatch-id` for the item, then accept only `outcome`
entries strictly after it. An item with a dispatch-id and no later outcome is not
finished, not failed, and absolutely not evicted. That evidence is still only
negative: it cannot separate EXECUTING from WEDGED from EVICTED, and it carries no
elapsed time.

The remote factory process view is queryable. This is READ-ONLY inspection, not
routing work. Use the URLs already declared in `.livespec.jsonc` under
`dispatcher.factories` (`hp`, `vps`) and point fabro at the factory:

    fabro ps --server https://FACTORY-HOST:PORT

Measured 2026-08-22T08:26Z against `hp`: it listed three runs executing in this
repo with run ids, statuses and durations, plus one BLOCKED run in a sibling repo
at 195m — exactly the state the journal cannot distinguish from healthy progress.

Use both instruments, in order. The journal tells you WHICH run belongs to your
item: the current `dispatch-id`, floored by its timestamp. The remote process view
tells you WHAT that run is doing now. A blocked run is the interview-destroyed
shape in progress and is still rescuable; a running run at an unremarkable
duration is working and must be left alone.

This is the same failure as a stale baseline wearing a different hat, and the same rule
fixes it: a comparison has two sides, and an append-only log is one of them. See the
settings-default note in `overseer/AGENTS.md` for the general form.

### THE DOUBLE-BRACE TRAP REACHES LEDGER COMMENTS, AND THERE IT IS TERMINAL

Measured 2026-08-19 on `overseer-bc55wx.8`, which had to be **superseded** rather than
fixed. The first entry in this section says "do NOT fix this by editing the work item".
That advice quietly presumes editing is *possible*. For a comment it is not.

**Three things the original entry does not cover.**

**The goal includes COMMENTS.** `_dispatcher_goal.render_goal` assembles item fields,
**ledger comments**, and ratified lessons into one brief. A dispatch-safety check that
scans only `description`, `acceptance` and `title` — which is the obvious thing to
check, and what was checked here — passes an item that is already poisoned. The
failure arrives at stage `fabro-run` with the workflow file's own path and line number
in the message, which reads like a defect in the workflow rather than in your item:

    fabro::template::syntax
    template expansion failed in graph attribute `goal`:
    syntax error: unexpected `.` at line 73

The line number is an offset into the **expanded goal**, not into the file it names.

**The trap fires on prose ABOUT the trap.** The poisoned comment here was documenting
*this very hazard* and quoted the token in order to name it. Writing the literal
delimiter to warn a future reader is enough to break the item. **Name it in words** — "a
doubled left brace" — or describe the shape without reproducing it. The same applies to
`{%` and `{#`.

**Comments are APPEND-ONLY, so the record is unrecoverable.** `bd comments` offers
`add` and `list` and nothing else — no edit, no delete. Once a comment carries the
token, every future dispatch of that id fails identically, forever. The only remedy is
to **file a clean-text successor and close the original as superseded**, recording why,
so the finding's provenance survives even though the record cannot be dispatched.

**Run the successor as a CONTROL rather than assuming the diagnosis.** Here
`overseer-bc55wx.9` carried the identical scope and acceptance with no brace tokens and
dispatched normally on the *same* plugin build minutes later, which is what proved the
item text — not the build, not the fleet — was at fault. Two failed dispatches, each
under a minute, both leaving a phantom `active`/`fabro` claim to release by hand.

**THE ESCAPER IS NOT MISSING — ITS OUTPUT IS WHAT FABRO REJECTS.** Measured later the
same day, and it changes what you should ask for. `render_goal` *does* run
`escape_minijinja_literal` over the whole assembled brief, comments included, and it
produces exactly what it intends. It still fails.

**The proof is an artifact you can go and read, which is the useful part of this
entry.** The Dispatcher writes the assembled brief to `/tmp/fabro-goal-<item-id>.md`
before invoking fabro, and **that file survives a failed run** — so after any dispatch
failure you can inspect the exact bytes fabro was handed. Two of them, seven minutes
apart on the same build, are a clean two-way control:

| goal file | escaped openers | outcome |
|---|---|---|
| `fabro-goal-overseer-bc55wx.8.md`, 77 lines | exactly one, on **line 73** | rejected: `syntax error: unexpected` `.` **at line 73** |
| `fabro-goal-overseer-bc55wx.9.md`, 35 lines | none | ran normally, merged |

The error names *the very line the escaper produced*. So "add escaping" is not the fix,
and asking for it sends an implementer the wrong way. Filed with both candidate
mechanisms and a cheap disambiguation as `bd-ib-ai9a` (orchestrator tenant), which
supersedes `bd-ib-vv9y` — whose own **title** quotes the token, making the item that
describes the defect one of its casualties.

**QUOTING THE EVIDENCE POISONS THE REPORT.** This is the part to design around rather
than resolve to remember. A good bug report quotes the failing line verbatim; here the
failing line *is* the poison. The session that wrote the section above lost a
freshly-filed orchestrator item to exactly that within minutes of merging this guidance,
because what it needed to quote was the escaped line itself. Warnings do not fix this.
**Describe the byte sequence in words, and check mechanically before you file.**

**THE CHECK, which costs a second and needs no new tooling.** Run it against the item as
*stored*, not against your draft — a title, an acceptance clause or someone else's
earlier comment can carry the token:

    bd show <id> | grep -nF -e "$(printf '\173\173')" -e "$(printf '\173%%')" -e "$(printf '\173#')"

`printf` keeps the delimiters out of your own command line and shell history. No output
means the record is dispatchable. Any hit names the line to reword. Do this **before**
`bd comment` too — the comment is the common poisoning route, and once it lands it is
permanent.

### A SEVENTH SHAPE: the FACTORY HOST has no room for a run directory, and every local signal reads healthy

**MAINTAINER INSTRUCTION, 2026-08-22: DO NOT ROUTE ANY WORK TO THE `vps`
FACTORY FOR THIS REPO, UNTIL THE MAINTAINER LIFTS THIS.** `hp` is the only
dispatch target for livespec-overseer. A capacity defer where `active_count`
equals `wip_cap` is this repo's WIP cap working as designed: wait for a slot.
It is not a routing problem, not grounds to pass a `vps` factory argument, and
not grounds to substitute a local run. The pre-push aggregate is the sole
standing local exception, because it runs by design and cannot be dispatched.
The second factory declared in `.livespec.jsonc` is still useful for read-only
process inspection, but it is not available for routing work despite being
configured.

**INSPECTING A FACTORY IS NOT ROUTING WORK TO IT.** Pointing `fabro ps` or
`fabro inspect` at the second factory's server to read the state of a run that is
already there is a READ, and it stays permitted — it is the only way to report
accurately on a run you must not touch. Sending work is what is forbidden.

**THE ROUTE IS STICKY, WHICH IS WHY ONE RE-ROUTE OUTLIVES THE DECISION THAT MADE
IT.** `resolve_dispatch_factory_target` resolves the factory in the order explicit
`--factory`, then `LIVESPEC_FABRO_FACTORY`, then **the factory recorded on the work
item's own ledger metadata**, then `default_factory` — and it then writes the
resolved value BACK onto the item. So a single re-route PINS that item, and every
later dispatch of it goes to the pinned factory with nobody passing anything and
nobody intending it. Measured 2026-08-22: `overseer-v2vs` carried
`dispatch_factory: vps` in its metadata after one re-route, and would have returned
there on any re-dispatch.

Clear a stale pin with

    bd update <id> --unset-metadata dispatch_factory

and READ THE ITEM BACK. Do not use `bd update <id> --metadata @<file>` with an empty
object to do it: measured the same day, that reports `✓ Updated issue` and leaves the
key in place. `--unset-metadata` worked and the metadata read `null` afterwards. This
is the same write-path shape recorded throughout this file — a path that reports
success while writing nothing — and the remedy is the same: verify the read-back,
never the exit message.

Three things make a pin sweep read falsely clean. A default `bd list` omits `closed`
and `backlog` items, so pinned items resting in either state are invisible and the
sweep reports zero. The dispatch journal records the field as `dispatch_factory`,
not `factory`, so a tally keyed on `factory` returns every row unattributed and reads
as though no dispatch ever named a factory at all. And the journal only began
emitting `dispatch_factory` at 2026-08-21T04:12:10Z; a factory census built from the
journal is blind to every dispatch before that instant, and it under-reports silently
rather than erroring. Measured 2026-08-22T09:3xZ against
`tmp/fabro-dispatch-journal.jsonl`: `overseer-fwxl` carried
`metadata.dispatch_factory=vps` from dispatches at 2026-08-17T23:35:30Z,
2026-08-18T00:18:45Z, and 2026-08-18T01:34:56Z, but journal searches missed it and
it was found only by a full ledger metadata sweep over 711 items. The ledger stores
only the LAST route an item took, never a history, so once a pin is cleared neither
the journal nor the ledger can reconstruct that the item was ever pinned. A pin
sweep is evidence only at the moment it was taken; record the result where it was
taken instead of treating the sweep as a repeatable audit.

**DO NOT GO HUNTING FOR THE SEAT THAT CHOSE THE FORBIDDEN ROUTE.** On 2026-08-22 that
search was requested and could not have succeeded, because there was no freelancing
caller: the re-routes were seats correctly following the remedy this very entry used
to prescribe, and later dispatches came from the sticky pin above. When guidance and a
standing instruction disagree, the guidance is the caller.

**IT IS INTERMITTENT — do not escalate this as a factory outage.** The same host
carried a full run to an opened PR thirteen minutes after the failures below; the
evidence is at the end of this entry. Re-try `hp` first unless the standing
maintainer instruction above has been lifted. The diagnosis that follows is
accurate and worth reading in full; only its urgency is not.

Measured 2026-08-22T00:51Z dispatching `overseer-temi26.2` on plugin build
`392b3fa90f86`. The dispatcher's own JSON envelope, stage `fabro-run`, status
`failed`, `fabro_run_id` null:

    could not create run
    ╰─▶ Failed to persist run state: I/O error: creating run directory
        /home/cwoolley/.fabro/storage/scratch/<run>: No space left on device (os error 28)

**While it lasts, the blast radius is the whole factory, not one item.** The failure is in
run-DIRECTORY creation, so it precedes every item-specific step: the ready-set
test, the goal render, the acceptance guard. Nothing about your item causes or
avoids it, and every repo pointing at that factory is down at once.

**BOTH LOCAL INSTRUMENTS READ CLEAN, WHICH IS WHAT MAKES THIS EXPENSIVE.** The
path is on a REMOTE host: `/home/cwoolley` does not exist on the dispatching
machine (the local user is `ubuntu`), and local `df` reported **127G free at 82%
used** at the moment of the failure. So a `df` clears the host, `fabro ps` is
blind for the reason already documented above — the factory is remote — and the
investigator is sent back to the item text, which is the one thing that is fine.
**Read the `detail` string. It names the host's path and the errno.**

**It leaves a phantom claim, and its signature is its own.** Afterwards the item
read `status=active, assignee=fabro` with `fabro_run_id` null and no run in
existence; release it by hand before re-dispatching. Do not read it as any of
the six shapes above: the discriminator is an **immediate** failure at stage
`fabro-run` carrying an explicit ENOSPC `detail` that names the factory's
storage path — not `run-config-overlay` (exhausted credential), not `not in the
ready set`, not a `template_undefined_variable` token, and not silence.

**THE OLD SECOND-FACTORY MITIGATION IS FORBIDDEN HERE, AND THE DRIVE FLAG CLAIM
WAS FALSE.** A generic dispatcher re-route, where permitted, is only reachable
through the dispatcher entrypoint:

    python3 /absolute/path/to/dispatcher.py dispatch --repo <repo> --item <id> --factory <name>

Measured 2026-08-22T08:38Z on plugin build `088d313a361e`: `drive.py` rejects
`--factory` with `drive: error: unrecognized arguments: --factory`, and
`drive.py --help` exposes only `[--repo REPO] [--action ACTION] [--json]` plus a
retired positional. The detached-dispatch verdict `status=failed exit_code=2`
does not distinguish this argparse rejection from a factory refusal; read
`output.log`, not only `verdict.env`.

Do not apply that generic re-route in this repo while the 2026-08-22 maintainer
instruction stands. The measured 2026-08-22 violation was exactly this shape: an
`hp` dispatch of `overseer-6l7v.1` returned stage `capacity-deferred` at
08:36:57Z with the WIP cap saturated, and a follow-up `vps` re-route at
08:39:36Z treated configured topology as approval. It was not approval. A
capacity defer, including `active_count` equal to `wip_cap`, leaves the item
`ready` with no phantom claim and means wait for `hp`, not route elsewhere.

**Expect accumulation, not a spike.** Fabro run state persists per run under
`.fabro/storage`, the documented recovery recipes call `fabro rm --force` only
for specific blocked runs, and `fabro dump` is documented working on runs a week
old — so retention is long *by design* and nothing reaps succeeded runs on a
schedule. A host serving several repos at this fleet's dispatch rate fills.
That also means **a blind purge is the wrong remedy**: `fabro dump` is the fleet's
only rescue path for work stranded by the interview-destroyed shape, so deleting
recent run state to reclaim space trades an outage for the loss of that safety
net. Reclaiming space is host-mutation tier — not session-performable, and not
factory-dispatchable either, since a sandboxed agent cannot clean the host it
runs on. Carrier: `bd-ib-gr9f` (orchestrator tenant).

**IT IS INTERMITTENT, NOT AN OUTAGE — and this correction is here because the
first version of this entry said otherwise.** As filed, it claimed the host "is
out of disk" and that "every dispatch routed to it fails". The sibling tenants'
journals disprove the second half:

    00:51:02Z  overseer-temi26.2                  hp   FAILED at fabro-run, ENOSPC
    00:51:46Z  livespec-console-beads-fabro-jmqb  hp   FAILED identically, another session
    00:55:09Z  livespec-console-beads-fabro-jmqb  vps  re-routed, independently
    01:04:12Z  bd-ib-jb7rzr.10                    hp   dispatch-id issued
    01:18:03Z  bd-ib-jb7rzr.10                    hp   fabro-run COMPLETED, PR opened

The host accepted and completed a full run **thirteen minutes after** the
failures — whatever filled the disk cleared on its own, most plausibly a run
finishing and returning its scratch directory. So the condition is
threshold-shaped: it bites everything routed there while it lasts, and then stops
without intervention.

**Two consequences for how you act on it.** Do not declare a factory outage from
one failure — **re-try or re-route, and check a sibling tenant's journal before
escalating**, because a stop-the-line report costs a maintainer's attention and
this one would have been wrong. And do not read a later success as evidence the
first failure was misdiagnosed: both are real, and the durable defects are that
the host runs close enough to full to fail at all, that neither factory host has
headroom telemetry, and that there is no preflight refusal — the dispatcher
already refuses before sandbox launch for an exhausted credential and names the
condition, and a factory with no room deserves the same.

**The method lesson, which is the transferable part.** The claim was filed from
one observation plus one corroborating failure sixty seconds apart, and a
continuing state was inferred from two points. The check that overturned it cost
a single journal read in a sibling tenant — and it was run while trying to
QUANTIFY the blast radius, not to test the claim. **Quantifying a scope claim and
testing it are the same act**; going to look for the boundary first would have
filed it correctly.

### AN EIGHTH SHAPE: the work MERGED and the POST-MERGE JANITOR failed — and the cause was the REPO, not the item

Measured 2026-08-22 dispatching `overseer-temi26.6`. **This shape is dangerous for
the same reason the fourth one is: its symptom is a `failed` dispatch with a phantom
claim, which the table above maps onto queue eviction — whose remedy is to release and
re-dispatch. Doing that here re-runs work that is already on master.**

The dispatcher's own JSON envelope is unambiguous once read carefully:

    "stage": "janitor-post-merge",  "status": "failed",
    "pr_number": 1624,  "merge_sha": "5e2ba05f97c6…",
    "detail": "post-merge janitor red in fresh checkout
               /home/ubuntu/.worktrees/livespec-overseer/janitor-<item> (kept for diagnosis)"

**`pr_number` AND `merge_sha` ARE POPULATED. That is the discriminator, and it is
available immediately.** Every pre-merge shape in this section leaves both null,
because no PR was ever merged. A stage that runs *after* the merge cannot be evidence
about whether the merge happened — so `status: failed` here means "the repo was red
when we checked afterwards", never "your work did not land".

**THE CAUSE WAS ANOTHER TRACK'S COMMIT.** Master carried a standing ruff `PLR0915`
breach — a function at 31 statements against a budget of 30 — arriving with a merge
hours earlier on an unrelated track. A red master blocks every dispatch in this repo
**and** fails the post-merge janitor of every item that merges into it, so the blast
radius is every track at once while it lasts.

**TWO CHECKS SETTLE IT, AND BOTH ARE CHEAP.**

**The population.** Three post-merge janitors failed inside three minutes, on three
unrelated items in two different repos. *A failure that lands on several unrelated
items at once is a property of the repo, not of any of them.* Grep the dispatch
journal for other `outcome` entries in the same window before diagnosing your own:

    grep '"stage": "janitor-post-merge"' tmp/fabro-dispatch-journal.jsonl | tail

**The direct control, and this is the part worth knowing.** The janitor **keeps its
checkout** and names the path in the `detail` string. That is the exact tree the
janitor judged, so re-running the aggregate there answers the question with a
measurement rather than an argument — through the detached gate runner, since a bare
backgrounded gate is refused:

    cd <the kept janitor checkout>
    mise exec -- just gate-start -- just check     # then gate-wait the printed run id

Here it returned PASSED, exit 0, in 4m48s at the item's own merge sha. The item's tree
was green; the repo was not.

**REMEDY: CLOSE THE ITEM, FIX THE REPO.** Confirm the merge on the forge, record the
verification, and close — never re-dispatch. Then fix master, because until it is
green every subsequent dispatch is refused at the master-CI gate and every merge that
slips through fails its janitor for a reason that has nothing to do with it.

| | succeeded-untransitioned | **janitor-post-merge red** |
|---|---|---|
| `pr_number` / `merge_sha` | (not reported) | **both POPULATED** |
| stage | — | **`janitor-post-merge`** |
| others failing at once | no | **yes — several unrelated items** |
| work landed | yes | **yes** |
| remedy | close it | **close it, then fix master** |

**AND NOTE WHAT THE JANITOR IS ACTUALLY FOR.** It is the only thing in this fleet that
re-tests master *after* a merge; every other gate judges a branch *before* it lands.
That is why a janitor failure is a report about MASTER first and about your item
second — read it that way round.

**How this particular breach got past the pre-merge gates was NOT established**, and
the honest answer is that nobody looked: the repair was the urgent thing and the
forensics were never done. Do not repeat the plausible-sounding story that two
independently-green branches interacted — that is a hypothesis, and an unmeasured one.
If it happens again, the question worth answering is whether the introducing branch's
own CI ran against a merge that already contained the other half.

**AND EXPECT THE REPAIR TO BE REDUNDANT BY THE TIME YOU LAND IT.** A red master is
visible to every track at once, so several seats may fix it independently. Measured
here: a fix written at 11:00Z was still uncommitted at 23:20Z, by which time the owning
track had reverted, applied the *same* split, and re-landed on top — and had added a
seam test under the *same filename* the other seat had chosen. **Re-run the failing
check against current master immediately before committing a repair**, and do not
answer "is it still broken?" by grepping for your own fix's symbol: that instrument is
blind to every other repair of the same defect and will tell you the work is still
needed when it is not.

### A NINTH SHAPE: the run SUCCEEDED, the PR is OPEN, and a RED GATE is holding the merge

Measured 2026-08-23 on `overseer-tdfe.13`, run `01M0PP1ZF673`. **Its discriminator is
`pr_number` POPULATED with `merge_sha` NULL, and it sits exactly between two documented
rows** — the janitor-post-merge shape has BOTH populated and means the work landed;
every pre-merge shape has both null and means it did not. Here the work exists, is
reviewable, and is one gate away from landing.

    verdict.env      status=failed exit_code=1
    fabro ps         absent from the live view
    fabro ps -a      01M0PP1ZF673  SUCCEEDED  82m30s
    envelope stage   merge-poll
    envelope detail  "PR did not reach MERGED within the poll budget"
    pr_number 1833   merge_sha null   fabro_run_id non-null
    ledger           active / fabro

Read either neighbour and you act wrongly: close it as landed when it has not merged, or
release-and-re-dispatch against a live publish branch, which is the collision. **The
remedy is to fix the gate that is holding the merge and let auto-merge land it** — do not
touch the claim, and do not close the row.

**THE CAUSE WILL RECUR ON ANY DISPATCHED ITEM THAT ADDS A SIZEABLE MODULE.**
`check-no-lloc-soft-warnings` (see `.ai/pr-and-gate-mechanics.md`, which records why
it cannot fail when run by hand) failed on three new modules in the 201-250 soft band with
no owning marker. Every other check was green, and the run's own `review_fix` stage had
tried the repair and failed. **So the factory can produce complete, green work and still
be unable to land it over a mechanical debt gate**, after which the dispatcher reports
failure about work that is fine.

**And the marker alone is NOT sufficient.** `tests/test_lloc_owner_marker_liveness.py`
refuses any marker naming an owner outside an ENUMERATED set, so the marker and its pin
registration must land together. Worse, the pre-commit aggregate reported that failure as
`check-per-file-coverage` and `check-coverage` **while coverage was 100.00%** — the real
failure was one assertion inside a differently-named target. Same shape as the LLOC check
itself: the reported target name points away from the cause.

### THE ENVELOPE'S `status` DESCRIBES THE STAGE THAT GAVE UP, NOT THE RUN

This supersedes the narrower "read the `detail`, not only the `status`" rule recorded
above, and it is the generalisation two independently-measured shapes now support:

- a **transport** `detail` (a timeout, a body read, a connection) means the envelope is
  reporting on the DISPATCHER's health;
- a **merge-poll** `detail` means it is reporting on the FORGE's state.

Neither is evidence about the run. **The envelope's `status` is evidence about the run
only when the stage that failed IS the run** — and only the `detail` says which stage that
was. In every other case the run outcome comes from `fabro ps -a` on the owning factory,
and whether the work landed comes from the forge.

### THE GITHUB APP INSTALLATION PIN CANNOT BE PASSED THE OBVIOUS WAY — the credential wrapper scrubs it

Measured 2026-08-23T02:1xZ, dispatching `overseer-au3pt3.16.3`. This one refuses with a
message that names the exact remedy you just applied, which is what makes it expensive.

Since the App gained a second installation, `resolve_installation_id` fails closed on
anything other than exactly one unless pinned, and every dispatch from this repo is
refused before sandbox launch:

```
"detail": "C-mode dispatch refused: GitHub App token mint failed: the App has 2
 installations; set GITHUB_APP_INSTALLATION_ID to pin the one to mint for",
"stage": "run-config-overlay", "status": "failed", "fabro_run_id": null
```

**Setting the variable before `drive.py` does NOT work, and it fails silently.** `drive.py`
re-execs itself under the `credential_wrapper` whenever credential env is absent, and the
wrapper's stage-1 hop is an `exec env -i` with a short explicit allowlist. A caller-set
`GITHUB_APP_INSTALLATION_ID` is scrubbed there and never reaches the dispatcher, so the
refusal above is what you get back — telling you to do the thing you did.

Its `OPENV_PRESERVE_VARS` allowlist does not rescue it either: measured, the exact name
still does not survive, presumably dropped at the `sudo` hop before the allowlist is read.

**THE WORKING FORM sets the variable INSIDE the wrapper invocation**, after the scrub, so
`drive.py` never needs to re-exec at all:

```
scripts/detached-dispatch.sh "$run_dir" -- \
  /usr/local/bin/with-livespec-env.sh -- \
  env GITHUB_APP_INSTALLATION_ID=<id> \
  python3 <build>/scripts/bin/drive.py --action impl:<id> --repo <repo> --json
```

**Probe either claim in one second, and probe rather than reasoning about it** — the two
forms differ only in where four words sit:

```
GITHUB_APP_INSTALLATION_ID=<id> with-livespec-env.sh -- env | grep '^GITHUB_APP_INSTALLATION_ID='   # nothing
with-livespec-env.sh -- env GITHUB_APP_INSTALLATION_ID=<id> env | grep '^GITHUB_APP_INSTALLATION_ID='  # the value
```

**THE NEAR-MISS NAME IS THE PART THAT WILL COST SOMEONE AN HOUR.** The wrapper DOES inject
`GITHUB_APP_INSTALLATION_ID_E2E`, and its value is a DIFFERENT installation from the one
this repo must mint for. So an investigator who dumps the environment finds a
plausible-looking installation id already present and concludes the pin is set. That is
the same asymmetric-discoverability shape as the `CLAUDE_CODE_OAUTH_TOKEN` versus
`ANTHROPIC_API_KEY_LIVESPEC_E2E` trap above: two real credentials, adjacent names, only
one correct for the path in use. **Match the name exactly, `_E2E` suffix included, before
concluding anything.**

**THE PIN IS A PER-INVOCATION WORKAROUND, NOT A FIX, and the distinction matters
because the callers still failing are the ones no relay reaches.** An automatic caller —
the central autonomous loop — cannot learn an env var from a message to a seat, so
unpinned dispatches keep being refused (observed again at 02:04:44Z on an unrelated item,
identical stage and identical message, while this form was working here). Until the pin is
set where that loop reads it, or the second installation is removed so discovery resolves
with no pin anywhere, expect refusals from callers you do not control — and do not read
one as evidence that your own invocation form is wrong.

Signature, since it collides with nothing else in this section: `drive.py` exits non-zero,
the envelope names stage `run-config-overlay` with `fabro_run_id: null`, no run is created,
and — unlike the exhausted-credential refusal at the same stage — **no phantom claim is
left**; the item stays `ready` with no assignee.

### A DEFERRED item ANYWHERE in the tenant blocks EVERY dispatch in the repo

Measured 2026-08-19. This trap is not about your item, and its error text names
ids that have nothing to do with what you dispatched.

    LEDGER: status-conformance  <other-id>  status 'deferred' is outside the
      livespec lifecycle (allowed: acceptance, active, backlog, blocked,
      closed, pending-approval, ready)
    ERROR: pre-dispatch ledger checks failed; dispatch blocked

The pre-dispatch ledger check is a GLOBAL conformance sweep over the whole
tenant, not a check on the requested item. ONE non-conforming row refuses EVERY
dispatch in the repo until it is cleared.

**The cause is a TOOLING CONFLICT, not operator error, which is why it recurs.**
`bd` offers `--defer <date>` on both `create` and `update` ("Defer until date.
Issue hidden from bd ready until then"), and using it sets `status=deferred`
plus a `defer_until` timestamp. That status is native to the substrate and
absent from the orchestrator's allowed set above, so an ordinary, supported
scheduling action by ONE thread silently disables the factory for EVERY thread.
Nothing in the refusal points at the deferring action, and the deferring session
gets no signal at all.

**Check the horizon before deciding to wait it out.** `defer_until` is
arbitrary. The instance measured here had one item deferred about six hours and
another a full WEEK, so "wait for it to clear" was a seven-day answer.

**Its signature is in none of the shapes above — do not read it as one.**

| | this trap | anchor-as-dep |
|---|---|---|
| `drive.py` exit | 1 | 1 |
| dispatcher exit | **1** | 3 |
| error text | `status-conformance`, naming OTHER ids | `not in the ready set` |
| fabro run | none | none |
| phantom claim | **no** | no |

Dispatcher exit **1** with a `status-conformance` line is the discriminator. No
run is created, so there is nothing to find in `fabro ps -a` and nothing to
release.

**The remedy is NOT to un-defer someone else's item.** A deferral is a
deliberate scheduling decision by the thread that owns the item, and reverting
it discards that intent. Route it to that thread and ask for the intent to be
re-expressed as a conforming status with the horizon recorded in a comment or in
metadata: that unblocks the tenant immediately and keeps the schedule. Only the
owning thread should change it.

**Verify AFTER the whole repair, never between commands.** Clearing a deferral
with an empty `--defer` lands the item at the bd-native intermediate that is
itself outside the allowed set — so the documented remedy RE-TRIGGERS the same
global refusal mid-repair, and a repairer who checks the tenant between the
clear and the status-set watches it flip back to blocked and concludes the fix
is failing. Do the clear and the status-set as a pair, then verify once.

**That paragraph used to be fenced as an unreproduced report, and the fence is
now retired.** It is measured, and it is filed: `bd-ib-cleg6g` (orchestrator
tenant) carries it as its Defect 3, with the safe ordering recorded from the
live repair. Its acceptance requires the fix to cover the CLEAR path and not
only the set path — which is exactly the leg an implementer would otherwise
skip, since the set path is the one the bug report is written about.

**Two further things that item establishes, both of which change how you read
this section.** First, the incident it records happened HERE — measured live in
this tenant, roughly forty minutes of tenant-wide dispatch refusals, stop-the-
line. Second, and worse for anyone relying on tooling to protect them:
**bd-guard does NOT guard the `--defer` flag, and its own documentation of why
is false.** The guard blocks the `defer` SUBCOMMAND while deliberately passing
the FLAG through, documented as "a defer-date FLAG that writes no status". On
the deployed bd that premise was measured false — the flag DOES set the status.
So the trap is armed by default and the guard is not standing between you and
it.

**Do not let the immediate unblock close the underlying defect.** A consumer
that hard-blocks on a first-class status its own substrate produces will break
the fleet again the next time anyone uses a documented flag. That belongs in the
orchestrator tenant, sibling to the delimiter-token defect above. Likewise, any
conformance checker written to detect this needs a discriminating control
proving it REPORTS a genuinely non-conforming row — a scan that quietly
whitelists a status it should flag reports a clean tenant and is worse than no
scan.

### RETRACTED: `bd create --ephemeral` does NOT block dispatch — `open` is auto-healed

**This entry previously claimed the opposite, and the claim was wrong.** It is
kept rather than deleted because the wrong version was published here and
routed to another repo's foreman, who folded it into a tracked item as a third
defect channel. A silent deletion would leave that claim circulating with
nothing to find when someone came looking.

**What was claimed:** that `bd create --ephemeral` leaves a row at `open`, that
bd-guard exempts ephemeral from its backlog normalization, that the
conformance sweep has no ephemeral filter, and therefore that such a row
refuses every dispatch in the tenant.

**What is actually true — measured in the dispatcher's own source:**

- `_dispatcher_ledger_close.py` defines `_NATIVE_STATUS_REMAP` mapping `open` →
  `backlog` and `in_progress` → `active`, and the apply function WRITES that
  remap to the store.
- `_dispatcher_ledger_gate.py` orders the work: load, plan the remaps, heal and
  report, and only THEN run the ledger checks over the *projected* items. So
  `open` is healed in place and never survives to become a residual
  status-conformance finding.
- Only KEY-MISSES block — `deferred`, hooked, ad-hoc, unknown. **That is why
  the `--defer` trap above is real and this one is not.** The two statuses are
  not interchangeable, and the whole error was assuming they were.

**The design says so explicitly, and reading it first would have prevented
this.** The gate's own docstring: *"On a SHARED tenant the two transient
statuses appear CONTINUOUSLY (any active session's raw `bd create` lands
`open`; any raw `bd update --claim` lands `in_progress`). A detect-and-fail
gate blocks every session on any OTHER session's fresh transient item —
constant cross-session friction."* An ephemeral row at `open` is precisely the
case that design accommodates on purpose.

**What survives, and it is small.** Two measured facts still hold: the row IS
created at `open`, and bd-guard DOES exempt `--ephemeral` from its own
normalization. The consequence drawn from them does not, because a second layer
heals what the first declines to. The only residue worth knowing is a curiosity
rather than a hazard: a wisp row — documented as "not exported to JSONL", i.e.
deliberately disposable — gets mutated to `backlog` in the store by the
auto-heal on the next gate or dispatch run.

**Still delete a probe row when you are done with it.** That advice was right
for the wrong reason. The reason is tidiness in a shared tenant, not blast
radius.

**WHICH SURFACE YOU RUN DECIDES WHAT YOU SEE, and this is the part that
reconciles the retraction with a contradictory-looking report elsewhere.**
"Auto-healed" is true of the GATES and not of the bare check:

| surface | heals first? | reports `open`? |
|---|---|---|
| pre-dispatch (`ledger_blocked_after_normalization`) | yes — writes + journals | no |
| pre-push gate (`run_ledger_gate`) | yes — writes, prints each remap | no |
| `ledger-normalize` | yes (or projects, under `--dry-run`) | no |
| bare `ledger-check` | **NO** | **YES** |

So the intake status **never blocks a dispatch or a push**, and a standalone
`ledger-check` **does** report it. Both statements are true and they are about
different code paths — the pre-dispatch entry point is literally named
*after normalization*, while the plain check loads and runs the checks with no
remap step at all.

**Why that matters beyond pedantry.** An orchestrator-tenant item records a
repair in which clearing a deferral left the item at this status and appeared to
re-trigger a global refusal mid-repair. That reads as contradicting everything
above — and it does not. A repairer checking the tenant BETWEEN commands runs
the standalone check, which is exactly the surface that does not heal. The
dispatch that would have healed it never ran. **Both measurements are correct;
they were taken on different surfaces.**

So when you see a conformance finding for this status, ask which surface
produced it before concluding anything is blocked. And if you are writing
acceptance criteria around it, name the surface — an acceptance written as "the
status no longer appears" is satisfiable on one path and meaningless on
another.

**The method lesson, which is the reason this stays here.** The original entry
*fenced itself correctly* — it stated in terms that a dispatch refusal had not
been observed, and marked the blast radius as inherited from the `--defer` trap
rather than reproduced. **The fence named exactly the leg that turned out to be
false.** What was missing was the cheap follow-up the fence implied: read the
dispatch path to see whether the refusal *could* occur, instead of assuming it
transferred from a neighbouring status. A fence is only worth what you do about
it, and an unactioned fence reads to everyone else as diligence.

### A LEDGER-EDIT item can never be factory-dispatched

Measured 2026-08-04. If an item's deliverable is a beads mutation rather than a repo
change, no sandboxed agent can satisfy it: the fabro sandbox has no `bd` on PATH, no
`/usr/local/bin/bd`, no `BEADS_DOLT_PASSWORD` and no `.beads/metadata.json`, and the
assignment forbids writing a `.beads/` directory, so the documented recovery path is
closed too. The run reports the blocker honestly and parks at
`blocked(human_input_required)`, holding a claim until force-removed.

Tier such items supervisor/host and do them with the credential wrapper. The tell at
filing time: the acceptance is phrased as `bd show <id>` reading a certain way.

### "dispatcher plugin build is stale" names a remedy that appears to do nothing

```
ERROR: dispatcher plugin build is stale; executing build <old> predates
latest release <new>. Run `claude plugin update ...` before dispatching.
```

Running the update (or `just ensure-plugins`) **is correct and does work** — but
**a running session keeps its originally-resolved plugin path**, so the
Skill-resolved `drive.py` is still the old build and re-running the same command
reproduces the identical error. It reads as "the remedy is broken".

**Ruling, measured 2026-08-03:** dispatch-time absolute-path resolution is the
sanctioned remedy for an already-updated-but-stale session. It does not bypass
the stale-build gate; it uses the build that the gate itself names as current.
Session restart remains acceptable, but it is not required before routine
dispatch. The older Gate 1 sentence in
`plan/archive/background-shell-supervision-liveness/handoff.md` that equated this
with `--no-verify` is retired for dispatch commands.

Invoke the new build by ABSOLUTE PATH instead:

```
python3 ~/.claude/plugins/cache/livespec-orchestrator-beads-fabro/\
livespec-orchestrator-beads-fabro/<new-build>/scripts/bin/drive.py --action impl:<id> ...
```

Confirm which build is current with `just ensure-plugins` (it prints
`already at the latest version (<build>)`), then point at that directory.
Take the build id from `ensure-plugins`' own output, never from the error
message: the `<new>` id the error names is whatever was latest when the stale
build resolved, and can itself be superseded by the time you read it — pointing
at it reproduces the refusal with a fresher pair of ids (measured 2026-08-19).

**AND ITS FOUR-WAY SIGNATURE IS NOT UNIQUE — IT COLLIDES WITH THE
ANCHOR-AS-DEPENDENCY ROW OF THE TABLE ABOVE.** Measured 2026-08-21 dispatching
`overseer-7pqr3p`. A stale build refuses with `drive.py` exit **1**, dispatcher
exit **3**, **no** fabro run, **no** dispatch-id in the journal, and **no**
phantom claim — the item stays `ready` with no assignee. That is character for
character the reading the table maps to "anchor-as-dependency", whose remedy is
to inspect and possibly unset a dependency edge. Following it sends you looking
for an edge that is not there: status was `ready`, there was no `depends_on` of
any kind, and the repo's own `dispatch_acceptance_guard.py` returned `ok`.

**The refusal text is NOT in the detached run's `output.log`.** That file held
only the credential re-exec line and `drive`'s four-line report — status failed,
dispatcher exit code 3, "did not report green". `drive` swallows the
dispatcher's own stderr, so the one sentence naming the cause never reaches the
place a loop-parked session is told to read.

**So on any dispatcher exit 3 with no run, re-invoke the dispatcher DIRECTLY and
read its refusal before reasoning from the exit-code table:**

```
python3 <build>/scripts/bin/dispatcher.py dispatch \
  --repo <repo> --item <id> --json
```

It refuses before any sandbox work, creates no run, costs no spend, and prints
the actual cause. The table's rows are discriminators only once you have the
message; they are not a substitute for it.

**The window is narrower than it looks.** These two dispatches were nineteen
minutes apart: `overseer-vr3ym4.1` went out on build `15a4ae9aff88` at
06:29:42Z and succeeded; `overseer-7pqr3p` was refused on that same build at
06:48:48Z because `15b9787566a7` had been released in between. A build id
resolved at the top of a session — or even one that worked a quarter of an hour
ago — is not evidence about the next dispatch. Re-read `ensure-plugins` per
dispatch, not per session.

### A TENTH SHAPE: the envelope says GREEN, the PR is MERGED, and the row still reads `active`

Measured 2026-08-30, twice in one afternoon, dispatching `overseer-2a1` and `overseer-403`
from this repo. Both returned `stage: done`, `status: green`,
`detail: "merged, post-merge janitor green"`, exit 0. Both PRs merged (2081/`e1fc24bd`,
2083/`874db41d`). Both rows then read `active` with assignee `fabro`.

**DO NOT READ THIS AS A STRANDED CLAIM.** That is the expensive misdiagnosis, and it is
the one this section exists to prevent — the documented hygiene for a REFUSED dispatch is
to release the claim by hand, and applying it here is wrong in a way that hides the real
condition. The discriminator is a LABEL, not the status:

| | label on the row | meaning |
|---|---|---|
| accepted | `resolution:completed` | the valve passed it; the row closes normally |
| **failed by the valve** | **`rework:pending`** | the post-merge acceptance valve FAILED it |

`rework:pending` is stamped by exactly two entries — "the under-cap dispositive FAIL of the
post-merge acceptance valve" and the human `reject:<id>:rework` valve — per
`_store_rework_mutations.py`, which owns the vocabulary. `active` is then the row's CORRECT
state: the ratified contract keeps `acceptance → active` and makes fix-forward executable
through the marker, which is the rework drain's selection input.

**That module also carries a standing invariant: an item whose status is not `active` MUST
NOT carry the marker.** So "tidying" such a row to `acceptance` or `closed` creates a
forbidden state and takes it out of the drain. Measured: doing exactly that to
`overseer-2a1` had to be reverted.

**THE ENVELOPE CANNOT TELL YOU ANY OF THIS.** It reports through the janitor stage only;
the acceptance valve runs afterwards, outside the envelope, and can fail work the envelope
already called green. **Check the row's LABELS after every dispatch, not just its status
and the envelope.**

#### The reason is in the JOURNAL and nowhere else

`_dispatcher_acceptance_rework.py` routes both disposition records through
`JournalFile.append`, so a failed pass leaves `rework:pending` on the row with **no readable
reason on the ledger at all**. Read `tmp/fabro-dispatch-journal.jsonl` and find the record
carrying a `criteria` key for the item; its `checks` array gives per-criterion `passed` and
`reason`:

```
python3 - <<'PY'
import json
WID = "overseer-403"
for line in open("tmp/fabro-dispatch-journal.jsonl"):
    line = line.strip()
    if not line:
        continue
    rec = json.loads(line)
    if rec.get("work_item_id") != WID or "criteria" not in rec:
        continue
    for check in rec["criteria"].get("checks", []):
        if not check.get("passed"):
            print(check.get("reason"), "|", check.get("text")[:100])
PY
```

#### What it actually fails on, and why re-dispatching first is destructive

Both 2026-08-30 failures were on fragments that are **not requirements at all**:

```
"AUTONOMY TIER: factory."                 no merged diff or telemetry evidence
"AUTONOMY TIER: dispatch-safe."           insufficient merged diff evidence
"NO WEAKENING IS INTRODUCED BY THE FIX."  no merged diff or telemetry evidence
```

The third is a section HEADING whose substantive body is the next sentence and passed. The
implementations were correct — verified independently: 27 tests across those merges run
green on the operator host.

**Measured over 1,975 graded checks in this repo's journal, the driver is FRAGMENT LENGTH**,
not category. Failed checks have median 66 characters against 97 for passed; fragments under
40 characters fail at **46.9% against a 10.2% baseline**. Two tempting explanations were
tested and BOTH FAILED, so do not re-derive them: a metadata prefix appears in 3.9% of passed
and 4.0% of failed checks (no signal), and negation — the theory that a prohibition cannot be
evidenced by a positive diff — runs the WRONG WAY, appearing in 51.3% of passed checks against
31.2% of failed. The likely mechanism is token overlap: a short fragment carries too few
distinctive tokens to match the merged diff, which is the literal reason string on 143 of 202
failures. The refinement is in one item's own pass: `overseer-403` FAILED
`"NO WEAKENING IS INTRODUCED BY THE FIX."` (38 chars) while PASSING
`"THE FALSE DOCSTRING IS CORRECTED."` (33 chars) — the shorter one passed, because
`docstring` is in that diff.

**Fix the acceptance TEXT before any rework re-dispatch.** The disposition record says so
itself: the rework dispatch "deliberately reaches acceptance again, so an unfixed criteria
fragment re-fails there and spends another `acceptance_rework_cap` attempt — on the last
attempt converting a recoverable state into blocked / needs-human." The cap is 2. A
re-dispatch that changes only code burns the last attempt on the same fragment.

**Pre-screen before dispatching** rather than discovering this after the fact: scan the
item's acceptance field for standalone sentences under ~60 characters whose vocabulary the
diff will not contain — headings and routing metadata are the usual carriers. Relocating a
routing line into the DESCRIPTION avoids it entirely; the description is not graded, which is
why a sibling dispatched the same day on the same build passed with its tier recorded there.

Upstream carrier for the evaluator defect: `bd-ib-vbm7` in the
`livespec-orchestrator-beads-fabro` tenant. It is a new member of a family already fixed
twice — `bd-ib-mhhg` (segments on line breaks) and `bd-ib-ujihbw.12` (fuses across a trailing
abbreviation boundary), both CLOSED — so verify the current behaviour rather than assuming
either fix covers this.
