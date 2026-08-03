# Plan — charter-gate-ratchet

**Owning repo:** `livespec-overseer`. **Ledger anchor:** `overseer-x1q`
(this repo's beads tenant, P1). Opened 2026-08-03 from the single unaddressed
item left by `plan/archive/fleet-charter-remediation/`, which archived the same
day after taking the fleet **119 → 0**.

**Status is not stored here.** Read it from the ledger. `bd` needs the fleet
credential wrapper in this tenant — a bare `bd` returns `Access denied`. Use
`with-livespec-env.sh -- bd show overseer-x1q --json`.

## What this is

The 2026-08-03 sweep took every supervisor charter in the fleet to zero defects.
**That result is a SNAPSHOT, NOT A RATCHET.** Nothing prevents any of it
regressing in five of the six repos, and the regression path is the same one
that produced the original 119: the generator was fixed long before the emitted
charters were, and nothing noticed the gap for weeks.

Measured 2026-08-03: `find` for `test_charters_carry_no_known_defects.py` across
all six fleet repos returns **exactly one copy**, in `livespec-overseer`. Its
`_REPO_ROOT` is `Path(__file__).resolve().parent.parent.parent`, so
`test_every_charter_in_this_repo_is_free_of_the_known_defects` iterates
`_charters()` over its **own tree only**:

| repo | charters | gated? |
|---|---|---|
| `livespec-overseer` | 13 | **yes**, CI-enforced |
| `homelab` | 8 | no |
| `livespec` | 7 | no |
| `livespec-orchestrator-beads-fabro` | 6 | no |
| `livespec-dev-tooling` | 5 | no |
| `livespec-console-beads-fabro` | 1 | no |

**27 of the fleet's 40 charters have no enforcement at all.** Re-measure before
quoting those numbers — the corpus grew 33 → 41 during the sweep itself, as
other tracks opened threads, so a total measured yesterday is not a total today.

## The scope is DECIDED — do not re-derive it

**Ship the detectors from the pinned `livespec-dev-tooling` package** so
pin-consuming repos gate their own charters in their own CI, and accept that
`homelab` needs a different mechanism. That is the `3-for-pin-consumers +
1-for-homelab` shape already recorded on `overseer-yho.3`'s measurement, and it
is the item's own decided design rather than an option to re-cost.

**`homelab` consumes no pin and that is a toolchain fact, not a choice.** It is
Rust/Nix — `Cargo.toml`, `Cargo.lock`, `crates/`, `flake.lock`, and **no**
`pyproject.toml`, `justfile`, or `.mise.toml`. There is no Python dependency
surface to pin into and no `just` entry point to hang the gate on. It does have
CI (`.github/workflows/ci.yml`, a `ci/` directory), so the obstacle is the
pin/package **delivery** mechanism, not absent automation. A scheduled external
scan, or nothing, are the honest options.

**An earlier framing called `homelab` "the single biggest hole left". That was
true but NARROW and it is corrected.** `homelab` is merely the repo that
*cannot* be fixed by per-repo adoption. The other four **could adopt today and
have not** — that is the larger part of the hole and the cheaper part to close.

## Explicitly rejected — do not propose it again

**Widening the existing gate's globs to scan sibling repos.** It was considered
and it is wrong twice over: a test that reads outside its own repo root breaks
the repo-containment property this fleet enforces elsewhere, and it would make
one repo's CI red for another repo's commit.

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

`(h)` is now **zero fleet-wide — every finding it had left was a false
positive.** Instances 1 and 2 were fixed in the detector; instance 3 was
resolved by UN-FENCING the demonstration, preserving all three lines
byte-for-byte, and **no "skip this block" escape hatch was added.** Do not add
one under adoption pressure: an escape needs its own discrimination leg and is
exactly the kind of thing later used to silence a real finding.

`AGENTS.md` now records the three-way-control rule and the indented-literal-block
escape. **An adoption slice should not proceed without both.** Pointing this gate
at four more repos will meet more false positives of this family.

## Deliberately separate, and still unowned

**Nothing schedules charter REGENERATION.** The sweep fixed emitted charters by
hand; a thread that never re-runs `supervise-plan` keeps whatever it was given,
however old. Adoption gates *regression*; it does not refresh a charter whose
generator has moved on. File it separately if it is to be worked — it is not
part of `overseer-x1q`.

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
repos here do not share one convention.

**Score with the shipped module imported and called, never a grep.** The
detectors resolve variable bindings across a whole document, strip trailing
comments while respecting quotes, and dedupe two rules that describe one defect.
A count produced any other way is not comparable. **Name the detector set with
every count**: the sweep's `124 → 120` was not four defects fixed, it was four
that were never there, because the set went from eleven detectors to twelve
underneath the measurement.

## Next action

Re-measure `overseer-x1q` from the ledger first — everything above is a claim
with a timestamp, including this sentence. The item is `backlog`, P1, and
**unassigned**; moving it onward is the maintainer's valve.

Before dispatching, confirm the item's text carries no literal double-brace
interpolation token: `drive.py` interpolates item text into fabro's templated
`goal`, so such a token is parsed as a fabro template variable and the graph is
rejected before any agent runs, leaving a phantom `active`/`fabro` claim with no
run behind it. `fabro ps` is the evidence of a run; `ACTIVE` never is. Note also
that a `drive.py` exit of **0** means the request was accepted, not that work
started — a queued run can be evicted without ever executing and leaves the same
wreckage.

## Discipline

Fleet-standard: worktree → PR → rebase-merge, never a commit on the primary
checkout. Never `--no-verify`; halt and report on hook failure. Never touch
another session's worktrees or branches. Never kill the acting overseer daemon in
tmux `livespec-overseer:1.1`.

**`just worktree-create` is effectively broken in THIS repo at scale** —
`worktree-lib.sh:89` pipes `git worktree list --porcelain` into an `awk` that
exits on the first match, so git takes SIGPIPE and the recipe dies at 141 before
printing anything. Filed as `livespec-dev-tooling-zi4q`. **Rescue path:**
`git worktree add <path> -b <branch>`, then `just install-worktree-pack` inside
it, then `git checkout -- .livespec.jsonc` to discard the `worktree_discipline`
key it writes into that tracked file.

**Auto-merge is enabled in several fleet repos and it changes sequencing.**
Push every commit you intend to ship BEFORE opening the PR, and do not plan to
amend a title afterwards. **And do not land an edit into a thread that is
mid-archive** — a content change racing a rename leaves the archive PR
`CONFLICTING`, where auto-merge silently never fires while every check reads
green.
