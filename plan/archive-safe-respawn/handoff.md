# Plan — archive-safe-respawn

**Owning repo:** `livespec-overseer`. **Ledger anchor:** epic `overseer-4w2m`

**Status is not stored here.** Read it from the ledger. `bd` needs the fleet credential
wrapper in this tenant — a bare `bd` returns `Access denied`:

```bash
/data/projects/1password-env-wrapper/with-livespec-env.sh \
  bd -C /data/projects/livespec-overseer show overseer-4w2m --json
```

Pass `--limit 0` to any `bd list`; the default caps at 50 rows.

Everything below is a claim with a timestamp, including this sentence. Re-measure.

## Why this thread exists

**Archiving a supervised plan thread strands its respawn, and agents close that gap by
writing tombstones.** The overseer respawns a pane with exactly one prompt naming a
COMPUTED LIVE path. An archive moves the file; nothing re-points the prompt; the fresh
session boots into a path that does not exist.

`overseer-y26` is the root-cause bug and is this epic's first child.

**It defeated the tombstone ban within hours, which is the reason this is P1.** The ban
was ratified fleet-wide 2026-08-04 (`livespec` v194, `livespec-overseer` v008,
`livespec-orchestrator-beads-fabro` v057). **Thirteen hours later a supervisor in
`livespec-dev-tooling` wrote a stub at the live path anyway** and explained why: without
it "the next supervisor would have booted into a dangling path with NOTHING." They were
right about the pressure. The ban says do not leave a stub; it never said what to do when
the respawn prompt names a path the archive deleted.

So the ban is ENFORCED (`plan_thread_no_tombstone`, v1.19.0, structural and fail-closed,
on master in 9 of 10 pin-consuming repos) but its CAUSE is open. Competent agents will
keep re-deriving the workaround until this lands.

## The two halves — a fix that closes only one will report success

Both are documented in `plan/archive/kill-tombstones/research/mechanism.md`; re-measure
against the code before trusting either.

**Worker half — STORED, misdirects.** `~/.livespec-overseer.jsonl` holds a `handoff` path
and a `resume` line per track, both hard-coding `plan/<topic>/handoff.md`. An archive
moves the file; nothing rewrites the row. `_do_restart` bracketed-pastes the stored line
verbatim, so the fresh session is handed a prompt naming a missing file.

**Supervisor half — COMPUTED, REFUSES.** `overseer/_supervisor_prompts.py`'s
`supervisor_handoff_path()` computes `plan/<topic>/supervisor-handoff.md`. Nothing stores
it, so nothing can migrate it and no store-side assertion can see it.
`overseer/_supervisor_restart.py` existence-tests that path and, when missing, calls
`sup.alert` with `condition="supervisor-handoff-missing"` and returns WITHOUT restarting.
A supervisor that winds down correctly and declares `ready` is exactly the case that hits
it — and it is the half that produced the live tombstone.

## Scope

- Resolve a thread's binder at EITHER `plan/<topic>/` or `plan/archive/<topic>/`, so an
  archived thread boots to its real archived record and no stub is ever needed.
- Cover BOTH halves above.
- Keep `overseer-y26` remedy 2: a store-side assertion that every mapping row's `handoff`
  path and its `resume` target resolves. It also covers the window between an archive
  merging and the next GC tick.

## Explicitly rejected — do not re-derive these

Carried forward from `kill-tombstones`, where each was settled:

- **Making `registry.archived_or_gone` file-level.** Its directory-first precedence is
  adversarial-review blocker **B6** and protects a new plan reusing a retired slug.
- **Relaxing architecture invariant 1** so the daemon may stat `plan/`. The invariant is
  correct; the fix belongs on the archival side or in a store-side check.
- **Hand-editing `~/.livespec-overseer.jsonl`.** Shared fleet state read by every track;
  editing it hides the condition.
- **Leaving a stub at the live path.** The banned pattern this thread exists to remove
  the need for. `check-plan-thread-no-tombstone` will fail your build.

## Read first

- `plan/archive/kill-tombstones/research/mechanism.md` — the mechanism, the two halves,
  and the measured daemon-log evidence (archived threads NUDGED, WRAP-UP-INJECTED and
  RESTARTED hours after completion).
- `overseer-y26`'s own notes — the first-live-catch measurement in full.
- `overseer/AGENTS.md` — architecture invariants that must not regress. **Enumerate
  collaborators from the tree, not from its lists.**

## Next action

Re-measure `overseer-4w2m` and `overseer-y26` from the ledger first. Then re-measure both
halves against the code — the module paths above are 2026-08-06 claims.

`overseer-y26` is a `.py` change in this repo. `.py` CAN land here today: the repo pins
`livespec-dev-tooling` v1.19.6+, `check-public-api-result-typed` exits 0 (its
`pure_trees` role is `unarmed_until` `livespec-mutreal.1`), and the full aggregate passes
68/68 in a pack-provisioned worktree. **Measure repo health in a WORKTREE, never on the
primary checkout** — there `check-primary-checkout-commit-refuse-hook-installed` and
`check-shell-quality` both fail as pack artifacts.

## Closing this thread

Every child closed, or every survivor transferred to a live thread or work-item first.
Then `git mv plan/archive-safe-respawn plan/archive/archive-safe-respawn` — whole
directory, nothing left behind, epic CLOSED in the same motion.

**Check before archiving whether this thread has a `supervisor-handoff.md`.** If it does,
archiving it while `overseer-y26` is unfixed recreates the very condition this thread
exists to fix. That check is cheap and was the deciding factor in archiving
`kill-tombstones` safely.
