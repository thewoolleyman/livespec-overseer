# Plan — fleet-charter-remediation

**Owning repo:** `livespec-overseer`. **Ledger anchors:** `overseer-yho.3` and
`overseer-c45` (this repo's beads tenant). Split out of
`plan/supervisor-prompt-quality/` when that thread archived on 2026-08-02.

**THIS THREAD IS CLOSED AND ARCHIVED.** It is the permanent account of a
finished sweep, not a live handoff — every ledger anchor below is closed and
all eight PRs are merged. The one thing still OPEN is `overseer-x1q`, filed
from the last section of this file.

**Status is not stored here.** Read it from the ledger. `bd` needs the fleet
credential wrapper in this tenant — a bare `bd` returns `Access denied`. Use
`with-livespec-env.sh -- bd show overseer-yho.3 --json`.

## THE SWEEP IS DONE — the whole fleet, not just phase 1. Measured 2026-08-03

Every generated supervisor charter in the fleet is scored by this repo's shipped
gate, `tests/prompts/test_charters_carry_no_known_defects.py`.

| repo | before | after | PR |
|---|---|---|---|
| `livespec-orchestrator-beads-fabro` | 55 | **0** | #1248 |
| `homelab` | 26 | **0** | #215 |
| `livespec-dev-tooling` | 18 | **0** | #1140 |
| `livespec-console-beads-fabro` | 15 | **0** | #602 |
| `livespec` | 5 | **0** | #1919 |
| `livespec-overseer` | 0 | **0** | — |
| **total** | **119** | **0** | |

## The one finding that could NOT be remediated by editing code

`homelab/.ai/supervisor-protocol.md` carried a block labelled
`# DEMONSTRATION, not a check: the non-zero exits below ARE the result`, showing
the loose and exact tmux target forms SIDE BY SIDE so a reader can reproduce the
false pass. **The gate reads FENCED bodies and cannot tell a counter-example from
a prescription**, so it scored that evidence as two defects of its own. Rewriting
the lines would have deleted the lesson and raised the file's apparent score *by
destroying its evidence* — the precise failure the gate's own module docstring
warns about.

**The block was UNFENCED, not rewritten. All three lines survive byte-for-byte.**
Converting it to an indented literal block clears both findings and changes not
one character of the demonstration, because `_code_blocks` matches only ``` and
`~~~` fences. That is the precedent **this repo's own twelve charters already
set**: they score zero while discussing every one of these hazards, because they
state them in prose rather than in fenced blocks.

**No escape hatch was added to the gate.** A self-declared "skip this block"
marker would need its own discrimination leg and is exactly the thing that later
gets used to silence a real finding. Route proposed by the thread supervisor.

## Three numbers moved, and TWO of the three were the GATE being wrong

The handoff this replaces said **117**. It is **119**. The path matters more than
the number.

1. **117 → 124.** Real growth plus new charters, all in `homelab`.
2. **124 → 120.** Detector `(h)` hardcoded the literal `with-livespec-env.sh`, so
   `homelab`'s **correct** config-driven wrapper lookup scored 4 false positives.
   Fixed by keying on the wrapper PROPERTY, not a name.
3. **120 → 119.** `(h)` also required the wrapper and `bd` on ONE PHYSICAL LINE,
   so the orchestrator's correct **continued** invocation scored 1 more. Fixed by
   joining continuations.

**`(h)` is now ZERO fleet-wide. Every finding it had left was a false positive.**
Both fixes were found by pointing the detector at repos it was not developed
against, and both failed in the same direction: they would have had a remediating
session **rewrite correct code to satisfy a broken check.** The demonstration
block below was a third instance of that same family, resolved a different way.

**THE GENERAL LESSON: this gate's false positives all point the same direction.**
Every one of the three would have had a session degrade a correct file — a
config-driven wrapper lookup into a hard-coded name, a readable continued command
onto one line, a worked counter-example into a prescription. When a charter looks
wrong, **suspect the detector first and prove it with a three-way control**: the
suspect form, the same thing written differently, and a known-real defect. Two of
the three were caught that way; the numbers in this file moved because of it.

## The premise that was FALSE — do not re-inherit it

The previous handoff said the one-line `$WORKER_TARGET` binding in
`livespec-orchestrator-beads-fabro/.ai/supervisor-protocol.md` was "the single
highest-leverage edit in the fleet" because "it is a SHARED layer, so it fixes
every thread in the repo holding 48% of the exposure."

**That is wrong.** Only `plan/beads-v1-1-2-upgrade/` references the shared layer
at all (5 times). The other four charters — including all three archived ones,
which held **43 of the 55** — reference it **ZERO** times. They are pre-layering
monoliths and had to be fixed directly. The shared-layer edit was **10 of 55
(18%)**, reaching exactly ONE downstream charter.

Caught by the **`retire-host-dispatch-cap` supervisor**, which verified its own
charter never referenced the shared layer and reported it through the supervisor
relay. Confirmed here with a positive control: the same probe returns 7 against a
two-layer charter in this repo, so it can find a positive.

## `overseer-c45` — both asks discharged

**Ask 2 (membership) — ANSWERED, and it is the branch the item anticipated.** The
`rop-railway-enforcement` charter IS in the corpus and did carry 15 defects, but
**none of them is the divergent watcher.** That watcher was **session-improvised
and never committed to any charter file**: the commit recording the incident
(`f93fc8a` in `livespec-dev-tooling`) is **+81/−0**, pure addition of a warning,
and the charter's prescribed watcher rested on pane stability alone both before
and after. File remediation could never have reached it, so the detector is the
only durable guard.

**Ask 1 (detector) — LANDED as class `(l)`, but NOT in the form the item named.**
The item's absolute phrasing — "the idle exit MUST depend on pane stability
alone" — was considered and **rejected**, for two independent reasons:

- it would flag the **corrected** rop-railway charter, which computes `busy` from
  a content grep without gating the idle exit with it — the shape the fleet is
  supposed to ADOPT;
- rop-railway's own Corrections log records pane-stability-ONLY producing a
  **destructive false IDLE** (it called a 7m28s `git commit --amend` "STUCK"; the
  supervisor interrupted it and discarded two briefs).

What landed is the item's own fallback clause: **run the charter's busy pattern
against a measured idle pane.** "Run the pattern, not match the pattern." The
detector models the shell PIPELINE rather than the pattern in isolation, because
the corrected charter is safe only by virtue of its `grep -v` exclusion.

**`(l)` scores ZERO fleet-wide and the zero is CONTROLLED** — the historical trap
injected in memory into four real charters returns 1 each time, an unmodified
re-scan afterwards returns 0, and the corrected charter stays clean. It gates a
REGRESSION; it remediated nothing.

## Facts worth carrying

- **The exact-target rule has a nuance the old handoff flattened.** "Only `=name`
  without the colon fails" holds for PANE-ADDRESSING commands
  (`capture-pane -t '=name'` → rc=1) but **not** for `has-session`, which accepts
  `=name` and is still exact (`=alpha` does not match `alpha-long`). Measured on a
  private socket. Existing `has-session -t "=name"` lines were therefore already
  correct and were left alone.
- **Bare targets prefix-match, and it has bitten this fleet for real.**
  `tmux list-panes -t '07-build-substrate-superv'` returned the SUPERVISOR'S OWN
  pane for a session name that does not exist.
- **`prev=""` is the same string an ABSENT session's capture returns**, so a dead
  pane counted as stable and watchers announced "idle" for sessions that no longer
  existed. Seeded with a sentinel everywhere now.
- **Archiving does NOT disarm a charter.** Two `plan/archive/` threads had worker
  AND supervisor sessions live during this sweep.
- **A `{{...}}` token in a work item makes it undispatchable** and leaves a phantom
  `active` claim. `fabro ps` is the evidence of a run; `ACTIVE` never is.

## Cross-track courtesy — discharged

Four armed charters (worker AND supervisor both live) were notified before any
edit, via `load-buffer` → `paste-buffer` → verify → separate `Enter`:
`beads-v1-1-2-upgrade`, `retire-host-dispatch-cap`, `rop-railway-enforcement`,
`console-happy-path-mvp`. Landing confirmed by the `[Pasted text …]` placeholder
or a non-empty prompt line — **never** by grepping the pane for the text, which
returns zero on a paste that landed perfectly.

## What is NOT done

- **EVERY PR IS MERGED — this section is about what the sweep did not REACH, not
  about unfinished delivery.** Verified against the forge 2026-08-03T03:33Z:
  `livespec-orchestrator-beads-fabro#1248`, `homelab#215`,
  `livespec-dev-tooling#1140`, `livespec-console-beads-fabro#602`,
  `livespec#1919`, and `livespec-overseer#542`, `#549`, `#551` — all eight MERGED.
  An earlier draft of this bullet listed four of them as OPEN, which was true when
  written and false within the hour. **Re-measure against the forge; do not trust
  this list either.**
- **`#1248` merged with an overclaiming title** ("55 defects to zero") one minute
  after a supervisor measured it as 56 → 1. The residue was the `(h)` continuation
  false positive, and `#542` **has since merged**, so the claim is now true — but
  it was not true at the moment it was published, which is the part worth keeping.
  A correction stating the precise sequencing is posted as a comment on `#1248`.
- **NOTHING ENFORCES THIS ANYWHERE BUT `livespec-overseer`, AND THAT IS BIGGER
  THAN AN EARLIER DRAFT OF THIS FILE SAID.** The draft named `homelab` as "the
  single biggest hole" because it consumes no pin. **Measured 2026-08-03: the hole
  is FIVE repos, not one.** `test_charters_carry_no_known_defects.py` exists in
  exactly one repo — a `find` across all six returns 1 copy, in `livespec-overseer`
  — and its `_REPO_ROOT` is `Path(__file__).parent.parent.parent`, so
  `test_every_charter_in_this_repo_is_free_of_the_known_defects` scans **only its
  own tree**. The other five repos have **no gate at all** and every one of them
  will drift back.

  So the sweep's 119 → 0 is a **snapshot, not a ratchet.** `homelab` is merely the
  repo that cannot be fixed by per-repo adoption (Rust/Nix — no `pyproject.toml`,
  no `justfile`, no `.mise.toml`); the other four *could* adopt it and have not.
  Filed as `overseer-x1q` (P1) rather than left in prose here. That item also
  records why widening this gate's globs to scan sibling repos is the WRONG
  shape, and that any adoption must carry the false-positive lesson with it.
- **Nothing schedules regeneration.** This sweep fixed the emitted charters; a
  thread that never re-runs `supervise-plan` keeps whatever it was given.
- **The corpus GREW while the sweep ran** — 33 charters at the start, 39 by the
  end, as other tracks opened threads. `livespec-overseer` alone went 8 → 13 while
  staying at zero. **A total measured yesterday is not a total today**; re-measure
  before quoting any number in this file.

## Discipline

Fleet-standard: worktree → PR → rebase-merge, never a commit on the primary
checkout. Never `--no-verify`; halt and report on hook failure. Never touch
another session's worktrees or branches. Never kill the acting overseer daemon in
tmux `livespec-overseer:1.1`.

**`just worktree-create` is effectively broken in THIS repo at scale** —
`worktree-lib.sh:89` pipes `git worktree list --porcelain` into an `awk` that
exits on the first match, so git takes SIGPIPE and the recipe dies at 141. Filed
as `livespec-dev-tooling-zi4q`. **Rescue path, used throughout this thread:**
`git worktree add <path> -b <branch>`, then `just install-worktree-pack` inside
it, then `git checkout -- .livespec.jsonc` to discard the `worktree_discipline`
key it writes into that tracked file. It still works normally in the other fleet
repos, which have far fewer worktrees.

**Auto-merge is enabled in several fleet repos, and it changes how you must
sequence.** Two PRs here merged themselves the moment checks went green — one
before a follow-up commit could be pushed to it, which orphaned that commit onto
the branch and cost a second PR. **Push every commit you intend to ship BEFORE
opening the PR**, and do not plan to amend a title after opening one.

**The red-green-replay ritual is a SINGLE commit with `--amend`, not two
commits**, and the test file bytes must be byte-identical across the pair. A
change confined to `tests/` has no impl bucket at all, so it takes the
green-verified leg instead: one commit, a NON-`feat:`/`fix:` prefix, and the full
suite must pass. `feat:` there is rejected with `test-passed-at-red`.
