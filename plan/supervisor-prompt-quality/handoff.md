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

## WORKER RESUME STATE — updated 2026-07-30 (01:15Z) by the `supervisor-prompt-quality` worker

### THE TOP OPEN ITEM: the generator that RUNS has none of these fixes

**Read this before doing anything else with the generator.** Fixing
`.claude-plugin/prose/supervise-plan.md` in this repo does NOT fix the generator
that produces charters. Measured 2026-07-29 across **all nine** cached plugin
versions under `~/.claude/plugins/cache/livespec-overseer/`: **zero** contain the
exact-target mandate (S1's fix) and **zero** contain the supervisor liveness
proof (`overseer-ejja5o`'s fix). Newest cache dir resolved with
`find -printf '%T@ %p\n' | sort -rn`, never `ls` (C6).

This is not a lone reading. Commit `ef4b098` states it while hand-hardening a
charter to unbreak master: *"Fixing the generator in the repo does not fix the
generator that runs."* That charter was generated from the stale `0.12.2` cache
**~17h after** S1's fix merged, and arrived with 12 bare targets and an unguarded
`readlink`.

Two consequences, both load-bearing:

1. **The charter gate is earning its keep already** — it is what turned master
   red on that charter, the same day the gate landed. That is exactly the "stop
   the population growing" case `GAP-no-remediation-slice.md` predicted.
2. **Every generator fix in this thread is inert until a release ships.** The
   contract test asserts the REPO's prose, which is not the artifact that
   produces charters — the deepest form of the verifier-that-cannot-fail shape
   this thread exists to remove, and the same REGISTRATION IS NOT INSTALLATION
   pattern `ship-overseer-to-fleet` recorded.

**This is a maintainer/release-lane decision and was deliberately NOT built.**
Three candidate shapes: (a) assert the INSTALLED plugin's prose satisfies the
contract — cannot run in CI where no cache exists, and needs a no-skip answer;
(b) a release-hygiene check that a prose change forces a version bump; (c) accept
it and document the release step as mandatory after any prose fix. Real competing
costs, so it is a genuine valve rather than a plan to execute.

### The charter gate now covers SIX defect classes, all keyed on the PROPERTY

`tests/prompts/test_charters_carry_no_known_defects.py`, in `just check`:

| class | keys on the ABSENCE of |
|---|---|
| (a) bare tmux target | an exact `'=name:'` target |
| (b) unguarded path resolution | a non-empty guard before `readlink -f`/`realpath` |
| (c) history-fed capture | visible-only capture feeding the picker test / pane diff |
| (d) empty watcher seed | a sentinel no real capture can equal |
| (e) supervisor trusted by name | a supervisor process-tree liveness proof |
| (f) regex session-existence test | `grep -F`, so the match is LITERAL |

**THE DESIGN RULE THAT PRODUCED THAT COLUMN — carry it forward.** A detector must
key on the **absence of the correct property**, never on the **presence of one
wrong spelling**. It was learned the hard way: class (e) pinned the literal `-qx`,
so the moment (f) was remediated to `-Fqx` the (e) detector **went blind** and
stopped firing on the very charters it had flagged an hour earlier. A detector
keyed to another defect's pre-fix spelling is a verifier that **disarms itself
when the neighbouring fix lands** — a failure mode that appears only where two
remediations meet, which is why inspecting either one alone will never find it.
`test_remediating_f_does_not_disarm_e` pins the instance that actually happened;
(b) and (d) were then re-keyed the same way before anything walked through them.

### Landed since 19:45Z — all merged, all forge-verified after a fetch

- **PR #293** — gate class (e) plus the sweep of the four charters carrying it.
- **PR #296** — gate class (f). `grep -qx` is exact-LINE but its pattern is still
  a REGEX: proven on a private socket, with a session `axb` alive `grep -qx 'a.b'`
  MATCHES while `grep -Fqx 'a.b'` refuses. LATENT, not live — it needs a regex
  metacharacter in a session name and slugs are `[a-z0-9-]`. Also fixed a prose
  Corrections entry that was PRESCRIBING the incomplete `grep -qx` as C1's remedy.
- **PR #297** — corrected a backwards coreutils attribution and closed the
  `realpath` evasion in (b).
- **PR #300** — closed (d), the last spelling-keyed detector, strictly additively.

### An environmental fact that was recorded WRONG for days

**This host runs uutils coreutils 0.2.2 for BOTH `readlink` and `realpath` — not
GNU.** Measured 2026-07-30:

    readlink -f ""      rc=0, prints $PWD    FALSE PASS
    readlink -f -- ""   rc=0, prints $PWD    the `--` does NOT save it
    realpath ""         rc=1                 fails safe

So the false pass belongs to **uutils**; GNU exits 1 and fails safe by accident.
`test_repo_containment_discriminates.py` had this mapping right all along and
`test_charters_carry_no_known_defects.py` had it inverted — **two files in one
directory disagreeing about an environmental fact is how a wrong belief survives
review**, and the one that was easy to check was the wrong one. The emitted
charter form was never unsafe: the non-empty guard is what saves it, and the `--`
guards a leading-dash path, a different hazard. Only the explanation was wrong.

**Re-measure from the ledger and the forge rather than trusting any line below.**
Every claim here is a claim with a timestamp, including this one. Two claims in
the 15:30Z version went stale within hours — the blocker and S3's state — and
both are corrected below rather than edited away.

### `overseer-ejja5o` is DELIVERED — PR #286, merged

The supervisor-side liveness precondition. `supervise-plan` refused to trust a
session NAME for the worker and then trusted one for the supervisor; observed
2026-07-28, a supervisor session created as a bare `zsh` returned PASS, so a
session that could not supervise anything cleared the gate.

Precondition 3 now resolves BOTH pids in its own block (it cannot pass on an
unset `$pane_pid` inherited from precondition 2), guards the supervisor pid
non-empty, guards it **distinct from the worker's pane**, and runs the same
process-tree proof precondition 2 uses. Fixed in
`.claude-plugin/prose/supervise-plan.md` **and** in the exemplar charter.

**The exemplar carried the defect too, and that was not in the item.** Its C1
hardening (exact `'=name:'` targeting) is a DIFFERENT defect from agent liveness.
Adding the requirement went red on **three** legs — generator prose, exemplar, and
the contract module's own conformant control. Fixing only the prose would have
left the positive control red.

Two rungs: `test_generated_supervisor_handoff_contract.py` (over generated
output — a needle PLUS a structural check, because `pane_pid` is a substring of
`supervisor_pane_pid` and the worker's own binding would otherwise satisfy it)
and `test_supervisor_liveness_discriminates.py` (real tmux, private socket). The
two halves fail INDEPENDENTLY in both directions, so a red verdict names which
half broke.

### ejja5o vs `overseer-2a1` — I checked, and the alarming reading was WRONG

`overseer-2a1` records that 4 of 5 HALT preconditions need a live session that a
NEW plan thread does not have yet. ejja5o tightened one of those preconditions, so
the obvious worry is that it made 2a1 strictly worse. **Measured: it did not.**

2a1's observed failure was `can't find session` — the session was ABSENT. The
emitted block HALTs at `tmux has-session` BEFORE resolving the pid or running
`ps`, so an absent supervisor session halts at the same check with the same
message as before. What changed is narrow and is exactly the defect ejja5o
closed: a supervisor session that EXISTS but holds only a bare shell used to pass
and now HALTs. The cost lands only on 2a1's recorded workaround, which now also
needs an agent in the supervisor pane — and that is often free, since running
`supervise-plan` FROM the supervisor session means that session already holds the
agent running the skill.

**What ejja5o DOES do is strengthen 2a1's second candidate shape** — split the
preconditions so artifact-only checks gate AUTHORING and live-session checks gate
DRIVING. There are now five live-session checks against one artifact check, which
makes the authoring/driving split the obvious cut rather than one option of three.
**Not acted on: `overseer-2a1` is `pending-approval` and the ledger is the
supervisor's.**

### Ledger state — there are NO ready items

15 backlog, 15 pending-approval, 2 active, **zero ready**. `ejja5o` was the
top-ranked ready item and it is delivered. Nothing is hand-drivable without the
supervisor releasing an item, and this worker does not transition, approve, or
set-admission on anything.

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
| S3 iteration-stable two-layer form | `overseer-t7qqik` | pending-approval (reset from a dead claim, twice) |
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

### THE BLOCKER — IT IS NO LONGER THE SPEND LIMIT

**This section said "the monthly spend limit" for most of 2026-07-29 and that is
now WRONG. Do not re-assert it.** The live gate is the **host Codex credential**:
a re-dispatch failed FAST at stage `run-config-overlay` with `fabro_run_id`
**null**, carrying *"Host Codex credential is too short-lived for the run budget;
run `codex login` on the orchestrator host to renew it."* `codex-cred-status`
reports the credential present and well-formed but with `alarm true` and
`refresh_due FALSE`, and `codex-cred-refresh` returns `noop-not-due` — outside
the refresh guard, so codex is never invoked and **the automated path cannot fix
it.** It needs an interactive login only the maintainer can run.

**CONSEQUENCE, and this is the part worth carrying:** whether the Anthropic spend
limit is still exhausted is now **UNVERIFIED, not cleared.** No run was ever
created, so the cap was never reached and never tested. Record it as unknown.
A separate track (`codex-parity-and-rollout-safety`, its own PR #274) has
independently diagnosed the billing cap across five runs, two repos and four
work-items — **that PR is theirs, not this thread's.**

**S3's parked-run advice is also retired.** Run `01KYP93877SDPHC7DVM0BXRJ33` went
TERMINAL (`failed`/`workflow_error`), so it is not resumable. The supervisor reset
S3 to `pending-approval` — **twice**, because a dispatch that fails at
`run-config-overlay` still CLAIMS the item even though no run exists and
`fabro_run_id` is null. S3 now reads `pending-approval`, `admission:auto` intact.
Do not wrap `dispatcher.py dispatch` in a short timeout; it BLOCKS for the entire
life of the run.

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

### What is TRACKED versus what only exists on this host

The two most valuable findings of 2026-07-29/30 — the stale-plugin-cache gap and
the detector self-disarm rule — were reached in a **gitignored** log and would have
died with this working tree. They are recorded above for that reason. When a
finding is worth carrying, the handoff or a test is where it goes; the wake channel
is a transcript, not storage. That criticism was made of this thread's own evidence
earlier the same day, so it applies here too.

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
  track's. Remove only your own. **Now filed as `overseer-btt` (P1)** — its merged-ness
  test is `merge-base --is-ancestor "$wt_head" "$base_ref"` at
  `dev-tooling/worktree-lib.sh:347`, and rebase-merge replays work as a NEW SHA, so a
  correctly-landed branch is never an ancestor. Measured 0 to remove, 19 skipped, while
  `needs-attention`'s hygiene lane lists those same worktrees as removable — two tools in
  this repo disagreeing. **Do not reap them; most belong to other tracks.**
- **A `test:` subject is not cosmetic when the `.py` bucket is tests-only.** A
  `fix:`/`feat:` subject on a tests-only staged tree whose tests PASS is rejected as
  `test-passed-at-red`. Markdown does not enter the `.py` bucket, so a change that fixes
  generator prose plus its tests is still "tests-only" to the hook.
- **Restore a sabotage from a byte copy, never `git checkout -- <file>`.** That reverts to
  HEAD rather than to your uncommitted work, and it silently wiped a completed sweep here;
  the next run's failure then reads as a broken test rather than a lost edit.
- **A GREP THAT MATCHES NOTHING IS INDISTINGUISHABLE FROM A CLEAN PASS, and this bit
  the verification of a verifier.** A sabotage run piped through
  `pytest ... | grep -E '^FAILED'` printed nothing, which read as "my new check is not
  load-bearing" — one step from deleting a working check as dead code. Re-run with FULL
  output, the sabotage reddened exactly the intended leg. The charter's pipe-exit-code
  rule already covers this, but note WHERE it landed: not on the code under test, on the
  step that was supposed to prove the test could fail. **When a sabotage produces no
  output, that is the one result you must never accept without reading the artifact** —
  a silent sabotage and a sound check look identical.
- **Widening a detector is a chance to silently REMOVE what it already caught.** When
  re-keying (b) and (d) from a spelling to a property, the original literal rules were
  RETAINED and asserted directly, rather than trusted to fall out of the broader rule.
  Prove the old shape still reddens; do not infer it.
- **`--set-metadata` stores STRINGS.** Clearing a list-valued field with it prints
  `✓ Updated` and stores `"[]"`, which the consumer then walks character-wise. Rewrite the
  whole object via `--metadata @file.json` and assert the TYPE on read-back, not the
  rendered value (Correction C11).

### Boundaries

The supervisor owns this file's sections ABOVE the separator. Do not touch branches
`docs/supervisor-charter-hardening`, `docs/regenerate-supervisor-prompt-quality-charter`,
or `docs/handoff-execution-order-correction`. Worktrees via `just worktree-create`, never
raw `git worktree add`. Never `--no-verify`; halt and report on hook failure. Never kill
the acting overseer daemon in tmux `livespec-overseer:1.1`.
