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

## WORKER RESUME STATE — re-measured 2026-07-30 05:39Z by the `supervisor-prompt-quality` worker

**Everything below is a claim with a timestamp. Re-measure from the ledger and the
forge before acting on any of it.** This section has been wrong about the blocker
three separate times in two days, which is the best reason to distrust it.

**AND ITS TIMESTAMPS HAVE THEMSELVES BEEN WRONG.** The previous rewrite was
labelled "05:50Z" and its measurement "05:45Z", but its file mtime was 05:33:50Z
and the commit carrying it (`b671cf5`) landed 05:26:42Z — both labels postdate the
artifact they describe. Local here is CEST (+0200), so a local-clock reading
published with a `Z` is the likely cause; see the `date -u -r` entry under Hazards.
Worth correcting rather than shrugging at, because "a filed item is a claim with a
timestamp" is S5's whole point and a stamp that cannot be true undermines it.

### Where the epic actually is — re-measured 2026-07-30 05:39Z

| slice | id | state |
|---|---|---|
| S1 HALT preconditions classify their failure | `overseer-ykneip` | **CLOSED** |
| S2 wake mechanism end to end | `overseer-4do7jx` | **CLOSED** |
| S3 iteration-stable two-layer form | `overseer-t7qqik` | **CLOSED** |
| S4 re-entry + durable obligation record | `overseer-fl5jlp` | **CLOSED** |
| S5 verification discipline | `overseer-nxaho7` | **CLOSED** |
| S6 full anti-stall playbook | `overseer-kptmgl` | **CLOSED** |
| S7 cold-open gate + placeholder sets | `overseer-lf7ieb` | **CLOSED** |
| S8 cross-track obligation handoff | `overseer-uc4l5e` | PR #317 **MERGED** (`57426df`), CI green, acceptance verified; item still `active` |
| S9 adopter parameterization | `overseer-f2lqj6` | `active`, run **`01KYRQPHDMSE` in flight** |

**THREE OF THESE NINE MOVED between the previous rewrite and this one**, which is
the whole argument for the re-measure instruction above: S7 was recorded as
`active` and is CLOSED; S8 was recorded as a run in flight and had already merged;
S9 was recorded as `pending-approval` behind S7 and is dispatched and running.
Re-measure again rather than trusting this table.

**S8's acceptance is verified discharged**, so it can be closed on evidence and
not merely on the merge. `57426df` adds `invalid_handoff_confirmations()` wired
into `missing_requirements()`, and four tests cover exactly the four acceptance
legs: sender-held with both confirmations `none` stays the SENDER's obligation (no
violation); peer-held missing `receipt_ack` rejected; peer-held missing
`peer_recorded` rejected; peer-held with both accepted. The detector keys on the
PROPERTY — a peer holder with an absent confirmation — not on one wrong spelling,
so it obeys the design rule in the gate-class section below, and the strings it
returns name WHICH confirmation is missing. `tests/prompts`: 123 passed at
`b671cf5`.

**Closing a hand-merged item is the SUPERVISOR's lane, not the worker's** — S7 is
done, S8 is the one now waiting. `dispatch` blocks for the life of a run and the
Bash tool caps at 20 min, so the launcher is always killed — which detaches
without killing the run, but the launcher is also what merges the PR and closes
the item. Each success needs finishing by hand: merge if CI is green, then
`reconcile-merged --repo <path> --item <id>` (it REQUIRES
`--item`; there is no sweep-all form). **Do not do this as the worker. Do not
dispatch, transition, approve, or set-admission on anything.**

### THE CHARTER IS NOW TWO LAYERS — this changes where things live

S3 landed the layered form, so master carries:

- **`.ai/supervisor-protocol.md`** — the shared role layer, holding all **16**
  Corrections (C1–C16). Verified present with 16 entries.
- **`plan/supervisor-prompt-quality/supervisor-handoff.md`** — a thin binder, now
  **126 lines** (was ~700).

S3 was **salvaged, not reimplemented**: its run completed implement and
janitor-green then died at review before the token rotation, and the PR stage is
downstream of review, so nothing reached the forge. The implement diff was
recovered with `fabro dump` (`stages/002-implement@1/diff.patch`) and landed by
hand as PR #307, with all 16 Corrections verified byte-equivalent — that patch
deletes 581 lines from the file whose whole purpose is accumulating corrections,
so that verification was load-bearing.

**Consequence for anyone editing the charter:** role-level content goes in the
shared layer; only bindings, thread-specific valves and the per-thread Corrections
log belong in the binder. Both layers are read together by the validators.

### THE BLOCKER WAS NEVER BILLING — carry this, it cost days

The provider error text reads *"You've hit your org's monthly spend limit · ask
your admin to raise it"*. **That message can mean an exhausted
`CLAUDE_CODE_OAUTH_TOKEN` rather than an account budget.** Confirmed by outcome:
review nodes started passing immediately after the token was rotated. The
supervisor diagnosed an account budget repeatedly and escalated it on that text
alone.

Two rules follow, and the second is a mistake this thread made in writing:

1. **Name WHICH credential you measured.** See `.claude/CLAUDE.md` §"The fleet has
   SEVERAL Anthropic credentials" — cited, deliberately not restated, per that
   section's own instruction. This handoff previously said "the Anthropic spend
   limit is UNVERIFIED" with no credential named, which is exactly the failure that
   section exists to prevent.
2. **The factory path is `CLAUDE_CODE_OAUTH_TOKEN`**, not
   `ANTHROPIC_API_KEY_LIVESPEC_E2E`. A probe on the E2E key, or on interactive
   `claude -p`, is NOT evidence about the factory. The Dispatcher's Claude
   pre-flight is presence-only, so a present-but-exhausted token passes and the run
   dies mid-review.

The Codex credential gate is separate and is **open**: measured 2026-07-30 03:05Z,
`alarm false`, `refresh_due false`, expires 2026-08-08, ~9.55 days remaining
against a ≥18000s gate.

### THE TOP OPEN ITEM — the generator that RUNS still has none of these fixes

**Read this before touching the generator.** Fixing
`.claude-plugin/prose/supervise-plan.md` in this repo does NOT fix the generator
that produces charters. Measured 2026-07-29 across **all nine** cached plugin
versions under `~/.claude/plugins/cache/livespec-overseer/`: **zero** carry the
exact-target mandate and **zero** carry the supervisor liveness proof. A charter
generated on this host ~17h after the exact-target fix merged still arrived with 12
bare targets, from the stale `0.12.2` cache — and the charter gate is what turned
master red on it (`ef4b098`).

So every generator fix in this epic is **inert until a release ships**, and the
contract test asserts an artifact that does not produce charters. This is the
deepest form of the verifier-that-cannot-fail shape the epic exists to remove.

**RE-MEASURED 2026-07-30 05:47Z — the claim holds, and it is worse than "nine
stale versions".** All nine cached `prose/supervise-plan.md` files are
**BYTE-IDENTICAL** (one `md5sum`, `2283862c…`), so this is ONE frozen artifact
under nine names, not a rollout that is merely behind. There is no gradation to
partially credit.

| probe | master | all 9 caches |
|---|---|---|
| `WORKER_TARGET='=` (exact-target mandate) | 6 | **0** |
| `supervisor_pane_pid` (liveness proof) | 4 | **0** |
| bare `-t "` targets (defect class (a)) | **0** | **4** |
| prose length | 485 lines | 291 lines |

The active version is `efe607c6a3e7` (what the session-start hook reports as "the
latest"), and its four bare targets are at lines 53, 63, 74 and 90 — so the
generator running on this host RIGHT NOW emits the exact defect class the charter
gate exists to catch. Master is at `0.13.3`; **PR #244 (`chore(master): release
0.14.0`) is OPEN and unmerged**, which is the release that would carry every fix
in this epic to the thing that actually generates charters.

**Run the positive control if you re-measure this.** A zero count from a grep is
indistinguishable from a wrong pattern, and this exact probe returns zero on all
nine caches — the control is that the same two patterns score 6 and 4 on master.
Without it the measurement is worthless.

**Deliberately NOT built — it is a release-lane decision.** Three candidate shapes:
(a) assert the INSTALLED plugin's prose satisfies the contract — cannot run in CI
where no cache exists, and needs a no-skip answer; (b) a release-hygiene check that
a prose change forces a version bump; (c) accept it and document the release step
as mandatory after any prose fix. Real competing costs, so it is a genuine valve.

### The charter gate — SEVEN classes, all keyed on the PROPERTY

`tests/prompts/test_charters_carry_no_known_defects.py`, running in `just check`:

| class | keys on the ABSENCE of |
|---|---|
| (a) bare tmux target | an exact `'=name:'` target |
| (b) unguarded path resolution | a non-empty guard before `readlink -f`/`realpath` |
| (c) history-fed capture | visible-only capture feeding the picker test / pane diff |
| (d) empty watcher seed | a sentinel no real capture can equal |
| (e) supervisor trusted by name | a supervisor process-tree liveness proof |
| (f) regex session-existence test | `grep -F`, so the match is LITERAL |
| (g) bash `PIPESTATUS` under zsh | the zsh spelling `$pipestatus[1]` |

**THE DESIGN RULE THAT PRODUCED THAT COLUMN — carry it forward.** A detector must
key on the **absence of the correct property**, never on the **presence of one
wrong spelling**. Learned the hard way: (e) pinned the literal `-qx`, so the moment
(f) was remediated to `-Fqx` the (e) detector **went blind** on the charters it had
flagged an hour earlier. A detector keyed to another defect's pre-fix spelling
**disarms itself when the neighbouring fix lands** — a failure mode that appears
only where two remediations meet, so inspecting either alone will never find it.
`test_remediating_f_does_not_disarm_e` pins the instance that happened.

Scope limits, stated rather than hidden: the detectors read **fenced code only**, so
inline backticked commands in prose are unscanned; and (e) fires only on a charter
that actually emits a supervisor check.

### S7's fix, in case it recurs

PR #316 was red on S7's own gate at blocks 1 and 9 with coverage at 100%. The cause
was **none** of the three shapes it looked like: the harness's **stub set was
incomplete**. `bd` was the only unstubbed command across all 11 blocks (7 shared +
4 binder), so `bd show` failed and the `||` HALT branch exited 1.

The gate stubs `tmux`, `ps`, `sleep`, `seq` — external-state blocks were never out
of scope, standing in for the tool IS how the gate holds executability. Adding a
`bd` stub keeps every block required to execute. The stub **discriminates** (a
blanket `exit 0` would retire the execution leg for every ledger block), and the
narrowing-free result was RED-demonstrated asymmetrically: blanket `exit 0` reddens
only the discrimination leg; removing the stub reddens only the real-layers gate.

### Hazards to carry forward

- **A COMMIT REJECTED BY A HOOK LEAVES THE CHANGE STAGED, and `git log` then shows
  someone else's HEAD.** Check `git status`, never `git log`. Hit twice; on S7 the
  rejection was state-dependent and a clean retry succeeded, so re-run
  `red_green_replay` in commit-msg mode directly before assuming a real objection.
- **A `fix:`/`feat:` subject on a tests-only staged tree whose tests PASS is
  rejected** as `test-passed-at-red`. Markdown does not enter the `.py` bucket, so a
  change fixing generator prose plus its tests is still "tests-only" to the hook.
  Use `test:`.
- **A GREP THAT MATCHES NOTHING IS INDISTINGUISHABLE FROM A CLEAN PASS.** This bit
  the verification of a verifier: a sabotage piped through `grep -E '^FAILED'`
  printed nothing, read as "my new check is not load-bearing", one step from
  deleting a working check as dead code. When a sabotage produces no output, read
  the artifact — never accept the silence.
- **`fabro` DOES NOT RESOLVE UNDER `with-livespec-env.sh`, AND THE WRAPPER STILL
  EXITS 0.** `with-livespec-env.sh fabro ps` prints `env: 'fabro': No such file or
  directory` and returns **rc=0**, so it lists no runs and reads as a clean
  "nothing in flight". Call it by absolute path: `/home/ubuntu/.local/bin/fabro`.
  **And `ps -eo cmd | grep fabro` is not a substitute** — it showed only another
  track's `drive.py` launcher and MISSED S9's detached run entirely. On that pair
  of false negatives this session was one step from hand-implementing a slice the
  factory already had in flight, which is the duplicate-work version of the
  grep-matches-nothing hazard above. Known in
  `plan/codex-parity-and-rollout-safety` and `plan/fabro-review-classifier-defect`,
  but it was missing HERE, where it could do this particular damage.
- **A BLOCKED RUN PARKS AN ENGINE ON THE DISPATCH CAP INDEFINITELY, INCLUDING FOR
  AN ITEM THAT IS ALREADY CLOSED.** Measured 05:39Z: `01KYRGQX2FES` blocked 134m on
  `overseer-t7qqik` — S3, which is CLOSED because it landed BY HAND as PR #307, so
  that engine is parked on work that no longer exists; and `01KYRGA3HMSE` blocked
  141m on `overseer-vyie5q` (another track). This thread records the dispatch cap
  as the binding constraint on the whole epic, so a blocked run is a capacity leak,
  not just a stalled item. **Reconciling a slice by hand does not reap its run** —
  check `fabro ps` for orphans after any hand-landing. Answering or killing a run
  is the supervisor's lane.
- **Assert every scripted edit, before writing.** Two edits refused to write this
  session — one on an anchor the formatter had reflowed, one on a stray non-ASCII
  character typed into a replacement. An unasserted `str.replace` would have written
  the first and corrupted the second. Writing a hazard down does not stop you
  walking into it; the guard does.
- **Restore a sabotage from a byte copy, never `git checkout -- <file>`** — that
  reverts to HEAD, not to your uncommitted work, and silently wiped a completed
  sweep here.
- **Widening a detector is a chance to silently REMOVE what it already caught.**
  When re-keying (b) and (d) to properties, the original literal rules were RETAINED
  and asserted directly. Prove the old shape still reddens; do not infer it.
- **`PIPESTATUS` is bash; this fleet runs zsh** (`$pipestatus[1]`, lowercase,
  1-indexed). The bash spelling yields an EMPTY string, which reads like a pass.
- **This host runs uutils coreutils 0.2.2 for both `readlink` and `realpath`, not
  GNU.** `readlink -f ""` returns `$PWD` with rc=0 here (false pass) and `--` does
  not save it; GNU exits 1. The non-empty guard is what saves the charter form.
  **The same divergence bites `date`:** `date -u -r <file>` here does NOT apply
  `-u` — it prints a LOCAL time, and the `Z` you then append to it is a lie. Local
  is CEST (+0200), so that is a silent two-hour error in a published timestamp.
  Read mtimes through Python's `datetime.fromtimestamp(ts, timezone.utc)` when the
  value is going into a claim.
- **`just worktree-reap` cannot see a rebase-merged branch as merged** (the SHA
  changes), so it skips your own and offers `--force`, which would act on every
  other track's. Filed as `overseer-btt`. Remove only your own.
- **A PR failing on `Failed to download … operation timed out` from PyPI is
  INFRASTRUCTURE** and a legitimate rerun — not the same as re-running a flaky test
  until it goes green.
- **`--set-metadata` stores STRINGS.** Clearing a list field with it stores `"[]"`,
  which the consumer walks character-wise. Use `--metadata @file.json` and assert
  the TYPE on read-back (C11).
- **Never wrap `dispatcher.py dispatch` in a short timeout** — it BLOCKS for the
  life of the run. And a dispatch that fails at `run-config-overlay` still CLAIMS
  the item with `fabro_run_id` null, which is why S3 needed resetting twice.

### Boundaries

The supervisor owns this file's sections ABOVE the separator, the ledger, and all
dispatching, merging and `reconcile-merged`. The worker owns below the separator.
Do not touch branches `docs/supervisor-charter-hardening`,
`docs/regenerate-supervisor-prompt-quality-charter`,
`docs/handoff-execution-order-correction`, or PR #274 and the
`codex-parity-and-rollout-safety` track. Worktrees via `just worktree-create`,
never raw `git worktree add` — the latter omits the discipline pack and the failure
fires only at commit or push time. Never `--no-verify`; halt and report on hook
failure. Never kill the acting overseer daemon in tmux `livespec-overseer:1.1`.

### Durable artifacts (gitignored — this working tree only)

`tmp/overseer/supervisor-prompt-quality/` holds `GAP-no-remediation-slice.md` (the
fleet-wide remediation options, still the maintainer's cut), `FILED-RESULT.md`,
`EVIDENCE-REVERIFICATION.md`, the S1/S2 coverage maps, `worker-status.log` (the
supervisor's wake channel), and `evidence/`. **A fresh clone has none of it.**
Anything worth carrying belongs here or in a test, not in the log — the wake
channel is a transcript, not storage.
