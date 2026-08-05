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

## Status — goal 3 done; goals 1 and 2 filed but NOT started. THIS THREAD IS ACTIVE, NOT ARCHIVED.

`overseer-5jttov` was groomed and is `status: done` / `resolution:
no-longer-applicable` — administratively retired because its content was split
into two replacement ledger items. **That status transition is not evidence
that any work shipped.** As of last check, both replacements are `status:
ready`, unassigned, undispatched — zero code written, zero PRs opened:

- `overseer-otjmoh` — goal 2, the `tmp/supervisor/` enforcement check.
- `overseer-m4o33z` — goal 1, the charter rule + corollaries.

Goal 3 is measured and landed in-thread (see the read-first chain above) and
was never filed to the ledger — it is not factory-dispatchable (see the goals
table).

**Do not archive this thread** until goals 1 and 2 are each implemented,
merged to `master`, and (if this repo cuts a release for the change) shipped
in a release and confirmed working — not merely filed, not merely
"dispatched," and not merely pointed at by a ledger item whose status says
something terminal. An epic/work-item's ledger STATUS is never evidence of
real-world completion by itself; only a merged PR, green CI on `master`, and
(where a release applies) a shipped-and-verified artifact are.

**Corrects a live incident (2026-08-05):** an earlier revision of this
handoff archived this thread to `plan/archive/` in the same commit that filed
goals 1 and 2 as `ready` — before either was dispatched, implemented, or
merged — reasoning that "the epic is closed, and this repo's plan-thread rule
says archived iff epic-closed." That inference conflated a *procedural*
epic closure (groom's regroom-out: the original ticket is retired because its
content moved to new tickets) with a *completion* closure (the work described
is actually done). The PR merged (repo auto-merge) before the mistake was
caught; corrected in a follow-up PR the same day. The underlying rule text
this came from — and whether it needs correcting fleet-wide, since `plan` and
`groom` are shared `livespec-orchestrator-beads-fabro` operations — is a
separate, larger question the maintainer is tracking outside this thread; do
not silently absorb that fix here.

## Next action

Dispatch the two filed children through the factory path — one command per id,
in either order (they are independent, no `depends_on` between them):

```text
/livespec-orchestrator-beads-fabro:drive --action approve:overseer-otjmoh
/livespec-orchestrator-beads-fabro:drive --action impl:overseer-otjmoh
/livespec-orchestrator-beads-fabro:drive --action approve:overseer-m4o33z
/livespec-orchestrator-beads-fabro:drive --action impl:overseer-m4o33z
```

Do not hand-code implementation inline in a planning session. **Once both are
merged** (and released/deployed, if applicable), re-open this handoff and
update this Status section with real evidence (PR links, merge commits,
release tag) before considering archival — and re-run the plan operation's
handoff self-sufficiency gate before archiving, same as any other refresh.
