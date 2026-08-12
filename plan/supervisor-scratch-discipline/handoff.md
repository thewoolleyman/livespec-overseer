# Plan — supervisor-scratch-discipline

**Owning repo:** `livespec-overseer`. **Ledger anchor:** epic
**`overseer-5jttov`** (this repo's beads tenant). **Status: read it from the
ledger** — `/livespec-orchestrator-beads-fabro:list-work-items --json` and
`/livespec-orchestrator-beads-fabro:next`. This file stores no status and
carries no checkbox queue.

Created 2026-07-28 at maintainer direction, after an audit found 1,811 lines of
prose — including a groom draft and a staged set of workflow files — living in a
gitignored directory with zero durable backing.

## Read-first chain

1. This file.
2. `research/what-was-in-tmp-supervisor.md` — the audit, the three specific
   hazards, the disposition already applied, and the CI-blindness constraint
   that shapes any fix.
3. `research/brief-mirroring-verification.md` — goal 3's measurement: the
   per-brief mirroring trace and the brief-14/brief-18 count discrepancy.

That is the whole chain.

## The rule — stated by the maintainer, verbatim in effect

> Only JSON can live in `tmp/supervisor/`, and the only place prose can live is
> `tmp/supervisor/briefs/`, which should ONLY hold briefs for the supervised
> session to read.

Two corollaries follow, and both are load-bearing:

- **A brief may CITE but never CONTAIN.** Anything load-bearing must be landed
  first — ledger item, research note, or charter Corrections entry — and the
  brief then points at it. This is what makes the directory safe to lose:
  nothing important can be in it, because anything important had to be durable
  before it could be cited.
- **A changeset is never an artifact.** A staged set of proposed file changes,
  with diffs and a description of intent, held for review before landing, IS a
  branch and a pull request. Hand-rolling one gives every downside of git and
  none of the upside — no review, no CI, no history, and silent drift. If a
  change is worth staging it goes on a branch; if it is not ready for a branch
  it is not ready to be a file, and belongs in the ledger or a research note.

## Goals, each with its acceptance

**Acceptance is mechanical or demonstrated-red. "The rule is written down" is
not acceptance** — this repo has shipped two rules that ran and could not fail
(`check-no-workflow-edits`, in neither the aggregate nor CI;
`LIVESPEC_RUN_MUTATION`, a verified no-op), and the whole point of this thread
is that convention already failed once.

| # | goal | acceptance |
|---|---|---|
| 1 | **The rule ships in the generated supervisor charter**, so every future supervisor inherits it rather than rediscovering it | The prose contract `.claude-plugin/prose/supervise-plan.md` carries the rule and both corollaries, and a fixture over GENERATED output goes RED when the rule is absent — demonstrated red, not asserted |
| 2 | **An enforcement check that can actually fail** — `tmp/supervisor/` contains only `*.json`; `tmp/supervisor/briefs/` contains only briefs; nothing else anywhere beneath it | A planted violation (a stray `.md` at top level, a non-brief under `briefs/`) turns the check RED, demonstrated. The check must state in its own output that it is LOCAL-ONLY and cannot fire in CI, because `tmp/` is gitignored |
| 3 | **Verify the existing briefs are already mirrored** — the audit asserts "mostly mirrored" from knowledge, not from measurement | **Done.** See `research/brief-mirroring-verification.md`: 16 of 16 present briefs traced to a landed artifact; 0 unmirrored (the handoff's "nonzero is expected" was itself an unmeasured guess). `brief-14.md`/`brief-18.md` from the claimed 18 do not exist on disk — unexplained, flagged as open. This measurement could not run factory-side — it reads the gitignored, local-only `tmp/supervisor/briefs/`, which no sandbox clone has — so it ran host-side in the planning session instead of being filed to the ledger |

## Ordering

Goal 3 is independent and can run first or in parallel — it is measurement over
existing files and blocks nothing. Goals 1 and 2 are independent of each other.
There is no hard edge between any of the three.

Suggested first slice: **goal 2**. It is the smallest, it makes the rule
self-policing on the machine where the risk lives, and it converts every future
violation from a judgement call into a red check.

## Scope boundary — do not silently widen

The maintainer scoped this to `tmp/supervisor/`. The same hazard exists for
anything an agent writes outside SCM and the ledger, and that generalization may
be correct — but it is a **different, larger thread** and must not be absorbed
here without an explicit decision. Name it if you find it; do not take it.

## Status — 2026-08-12. Goal 3 done. Goals 1 and 2 DISPATCHED, in flight. THIS THREAD IS ACTIVE, NOT ARCHIVED.

`overseer-5jttov` was groomed and is `status: done` / `resolution:
no-longer-applicable` — administratively retired because its content was split
into two replacement ledger items:

- `overseer-otjmoh` — goal 2, the `tmp/supervisor/` enforcement check.
- `overseer-m4o33z` — goal 1, the charter rule + corollaries.

Goal 3 is measured and landed in-thread (see the read-first chain above) and
was never filed to the ledger — it is not factory-dispatchable (see the goals
table).

**Do not archive this thread** until goals 1 and 2 are each implemented,
merged to `master`, and (if this repo cuts a release for the change) shipped
in a release and confirmed working. An epic/work-item's ledger STATUS is
never evidence of real-world completion by itself; only a merged PR, green
CI on `master`, and (where a release applies) a shipped-and-verified
artifact are. **This is not theoretical — see "The premature-archival
incident and fleet-wide fix" below: this exact thread was already archived
prematurely once, on this exact reasoning error, and had to be corrected.**

### Dispatch status — both goals are RUNNING as live Fabro factory runs right now

Dispatched 2026-08-12 via `/livespec-orchestrator-beads-fabro:drive --action
impl:<id>`. **First attempt failed** with `dispatcher exit code: 3,
"Dispatcher did not report green"` — this was NOT a real implementation
failure; it was the documented "dispatcher plugin build is stale" trap (the
session's resolved plugin path predated the latest release). Master CI was
confirmed green on both repos at the time, ruling out the more common
red-master cause. **Remedy applied:** re-invoked `drive.py` by absolute path
at the current build
(`~/.claude/plugins/cache/livespec-orchestrator-beads-fabro/livespec-orchestrator-beads-fabro/441050295f31/scripts/bin/drive.py`
— confirm this is still current with `just ensure-plugins` before trusting
the path; a newer build may exist by the time you read this). That
re-dispatch succeeded in creating real runs:

| item | Fabro run id (at dispatch time) | status at dispatch time |
|---|---|---|
| `overseer-otjmoh` | `01KZSPRJCQQX` | running |
| `overseer-m4o33z` | `01KZSPRNWA8E` | running |

(Two more items in sibling repos were dispatched in the same batch — see "The
premature-archival incident and fleet-wide fix" below for the full cross-repo
picture: `bd-ib-ycihm7` and `livespec-dev-tooling-q3emww`.)

**These are independent, server-side Fabro runs — they do NOT depend on any
Claude Code session staying alive.** Confirmed live: killing this session's
local `drive.py` polling subprocess (via `TaskStop`) did not affect the
Fabro runs' `running` status or reset their duration counters. So this
session's wind-down does not abandon them.

**On resume, do this first, before anything else:**

```bash
/home/ubuntu/.local/bin/fabro ps -a
```

Check `overseer-otjmoh` and `overseer-m4o33z` specifically. Per this fleet's
own documented dispatch traps (`.claude/CLAUDE.md` §"Dispatch traps whose
error messages point AWAY from the fix"):

- **If still `running`/`starting`**: just wait, or check back later. Do not
  re-dispatch.
- **If `succeeded` in `fabro ps -a`**: check whether a PR merged (`gh pr list
  --repo thewoolleyman/livespec-overseer --state merged --search
  "overseer-otjmoh"` or similar) before assuming it's actually landed — a
  `succeeded` run whose item was never ledger-transitioned is a documented
  trap (`CLAUDE.md`'s "fourth shape"). If it merged, update this Status
  section with the PR number and merge evidence.
- **If `failed`**: read why (`fabro attach <run-id>` or the run's own
  output) before re-dispatching. A `failed` run may have hit a stuck
  interview — check whether real work was lost or whether it's simply
  blocked on a question a human now needs to answer.
- **Absent from `fabro ps -a` entirely** (neither `running` nor listed as
  terminal): possible queue eviction (another documented trap) — check the
  ledger item's status; if it reads `active`/assigned but no run exists
  anywhere, that's a phantom claim — release it by hand and re-dispatch.

**Do not trust the ledger item's `status` field alone for either item.**
Verify against `fabro ps -a` and the actual PR/merge state, exactly as this
whole thread's central lesson demands.

## The premature-archival incident and fleet-wide fix (2026-08-05 through 2026-08-12)

This is NOT part of goals 1–3 above — it is a separate, serious incident
this thread's own execution caused and then had to fix, spanning four repos.
Recorded here in full because it is exactly the kind of thing a resuming
session must not silently miss.

**What happened:** after goals 1 and 2 were groomed and filed (see above),
an earlier revision of this handoff **archived this thread** to
`plan/archive/` in the same commit — reasoning "the epic is closed, and this
repo's plan-thread rule says archived iff epic-closed." That PR merged (repo
auto-merge) before the maintainer caught it: both replacement items were
still `ready`, undispatched, zero code written. The maintainer's correction
(verbatim): *"By default, nothing should be archived until it is done,
tested, proven, fully merged, shipped to production... and deployed
everywhere it needs to be, and proven to be working in prod after
deployment."*

**Root cause:** `livespec-orchestrator-beads-fabro`'s `plan.md`/`contracts.md`
and `livespec` core's fleet-wide **Archive-on-epic-close** Conformance
Pattern member all treat *any* epic-closed status as archival justification,
never distinguishing a *procedural* closure (`groom`'s regroom-out: content
moved to new tickets) from a *completion* closure (work actually shipped).

**Corrections landed (all merged):**
- `livespec-overseer` PR #756 — un-archived this thread, corrected the
  status text.
- `livespec` PR #2066 (incident evidence, added to the existing open
  `planning-lane-redesign` thread) + PR #2074 (self-correction: an
  overclaim that "no mechanical verifier exists" was wrong — one does exist,
  `plan_thread_epic_parity`, it's just unarmed fleet-wide and points the
  wrong direction for this failure shape).
- `livespec-orchestrator-beads-fabro` PR #1314 (new plan thread
  `plan-archive-completion-gate`, epic `bd-ib-2vaeny`) + PR #1317
  (self-correction + re-scope: the mechanical-verifier goal moved entirely to
  `livespec-dev-tooling` since the check is shared code; `bd-ib-2vaeny`
  regroomed-out into the single correctly-scoped `bd-ib-ycihm7`).

**Fleet-wide sweep finding:** a background investigation swept all 9 local
fleet repos' `plan/archive/` trees for other victims of the same defect.
Found ONE confirmed prior incident, independent of this one: `homelab`
thread-05 epic `hl-6uldtn`, self-corrected 2026-08-03 — **two days before**
this incident, unrelated repo, zero shared context. Its false closure also
**cascaded** (a `depends_on` edge on the closed epic false-signaled readiness
to an unrelated downstream thread). Two independent occurrences of the
identical failure shape within 3 days is first-hand evidence this is
systemic, not a one-off. Recorded as corroborating evidence directly on the
fix item via `bd update --append-notes` (non-destructive ledger note, not a
new PR).

**Ledger items filed for the actual fix (cross-repo, all `ready`):**
- `bd-ib-ycihm7` (`livespec-orchestrator-beads-fabro`) — correct the
  prose/spec text. **Dispatched 2026-08-12, run `01KZSPRVF9E2`** — check
  `fabro ps -a` same as goals 1/2 above.
- `livespec-dev-tooling-q3emww` (pre-existing, found independently by another
  thread the same day as the homelab incident) — fixes the converse gap: an
  archived thread whose anchor epic is still open passes green today.
  **Dispatched 2026-08-12, run `01KZSPSTPFX6`** — check `fabro ps -a`.
- `livespec-dev-tooling-5asgvm` — fixes THIS incident's specific gap:
  descendant-completion checking (an archived thread whose anchor closed via
  regroom-out, with live undisposed replacement descendants, passes green
  today). **NOT YET DISPATCHED — deliberately held.** Both `q3emww` and
  `5asgvm` touch the same check family (`plan_thread_epic_parity` and
  siblings) in the same repo; dispatching them simultaneously risked file
  collisions or two factory agents designing incompatible solutions blind to
  each other. **Dispatch `5asgvm` only after `q3emww` has merged**, so its
  implementer can see `q3emww`'s actual shipped shape:
  ```bash
  # confirm current build first: just ensure-plugins
  python3 <current-build>/scripts/bin/drive.py --repo /data/projects/livespec-dev-tooling --action impl:livespec-dev-tooling-5asgvm
  ```

**None of goals 1, 2, `bd-ib-ycihm7`, `q3emww`, or `5asgvm` are done.** They
are dispatched-or-about-to-be, running in independent Fabro sandboxes. Do not
report any of this as complete, do not archive anything, until each has a
real merged PR to point at.

## Next action

1. `/home/ubuntu/.local/bin/fabro ps -a` — check `overseer-otjmoh`,
   `overseer-m4o33z`, `bd-ib-ycihm7`, and `livespec-dev-tooling-q3emww`
   (see "Dispatch status" above for how to interpret each state).
2. For each that's `succeeded`: verify a PR actually merged before treating
   it as done; update this Status section with the evidence.
3. For each that's `failed`: diagnose (don't blindly re-dispatch — see the
   trap table above).
4. Once `livespec-dev-tooling-q3emww` has a merged PR, dispatch
   `livespec-dev-tooling-5asgvm` (command above).
5. Only once ALL FIVE items (goals 1/2 here, plus the three fleet-wide fix
   items) have real merged PRs: come back to this handoff, replace this
   whole "Status"/"Dispatch status"/"premature-archival incident" section
   with a short completion summary citing every PR, and only THEN consider
   archiving — re-running the plan operation's handoff self-sufficiency gate
   first, same as any other refresh.

Do not hand-code implementation inline in a planning session — the factory
path (`drive --action impl:<id>`) is the only implementation path for any of
this.
