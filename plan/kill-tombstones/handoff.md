# Plan — kill-tombstones

**Owning repo:** `livespec-overseer`. **Ledger anchor:** `overseer-7zhfdr`
(this repo's beads tenant). Opened 2026-08-04 on a maintainer declaration that the
tombstone convention is broken and is retired fleet-wide.

**Status is not stored here.** Read it from the ledger. `bd` needs the fleet
credential wrapper in this tenant — a bare `bd` returns `Access denied`:

```bash
/data/projects/1password-env-wrapper/with-livespec-env.sh \
  bd -C /data/projects/livespec-overseer show overseer-7zhfdr --json
```

Pass **`--limit 0`** to any `bd list`: the default caps at 50 rows and hides the
rest behind a footer line, which already cost this thread one wrong "it did not
file" conclusion. Each sibling repo's items are in ITS OWN tenant — run `bd` with
`-C <that repo>`, or the id will not be found.

## Read first

1. `plan/kill-tombstones/research/mechanism.md` — what a tombstone is, the four
   things wrong with it, the measured daemon-log evidence, and the removal
   procedure with its trap.
2. `plan/kill-tombstones/research/enforcement-inventory.md` — the gates that
   already exist, why neither fired, the missing detector, and where the
   prohibition gets written down.

Everything below is a claim with a timestamp, including this sentence. Re-measure.

## The rule this thread exists to install

A **tombstone** is a stub `handoff.md` left at the LIVE path
`plan/<topic>/handoff.md` after the real thread moved to `plan/archive/<topic>/`,
whose body says "STOP. THIS TRACK IS COMPLETE AND ARCHIVED".

**Maintainer-declared 2026-08-04: it is FORBIDDEN, permanently, in every fleet
member and every adopter.** When a plan thread would close with anything
unresolved, do exactly ONE of:

1. **LEAVE THE PLAN UN-ARCHIVED** until its blockers are resolved; or
2. **TRANSFER ALL BLOCKERS** to a different or new NON-ARCHIVED plan thread
   and/or work-item, then archive with a clean whole-directory
   `git mv plan/<topic> plan/archive/<topic>` that leaves NOTHING behind.

## Why, in one paragraph

A tombstone keeps a finished thread registered as a live overseer track, and it
DEFEATS the daemon's own cleanup: `registry.archived_or_gone` is DIRECTORY-level
and a live `plan/<topic>/` wins, so `_supervisor_discovery.archive_gc` can never
drop the row. The workaround disarms the mechanism that makes it unnecessary.
Measured cost, from `tmp/overseer/daemon.log`: `daemon-liveness-truth` was
**RESTARTED 1h02m after its archive merged**, and `fleet-charter-remediation` was
**RESTARTED 4h19m after**, then nudged again **14h10m after** it was finished.

## The scope is DECIDED — do not re-derive it

Nine children are filed against `overseer-7zhfdr`. Re-read each item's own text
before acting on it; the one-liners here are labels, not briefs.

**`livespec-overseer`** (this repo's tenant, linked to the epic by beads
`parent-child` edges):

| id | what |
|---|---|
| `overseer-5nuir3` | Purge `plan/foreman/handoff.md` — the last tombstone — and verify the PRIMARY CHECKOUT drops the track |
| `overseer-3i43qx` | Strike remedy 1 from `overseer-y26`'s DESCRIPTION; it still recommends the banned stub |
| `overseer-ihwyin` | Write the ban into `SPECIFICATION/spec.md` §"Track discovery and the mapping store" |
| `overseer-e723tt` | Re-derive the `_prefer_archived` tiebreak in two test files (depends on `livespec-dev-tooling-rowxc6`) |

**`livespec-dev-tooling`** (its own tenant; cross-repo `depends_on` back to the epic):

| id | what |
|---|---|
| `livespec-dev-tooling-rowxc6` | NEW fail-closed `plan_thread_no_tombstone` check — a topic present at BOTH `plan/<topic>/` and `plan/archive/<topic>/` |
| `livespec-dev-tooling-q6oob4` | `plan_thread_epic_parity` hard-codes the `livespec-dev-tooling-` tenant prefix, so it checks nothing anywhere else |

**`livespec`** (core's tenant):

| id | what |
|---|---|
| `livespec-zp5mkd` | `propose-change`: the ban + both alternatives into §"Planning Lane guidance" → "Archive on epic close" — the clause adopters inherit |
| `livespec-fvhvui` | Fleet fan-out epic: opt every governed repo into `plan_lifecycle_anchor = true` (set in **1 of 12** today). NEEDS GROOMING |

**`livespec-orchestrator-beads-fabro`** (its own tenant):

| id | what |
|---|---|
| `bd-ib-xhcqbc` | The ban into the Planning Lane realization spec AND `prose/plan.md` §"Step 5" — the prose an agent reads at archive time |

Related, already filed, NOT duplicated: **`overseer-y26`** is the root-cause bug
(an archive leaves the stored resume line pointing at the moved handoff). It stays
its own item. `overseer-3i43qx` only repairs its misleading description.

## Explicitly rejected — do not propose these again

- **Making `registry.archived_or_gone` file-level.** Its directory-first
  precedence is adversarial-review blocker **B6** and protects a new plan that
  reuses a retired topic slug from being GC-dropped every tick. Banning tombstones
  closes the window at the source instead.
- **Relaxing architecture invariant 1** so the daemon may stat `plan/`. The
  invariant is correct; the fix belongs on the archival side or in a store-side
  check.
- **Hand-editing `~/.livespec-overseer.jsonl`** to pre-empt the GC. It is shared
  fleet state read by every track, and editing it hides the condition the fix
  exists to remove.
- **A content-sniffing detector** that greps a live handoff for "COMPLETE AND
  ARCHIVED" or "TERMINAL". Evadable by rewording, and it false-positives on any
  document that legitimately quotes the phrase — including this thread's own
  research notes. Detect the STRUCTURE (the both-present directory pair).
- **Removing the ARMED-ONLY gating on `plan_thread_epic_parity`.** It is
  deliberate and correct; it just means parity can never be the primary guard.

## Traps that have already cost turns — all measured, none hypothetical

**The daemon reads the PRIMARY CHECKOUT'S WORKING TREE, not git.** Merging a
tombstone deletion is NOT enough. After every removal:

```bash
git -C /data/projects/livespec-overseer rev-list --count HEAD..origin/master   # must be 0
test -d /data/projects/livespec-overseer/plan/<topic>                          # must FAIL
```

**Re-measure the tombstone inventory before acting on it.** A same-day report to
this thread named `release-automation-gap` and `daemon-liveness-truth` as
surviving instances; both had already been retired at `5560b5e`. As of
2026-08-04 exactly ONE remains: `plan/foreman/handoff.md`.

**`plan/foreman/` may be removed by someone else.** The `foreman-supervisor`
session was reported cleaning itself up at filing time. Do NOT land a content
change into a thread that is mid-archive — a content change racing a rename
leaves the PR `CONFLICTING`, where auto-merge silently never fires while every
check reads green. If the tombstone is already gone, `overseer-5nuir3`'s
remaining work is the VERIFICATION above, which is the half a cleanup session is
most likely to skip.

**A beads gap, hit while filing this thread.** `bd` refuses a `blocks` edge
between a task and an epic in BOTH directions ("tasks can only block other tasks,
not epics"; "epics can only block other epics, not tasks"), and the store wrapper
`_store_mutations._add_dependency_edges` only ever emits `EDGE_BLOCKS`. So a local
child→epic link CANNOT be expressed through `capture-work-item`'s `depends_on`.
Workaround used here: file the child with no local dep, then
`bd dep add <epic> <child> --type parent-child`. Cross-repo refs
(`{"kind": "cross-repo", "ref": "<repo>#<id>"}`) are unaffected — they are stored
verbatim and never become edges. Worth an entry in `.ai/beads-gaps-workarounds.md`.

**`bd update --notes` is SET, not APPEND.** Read the field, concatenate, write,
then read back. A previous edit to `overseer-y26` silently destroyed a prior
correction while printing a success line (charter correction C11).

## Next action

Re-measure `overseer-7zhfdr` and its children from the ledger first — everything
above is a claim with a timestamp.

Then dispatch the ready factory-tier items. **`livespec-dev-tooling-rowxc6`
(the `plan_thread_no_tombstone` check) is the keystone**: it is what makes the ban
mechanical rather than a convention, and `overseer-e723tt` depends on it. Take it
first unless the ledger says otherwise.

**Implementation route is the FACTORY PATH** — the Dispatcher drain, or an
operator running `/livespec-orchestrator-beads-fabro:drive --action impl:<id>`.
Do NOT hand-code these in a planning session and do NOT route them through the
in-session `implement` operation.

**Four items are `spec-change` tier and are human-gated** — `overseer-ihwyin`,
`livespec-zp5mkd`, `bd-ib-xhcqbc`, and the description repair `overseer-3i43qx`'s
spec-adjacent half. They route through `/livespec:propose-change` then
`/livespec:revise`, are never factory-dispatched, and each accept requires an
independent adversarial review by a separately-spawned Fable-model agent as a
precondition. `livespec-fvhvui` is epic-shaped and needs `/groom` before dispatch.

Before dispatching anything, confirm the item's text carries no literal
double-brace interpolation token: `drive.py` interpolates item text into fabro's
templated `goal`, so such a token is parsed as a fabro template variable and the
graph is rejected before any agent runs, leaving a phantom `active` claim with no
run behind it. `fabro ps` is the evidence of a run; a `drive.py` exit of 0 means
the request was accepted, not that work started.

## Closing this thread

This thread's own archive must obey the rule it installs. When the epic closes,
either every child is closed, or the survivors are transferred to a live thread or
work-item first. Then `git mv plan/kill-tombstones plan/archive/kill-tombstones` —
whole directory, nothing left behind. **If you find yourself wanting to leave a
note at the live path, that is the exact impulse this thread exists to forbid.**

## Discipline

Fleet-standard: worktree → PR → rebase-merge, never a commit on the primary
checkout. Never `--no-verify`; halt and report on hook failure. Never touch
another session's worktrees or branches. Never kill the acting overseer daemon in
tmux `livespec-overseer:1.1`. Resolve a repo's default branch from the forge
(`gh repo view --json defaultBranchRef`) — `homelab` is `main`, not `master`.
