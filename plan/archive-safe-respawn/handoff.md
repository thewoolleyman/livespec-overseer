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

## THE SCOPE ABOVE IS AMENDED — read this before building to it

**Scope bullet 1 ("resolve the binder at EITHER `plan/<topic>/` or `plan/archive/<topic>/`")
contradicts the ratified spec and MUST NOT be implemented.** Maintainer-approved amendment
2026-08-06; full reasoning on `overseer-4w2m`, short form on `overseer-y26`.

`SPECIFICATION/spec.md` §"Track discovery and the mapping store" excludes archived plans
from discovery — an archived thread is not a track at all — and states the tombstone
prohibition is load-bearing precisely because a live directory leaves a finished thread
"eligible for nudges, for wrap-up injection, and for RESTART". Booting an archived thread
from its archive re-creates that hazard **in the daemon** instead of on disk. A fix built
to that bullet would pass its own acceptance and re-open the defect.

**What replaces it.** `_registry_discovery.archived_or_gone` (line 306) is a DIRECTORY
test that already separates archived from live, and directory enumeration is
spec-permitted. `_supervisor_restart`, when the computed binder is absent, consults it and
branches: archived-or-gone → distinct TERMINAL condition, retire the track, no restart, no
missing-file alert; live-directory-but-binder-absent → keep today's
`supervisor-handoff-missing` alert, which is genuinely anomalous there.

**Why the wording is the whole point.** Today a CORRECTLY archived thread emits an alert
naming a MISSING FILE. That is what taught the `livespec-dev-tooling` supervisor to restore
the file 13 hours after the ban. The ban removed the stub; it never fixed the message that
asks for one. Fixing the message is the causal fix.

The WORKER half must stay stat-free — invariant 1 forbids stat-ing a FILE under `plan/`,
and relaxing it is on the rejected list — so it belongs in the resume PROMPT TEXT (pure
string work, as `default_handoff` already is). Remedy 2 is unchanged and still right.

## State as of 2026-08-06 — spec authored and green, blocked ONLY on ratification review

Branch `archive-safe-respawn` (worktree `~/.worktrees/livespec-overseer/archive-safe-respawn`).

- `SPECIFICATION/proposed_changes/archived-plan-is-a-terminal-restart-condition.md` filed
  via the CLI at exit 0 and COMMITTED.
- The `resulting_files[]` are AUTHORED and sitting UNCOMMITTED in the worktree, by design —
  the revise CLI applies them and cuts the version; hand-committing them would be an
  out-of-band spec edit. They are `SPECIFICATION/spec.md`, `SPECIFICATION/scenarios.md`
  (two new scenarios), and the co-edited `tests/heading-coverage.json`.
- **`just check` is GREEN on those bytes: 68/68 targets, green token written.**
- Canonical ratification digest over those exact bytes:
  `6508d9a463f8f3dfe64157b3a4c28e96e02b395a0496dc55cf67d5c05ea1ceb3`
  (algorithm: `_revise_ratification._canonical_ratification_digest` — sha256 over
  uint64-BE length-prefixed proposal bytes, then each `(path, content)` sorted by path).
  **Re-derive it after ANY edit; it pins the exact bytes reviewed.**

**The block:** `spec_governance` is unset in `.livespec.jsonc`, so `ratification_review`
takes its safe default `manual-spawn`. Every accept/modify needs INDEPENDENT review
evidence (reviewer model + identity, separate-reviewer and read-only declarations,
UTC-seconds timestamp, literal `NO BLOCKERS`, proposal stem, and that digest). The revise
CLI validates evidence and never spawns a reviewer, so this cannot be self-supplied.

## Traps measured this session — each cost real time

- **`resolve_core_root.py` MISFIRES in this repo and EXITS 0.** Its rule 2 takes
  `<project-root>/.claude-plugin/` when that carries `prose/` — meant to detect "the
  project IS livespec core". This repo ships its OWN plugin with `prose/`
  (`overseer.md`, `foreman.md`, `supervise-plan.md`), so it matches and silently returns a
  root with no `propose-change.md`. Every `/livespec:*` operation here needs
  `LIVESPEC_CORE_PLUGIN_ROOT` set explicitly (current core build:
  `~/.claude/plugins/cache/livespec/livespec/c0990486c874`).
- **`.claude-plugin/overseer/` is a byte-identical VENDORED COPY of all 91 shipped
  modules** (tests excluded), and **nothing gates it** beyond `version.json` lockstep. A
  `.py` fix applied only to `overseer/` tests green and SHIPS NOTHING. Mirror both.
- **`supervisor-handoff-missing` has ZERO test coverage today** — grep finds it in
  `_supervisor_restart.py` and its vendored twin, in no test. The refusal path this thread
  is changing is currently unpinned in both directions.
- **`scenarios.md` headings MUST map to INTEGRATION-tier tests** in
  `tests/heading-coverage.json`. An `overseer.*` unit-tier target fails
  `check-heading-coverage` with "scenario heading mapped to unit-tier test" — which reads
  like a missing test but is a TIER error. The two new scenarios are wired to
  `tests.integration.test_ready_declaration_restart`, where the tests must therefore live.
- **The PreToolUse background guard names a remedy that does not exist at this pin.** It
  denies backgrounding `just check` and directs you to `just gate-start` /
  `.ai/gate-runtime-vs-harness-patience.md`; NEITHER exists in this repo. Run the aggregate
  in the FOREGROUND with a long timeout (it completes in ~5 min here).
- **Revise's Step 3.5 stale-branch check FAILS on a FALSE POSITIVE.**
  `spec/codex-yolo-structured-question-protocol` reads 1-ahead of `origin/master`, but its
  proposal was ratified as **v009** and is archived under
  `SPECIFICATION/history/v009/proposed_changes/`. Ancestry does not resolve under
  rebase-merge — the same defect class as `just worktree-reap`. Clear it with
  `--skip-stale-branch-check` (narration required) or reap the ref.

## Next action

Obtain the independent ratification review for digest
`6508d9a463f8f3dfe64157b3a4c28e96e02b395a0496dc55cf67d5c05ea1ceb3`, then run revise with
`--post-step-doctor --skip-stale-branch-check` to cut the new version. THEN implement:
the `archived_or_gone` branch in `_supervisor_restart` (mirrored into
`.claude-plugin/overseer/`), the two integration tests, and remedy 2's store-side check —
under red-green-replay.

Before trusting anything above, re-measure. The module paths are 2026-08-06 claims.

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
