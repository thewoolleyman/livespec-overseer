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

## PHASE 2 — the nine-slice epic is DELIVERED; this is what it surfaced

**`overseer-byvxlp` is CLOSED and it succeeded.** All nine slices plus
`overseer-dk6hwi` and `overseer-ejja5o` are closed; `tests/prompts/` carries ten
modules driving real tmux; release **0.15.0** shipped; and — measured
2026-07-30T17:20Z — **the adopter cache on this host has refreshed to prose
byte-identical to `origin/master`** (`md5 9ca18d56772dcf8fcdc2cf78ed8108a8`, cache
dir `013d35d48cde`). The generator that actually RUNS now emits the fixed form,
with zero occurrences of the wrapper-less `bd show`. That chain —
fix → gate → release → adopter refresh → running generator — is the thing this
thread existed to make work, and it has now been observed working end to end.

**Phase-2 ledger anchor: epic `overseer-yho`.** A NEW epic rather than reopening
`overseer-byvxlp`, deliberately: that epic's nine slices all delivered and its
record should stay a clean completion. Reopening it to absorb follow-on work would
blur "the cut we planned" against "what the cut revealed".

| slice | what it is |
|---|---|
| `overseer-yho.1` | **Gate the `date -u -r` trap.** A charter emitting it reports LOCAL time labelled `Z` — a silent two-hour error under uutils coreutils. Already caused a false accusation (charter correction C19). Same shape as detector (g); add detector (k). |
| `overseer-yho.2` | **A charter records no provenance.** Nothing distinguishes a charter emitted from a current plugin from one emitted from a stale pinned cache. Carries `overseer-d4t`'s unmet acceptance clause: demonstrate RED against a STALE-CACHE generation specifically. |
| `overseer-yho.3` | **The fleet-wide remediation half** — 117 defects, 12 files, 5 repos, re-measured with this repo's own ten-detector gate. Maintainer's cut. |
| `overseer-gjb` | Two module docs still assert in the present tense that there is no `.ai/` directory — fallout from this thread's own two-layer split. |

**`overseer-d4t` stays open and is NOT a phase-2 slice.** Its thesis ("a generator
fix is inert until adopters refresh") is now historically true rather than
currently true here, but it is about adopters *in general* and its own acceptance
clause is unmet. Its live residue is `overseer-yho.2`. Recommended disposition:
narrow and retitle it to the detection gap, or close it and let `yho.2` carry it —
a triager reading only its title today would act on a premise that has moved.

**Routed OUT of this thread as a separate track:** the daemon-liveness pair —
a live track reporting session-gone, and a torn-down one reporting hung
mid-wrap-up. Epic `overseer-x29`, plan thread `plan/daemon-liveness-truth/`. They
surfaced here but are about the daemon's runtime liveness model, not about what
the generator emits.

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

## NEXT SESSION — START HERE (written 2026-07-30 20:50Z; step 3 and the status table rewritten 2026-07-31 05:56Z after the session that followed it)

**THERE IS NO WORKER TASK QUEUED IN THIS THREAD RIGHT NOW.** That is the single
thing to know before doing anything, and it is a deliberate state, not an
oversight. **It is also not a reason to stop — see step 3.**

**WHERE THE THREE OPEN ITEMS STAND, as of 2026-07-31T05:56Z.** All three now sit
with the maintainer, each with its numbers, and none is filed or closed:

| item | state |
|---|---|
| `overseer-yho.3` | Fully COSTED. The fleet edit is near-mechanical (117 → 25 demonstrated in memory, all of class (a) cleared); the highest-leverage fix is ONE line clearing 10 defects in a shared layer; option 3 reaches 94 of 117 because `homelab` consumes no pin. **Needs a decision, not a number.** |
| `overseer-jcw` | Mechanism 1 (shared tmux socket across concurrent runs) FIXED and gated, two instances. Mechanism 2 (a timing premise CPU starvation invalidates) COSTED, with the obvious fix eliminated by arithmetic. **Needs a contract decision.** |
| `overseer-bak` | Gap real and reproduced from both directions; **incidence nil** (0 of 7 comparable threads drift). One local static gate landed. **Needs a scope decision.** |

The only defect this thread found in itself is fixed: the charter's `ledger_anchor`
pointed at a closed bug and now points at `overseer-yho`, gated by
`tests/test_plan_thread_records_agree.py`.

Phase 2 (`overseer-yho`) had four slices. Three are CLOSED and merged —
`overseer-yho.1` (#389), `overseer-yho.2` (#393 + #398), `overseer-gjb` (#404).
The fourth, `overseer-yho.3`, is the fleet-wide charter remediation, and it is
**the maintainer's cut**: remediating another repo's charters means touching
tracks this thread does not own, and it needs a decision (remediate at all;
phased or fleet-wide) that a worker cannot make. Its costing input is already
measured and recorded below — the measurement is done, the decision is not.

**DO NOT SELF-ASSIGN `overseer-yho.3`.** Measuring it again is fine and cheap;
cutting it is not yours.

**AND THE MEASURING IS NOW DONE — do not spend another session redoing it.** A
2026-07-30 22:20Z session took the costing as far as it goes without deciding
anything: the fleet edit is demonstrably near-mechanical (117 -> 25 in memory,
all of class (a) cleared, controls passing), the highest-leverage fix in the fleet
is ONE line clearing 10 defects in a shared layer, and option 3 reaches 94 of 117
because `homelab` does not consume the pin. See "`overseer-yho.3` IS NOW COSTED"
below for all five findings. What is missing is a DECISION, not a number. If you
find yourself re-running the fleet scan, ask first what new question it answers.

So, on a cold open, in this order:

1. **Re-measure the ledger first** — `with-livespec-env.sh -- bd show overseer-yho
   --json` and each slice. A bare `bd` returns "Access denied" in this tenant.
   Everything in this file is a claim with a timestamp, including this sentence.
2. **If a new slice has been filed or assigned to the worker, do that.**
3. **If not — REPORT IT, THEN AUDIT THIS THREAD'S OWN ARTIFACTS. Do not stop.**
   This step used to say "say so to the supervisor and stop", and following it
   literally produced a session that delivered nothing until the overseer pushed
   back. What followed was seven merged PRs, and every one of them came from
   auditing what this thread already owns rather than from taking new work.
   **There is a middle ground between self-assigning another track's slice and
   stopping**, and it is where the value was:

   - **This thread's own charter had a live defect** — `ledger_anchor` bound to a
     CLOSED BUG, inside the block whose job is to stop stale claims, in the repo's
     hardened exemplar. Nothing in the fleet could see it. Found by comparing the
     thread's two records against each other, which nobody had done.
   - **This thread's own tests had a real bug** — `overseer-jcw` mechanism 1,
     reproduced on demand and fixed, with a second independent instance found only
     because the whole suite was run concurrently rather than one module.
   - **Three items the maintainer owes decisions on had no numbers.** Costing them
     — `yho.3`, jcw mechanism 2, `bak` — needed no permission and no ledger write.

   The original prohibition still stands and is not weakened: **do not file, do not
   transition, do not close, and do not touch another track.**
   `codex-parity-and-rollout-safety` and `daemon-liveness-truth` (`overseer-x29`)
   have their own sessions. But "no slice is queued" is not "there is no work" —
   it means the work is verification, measurement, and preparing decisions rather
   than execution. **Ask what this thread has ASSERTED that nobody has CHECKED.**

**Do not merge release PR #360** (0.15.1) or any Release Please PR.

**One live consequence to expect, which looks like a bug and is not:** this
repo's own charter now HALTs its provenance precondition, naming two different
digests. That is correct — see "Provenance" below — and it clears when #360
ships. Do not re-stamp the digest to silence it.

## WORKER RESUME STATE — re-measured 2026-07-30 19:40Z by the `supervisor-prompt-quality` worker

**Everything below is a claim with a timestamp. Re-measure from the ledger and the
forge before acting on any of it.** This section has been wrong about the blocker
three separate times, and its own timestamps have been wrong too — an earlier
rewrite was labelled `05:50Z` while the commit carrying it landed `05:26:42Z`,
because a local clock was published with a `Z`. That is charter correction C19 and
detector (k); read mtimes through `datetime.fromtimestamp(ts, timezone.utc)`,
never `date -u -r`, which does not apply `-u` under this host's uutils coreutils.

### Where PHASE 2 actually is — re-measured 2026-07-30 19:40Z from the ledger

| slice | id | state |
|---|---|---|
| Gate the `date -u -r` trap (detector k) | `overseer-yho.1` | **CLOSED** — PR #389 |
| A charter records no provenance | `overseer-yho.2` | **CLOSED** — PR #393 + #398 |
| Two module docs deny `.ai/` | `overseer-gjb` | **CLOSED** — PR #404 |
| Fleet-wide remediation half | `overseer-yho.3` | `backlog` — **the maintainer's cut** |
| epic | `overseer-yho` | `backlog` |

Three of the four are delivered. `overseer-yho.3` is NOT a worker task: remediating
another repo's charters means touching tracks this thread does not own. Measuring
it is fair game and is done below; cutting it is not.

### The fleet measurement, re-measured 2026-07-30 19:40Z with ELEVEN detectors

The number on `overseer-yho.3` was taken at 13:00Z with the TEN-detector gate,
before (k) existed. Re-run with the current eleven — same shipped module, not a
grep — it is UNCHANGED:

| repo | charters | dirty | defects |
|---|---|---|---|
| livespec-orchestrator-beads-fabro | 6 | 5 | 56 |
| homelab | 7 | 2 | 23 |
| livespec-dev-tooling | 3 | 2 | 18 |
| livespec-console-beads-fabro | 1 | 1 | 15 |
| livespec | 4 | 2 | 5 |
| livespec-overseer | 8 | 0 | **0** |
| **TOTAL** | **29** | **12** | **117** |

By class: (a) 92, (c) 7, (d) 7, (b) 5, (h) 2, (e) 1, (f) 1, (i) 1, (j) 1, **(k) 0**.

**(k) ADDS NOTHING FLEET-WIDE, and that zero is controlled.** A zero from a probe
is indistinguishable from a broken pattern, so the trap was injected IN MEMORY
into a real fleet charter (`livespec-orchestrator-beads-fabro`
`plan/beads-v1-1-2-upgrade/supervisor-handoff.md`, nothing written to disk) and the
same call returned 1. The absence is real. So the maintainer's costing is
unchanged by (k), and the earlier "must carry all TEN detectors" now reads ELEVEN
with no change to the numbers.

The exposure is still CONCENTRATED: one repo holds 56 of 117 with 5 of 6 charters
dirty, so a phased cut scoped to `livespec-orchestrator-beads-fabro` clears about
half. That option post-dates the costed options in `GAP-no-remediation-slice.md`.

### `overseer-yho.3` IS NOW COSTED — 2026-07-30T22:20Z, and the answer is NOT what the packet assumed

**Carried here deliberately, because `GAP-no-remediation-slice.md` is GITIGNORED and
a fresh clone has none of it.** The full working lives there while this tree exists;
these are the conclusions that must outlive it. All read-only, using the SHIPPED
eleven-detector module imported and called — never a grep — with per-class positive
controls and an in-memory injection control.

**1. THE EDIT IS NEARLY MECHANICAL; THE ROUTING IS ~ALL THE COST.** Class (a) alone
is 92 of 117 (79%). Classified by target shape: **71 LITERAL** (the session name is
ALREADY in the line — a purely syntactic rewrite that decides nothing), 9
PLACEHOLDER, 2 `name:window.pane`, and 10 VARIABLE that collapse to **ONE** binding —
there is exactly one distinct variable binding fleet-wide.

**2. DEMONSTRATED, NOT ARGUED.** A deliberately stupid rewrite (`-t X` -> `-t '=X:'`,
plus one added binding line), applied IN MEMORY and re-scored by the shipped gate,
took the fleet **117 -> 25**, clearing **all 92 of class (a)**. Control: an
unmodified re-scan afterwards still reports 117, so nothing leaked to disk. The
residue is exactly the non-(a) classes, and even that shrinks — (b)'s 5 instances
are ONE distinct line and (d)'s 7 are ONE distinct line, leaving ~13 genuinely
distinct edits fleet-wide. **Limit, stated: this proves mechanically CLEARABLE PER
THE GATE, not mechanically CORRECT.** A human should still read the diff; the claim
is that the diff is uniform and readable, not that review is unnecessary.

**3. THE SINGLE HIGHEST-LEVERAGE EDIT IN THE FLEET IS ONE LINE.**
`livespec-orchestrator-beads-fabro/.ai/supervisor-protocol.md` uses
`-t "$WORKER_TARGET"` ten times and **never binds it**; adding the one binding line
this repo already ships (`WORKER_TARGET='=<worker-session>:'`) took it **10 -> 0**
with zero other changes. It is a SHARED layer, so it fixes every thread in the repo
holding 48% of the exposure.

**4. OPTION 3 IS CHEAPER THAN COSTED BUT DOES NOT REACH EVERYTHING.**
`livespec_dev_tooling/checks/` already ships **57** public check modules, THREE of
which walk the plan tree, and **ZERO** read `supervisor-handoff.md` (control passed;
independently reproduces `overseer-bak`). Our gate imports and runs unmodified from
outside this repo. So it is a 58th module adopted by pin bump — not new
infrastructure. **BUT `homelab` is not a pin consumer** (Rust/Nix; no
`pyproject.toml`, no `justfile`, no `.mise.toml`) and holds **23 of 117**. So option
3 covers 94 of 117 (80%) cheaply, and the last 23 need a different answer. The
measurement points at **3-for-pin-consumers + 1-for-homelab**, a shape none of the
four costed options describes.

**5. 51 of 117 (44%) sit in `plan/archive/`**, which never regenerates — a direct
argument against option 4 ("accept it; instances decay").

**None of this is a decision.** Nothing was filed, nothing was cut, no other repo
was written to. `overseer-yho.3` remains the maintainer's.

### Provenance: what landed, and the consequence it carries

`overseer-yho.2` shipped a `## Generator provenance` section in both emitted
layers. It records `generator_plugin`, `generator_ref`, `generator_version` and
`generator_prose_md5`, and the DIGEST is the identity — six releases (0.12.2
through 0.13.3) shipped byte-identical prose, so a version reports six generators
where there is one, and the ref directory name is sometimes a sha and sometimes a
version (`0.12.2` and `0.12.3` are real ref directories).

**THIS REPO'S OWN CHARTER HALTS ITS PROVENANCE PRECONDITION UNTIL THE NEXT
RELEASE, AND THAT IS CORRECT.** It records the prose in THIS repo; the cache holds
the last released prose; between a prose change and its release those differ, and
the check HALTs naming both digests. Do NOT re-stamp the digest to silence it —
that forges currency the charter does not have. It self-resolves when the release
ships. An adopter generating from a released ref sees PASS.

### THE CHARTER IS NOW TWO LAYERS — this changes where things live

S3 landed the layered form, so master carries:

- **`.ai/supervisor-protocol.md`** — the shared role layer, holding **19**
  role-level Corrections, C1–C19. Re-counted 2026-07-31 (584 lines).
- **`plan/supervisor-prompt-quality/supervisor-handoff.md`** — the thin binder,
  **266 lines**, carrying **1** thread-specific correction (T1). Re-counted
  2026-07-31.

**BOTH NUMBERS WERE STALE, AND THE FIRST ONE CONTRADICTED THIS FILE THREE LINES
LOWER.** This bullet said "all **16** Corrections (C1–C16). Verified present with
16 entries" and "a thin binder, now **126 lines**". Actual: **19** and **266**.
The same handoff cites **C19** elsewhere — it is the `date -u -r` correction that
detector (k) implements — so a reader trusting the count would have concluded that
C17, C18 and C19 do not exist, while reading a sentence that depends on C19.

Why it drifted, because the mechanism matters more than the correction: **a count
is a claim with a timestamp, and it is the WORST kind** — it looks like a fact
rather than a measurement, "Verified present with 16 entries" reads as though
someone checked (they did, once), and appending a correction never touches the
sentence that counts them. The `## Corrections` sections are append-only by
design, so this drifts on EVERY append, silently, forever. **Prefer a rule that
recounts over a number that ages**; where a number must appear, date it, as these
two now are. Nothing gates this — the count sits in prose that no test reads.

(The "all 16 Corrections verified byte-equivalent" in the S3 paragraph below is
NOT stale: it describes what was verified when PR #307 landed, and 16 was correct
then. Left alone deliberately — a historical measurement is not a drifted one.)

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

### THE STALE-CACHE CHAIN — resolved once, and re-armed by every prose change

This section used to say the generator that RUNS carried none of the epic's
fixes. That was true and is now historically resolved: 0.15.0 shipped, and at
17:20Z the adopter cache on this host refreshed to prose byte-identical to
`origin/master`. The chain fix → gate → release → adopter refresh → running
generator has been observed working end to end.

**It re-arms on every prose change, by construction.** The moment generator prose
lands on master, every cache ref is stale relative to it until the next release.
That is the ordinary state of this repo for most of its life — not an incident —
and it is why nothing here asserts `repo == cache`: such an assertion reddens
master on every legitimate prose change.

What is now DETECTABLE that was not: an emitted charter records the generator that
produced it, so a stale-cache emission can be recognised as one. What is still NOT
detectable by content alone, and this is the finding that shaped the fix: the
contract floor reported the stale 0.14.0 generation as FULLY CONFORMANT, with a
verdict identical to the current generation's, while everything that does catch it
was written seven hours AFTER it shipped. A content gate recognises only the
staleness it already has a detector for, so it is permanently one release behind.
`tests/prompts/test_stale_cache_generation_is_detectable.py` pins that as
invariants — the frozen row as a DIFFERENCE against the current generation, the
finding as an EQUALITY — deliberately, so contract growth does not force edits
here and quietly weaken them.

**Run the positive control if you re-measure any of this.** A zero from a grep is
indistinguishable from a wrong pattern; that hazard has now bitten this thread
four times.

### The charter gate — ELEVEN classes, all keyed on the PROPERTY

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
| (h) wrapper-less ledger read | the fleet credential wrapper anywhere in the charter |
| (i) fixed-cap marker read | a truncation notice, so a cut announces itself |
| (j) unguarded marker binding | a non-empty guard BEFORE the `-f` test |
| (k) local time labelled UTC | a `date` that reads a file must not claim UTC |

Two more gates sit beside it: `test_stale_cache_generation_is_detectable.py` runs
the shipped validators over three REAL cached prose generations, and
`test_provenance_check_discriminates.py` executes the emitted provenance block
against a fabricated cache in all four of its states.

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

### `overseer-bak` MEASURED: the gap is real, the INCIDENCE is nil — 2026-07-31T02:19Z

`overseer-bak` establishes that nothing compares a plan thread's two durable
records and that nothing in the fleet reads `supervisor-handoff.md` at all. Both
reproduced here from the other direction (zero matching modules in
`livespec_dev_tooling`, against a passing control of three `plan_thread` readers).
What bak lacked is a COUNT. Measured read-only across `/data/projects`:

| | |
|---|---|
| plan threads carrying BOTH records | 12 |
| charters DECLARING a ledger anchor | 7 |
| charters declaring none (uncomparable) | 5 |
| **threads where the two records DISAGREE** | **0** |
| charters carrying `## Generator provenance` | **1 of 12** |

The only divergence in the fleet was THIS repo's own — `ledger_anchor='overseer-d4t'`,
a closed bug, fixed in PR #421 and now gated. **So the gap is real and the current
incidence is nil**, which should temper how urgently a fleet-wide comparator gets
built. That the provenance yho.2 shipped reaches 1 charter in 12 is the same
adopter-refresh chain `overseer-yho.3` is costed against — bak's remedy is gated on
it too.

**THE FINDING FOR WHOEVER BUILDS THE COMPARATOR, and I learned it by getting it
wrong:** a ledger anchor has at least THREE spellings in the wild —
`| \`ledger_anchor\` | \`x\` |` (table), `ledger_anchor='x'` (executable), and
`- Ledger epic anchor — \`x\`` (bullet prose, homelab ×5). My first pass, written
against this repo's spelling, reported "2 charters declare an anchor, 10 declare
none" **with its positive control passing** — because the control only exercised
the shape I had written the regex for. The widened extractor found 7, not 2.
Working evidence and both runs are in
`tmp/overseer/supervisor-prompt-quality/evidence/bak-record-drift-2026-07-31/`
(gitignored — a fresh clone has none of it).

Scope of what landed: `tests/test_plan_thread_records_agree.py` reads only this
repo's two spellings, which is correct HERE (verified: this repo's other two
charters declare no anchor in ANY spelling) but is NOT a fleet-ready comparator.

### `overseer-jcw` HAS TWO MECHANISMS. ONE IS FIXED; THE OTHER IS NOT — 2026-07-30T23:55Z

Diagnosed and half-fixed by this thread because `tests/prompts/` is this thread's
own deliverable. **The ledger is untouched — jcw is NOT closed, and closing or
re-scoping it is the supervisor's lane.**

**MECHANISM 1 — a shared tmux socket across concurrent runs. FIXED, PR #418.**
The rig named its private socket `legs-{tmp_path.name}`. That is the TEST's
identity and is byte-identical across separate pytest invocations — unique per test
and per xdist worker exactly as its docstring claimed, **not unique per RUN**. Two
concurrent `just check` invocations on one host therefore addressed the SAME
`tmux -L` server; the second `new-session -s wk` failed as a duplicate **without
being noticed** (the helpers pass `check=False` and tmux exits 0 anyway), and the
second run read the FIRST run's pane. Reproduced on demand: the leg passes 2/2 run
alone and one of two concurrent invocations fails at `assert live == str(repo)`
with two different `pytest-NNNN` roots in the diff. **It dies mid-test, so the
lines below never execute — which is why this surfaced as a COVERAGE shortfall at
lines 130-134 rather than as a test failure.** That is jcw's reported signature
exactly. It had a SECOND independent instance (`disc-{tmp_path.name}` in
`test_emitted_commands_discriminate.py`) that only appeared once the shared
conftest was fixed, so `tests/prompts/test_rig_sockets_are_run_unique.py` now gates
the property fleet-locally.

**jcw's three guessed mechanisms were all wrong** — not the shared `.coverage`, not
generic tmux contention, and not skip-instead-of-fail, which the refuse-to-skip
guard rules out by construction. Worth remembering before trusting the next
plausible-sounding cause list.

**MECHANISM 2 — a timing premise that external CPU load invalidates. NOT FIXED,
and deliberately not fixed by me.**
`test_watcher_wake_discriminates.py::test_both_forms_report_busy_while_a_pane_keeps_changing`
fails asserting BUSY and reading IDLE. `watcher_proposed` polls every 150ms and
declares IDLE after N identical captures; the test drives a 50ms tick, and its own
comment states the premise — "a 50ms tick against a 150ms poll guarantees a new
value every poll". Under enough external load the loop is descheduled and tmux
coalesces renders, so consecutive polls compare EQUAL and IDLE wins. That comment
already records the same failure from CPU saturation at ~1-in-5.

MEASURED, so the next session does not have to re-derive it: **0 of 8 alone, 0 of 8
under a light paired load, 2 of 8 under two FULL concurrent suites** — and after
mechanism 1 was fixed, **every** remaining failure across 8 concurrent full-suite
runs was this one and no socket collision appeared at all.

**CORRECTION, 2026-07-31T03:43Z — those numbers UNDERSTATE it, and the correction
matters more than the original.** "Alone" meant a single non-xdist pytest run of
one module. It fires in the ORDINARY `just check` AGGREGATE, with no external load
at all: caught live on a pre-push here, on worker `[gw3]`, minutes after a
foreground `just check` on the identical tree had passed 65/65. **The aggregate's
own xdist parallelism is sufficient CPU load** — which is precisely what `jcw`
reported as "run-alone passes, in-aggregate flakes", and I had read that as
pointing at the shared `.coverage` file rather than at CPU contention.

So do not treat mechanism 2 as a curiosity that needs a contrived double-load. It
is the ordinary failure mode of `just check` on this host, it blocks pre-push, and
because master CI feeds the Dispatcher's "latest master is green" pre-flight it can
intermittently halt fleet dispatch.

**And it presents EXACTLY as jcw described**, which is worth seeing once: the
headline is `ERROR: Coverage failure: total of 99 is less than fail-under=100` with
`check-per-file-coverage` and `check-coverage` named as the failing targets. The
actual assertion failure is buried far below. Anyone reading the summary concludes
they broke coverage. **Read for `FAILED` before believing a coverage verdict here.**

**Why I stopped here rather than fixing it.** The fix is a choice between "a
churning pane is ALWAYS reported BUSY" and "…is EVENTUALLY reported BUSY within a
bounded window". That changes what a DISCRIMINATION test proves, which is a
contract decision, not a repair. Tuning the tick until it goes green is the
re-run-until-green habit jcw itself argues against.

**COSTED 2026-07-31T04:50Z so the decision does not need re-derivation.** The
arithmetic first, because it eliminates the obvious answer. `_POLLS = 4`,
`_STABLE_TO_IDLE = 3`, poll interval `0.15s`. `stable` resets to 0 on ANY change,
so IDLE requires captures 2, 3 AND 4 to equal capture 1 — **an unchanging pane for
~450ms**, i.e. about NINE missed 50ms ticks in a row. The pane is visible-only and
the counter is monotonic, so equality means no new line RENDERED. That is genuine
CPU starvation of the spinner, not a spacing problem.

| option | verdict |
|---|---|
| **Tick faster** (`sleep 0.01`) | **CANNOT WORK, and it is the first instinct.** A descheduled process does not tick at any rate. It narrows nothing, and it would look like a fix until it flaked again. |
| **Raise `_POLLS` / `_STABLE_TO_IDLE`** | Those are the WATCHER's parameters — the thing under test. Changing them changes the contract to make its own test pass. |
| **Reduce parallelism** | **LEVER ALREADY SPENT.** `test_nprocs` is deliberately 25% of cores locally (4 of 18 here) precisely "so a shared host is never oversubscribed", and mechanism 2 fires anyway. The contention is HOST-WIDE — 57 worktrees, other tracks, the overseer daemon — not xdist alone. Note CI takes the other branch (`-n auto`, dedicated runner) and jcw recorded a master-CI red in this module too. |
| **Assert EVENTUALLY-BUSY within a bounded window** | The honest repair, and the contract decision. Discrimination SURVIVES: a genuinely idle pane never changes, so it yields IDLE at every attempt — retrying cannot manufacture a false BUSY. What is lost is the stronger "always" reading. |
| **Isolate the leg from contention** | Attractive because it changes nothing about what is asserted, but it only addresses xdist; a shared host starves it regardless. Partial at best. |

**My read, not my call:** the fourth option is the only one that survives the
arithmetic, and its cost is smaller than it first appears because the
discrimination is asymmetric — an idle pane cannot flake INTO busy. But "always"
becoming "eventually" is a real weakening of a contract test and the maintainer
owns it.

### Hazards to carry forward

- **WHEN A VERIFICATION DISAGREES WITH THE ARTIFACT, SUSPECT THE VERIFICATION
  FIRST. Measured 2026-07-31: four for four.** This is the synthesis of the
  individual entries below, and it is worth more than any of them, because in a
  single session EVERY apparent defect that a check reported turned out to be the
  CHECK's fault and not the artifact's:
  1. `ls … | grep '^_'` returned 0 helper modules against a true 20 — `ls` is
     `lsd` here and its output is inode-decorated, so a `^`-anchored filename
     match can never fire.
  2. A fleet scan reported "2 charters declare an anchor, 10 declare none",
     positive control GREEN — the control only exercised the spelling I had
     written the regex for. The real answer was 7.
  3. `gh pr checks --watch` reported 0 failures before any check had REGISTERED,
     one step from merging without CI. `fails=0` is not green unless `pass>0`.
  4. A test-function existence scan reported 7 MISSING functions, all of which
     were module names with `.py` stripped by my own regex.
  And a fifth, in the other direction: a module with SEVEN tests beside a claim of
  "all four of its states" looked like drift, and was not — four were cache states
  and three were charter-shape checks. **Correcting it would have falsified an
  accurate record and destroyed the distinction the module is built around.**

  The operational form, because "be careful" is not a rule: **before reporting a
  defect a check found, reproduce it by hand on the artifact itself.** Open the
  file you just claimed was empty. Read the test NAMES before trusting their
  count. Ask what population a number counts before deciding it is wrong. Every
  one of the five above dissolved in under a minute of looking directly, and each
  had already survived a control that I believed.

- **A POSITIVE CONTROL ON YOUR OWN SPELLING PROVES THE REGEX COMPILES, NOT THAT IT
  COVERS THE WILD.** This thread's hardest-won rule is that a zero needs a control.
  That rule has a hole: a control built from the same shape you wrote the pattern
  for is CIRCULAR. Measured 2026-07-31 — a fleet scan reported "2 charters declare a
  ledger anchor, 10 declare none", control GREEN, and it was wrong: five homelab
  binders declare theirs as `- Ledger epic anchor — \`x\`` rather than this repo's
  table/assignment forms. The widened extractor found 7. **When scanning artifacts
  you did not author, the control must come from a FOREIGN instance** — open one of
  the files you claim is empty and read it before believing the count.
- **A "UNIQUE" IDENTIFIER IS ONLY AS UNIQUE AS ITS NARROWEST AXIS, and the
  docstring will tell you it is fine.** The rig above claimed uniqueness "per test
  and per xdist worker" and was correct on both — while colliding on the axis
  nobody named, the RUN. `pytest`'s `tmp_path.name` is stable across invocations by
  design; only `tmp_path`'s PARENT carries the run-unique `pytest-NNNN`. When
  something must not collide, say out loud WHICH axes it varies on, then check the
  ones you did not list.
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

- **A SABOTAGE THAT PRODUCES NO RED IS UNVERIFIED, NOT PASSED.** Hit twice on
  2026-07-30, both times the SABOTAGE failing rather than the gate: one sliced
  from a `md5sum` line to the first `printf` in a file with two earlier
  `printf`s, so it DUPLICATED text instead of deleting any; the other reverted
  only the second line of a denial that wraps mid-claim, leaving "there was no"
  intact so no defect was ever reintroduced. Both read as "my check is not
  load-bearing". **Assert that the sabotage produced the defect BEFORE reading
  the verdict** — the corrected form computes the finding on the sabotaged text
  and asserts it is non-empty, then runs the gate.
- **A PROSE RULE THAT DEPENDS ON WHERE LINES BREAK IS ONE REFLOW FROM GOING
  BLIND.** Twice today: a set of prose needles failed because each phrase spanned
  a markdown line break, and a detector missed the very instance it was written
  for because that claim wraps mid-sentence. Strip blockquote markers and collapse
  whitespace before matching prose; markdown gets rewrapped constantly.
- **A GATE THAT INHERITS THE ENVIRONMENT IS NOT A GATE.** The cold-open gate
  fabricates the repo, the tool stubs and the bindings but inherited the real
  `$HOME`, so once a charter block read `$HOME/.claude/plugins/cache/...` it
  answered "executes" on a machine holding a plugin cache and "does not execute"
  on a CI runner without one. Same static question, different answers by machine.
  It now fabricates `HOME`. Latent until a block first read it.
- **`git commit --amend -F <file>` WIPES THE TDD TRAILERS the Red hook wrote.**
  The result is a `fix:` commit carrying no evidence of its own Red. Use
  `--amend --no-edit`, or rebuild the message with the existing `TDD-*` lines
  appended verbatim.
- **THE RED HOOK REFUSES TWO TEST FILES** (`red-green-replay-multi-test-file`):
  the trailer schema's checksum field is singular. If a change needs two test
  files, land the one that can stand alone FIRST, as its own commit, and make its
  assertions invariant to what the second will change — otherwise the pair cannot
  be ordered without a red commit in the middle.
- **`just worktree-create` failed THREE consecutive times** with 141/SIGPIPE
  before succeeding on the fourth, leaving no partial state each time (checked:
  no worktree, no branch, no directory). Filed as `livespec-dev-tooling-zi4q`;
  retry rather than investigate, but do not assume two attempts is the ceiling.
  **ROOT-CAUSED 2026-07-30T22:20Z — it is a RACE, and here is the line.**
  `dev-tooling/worktree-lib.sh:89`:

  ```sh
  worktree_primary_path() {
      git worktree list --porcelain | awk '/^worktree /{print $2; exit}'
  }
  ```

  `awk` **exits after the first match**, closing the pipe while
  `git worktree list --porcelain` is still writing. `git` takes SIGPIPE, the
  script's `set -o pipefail` (line 65) propagates 141, and `set -e` aborts —
  before any output, which is why a redirected run leaves an EMPTY log (stdout is
  block-buffered and the buffer dies with the process). Reproduced in bash under
  `pipefail`: **4 of 8 runs returned 141**, while the identical awk WITHOUT the
  early `exit` returned 0 on 3 of 3. That control is the proof; the alternation is
  the race.
  **It gets worse as the worktree count grows** — more porcelain output means more
  chance `git` is still writing when `awk` quits. This checkout has **56**.
  Consequences: **retry IS the correct workaround after all** (it is a coin flip;
  it took 4 attempts, then 4 again — the same "three then success" shape
  `zi4q` first recorded), and **an earlier note in this bullet blaming the `just`
  wrapper for closing stdout was WRONG** — `just` is uninvolved, the library fails
  the same way when called directly, and it only appeared otherwise because the
  first direct call happened to win the race. Do NOT reach for
  `git worktree add`: the fault is one line inside the library, not the library.
  **The fix is one line and belongs in `livespec-dev-tooling`'s package source**
  (never hand-edit the gitignored `dev-tooling/` copy): drop the `exit` and guard
  with a flag, or read the value without a pipeline. Worth putting on
  `livespec-dev-tooling-zi4q`, which currently records the symptom and no cause.
- **`ls` ON THIS HOST IS `lsd`, AND ITS OUTPUT IS INODE-DECORATED — so
  `ls … | grep '^<name>'` MATCHES NOTHING, ALWAYS.** Each line begins with an inode
  number and a permission string, not the filename, so any filename predicate
  anchored with `^` silently returns zero. This bit a live count tonight:
  `ls checks/ | grep -c '^_'` returned **0** helper modules when the true answer is
  **20**, and that zero was one step from being published in a decision packet as
  "77 check modules" when the real figure is 57. It is the
  grep-matches-nothing hazard again, with a new vector — the shell alias, not the
  pattern. **Use `find`, a shell glob, or `python3` `Path.glob` for any predicate
  over FILENAMES**; keep `ls` for human reading only. Same family as the uutils
  `readlink`/`realpath`/`date` divergences below: this host's coreutils are not
  the ones the command name implies.
- **THE HARNESS'S OWN "today's date" NOTICE IS LOCAL TIME, NOT UTC.** At
  2026-07-31T00:03 local (CEST, +0200) the session was told "Today's date is now
  2026-07-31" while **UTC was still 2026-07-30T22:03Z**. Anything stamped from that
  ambient date during the two-hour CEST window is wrong BY A WHOLE DAY, and it is
  wrong in the direction that looks newest — a reader sorting by date puts it after
  work that actually followed it. This is charter correction C19 and detector (k)
  reappearing through a THIRD vector: not `date -u -r`, and not a `Z` appended to a
  local clock, but an ambient date supplied by the harness that never claimed to be
  UTC and was simply assumed to be. **Every published stamp goes through
  `date -u` or `datetime.now(timezone.utc)`, including the one you are about to
  write in a heading.** Detector (k) cannot catch this one: there is no `date`
  invocation in the artifact to inspect.

### FOUR STALE CLAIMS ABOVE THE SEPARATOR — reported, NOT fixed, not mine to fix

Swept 2026-07-31 against the ledger and the tree. **Recorded here, in the worker
half, precisely because I must not edit the supervisor half** — and because the
wake channel is a transcript, not storage, so a finding left only there
evaporates. **A cold-open reader meets all four BEFORE reaching anything below the
separator**, and two of them put this file in direct disagreement with itself.

| # | line | the claim | measured |
|---|---|---|---|
| 1 | ~40 | "`overseer-d4t` stays open and is NOT a phase-2 slice" | **CLOSED 2026-07-30T19:34:35Z**, and its close reason records that the disposition that paragraph recommends was taken |
| 2 | ~37 | "this repo's own **TEN**-detector gate" | **ELEVEN** classes; (k) landed in PR #389, and the worker half says ELEVEN in three places |
| 3 | ~19 | "`tests/prompts/` carries **TEN** modules driving real tmux" | **TWELVE** modules; **FOUR** drive real tmux |
| 4 | ~20-23 | "the adopter cache **has refreshed** to prose byte-identical to `origin/master`" | true at the stated 17:20Z, **false now** |

**On (3)** — it conflates a total with a property, so no single number fixes it.
The four that drive real tmux are `test_repo_containment_discriminates`,
`test_supervisor_liveness_discriminates` and `test_watcher_wake_discriminates`
(shared fixture) plus `test_emitted_commands_discriminate` (its own rig).
`test_charter_boot_and_ledger_commands` and `test_cold_open_generation_gate`
deliberately STUB tmux, and a stub is not a drive;
`test_generated_supervisor_handoff_contract` is inspection-only (0 subprocess
calls). Suggested: "twelve modules, four of which drive real tmux", dated.

**On (4) — this one is a TENSE problem, not a wrong number, so do not re-measure
it.** The digest is still correct for the CACHE (`013d35d48cde` still holds
`9ca18d56…`); what moved is the REPO, to `eaebe06065b3efa0053d6ea5932d52c0` at
commit `16706e6`, 2026-07-30T19:17:26Z. The section "THE STALE-CACHE CHAIN" below
already explains that this **re-arms on every prose change by construction** and is
"the ordinary state of this repo for most of its life — not an incident". So the
sentence needs re-tensing to the past, exactly as `overseer-gjb` re-tensed the
module docs. Re-measuring and re-stamping it would just restart the same clock.

**What is NOT stale, so leave it:** all seven ledger `CLOSED` claims re-verified
against the ledger — `byvxlp`, `dk6hwi`, `ejja5o`, `hbr.16`, `hbr.4`, `hbr.15`,
`fitvmo` — and "release 0.15.0 shipped" (`plugin.json` reads `0.15.0`).

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
