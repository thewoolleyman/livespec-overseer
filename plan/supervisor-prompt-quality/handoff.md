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

## WORKER RESUME STATE — rewritten 2026-07-29 by the `supervisor-prompt-quality` worker

**Everything the previous version of this section called "the next action" is
DONE.** It said filing was held on the tmux valve; that valve was answered, the
groom was filed, and two PRs have since landed. Re-measure from the ledger and
the forge rather than trusting any line below — every claim here is a claim with
a timestamp.

### Where the work actually is

**The groom is FILED and the epic is closed.** `overseer-byvxlp` closed
regroomed-out; `overseer-7lv` hand-closed carrying the R→id mapping
(R1,R2→S4 · R3→S8 · R4→S5 · R5→S2).

| slice | id | state at 2026-07-29 |
|---|---|---|
| S1 HALT preconditions that classify their failure | `overseer-ykneip` | **CLOSED** |
| S2 wake mechanism end to end | `overseer-4do7jx` | **CLOSED** |
| S3 iteration-stable two-layer form | `overseer-t7qqik` | pending-approval, deps discharged |
| S4 re-entry + durable obligation record | `overseer-fl5jlp` | pending-approval |
| S5 verification discipline | `overseer-nxaho7` | pending-approval |
| S6 full anti-stall playbook | `overseer-kptmgl` | pending-approval |
| S7 cold-open gate + placeholder sets | `overseer-lf7ieb` | pending-approval |
| S8 cross-track obligation handoff | `overseer-uc4l5e` | pending-approval |
| S9 adopter parameterization | `overseer-f2lqj6` | pending-approval |

Plus **`overseer-dk6hwi`** — the delivery remainder filed when S1/S2 closed
having landed only their text half. **CLOSED** by the supervisor against PR #261.

**THERE IS NO APPROVE VALVE AND NONE IS NEEDED.** These items are
`admission:auto`; `effective_admission_policy` returns the per-item policy first,
and the Dispatcher's selection already treats `pending-approval` as a candidate
by projecting it to ready. `drive --action approve:<id>` REFUSES them — approve
requires an effective-MANUAL item. Forcing it needs `set-admission:<id>:manual`
first, which permanently rewrites recorded policy as a side effect. **Do not.**
(S1/S2 carry `admission:manual` because that two-step WAS run on them, before it
was understood to be unnecessary. The other seven are untouched — keep it so.)

### What is now proven IN THE GATE (this is the thread's whole point)

The epic's enforcement ladder is static prose → generated output → observed
conduct. Rung 3 now runs in `just check`, in `tests/prompts/`:

- **PR #261** (merge `eb14416b4`) — `test_emitted_commands_discriminate.py`,
  9 tests, defect **(a)**: bare tmux targets deliver into the supervisor's own
  pane while `-t '=<name>:'` refuses.
- **PR #262** (merge `2dbccf46b`) — `conftest.py` (the real-tmux rig),
  `test_repo_containment_discriminates.py` **(b)**, and
  `test_watcher_wake_discriminates.py` **(c)/(c′)/(d)**.

All drive REAL tmux on private sockets. **NO SKIPS is real**: if tmux is absent
the modules FAIL rather than skip, and the guard that enforces that carries a
`# pragma: no cover` WITH a do-not-delete rationale — it is unreachable when tmux
is present, so it is exactly the line a `fail_under=100` gate would otherwise
reject.

`livespec-dev-tooling-myx7` is **CLOSED** and **tmux 3.4 IS in the pinned CI
image** (`python-v1.0.5`, digest `sha256:305aefaf…`). The green-locally /
red-in-CI gate that blocked every execution leg is GONE.

### THE NEXT ACTION — and what actually blocks it

**Fabro dispatch is dead org-wide on the monthly spend limit.** S3's run
`01KYP93877SDPHC7DVM0BXRJ33` failed inside the implement node with
`rate_limit / transient_infra` and escalated to `blocked/human_input_required`.
**The supervisor holds that valve with the maintainer.** Do not dispatch, do not
retry, do not touch S3's ledger state.

So: **hand-driven work in this pane is the only lane that moves.** When capacity
returns, S3 is the head of the queue — its dependencies are discharged and it
carries no `non_local_depends_on`.

### THE ONE UNFILED FINDING worth carrying forward

**The cut fixes the GENERATOR and remediates none of the charters already
emitted.** Measured 2026-07-28: grepping all nine slices for remediation language
gives exactly one hit, in S3, and it is family 2's "regeneration must PRESERVE
Corrections" — a property, not a sweep. Complete scan (`plan/*/`,
`plan/archive/*/`, `.ai/`, `tmp/<session>/charter.md`): **141 bare targets, 17
files, 7 repos**, with **six threads ARMED** — both sessions alive, defect
dormant until the worker exits — across five repos. `ship-overseer-to-fleet` is
the instructive one: its charter is ARCHIVED but both its sessions still run, so
archiving a thread does NOT disarm it.

Write-up with four costed options is in
`tmp/overseer/supervisor-prompt-quality/GAP-no-remediation-slice.md`. **Nothing
filed — the maintainer owns the cut.** Recommendation there: put the check in the
gate to stop the population growing, then sweep what it exposes.

### Durable artifacts (gitignored — present in this working tree only)

`tmp/overseer/supervisor-prompt-quality/` holds `FILED-RESULT.md` (what was
minted + the dead-mint hazard), `EVIDENCE-REVERIFICATION.md`,
`GAP-no-remediation-slice.md`, `S1-COVERAGE-MAP.md`, `S2-COVERAGE-MAP.md`,
`LIVE-EXPOSURE-rop-sweep.md`, `worker-status.log` (the supervisor's wake
channel), and `evidence/` — including `blast_radius.py` and
`adopter_validator_drive.py`, both written by this thread. **A fresh clone has
none of it.** The two artifacts that mattered most (`red-green-harness.sh`'s
legs, and the discriminate fixture) are now TRACKED, which was the point.

### Hazards to carry forward

- **`overseer-wc2xfe` is a DEAD MINT** — `file_approved_slices` minted it for the
  cross-repo S0 slice and wrote it into S1/S2's `non_local_depends_on`. It exists
  in **no tenant**. Both deps were repointed to `livespec-dev-tooling-myx7` and
  verified by read-back. S0 was only ever a GATING handle; the DOING record is
  myx7, and S0 **must never be worked in this repo**.
- **The commit prefix is semantically load-bearing.** `red_green_replay.py`
  routes a tests-only staged tree whose subject matches `fix:`/`feat:` into RED
  mode, which then REJECTS a passing test. A passing test-only change must use
  `test:`. Red mode is also PER-FILE — one test file per commit.
- **`PIPESTATUS` is bash; this shell is zsh** (`$pipestatus[1]`, lowercase,
  1-indexed). The bash spelling yields an EMPTY string, which reads like a pass.
  Prefer reading the artifact, or run inside an explicit `bash -c`.
- **Check `git status`, not `git log`, after a hook-gated commit** — a rejected
  commit leaves the change STAGED and `git log` shows someone else's HEAD.
- **`just check` passing locally does not mean CI passes.** PR #262's first push
  was green locally and failed CI twice on timing-dependent coverage. Verify
  inside the pinned image (`docker run … python-v1.0.5`) before pushing anything
  that touches these fixtures.

### Boundaries

The supervisor owns this file's sections ABOVE the separator, and the archiving
of `plan/archive/supervise-plan-residual-gaps/` (already archived). Do not touch
branches `docs/supervisor-charter-hardening`,
`docs/regenerate-supervisor-prompt-quality-charter`, or
`docs/handoff-execution-order-correction`. Worktrees via `just worktree-create`,
never raw `git worktree add`. Never `--no-verify`; halt and report on hook
failure. Never kill the acting overseer daemon in tmux `livespec-overseer:1.1`.
