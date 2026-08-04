# Plan — charter-gate-ratchet

**Owning repo:** `livespec-overseer`. Opened 2026-08-03 from the single
unaddressed item left by `plan/archive/fleet-charter-remediation/`, which
archived the same day after taking the fleet **119 → 0**.

**The anchor `overseer-x1q` is CLOSED — regroomed-out on 2026-08-04** into eight
factory slices across five repos plus one human-gated spec change. It is no
longer the thing to read status from; the slices are. **Status is not stored
here.** `bd` needs the fleet credential wrapper in every one of these tenants —
a bare `bd` returns `Access denied`. Use
`with-livespec-env.sh -- bd show <id> --json`, run from the target repo's
checkout so tenant auto-discovery routes.

## What this is

The 2026-08-03 sweep took every supervisor charter in the fleet to zero defects.
**That result is a SNAPSHOT, NOT A RATCHET.** Nothing prevents any of it
regressing in five of the six repos, and the regression path is the same one
that produced the original 119: the generator was fixed long before the emitted
charters were, and nothing noticed the gap for weeks.

`test_charters_carry_no_known_defects.py` exists in exactly one copy, in
`livespec-overseer`. Its `_REPO_ROOT` is
`Path(__file__).resolve().parent.parent.parent`, so the gate iterates its **own
tree only**.

## The cut — eight factory slices, one spec change

Filed 2026-08-04. Each slice's own record carries its full scope, acceptance,
and measurements; this table is a map, not a substitute.

| slice | tenant | blocked by |
|---|---|---|
| Ship the detectors from `livespec_dev_tooling`, outside `checks/` | `livespec-dev-tooling-lwzbh5` | — (**the drain head**) |
| Re-point this repo's gate at the shipped module | `overseer-wnsq2d` | `lwzbh5` (sibling) |
| Self-wire dev-tooling's own 5 charters | `livespec-dev-tooling-ta5jy4` | `lwzbh5` (local) |
| Adopt in the orchestrator (6 charters) | `bd-ib-l4cpze` | `wnsq2d` (sibling) |
| Adopt in `livespec` (7 charters) | `livespec-wktlbc` | `wnsq2d` (sibling) |
| Adopt in the console (1 charter) | `livespec-console-beads-fabro-5zjk5b` | `wnsq2d` (sibling) |
| Scheduled external scan covering `homelab` (8 charters) | `overseer-oapv2x` | `wnsq2d` (local) |
| **Spec change** — declare the importable surface | not a ledger item; PR `thewoolleyman/livespec-dev-tooling#1251` | — |

Only `lwzbh5` is `ready`. Everything else sat at `pending-approval` behind a
blocker at filing time. **Whether the Definition-of-Ready router re-admits a
slice when its blocker closes was NOT verified** — treat the later layers as
needing the admission valve (`drive --action move:<id>:ready`) until you observe
otherwise.

**Re-pointing this repo (`overseer-wnsq2d`) is deliberately ahead of the three
foreign adopters.** It proves the shipped surface against the repo with the most
charters and the whole discrimination suite, with CI already green. If the
shipped surface is wrong it fails there, where the controls exist.

## The design decision, and why it is not a `just check-<slug>`

**MEASURED 2026-08-04, not inherited.** The item's notes flagged the gate's own
docstring — a `checks/` slug drags in the whole aggregate obligation — and said
to re-read that reasoning before designing anything. It was re-read against the
code, and it is stronger than the docstring states:

- `livespec_dev_tooling/canonical_checks.py:195` `canonical_check_slugs()` walks
  the **live** `livespec_dev_tooling/checks/` directory at every invocation.
  Adding any `checks/<name>.py` extends the canonical tuple automatically — "no
  second source of truth", by design.
- `livespec/SPECIFICATION/contracts.md:142` then requires **every** consumer to
  wire each shared check into `just check` **and** its CI matrix.
- `contracts.md:184` adds a `wiring-completeness-cross-repo` backstop so it
  cannot be quietly dropped.

So a `checks/` module conscripts **six** repos — including `homelab`, which
cannot comply by any means. **Ship outside `checks/`.** `lwzbh5`'s acceptance
guards this mechanically: a shipped test asserting `canonical_check_slugs()`
returns an identical tuple before and after.

One consequence: `livespec/pyproject.toml:59-61` declares the library's
semver-stable surface as the `python -m …checks.<slug>` invocation set, and
dev-tooling's own `contracts.md` §"CLI surface" says consumers **MUST NOT** call
internal helper modules directly. An importable API therefore needs the contract
amended **before** any consumer imports it — that is PR #1251, and it is the one
human-gated piece.

## Explicitly rejected — do not propose it again

**Widening the existing gate's globs to scan sibling repos.** Wrong twice over:
a test that reads outside its own repo root breaks the repo-containment property
this fleet enforces elsewhere, and it would make one repo's CI red for another
repo's commit.

The `homelab` slice (`overseer-oapv2x`) is **not** a rederivation of that. It
stays on the right side of the property precisely because it is scheduled and
out-of-band, and its acceptance says so: it must be wired into **no** PR gate in
any repo.

## The rider that must travel with any adoption

**All three false positives found during the sweep flagged code that was ALREADY
CORRECT**, and every one failed in the same direction — toward a session
rewriting correct code to satisfy a broken check:

1. `(h)` hard-coded one wrapper name, so `homelab`'s **better** config-driven
   lookup scored 4 defects.
2. `(h)` also required the wrapper and `bd` on one physical line, so a correct
   invocation split across a line continuation scored 1 more.
3. A block labelled `# DEMONSTRATION, not a check` showed the loose and exact
   tmux forms side by side; the gate reads fenced bodies and cannot tell a
   counter-example from a prescription, so it scored the evidence as 2 defects.

Instances 1 and 2 were fixed in the detector; instance 3 was resolved by
UN-FENCING the demonstration, preserving all three lines byte-for-byte, and **no
"skip this block" escape hatch was added.** Do not add one under adoption
pressure: an escape needs its own discrimination leg and is exactly the kind of
thing later used to silence a real finding. The detectors read **fenced** bodies
only, so an indented literal block scores zero while changing not one character
of the demonstration.

`AGENTS.md` records the three-way-control rule and that escape. **Every adopter
slice carries both in its own acceptance**, so no gate can land without them.
Pointing this gate at four more repos will meet more false positives of this
family.

## Deliberately separate, and still unowned

**Nothing schedules charter REGENERATION.** The sweep fixed emitted charters by
hand; a thread that never re-runs `supervise-plan` keeps whatever it was given,
however old. Adoption gates *regression*; it does not refresh a charter whose
generator has moved on. It was not part of `overseer-x1q` and is in none of the
eight slices. File it separately if it is to be worked.

## Baseline — re-measured 2026-08-04

Method: a read-only scan that **imports** this repo's shipped detectors and
applies its 12 detectors and 3 globs to every fleet repo tree, after
`git fetch` in all six. Nothing written to any repo.

| repo | charters | defects | gated today |
|---|---|---|---|
| `livespec-overseer` | 13 | 0 | **yes**, CI-enforced |
| `homelab` | 8 | 0 | no |
| `livespec` | 7 | 0 | no |
| `livespec-orchestrator-beads-fabro` | 6 | 0 | no |
| `livespec-dev-tooling` | 5 | 0 | no |
| `livespec-console-beads-fabro` | 1 | 0 | no |

**40 charters, 0 defects. 27 of the 40 gated by nothing.** Zero charters dirty
and zero differing from each repo's default branch, so this is a claim about
origin rather than about local trees. It reproduces the 2026-08-03 measurement
exactly — the corpus did not move in a day.

**Nothing has regressed, so this work is preventive rather than remedial.** That
does not weaken the case: the scan that produced this number is a throwaway
script in a scratch directory, not anything CI runs.

**The parent thread's "41 charters" is stale; 40 is correct.** The corpus went
42 → 40 at `5560b5e`, which retired two tombstone charters. **Re-measure before
quoting any of these numbers** — including this table.

## Method notes carried from the sweep — these were earned expensively

**A claim read off a stale base is not a measurement.** Four times on the parent
thread a confident finding would have been wrong: a `--numstat` row paired to the
wrong commit; a `git show origin/master:<file>` against a repo whose default
branch is **`main`** (the empty result scored as a clean file); a PR diff read
without simulating the rebase; and a watcher polling a `state` field that could
never change. **Simulate the actual operation, and check that what you are
waiting for is REACHABLE.**

**Resolve a repo's default branch from the forge** —
`gh repo view --json defaultBranchRef` — rather than assuming `master`. The six
repos here do not share one convention; `homelab` is `main` and the other five
are `master`.

**Score with the shipped module imported and called, never a grep.** The
detectors resolve variable bindings across a whole document, strip trailing
comments while respecting quotes, and dedupe two rules that describe one defect.
A count produced any other way is not comparable. **Name the detector set with
every count**: the sweep's `124 → 120` was not four defects fixed, it was four
that were never there, because the set went from eleven detectors to twelve
underneath the measurement. Today's set is **12** (`a`–`l`).

**A tenant name is not its repo directory name.** Measured while filing this
cut: `livespec-orchestrator-beads-fabro`'s tenant is `livespec-orch-beads-fabro`
and its prefix is `bd-ib`. An assertion that the two match fails mid-run.

## `groom`'s cross-repo path is broken — filed as `bd-ib-nqw5t3` (P1)

Hit while filing this cut, and it will be hit again by the next multi-repo groom:

- **A cross-repo slice id is minted with the LOCAL prefix**, which the target
  tenant refuses: `prefix mismatch: database uses 'livespec-dev-tooling-' but ID
  'overseer-r7s5ze' doesn't match (use --force to override)`. Do **not** force a
  foreign prefix past a tenant's own invariant. Let each tenant mint its own id
  and repoint any sibling edge already written against the dead one — exactly one
  such edge existed here, on `overseer-wnsq2d`.
- **A cross-repo slice's `depends_on` is silently discarded** — the
  `repo_target != local_repo` branch `continue`s before dependency resolution. A
  caller that files `GroomResult.cross_repo_slices` as returned gets **unblocked**
  slices; four of the eight here. The edges above were applied by hand.
- **The failure is partial.** The first cross-repo slice lands before the
  mismatch surfaces on a later tenant, so a naive re-run double-files it.

## Next action

Read the slices, not this file, for status. The drain head is
`livespec-dev-tooling-lwzbh5`; PR #1251 should land before it, since it is what
permits a consumer to import the module at all.

Before dispatching anything, confirm the item's text carries no literal
double-brace interpolation token: `drive.py` interpolates item text into fabro's
templated `goal`, so such a token is parsed as a fabro template variable and the
graph is rejected before any agent runs, leaving a phantom `active`/`fabro` claim
with no run behind it. Every slice filed by this cut was checked for that and is
clean. `fabro ps` is the evidence of a run; `ACTIVE` never is. A `drive.py` exit
of **0** means the request was accepted, not that work started — a queued run can
be evicted without ever executing and leaves the same wreckage.

## Discipline

Fleet-standard: worktree → PR → rebase-merge, never a commit on the primary
checkout. Never `--no-verify`; halt and report on hook failure. Never touch
another session's worktrees or branches. Never kill the acting overseer daemon in
tmux `livespec-overseer:1.1`.

**`just worktree-create` is still broken in THIS repo** — `worktree-lib.sh:89`
pipes `git worktree list --porcelain` into an `awk` that exits on the first
match, so git takes SIGPIPE and the recipe dies at 141 before printing anything.
Filed as `livespec-dev-tooling-zi4q`. **Reconfirmed 2026-08-04**, and the rescue
path works: `git worktree add <path> -b <branch> origin/master`, then
`just install-worktree-pack` inside it, then `git checkout -- .livespec.jsonc` to
discard the `worktree_discipline` key it writes into that tracked file. The same
recipe **succeeds** in `livespec-dev-tooling`, so this is repo-specific — do not
generalize it into a fleet-wide claim.

**Auto-merge is enabled in several fleet repos and it changes sequencing.**
Push every commit you intend to ship BEFORE opening the PR, and do not plan to
amend a title afterwards. **And do not land an edit into a thread that is
mid-archive** — a content change racing a rename leaves the archive PR
`CONFLICTING`, where auto-merge silently never fires while every check reads
green.
