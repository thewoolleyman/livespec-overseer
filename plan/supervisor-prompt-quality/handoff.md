# Plan — supervisor-prompt-quality

**Owning repo:** `livespec-overseer`. **Status: read it from the ledger**
(`list-work-items` / `next`; nothing here stores status). Created
2026-07-26 at maintainer direction, out of the homelab
supervisor-handoff build-out (homelab PR #37, commit `862b4d0`).

**Ledger anchor:** epic **`overseer-byvxlp`** (this repo's beads
tenant) — the full quality bar for what `supervise-plan` GENERATES,
carried in that epic's description. This thread TIES TOGETHER the
existing generated-prompt items so the maintainer can execute them in
order; it does not fork their content. After the groom the anchor is
the filed replacement-slice set rather than the epic id, since the
groom closes the epic as regroomed-out.

## The item map (ids cited read-only)

- **`overseer-byvxlp`** (epic, this thread's anchor) — the eight-family
  quality bar: iteration-stable generic form; anti-drift layering +
  Corrections preservation on regeneration; the cold-open generation
  gate; placeholder discipline; classified-remedy preconditions
  (parameterized spawn posture); wait-channel bootstrap; adopter
  parameterization; the full anti-stall playbook beyond the two stall
  modes. Will be CLOSED as regroomed-out by its own groom, replaced by
  the filed slices; this thread remains the single tie-together.
- **`overseer-hbr.16`** (S7, P1) — **CLOSED 2026-07-26.** The FLOOR:
  both stall modes (no-idle/no-silent-block AND
  never-end-a-turn-without-an-armed-re-entry) with fixtures that tell
  them apart, asserted over GENERATED output, each demonstrated RED.
  NOTE: beads forbids task-blocks-epic edges, so `overseer-byvxlp`'s
  dependency on this item and on `overseer-hbr.4` was PROSE-ONLY and
  encodable nowhere. That re-check was run 2026-07-26 and the floor is
  discharged — but this sentence is itself a claim with a timestamp, so
  re-run it rather than trusting it.
- **`overseer-hbr.4`** (bug) — **CLOSED 2026-07-26.**
  Executable-commands bar. Both clauses discharged; the second by
  PR #120 + PR #123.
- **`overseer-hbr.15`** (S6, P1) — **CLOSED 2026-07-26.** Goal-1
  acceptance outside this repo. This thread strengthens the bar it
  tests but did NOT gate it.
- **`overseer-fitvmo`** — CLOSED 2026-07-26 as superseded (stall mode 1
  restated in `overseer-hbr.16`; broader bar in `overseer-byvxlp`);
  the close reason carries the full mapping.

## Execution order (the reason this thread exists)

**Re-measured against the ledger 2026-07-26.** The prose-only floor is
DISCHARGED — `overseer-hbr.4` (executable-commands bar) and
`overseer-hbr.16` (both stall modes + tell-them-apart fixtures) are
both CLOSED, and `overseer-hbr.15` (goal-1 acceptance) is CLOSED too.
beads forbids task-blocks-epic edges, so those dependencies were never
encodable and had to be re-checked by hand; this line records that
re-check, and a future reader should re-run it rather than trusting
this sentence. The three steps this section used to list first, second
and fourth were all already discharged when it still described them as
pending — a filed item is a claim with a timestamp.

1. **Groom `overseer-byvxlp`** (the maintainer owns the cut), folding
   `overseer-7lv`'s R1–R5 residue in as replacement slices — one
   anchor, no duplication.
2. **Drain the approved slices by dependency layer.**

Note that the groom operation CLOSES `overseer-byvxlp` itself as
regroomed-out at filing time (`file_approved_slices` ends with
`close_regroomed_out`, whose reason string is machine-generated and
cannot carry narrative). So the epic closing is NOT the archive trigger
it used to be — see Discipline.

## Reference material (all verifiable, none of it status)

- **Reference implementation:** homelab @ `862b4d0` —
  `.ai/supervisor-protocol.md` (shared role-level layer) +
  `plan/<slug>/supervisor-handoff.md` ×6 (thin iteration-stable
  binders), synthesized from this repo's charters plus `livespec`,
  `livespec-orchestrator-beads-fabro`, and `livespec-dev-tooling`.
- **The generic form's prior art:** `livespec-dev-tooling`
  `plan/worktree-location-enforcement/supervisor-handoff.md`.
- **The six defect classes the cold-open dry-runs caught** in a prompt
  that already looked complete — the empirical case for the generation
  gate: an unsubstitutable `<workdir>` placeholder (three shell errors
  in one line); a Monitor wait channel whose file was never created nor
  fed; a boot brief that was a comment, not a command; an unbounded
  wait for the agent UI; a HALT precondition with no remedy (a
  guaranteed stall); a false "only placeholder" claim.

## Discipline

Fleet-standard: worktree → PR → rebase-merge; `mise exec -- git …`;
never `--no-verify`; status only from the ledger via the fleet
credential wrapper; this thread archives when the LAST replacement
slice from `overseer-byvxlp`'s groom closes — not when the epic itself
closes, because the groom closes it as regroomed-out at filing time.

---

## WORKER RESUME STATE — rewritten 2026-07-29 (15:30Z) by the `supervisor-prompt-quality` worker

**Re-measure from the ledger and the forge rather than trusting any line below.**
Every claim here is a claim with a timestamp, including this one.

### The one structural fact the previous version missed

**The remaining cut is a single serial chain, not a queue.** S4, S5, S6 and S7 all
depend on S3 (`overseer-t7qqik`); S8 depends on S4; S9 depends on S7. The previous
section called S3 "the head of the queue", which reads as though other slices were
workable. They are not. **There is no filed hand-drivable slice**, and the billing
valve therefore blocks 7 of 7 remaining slices rather than 1.

| slice | id | state at 2026-07-29 15:30Z |
|---|---|---|
| S1 HALT preconditions that classify their failure | `overseer-ykneip` | **CLOSED** |
| S2 wake mechanism end to end | `overseer-4do7jx` | **CLOSED** |
| S3 iteration-stable two-layer form | `overseer-t7qqik` | **ACTIVE, CLAIMED BUT PARKED** |
| S4 re-entry + durable obligation record | `overseer-fl5jlp` | pending-approval, blocked on S3 |
| S5 verification discipline | `overseer-nxaho7` | pending-approval, blocked on S3 |
| S6 full anti-stall playbook | `overseer-kptmgl` | pending-approval, blocked on S3 |
| S7 cold-open gate + placeholder sets | `overseer-lf7ieb` | pending-approval, blocked on S3 |
| S8 cross-track obligation handoff | `overseer-uc4l5e` | pending-approval, blocked on S4 |
| S9 adopter parameterization | `overseer-f2lqj6` | pending-approval, blocked on S7 |

`overseer-dk6hwi` (the S1/S2 delivery remainder) is **CLOSED**.

**THERE IS STILL NO APPROVE VALVE AND NONE IS NEEDED.** These items are
`admission:auto`, and the Dispatcher takes them as filed — see the next section,
which now has proof rather than a code read. `set-admission:<id>:manual` permanently
rewrites recorded policy for no benefit. **Do not run it.** S1/S2 read `manual` only
because it was run on them before that was understood; the other seven are untouched.

### THE BLOCKER — unchanged, and it is maintainer-side

**Fabro dispatch is dead org-wide on the monthly spend limit.** Re-confirmed
2026-07-29 on the FRESHEST run of all 356 (`01KYP9Z87QC3`), not on the stale quote:
`"You've hit your org's monthly spend limit"`, `errorKind: rate_limit`. The
maintainer has taken the valve (answer: raise it).

**WHEN IT CLEARS, DO THIS FIRST.** S3 sits `active`/`fabro` with nothing working it,
claimed by parked run `01KYP93877SDPHC7DVM0BXRJ33`. That state is invisible to
`ledger-normalize` and **cannot be re-dispatched from `active`** — the run must be
resumed or the claim reset before S3 moves. Do not wrap `dispatcher.py dispatch` in
a short timeout; it BLOCKS for the entire life of the run.

### What landed this session

**PR #276 — rebase-merged, forge-verified on `origin/master` at `7efc528` after a
fetch. 61 CI checks pass, 1 skip, 0 fail.** This is the local-first half of the
remediation gap, chosen by the maintainer over the fleet-wide sweep.

- `tests/prompts/test_charters_carry_no_known_defects.py` — 12 tests, 100% coverage
  (135 statements, 52 branches, 0 missed), gating defect classes (a) bare tmux
  target, (b) unguarded `readlink -f`, (c) history-fed picker capture, (d) `prev=""`
  watcher init, over **every** charter in this repo.
- The sweep of all four dirty charters to the exemplar's forms.

A pytest module rather than a new `just check-<slug>`: `check-aggregate-completeness`
makes wiring one canonical slug force wiring every other, and `tests/prompts/` is
already an enforced surface.

**THE DETECTORS READ FENCED CODE ONLY, and that is the load-bearing design choice.**
The untracked prototype scanned whole files and counted PROSE mentions of a hazard as
instances of it — the hand-hardened exemplar scored 3 on (b) with **zero** defective
code, because the section intro says "readlink -f first" and Correction C2 quotes
`readlink -f ""` while EXPLAINING the bug. A detector that fires on the documentation
of a fix makes hardening a charter RAISE its score. The exemplar is now a **positive
control** in the suite: any hit on it is a defect in the module, not in the charter.

(c) is deliberately narrow for the same reason. A bounded `capture-pane -S -N` read is
a legitimate inspection that the exemplar performs; only the bound
(`pane=$(... -S -40)`) and grep-piped forms are flagged.

RED demonstrated four ways, each reverted: genuinely red before the sweep (43 offences
across 4 charters, every fixture leg green); one restored bare target reddens the gate;
a quote-blind comment stripper reddens the gate, because real charters carry
`'#{pane_pid}'` and truncating there MANUFACTURES a bare target; widening (c) to every
`-S` reddens the exemplar control. **Two detector false results were found by sweeping
REAL charters rather than by imagining cases**, and both directions are now pinned.

**KNOWN LIMIT, stated rather than hidden:** inline backticked commands in PROSE are not
scanned. `plan/archive/ship-overseer-to-fleet/supervisor-handoff.md` line 19 still reads
``tmux has-session -t ship-overseer-to-fleet`` inside a numbered list. That is
deliberate — scanning prose is exactly what made the prototype unusable.

### `overseer-8jg` was REFUTED and rescoped

Its premise was measured false and the wrong half was in its TITLE. Retitled to the real
bug, description replaced, acceptance rewritten; the full refutation is preserved in the
item's NOTES (read-back asserted).

- **Survives:** "approve refuses (needs manual)" — true.
- **Refuted:** "every dispatch path refuses (not ready)". All three paths route through
  `ready_items` -> `is_dispatch_candidate`, which does `replace(item, status="ready")`
  and re-tests, so admission never refuses there. Only `next.py:138` uses the strict
  predicate, which is the sole reason the state ever LOOKED terminal.
- **Empirical, not just a code read:** S3 carries `admission:auto`, was
  `pending-approval`, was NEVER flipped to manual — and dispatched anyway as run
  `01KYP93877SD`, which reached the implement node before failing on billing.
- **Real cause of the observed refusals:** the dead mint `overseer-wc2xfe` failing closed
  as an unresolvable cross-repo sibling. The item is now about that diagnostic gap: an
  unresolvable sibling reports bare "not in the ready set" and names neither the sibling
  nor the fail-closed.

This discharged supervisor Correction C10's corollary, which had been recorded in a
charter and propagated nowhere — an obligation living in exactly the gap R3/S4 exist to
close. Also re-verified C11's fix held: `non_local_depends_on` reads back as type `list`,
not the string `"[]"`.

### The remainder of the remediation gap

The maintainer chose **local-first**, which is done. The fleet-wide half is NOT filed and
remains the maintainer's cut: **130 bare targets, 18 files, 6 repos** measured 2026-07-29
(down from 141/17/7 the previous day — the population MOVES, so re-measure rather than
citing this). Six threads are ARMED across five repos. The write-up with four costed
options is at `tmp/overseer/supervisor-prompt-quality/GAP-no-remediation-slice.md`.

The gate that just landed is repo-local. Adopting it elsewhere is a per-repo decision and
nothing here schedules it.

### Durable artifacts (gitignored — present in this working tree only)

`tmp/overseer/supervisor-prompt-quality/` holds `FILED-RESULT.md`,
`EVIDENCE-REVERIFICATION.md`, `GAP-no-remediation-slice.md`, `S1-COVERAGE-MAP.md`,
`S2-COVERAGE-MAP.md`, `LIVE-EXPOSURE-rop-sweep.md`, `worker-status.log` (the supervisor's
wake channel), and `evidence/` — including `blast_radius.py`, the prototype whose
prose-scanning flaw motivated the fenced-code-only design. **A fresh clone has none of
it.** The artifacts that mattered are now TRACKED, which was the point.

### Hazards to carry forward

- **`overseer-wc2xfe` is a DEAD MINT** — it exists in no tenant. Both deps were repointed
  to `livespec-dev-tooling-myx7` and verified by read-back. S0 was only ever a GATING
  handle; the DOING record is myx7, and S0 **must never be worked in this repo**.
- **The commit prefix is semantically load-bearing.** A tests-only staged tree with a
  `fix:`/`feat:` subject routes into RED mode, which REJECTS a passing test. A passing
  test-only change must use `test:`.
- **`git checkout -- <file>` reverts to HEAD, not to your uncommitted work.** Restoring a
  sabotage that way during a RED demonstration silently wiped a completed sweep, and the
  next run's failure read as a broken test. Check `git status` after restoring.
- **`PIPESTATUS` is bash; this shell is zsh** (`$pipestatus[1]`, lowercase, 1-indexed).
  The bash spelling yields an EMPTY string, which reads like a pass.
- **Check `git status`, not `git log`, after a hook-gated commit** — a rejected commit
  leaves the change STAGED and `git log` shows someone else's HEAD.
- **`just worktree-reap` cannot see a rebase-merged branch as merged** (the SHA changes),
  so it skips your own worktree and offers `--force`, which would act on every other
  track's. Remove only your own.

### Boundaries

The supervisor owns this file's sections ABOVE the separator. Do not touch branches
`docs/supervisor-charter-hardening`, `docs/regenerate-supervisor-prompt-quality-charter`,
or `docs/handoff-execution-order-correction`. Worktrees via `just worktree-create`, never
raw `git worktree add`. Never `--no-verify`; halt and report on hook failure. Never kill
the acting overseer daemon in tmux `livespec-overseer:1.1`.
