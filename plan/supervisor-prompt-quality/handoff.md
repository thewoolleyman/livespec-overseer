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

## NEXT SESSION — START HERE (written 2026-07-30 20:50Z; step 3 and the status table rewritten 2026-07-31 05:56Z; status table, in-flight state and step-3 evidence rewritten again 2026-07-31 17:40Z by the session that followed THAT one)

**THERE IS NO WORKER TASK QUEUED IN THIS THREAD RIGHT NOW.** That is the single
thing to know before doing anything, and it is a deliberate state, not an
oversight. **It is also not a reason to stop — see step 3.**

**RESTART STATE, rewritten 2026-08-01T10:05Z by the session that followed the
09:15Z wind-down. READ THIS FIRST.**

**SEVEN PRs ARE OPEN AND ALL ARE GREEN** — #440, #441, #445, #446, #452 from the
previous session, plus **#456** and **#457** from this one. All `CLEAN`, and their
file-sets are DISJOINT so none can conflict with another. **Merging them is the
supervisor's lane** — that is why they are open, not because anything is
unfinished. #440 and #441 are behind the pin bumps (not diverged) and may want a
rebase first.

**#440 CARRIES THIS FILE, AND ITS DIFF AGAINST MASTER IS NOW EMPTY.** Measured
2026-08-01T09:20Z: `git diff origin/master pr440 -- plan/…/handoff.md` returns
NOTHING, so the wind-down PR did land it and #440's rebase carries zero handoff
hunks. There is nothing to conflict. #457 is now the only open PR that changes
this file.

**THE ONE THING THAT MOST NEEDS A HUMAN — AND IT IS NOT A LOCAL DECISION.**
`just check` can report "All 65 targets passed" WITH A FAILING TEST:
`justfile:589` uses `set -uo pipefail` with no `-e`, so a non-zero `pytest` does
not abort and the recipe's status is the coverage check's. **That framing is
confirmed and its scope is now measured: this is a FLEET defect that `livespec`
core already FIXED a month ago, and five of eight repos never caught up.** See
"THE MASKED-FAILURE RECIPE IS A FLEET DEFECT" below before treating it as a
sequencing risk — the precedent it was thought to set already exists.

**TWO CORRECTIONS TO THE PARAGRAPH THAT USED TO SIT HERE.** It said the finding
was "captured with evidence": **the evidence is GONE.** `jdo/run-2.log` does not
exist anywhere on this host (searched the whole of `/data/projects`, including
all 67 worktrees). The FINDING survives — it was re-derived three independent
ways this session — but the receipt did not. See "A GITIGNORED CAPTURE IS NOT A
CAPTURE".

**NOTHING ELSE IS IN FLIGHT.** No background jobs, **no ledger writes this
session**, no other track touched, nothing filed, transitioned or closed. Seven
worktrees remain on disk because their PRs are open; reap them only after landing.

**WHAT THIS SESSION PRODUCED, in the order the findings matter** (all sections
below carry their own measurements; this is the index):

| # | finding | disposition |
|---|---|---|
| 1 | **The masked-failure recipe is a FLEET defect that `livespec` core fixed 2026-07-01.** 3 repos guarded, 5 masked — including `livespec-dev-tooling`, which ships the fleet's gates | **decision reshaped; still the supervisor's call** |
| 2 | The evidence for that finding (`jdo/run-2.log`) **does not exist**; finding re-derived three ways | recorded, with the missing clause in the lesson |
| 3 | **`overseer/AGENTS.md` steered operators to a prefix-matching `respawn-pane -k`**, and `=name:` works after all | **fixed — PR #456**, and it de-risks `yho.3` |
| 4 | The maintenance guide **maps 5 of 26** supervisor modules | measured; **PR #456** marks it, repair belongs to `overseer-x29` |
| 5 | Widening the corpus beyond charters adds only **4 live** instances | costing STANDS — do not re-run |
| 6 | **(h) hardcodes one wrapper name**, so homelab's correct code scores as a defect | fleet real figure **116, not 117**; blocks the "+1" half of 3+1 |
| 7 | A citation audit found **4 real misses**, incl. two gates described as "landed" that are unmerged | re-tensed here; one is a **fifth stale claim above the separator** |
| 8 | An **archived-citation gate** with zero false positives by construction | **ready to land, blocked by OWNERSHIP** — 7 violations, none mine |
| 9 | Two doc/code drifts in the cardinal contract doc + a duplicated `ledger_show()` | recorded at their real size; none urgent |
| 10 | **The pair state file is SPECIFIED and IMPLEMENTED but absent from the contract doc** — spec ↔ code ↔ doc, and only the doc lags | measured; sweep of all spec-mandated paths CLOSED (it is the only one) |
| 11 | **A correction to #3: the DAEMON was already proof against the prefix match** (`session_exists` is exact-membership, blocker B1, tested) | my published claim was wrong and is corrected in #456 + here; **the runbook fix still stands, better justified** |
| 12 | All **20** numbered review findings cited in the code are still pinned by tests | POSITIVE result — do not re-run |

**Two PRs opened: #456** (tests + doc corrections) and **#457** (this record).
Both 62 success / 1 skipped / 0 failures, `MERGEABLE/CLEAN`.

**READ ROW 11 BEFORE ROW 3.** Row 3's finding is real and its fix is landed, but
the reason I first gave for it was wrong — I reported the daemon as merely
"contained" when it is prefix-proof by a deliberate, tested design. The hazard is
a RUNBOOK hazard, not a daemon one.

### THE MASKED-FAILURE RECIPE IS A FLEET DEFECT, AND `livespec` CORE FIXED IT A MONTH AGO — measured 2026-08-01T09:25Z

**This changes the shape of the one decision this file says most needs a human,
so read it before weighing that decision again.** The previous session found the
masking, diagnosed it correctly, and declined to fix it because "it makes the
gate strictly stronger, which means the next occurrence of this flake turns
master RED — and master CI feeds the Dispatcher's pre-flight". That reasoning
treats `set -euo pipefail` as a NOVEL strengthening whose risk the fleet has not
yet accepted. **It is not novel. The fleet's reference repo took that exact
decision on 2026-07-01 and has run with it since.**

`livespec/justfile` carries the fix with the identical diagnosis written above it
as a comment — independently arrived at, a month before this thread rediscovered
it:

> `-e` (errexit) is load-bearing: without it a non-zero pytest exit is swallowed
> by the trailing per_file_coverage command, silently reporting GREEN on a RED
> suite.

Landed in `bc5c9bce`, 2026-07-01, subject **"chore: restore green master — narrow
README mermaid guard + unmask coverage recipe"**. The word is theirs: the recipe
was MASKING.

**THE FLEET IS SPLIT 3/5.** Of 33 git repos on disk, 11 carry a `justfile` and 8
define `check-per-file-coverage`. All five defective ones have the identical
two-command body (`pytest` then `per_file_coverage`), so all five mask the same way:

| `set -euo pipefail` (guarded) | `set -uo pipefail` (masked) |
|---|---|
| `livespec` | `livespec-overseer` |
| `livespec-driver-claude` | **`livespec-dev-tooling`** |
| `livespec-driver-codex` | `livespec-orchestrator-beads-fabro` |
| | `livespec-orchestrator-git-jsonl` |
| | `livespec-runtime` |

**`livespec-dev-tooling` is in the masked column, and that is the one that should
move the decision.** It is the repo that ships the enforcement gates the whole
fleet consumes by pin. Its own green board is subject to the same blind spot.

**THE MECHANISM, EXECUTED RATHER THAN ARGUED** (this is the whole of it):

    bash -c 'set -uo pipefail; false; true; echo $?'   ->  0
    bash -c 'set -euo pipefail; false; true'           ->  1

**AND A FALSE ALARM I NEARLY PUBLISHED, recorded because the negative result is
worth as much as the finding.** NINE recipes in this repo's justfile use
`set -uo pipefail` without `-e`, which looks like a nine-fold widening. **It is
not: `check-per-file-coverage` is the only defective one.** Every other one either
documents the omission deliberately (`check-prose-release-hygiene` explains that
`grep -c` exits 1 on a zero count, so `-e` would abort at the violation it exists
to report), ends with its load-bearing command so the status propagates
(`check-coverage`, `changed-files`), or `exit $?`s explicitly (`check-pre-commit`,
`check-pre-push`). **This repo is demonstrably aware of the pattern and reasons
about it per recipe — `check-per-file-coverage` is the one that carries no comment
and no guard.** So the fix really is one line, and "nine recipes are broken" would
have been the eighth entry in the suspect-the-verification list.

**WHAT IS STILL THE SUPERVISOR'S CALL.** Nothing here says land it. The
consequence the previous session named is real — a strictly stronger gate does
turn the next `overseer-jdo` flake into a red master. What has changed is that
this is no longer a repo-local judgement about accepting a new risk: it is a
question about **five repos being behind a fleet standard their reference
implementation adopted a month ago**, and about whether `livespec-dev-tooling` in
particular should be reporting green from a masked recipe. **Not filed, not
applied, no other repo written to.**

### A GITIGNORED CAPTURE IS NOT A CAPTURE — the evidence for the finding above is GONE

The previous session's write-up ends: "Evidence is retained at
`tmp/overseer/supervisor-prompt-quality/` (gitignored) as `jdo/run-2.log`."
**Measured 2026-08-01T09:22Z: that file does not exist.** No `jdo/` directory, no
`run-*.log` anywhere under `/data/projects`, and no file under `tmp/` mentioning
`test_the_rigs_socket_is_not_shared_with_a_concurrent_run`. The evidence
directory itself is intact and holds everything the inventory lists — this one
capture is simply absent, and the wind-down was ~2 minutes before this session
opened, so it did not decay over time.

**The finding SURVIVES, and that is the important half.** It was re-derived three
independent ways here without the log: the shell semantics executed directly, the
recipe read at `justfile:589`, and `livespec` core's month-old independent
diagnosis. **Do not re-open the finding; do not go looking for the log.**

**The lesson the previous session drew was one clause short.** It wrote: "capture
the FULL output of a failing aggregate BEFORE re-running... Redirect to a file;
grep the file, not the pipe." It did exactly that — and the file still evaporated,
because it was written into gitignored `tmp/`. **A capture that cannot survive a
`git clean` or a fresh clone is a transcript with extra steps.** The durable
forms are: a test that reproduces it, or the essential lines quoted into this
file. This is the same rule this thread already applies to citations
("a gitignored citation is a dangling dependency") arriving from the evidence
side rather than the reader's side.

### THE MODULE DOCS WERE THE THIRD UNSCANNED PROSE SURFACE — PR #456, and the corpus was NOT clean

Step 3's first move ("point an existing instrument at a corpus it has never been
run against") paid a third time. The eleven detectors had never read
`overseer/*.md` — the documents `.claude/CLAUDE.md` calls authoritative.
`overseer/AGENTS.md` carried **two class-(a) bare tmux targets**, both in the
reboot-recovery runbook's "Canary ONE pane first" block: a `respawn-pane -k` and
the `capture-pane` that confirms it.

**Why this surface is worse than a charter, and why it is worth knowing beyond
this repo.** That block is typed by a HUMAN during a fleet-wide tmux recovery —
the one moment the session being named is GONE. tmux prefers an exact match when
one exists, so the defect is invisible in steady state and fires ONLY in the
recovery the runbook exists for. The command is `respawn-pane -k`, the single
destructive operation in the system.

**DEMONSTRATED on a private socket, not argued.** With only `canary-two` alive,
`respawn-pane -k -t canary` returned **rc=0 and ran its command inside
`canary-two`**; `-t '=canary:'` refuses it (rc=1, `can't find session: canary`).
This host was carrying **14** session-name pairs where one name extends another,
including `supervisor-prompt-quality` / `supervisor-prompt-quality-supervisor` and
`livespec` / `livespec-overseer`.

**THE DOC ARGUED AGAINST ITS OWN FIX, and this is the transferable part.**
`AGENTS.md`'s gotcha list asserted that `respawn-pane` wants the BARE name and
rejects the exact-match form. **Half true, and the half that is wrong is the
operative half:** `=name` (no colon) does fail, but `=name:` **with the trailing
colon** — the form the charter gate mandates — works on `respawn-pane`,
`capture-pane`, `list-panes`, `send-keys`, `paste-buffer` and `has-session`, all
measured. So a true observation about a near-miss spelling had been generalised
into a rule that ruled out the safe form entirely.

**THIS DE-RISKS `overseer-yho.3`.** Its costing demonstrated the fleet edit
`-t X` → `-t '=X:'` takes 117 → 25, with the honest caveat "mechanically
CLEARABLE PER THE GATE, not mechanically CORRECT". The single most plausible way
that rewrite could be INCORRECT was that some tmux subcommand rejects the exact
form — and this repo's own docs asserted exactly that about the destructive one.
**Measured: it does not.** The remedy is universally applicable across every
subcommand the fleet's charters use.

**AND A CORRECTION TO MY OWN REPORT, WHICH REVERSES IT — the daemon was already
proof against this, and I said otherwise.** This section first read: "`tmuxio.py`
targets sessions the bare way too... CONTAINED rather than exploited... but R2
fails SOFT on an empty name map, so the containment is defence-in-depth, **not a
proof**", crediting `session-gone` classification and the R2 identity gate.
**Wrong, and it undersold a deliberate design decision.**

`tmuxio.py` does pass a bare `-t <session>` to five subcommands — and that is
**SAFE BY DESIGN**. `TmuxIO.session_exists` uses **exact membership in
`list-sessions`** rather than `has-session -t <name>`, *specifically because* a
bare `-t` prefix-matches: adversarial-review blocker **B1**, verified live
2026-07-13, pinned by `test_session_exists_is_exact_membership_not_prefix`. Its
docstring carries the rest, and it is the same precedence I measured
independently on a private socket: *"Every subsequent `-t <session>` call is then
safe because an EXACT session name takes precedence over a prefix match."* The
only residue is an inherent TOCTOU window if the session dies between the check
and the call.

**I suspected the artifact and the artifact was right** — this file's own rule
arriving at my expense, and the first time in its tally that the rule fired
against a claim already committed to a shipped doc rather than against a scan.
Corrected in `overseer/AGENTS.md` on PR #456.

**THE CORRECTION SHARPENS THE FIX RATHER THAN WEAKENING IT, which is why it is
worth the space.** The hazard is a **RUNBOOK** hazard, not a daemon one: a human
following the recovery steps types a session name straight into `respawn-pane -k`
with **no `session_exists` gate in front of it**, during a recovery, when the
session being named may well be gone. **The daemon earned its safety with a
tested design decision; the procedure never had one.** That is a better
justification for #456 than the one I originally wrote. **No `.py` was touched.**

### THE 117 IS CHARTER-SCOPED — I WIDENED THE CORPUS AND IT BARELY MOVES, which is the reassuring answer — 2026-08-01T10:20Z

Finding two class-(a) instances in a MODULE DOC (#456) raised an obvious doubt
about the open decision: **the 117 counts charters only, so does it understate the
population `overseer-yho.3` is costed against?** Measured across **827** markdown
files in the six fleet repos, excluding what the charter globs already cover
(`.ai/supervisor-protocol.md` and `plan/**/supervisor-handoff.md`), collapsing
symlinks, class (a) only:

**42 additional instances — and only FOUR of them are live and remediable.**

| bucket | count | disposition |
|---|---|---|
| vendored test FIXTURES (`tests/prompts/fixtures/cached-prose-*.md`) | **12** | **NEVER TOUCH.** Byte-exact copies of real cached prose, read by `test_stale_cache_generation_is_detectable.py:122,131`. "Fixing" them destroys the module's premise. |
| `overseer/AGENTS.md` | 2 | already fixed by **#456** |
| archived artifacts (`plan/archive/**`, mostly `live-adversarial-review-prompt.md`) | 24 | never regenerate — the same category as the 51-of-117 archive finding |
| live docs on OTHER tracks | **4** | real, and not this thread's to edit |

**So the charter-scoped 117 is very nearly the whole live picture, and the
recorded costing STANDS.** Recorded as a negative result precisely so nobody
re-runs this scan: widening the corpus was worth doing once and does not need
doing again.

**AND A NUMBER I NEARLY PUBLISHED THAT WAS WRONG BY ~9x — this is the part worth
carrying.** The first pass ran ALL ELEVEN detectors over arbitrary fleet markdown
and returned **368**. That number is garbage, and its failure modes are
instructive:

  - **A mermaid NODE LABEL trips (h).** `Beads["bd list / show / ready"]` inside a
    ```mermaid fence is a diagram caption, not a command — and it sits in
    `SPECIFICATION/history/vNNN/contracts.md`, so every historical snapshot
    re-counts it. One label became **13** findings in one repo.
  - **`homelab`'s own credential wrapper is unrecognised** — see below.
  - Both are the documented shape: *the false positive was always data or prose
    that legitimately RESEMBLES the defect.*

**THE DETECTORS ARE CALIBRATED TO CHARTERS AND DO NOT GENERALISE.** Nothing said
so. The charter gate's stated scope limits are about fenced-code-only and (e)'s
narrowness; there is no statement that pointing the module at a wider corpus
produces mostly noise. It does.

### `bd`-WRAPPER DETECTION IS KEYED TO ONE HARDCODED NAME — and it lands on the one repo option 3 cannot reach

**Executed, not read** (`_WRAPPER_DIRECT = re.compile(r"with-livespec-env\.sh[^\n]*\bbd\b")`,
line 188):

| input | (h) findings |
|---|---|
| `/usr/local/bin/with-livespec-env.sh -- bd show overseer-yho` | 0 |
| `/usr/local/bin/with-homelab-env.sh -- bd show hl-3ur` | **1 — FALSE POSITIVE** |
| `bd show overseer-yho` (the true defect) | 1 (control ARMED) |

`homelab` runs its own beads tenant behind its own wrapper, so
`with-homelab-env.sh -- bd show` is the CORRECT form there and the detector cannot
tell it from a genuinely bare `bd`.

**SIZE IT BEFORE ACTING ON IT.** homelab's 23 reproduces exactly; **1 of the 23 is
this false positive** and **0** are genuinely wrapper-less. So the fleet's real
figure is **116, not 117** — a 0.9% correction, recorded with its size so nobody
re-opens a settled measurement over it.

**THE ADOPTION CONSEQUENCE IS NOT 0.9%, and it is the reason this matters.**
Option 3 adopts the gate per repo; it reaches 94 of 117 because homelab consumes
no pin, and the packet's standing recommendation is the **3 + 1** shape whose "+1"
is precisely homelab. **Adopting this gate into homelab flags homelab's CORRECT
code.** And unlike the `_REPO_ROOT`-depth caveat already recorded — which fails
LOUDLY, because `test_this_repo_has_charters_to_scan` reddens on an empty set —
**this one fails QUIETLY and in the wrong direction**: it reports defects that are
not there, which is the failure mode that teaches a reader to ignore a gate.
**Parameterising the wrapper name is a precondition for the "+1" half**, and it is
a small one.

**I DID NOT CHANGE THE DETECTOR, deliberately.** The 117 is a baseline that has
been reproduced twice a day apart and that the maintainer's costing rests on;
moving it is the maintainer's call, not an audit's. The delta is recorded above so
it can be applied without re-measuring.

### EVERY CITATION IN THIS FILE, CHECKED MECHANICALLY — 2026-08-01T10:35Z

`jdo/run-2.log` being gone raised the obvious follow-up: **what else does this
file cite that does not exist?** Extracted every backticked repo-relative path
(16) and every `test_*` identifier (21) and resolved each against the tree.

**FOUR real misses, and my scan produced THREE false positives of its own** —
stated together because the hit rate is the honest part:

| cited | verdict |
|---|---|
| `jdo/run-2.log` | **REAL** — gone; already written up above |
| `plan/worktree-location-enforcement/supervisor-handoff.md` | **REAL — ARCHIVED.** See below; this one is ABOVE the separator |
| `tests/prompts/test_detector_scope_is_declared.py` | **REAL** — PR #441 is OPEN; not on master |
| `tests/test_charter_correction_counts_are_current.py` | **REAL** — PR #440 is OPEN; not on master |
| `plan/beads-v1-1-2-upgrade/supervisor-handoff.md` | my scan's fault — a CROSS-REPO path; it exists in `livespec-orchestrator-beads-fabro` |
| `SPECIFICATION/history/vNNN/contracts.md` | my scan's fault — `vNNN` is a placeholder I wrote myself |
| `test_nprocs` | my scan's fault — a **`just` VARIABLE** (`justfile:41`), not a test |

**THE TWO "LANDED" GATES ARE NOT LANDED, and the file contradicted itself about
it.** It described `test_detector_scope_is_declared` as "**Landed as** … PR #441"
and the correction-count gate's numbers as "Measured **at landing**", while the
restart state four hundred lines above says those PRs are deliberately OPEN.
Both cannot be true. **A fresh clone has neither module and neither protection**,
which matters most for the correction-count gate: this file asserts "nothing
gates this" is now false, when on master it is still true. Both re-tensed in this
change — that half is in the worker's lane.

**FIFTH STALE CLAIM ABOVE THE SEPARATOR — reported, NOT fixed, not mine.**
Line ~114, inside the section headed **"Reference material (all verifiable, none
of it status)"**:

> **The generic form's prior art:** `livespec-dev-tooling`
> `plan/worktree-location-enforcement/supervisor-handoff.md`.

That path no longer exists. The thread was ARCHIVED — `968c8b7`, *"archive
worktree-location-enforcement thread (epic 0eo closed)"* — and the charter is
intact at **`plan/archive/worktree-location-enforcement/supervisor-handoff.md`**
(13 KB, still titled "Generic Live-Session Supervisor Handoff", exactly the prior
art claimed). **Nothing is lost; only the path moved.** The one-word fix is to
insert `archive/`.

**Why this one is worth more than a broken link.** This repo ALREADY LEARNED
this lesson in code and wrote it down: `_EXEMPLAR_CANDIDATES` accepts the live
OR the archived location, commented *"a plan thread moves into `plan/archive/`
when it closes, and an unguarded read of the live path alone already made
archiving a thread a CI-reddening act once."* **The gate was hardened against
exactly this; the prose reference list was not** — and it sits under a heading
promising everything in it is verifiable. A thread closing elsewhere in the fleet
silently invalidates a citation here, and nothing looks.

### ARCHIVING A THREAD BREAKS ITS OWN CITATIONS — a gate that is READY, sound, and NOT MINE TO LAND — 2026-08-01T10:50Z

The archived prior-art citation above is not a one-off. Measured across all **9**
handoffs in this repo: **7 citations point at `plan/<topic>/…` where the thread
now lives at `plan/archive/<topic>/…`.**

| citing file | cited | now at |
|---|---|---|
| `plan/archive/background-shell-supervision-liveness/handoff.md` | its own `research/control-plane-liveness.md`, `research/root-cause.md`, `research/untracked-obligation-closure.md` (×3) | same paths under `plan/archive/…` |
| `plan/archive/ship-overseer-to-fleet/handoff.md` | `plan/ship-overseer-to-fleet/`, `plan/supervise-plan-residual-gaps/`, `…/handoff.md` (×3) | same paths under `plan/archive/…` |
| `plan/codex-parity-and-rollout-safety/handoff.md` (**LIVE**) | `plan/background-shell-supervision-liveness/handoff.md` | `plan/archive/background-shell-supervision-liveness/handoff.md` |

**SIX OF SEVEN ARE A THREAD CITING ITSELF.** Archiving moves the directory and
every self-reference inside the handoff goes stale at once. Nothing in the
lifecycle rewrites them, and `just worktree-*` / the archive step do not look.

**THE RULE HAS NO FALSE POSITIVES, BY CONSTRUCTION — and that is the design worth
keeping.** It fires only when `plan/archive/<topic>/<rest>` ACTUALLY EXISTS, so it
never guesses at a repair: a citation is flagged only when the file it should
point at is sitting right there. Contrast the naive version I tried first —
"every backticked path must resolve" — which flagged **32 of 86 (37%)** and was
overwhelmingly wrong, because citations are legitimately relative to the thread's
own directory (`research/…`), to `.claude-plugin/` (`prose/…`), or to
`/data/projects/`. **That is a fourth plausible gate killed by measuring the
corpus first, and it died the usual way.**

**WHY THIS ONE IS NOT KILLED, AND WHY I STILL DID NOT BUILD IT — the distinction
matters, because "zero false positives" reads like a green light.** It is blocked
by OWNERSHIP, not correctness. Landing it reddens master on 7 existing
violations; six sit in ARCHIVED threads and the seventh is in
`plan/codex-parity-and-rollout-safety/handoff.md`, a track this thread's
Boundaries name explicitly as off-limits. **A gate whose only remedy is editing
files you may not edit is not a gate you can land.**

**So it is handed over rather than built, and it is cheap to finish:** the rule is
the table above, the violation list is complete, and every repair is one word —
insert `archive/`. Whoever owns those files can fix the 7 and land the gate in the
same change. A live thread archiving in future would otherwise repeat this
silently, exactly as three threads already have.

**And there is a prior question a maintainer should settle first:** whether an
archived handoff is a historical RECORD that should not be rewritten at all. If it
is, the gate should scope to LIVE threads only — which reduces today's violations
from 7 to **1**, and that one is still not mine.

### THE MAINTENANCE GUIDE MAPS 5 OF 26 MODULES — 2026-08-01T11:05Z, second commit on PR #456

A second instrument over the same file, and it found more than the detectors did.
Comparing what `overseer/AGENTS.md` **enumerates** against what the tree
**holds**:

- the architecture section names **five** `supervisor.py` collaborators;
- `ls overseer/_supervisor_*.py` returns **26**;
- measured before the correction was written, **22 private modules / 4,069 lines**
  were named NOWHERE across all three module docs — `_supervisor_evaluate` (390),
  `_supervisor_discovery` (324), `_supervisor_observe` (322),
  `_supervisor_restart` (289), `_supervisor_pair` (267), `_supervisor_attention`
  (261), `_supervisor_liveness` (248) among them.

**Hand-verified before reporting**, per this file's own rule: three of those
return **zero** mentions across `AGENTS.md`, `marker-protocol.md` and `SKILL.md`.

**WHY IT IS WORSE THAN AN OUT-OF-DATE LIST.** The repo-root `.claude/CLAUDE.md`
instructs agents to read these three documents as authoritative *before changing
anything in `overseer/`*. A maintainer therefore arrives with a five-item map of a
twenty-six-module subsystem and **no signal that the rest exists**. The unlisted
modules trace to real shipped features (`feat: cover pair-stall supervisor
nudge`, `feat: escalate blocked declarations by age band`, `feat: surface
uncertifiable ready declarations`), so this is a documentation gap, not dead code.

**This is the same class as `overseer-gjb`** — a CLOSED slice of this very thread,
which re-tensed two module docs that denied `.ai/` existed. That slice fixed the
claim it was pointed at; the inventory three hundred lines away had drifted
further and nothing looked. **`.claude/CLAUDE.md`'s "these documents are CURRENT"
assurance is itself a claim with a timestamp**, and its own text says to
re-measure before refreshing the date — this is what a re-measure turns up.

**RECORDED, NOT REPAIRED, and the boundary is real:** describing what those 4,069
lines DO is `plan/daemon-liveness-truth/` (`overseer-x29`) territory. The
correction states measured facts only and tells the next reader to enumerate from
the tree rather than trust prose.

**AND IT INVALIDATED ITS OWN NUMBER — left visible deliberately.** Naming seven
modules inside the correction dropped the residue from 22 / 4,069 to **15 /
1,968** the instant it was written. Caught only by re-running the measurement
AFTER editing the artifact it was measured against. So the durable claim was
rewritten to "**5 named vs 26 on disk**", both re-derivable from the tree — a
property, not a residue count. That is this thread's oldest lesson arriving
unprompted in a paragraph written to apply it.

**TWO SMALLER DOC/CODE DRIFTS IN THE CARDINAL CONTRACT DOC, sized honestly so
nobody inflates them.** `marker-protocol.md` is THE contract for the one state
file, and comparing it against `signals.py`:

1. **`state-path-mismatch` is a FOURTH state-file verdict and appears in NEITHER
   module doc** (0 mentions in both). It is a fail-closed guard: if the per-topic
   state dir or the state file resolves outside its canonical
   `<repo>/tmp/overseer/<topic>/` location — a symlink escape —
   `read_state` returns it. `valid_token` rejects it, so the fail-closed
   behaviour is exactly as documented; what is missing is any explanation of
   the verdict itself. **Sized honestly: the operator-facing note is
   `BAD state file: 'state-path-mismatch'`, which names the condition, so this
   is a "nothing to look up" gap, not a misleading one.** One inaccuracy rides
   along: `valid_token`'s docstring says "Only genuinely unrecognized (typo'd)
   tokens are surfaced as malformed", and a path mismatch is surfaced the same
   way while being no typo.
2. **The supervisor PAIR state file is SPECIFIED and IMPLEMENTED but absent from
   the contract doc — a three-way comparison, which is the strongest form this
   check takes.**

   | record | says |
   |---|---|
   | `SPECIFICATION/contracts.md:21` (**governs**) | "A supervisor pair member keeps its OWN state file at `<repo>/tmp/overseer/<topic>-supervisor/.overseer-state`, with the same grammar, the same writers, and the same rules as a worker's." |
   | `overseer/signals.py` (**the final word on behavior**) | implements it — `_SUPERVISOR_SUFFIX`, `topic_reserved_for_supervisor`, `supervisor_entity_topic`, `supervisor_topic`, `state_path` |
   | `overseer/marker-protocol.md` (**the contract doc**) | **zero** occurrences of `<topic>-supervisor`; describes "ONE file — `<repo>/tmp/overseer/<topic>/.overseer-state`" |

   So the doc is behind BOTH the spec and the code, and `.claude/CLAUDE.md` sends
   agents to exactly this document for "the cardinal rule, the one state file,
   the restart interlock". An agent working on the pair mechanism is handed a
   single-entity picture of a two-entity contract. **Nothing is wrong in the code
   and nothing is wrong in the spec** — this is purely the middle record lagging.

   Worth noting beside the tmux finding above: the code already models `<topic>`
   / `<topic>-supervisor` as a PAIR, which is precisely the name shape that makes
   a bare `-t <topic>` prefix-match dangerous — and this host is running 14 such
   pairs right now.

   **AND THE SWEEP IS CLOSED, so nobody repeats it.** Every concrete path
   `SPECIFICATION/contracts.md` mandates was cross-checked against the code and
   both module docs — the worker state file, the pair state file, the mapping
   store, the injection-stamp sidecar, the watch-set declaration, and the charter.
   **The pair state file is the ONLY one missing from the docs**; the rest are
   covered. A negative result recorded deliberately: the question "what else has
   the spec mandated that the docs never absorbed?" now has an answer, and it is
   "nothing else".

Neither is a behaviour defect; both are the same shape as the inventory gap —
code moved, the authoritative docs did not.

**AND THE TWO CHARTER LAYERS SHARE A DUPLICATED HELPER — the concrete instance of
the masking property this file already predicted.** The layers are read TOGETHER,
so anything defined in both is a divergence risk. Measured: four variables and one
function are defined in both. **Three of the four are the DESIGN, not a defect** —
`WORKER_TARGET` and `ledger_anchor` differ exactly because the shared layer holds
placeholders (`'=<worker-session>:'`, `'<ledger-anchor>'`) and the binder's whole
job is to bind them (`'=supervisor-prompt-quality:'`, `'overseer-yho'`);
`pane_pid` and `tmux_rc` agree. **But `ledger_show()` is duplicated
BYTE-IDENTICALLY in both** (md5 `d67081bb84ac`, 7 lines), and **nothing asserts
they agree** — the two test modules that mention it do so for other reasons.

Three consequences, none urgent:

  - A fix applied to one copy silently leaves the other behind, and the layers are
    read together so the later definition wins.
  - **It is exactly what makes (h) masked in BOTH files independently.** This
    file's own finding says "a charter absorbs NEW defects of a document-scoped
    class once it holds the correct form once — a genuinely wrapper-less `bd`
    added to `.ai/supervisor-protocol.md` produces no finding". This helper is
    that correct form, and because it is duplicated, the same immunity holds in
    the binder too.
  - The hardcoded-wrapper limitation found above lives in **both** copies, so an
    adopter parameterising it for their own tenant has two places to change.

### EVERY NUMBERED REVIEW FINDING IN THE CODE IS STILL PINNED — a POSITIVE result, 2026-08-01T11:40Z

Finding `B1` in `tmuxio.py` raised a general question worth answering once: the
product code cites numbered adversarial-review findings all over
(`B1`–`B8`, `R1`–`R2`, `SF1`–`SF5`, `RB1`–`RB3`, `defect #5`, `defect #6`) as the
reason a given line is the way it is. **A citation is a dependency — so does each
one still have a test pinning it, or have some become folklore?**

**Measured across all 20: every one is covered.** 19 are traceable BY NAME from
product code into a test module. The twentieth, `defect #6` (the Codex
discovery-seam test isolation), is cited in `_supervisor_core.py:163` and named in
no test — but its behaviour IS pinned by
`test_refresh_and_adopt_route_codex_through_injected_seams`, which
`overseer/AGENTS.md` explicitly names as the proof. **So the apparent gap is a
naming gap, not a coverage gap** — and it dissolved in one grep, which is the
eighth time this session that suspecting my own check first was the right move.

**Recorded because a positive result nobody writes down gets re-derived.** This
thread spends most of its effort on drift, and this is a place where the
discipline holds completely: the reasons in this codebase are still anchored to
executable evidence. **Do not re-run this sweep** — and if a future review adds a
numbered finding, the cheap thing is to cite it in the test too, so the trace stays
mechanical rather than resting on a doc sentence.

### WHERE THIS SESSION'S YIELD ACTUALLY CAME FROM — the synthesis, and it should aim the next audit

Twelve findings, and the split is stark enough to be worth acting on: **every
CODE-side check came back clean; every PROSE-side check found something.**

| checked | result |
|---|---|
| all 20 numbered review findings still pinned by tests | **clean** |
| the wrap-up escalation gradient (`test_wrapup_escalates_from_suggestion_to_insistence`, both directions across 50/40/30/20/10, mutually exclusive) | **clean** |
| `session_exists` against the prefix-match hazard | **clean — and hardened deliberately, with a test; I was wrong to doubt it** |
| every path `SPECIFICATION/contracts.md` mandates, against the code | **clean** |
| `overseer/AGENTS.md` runbook commands | 2 defects |
| `overseer/AGENTS.md` module inventory | 5 named of 26 |
| `overseer/marker-protocol.md` vs spec + code | pair state file missing; `state-path-mismatch` undocumented |
| this handoff's own citations | 4 real misses |
| the fleet's `justfile` recipes | 5 of 8 masked |
| the repo-root "these docs are CURRENT" assurance | qualified |

**The code in this repo is in good order and its reasons are anchored to
executable evidence.** What drifts is everything a test does not read: prose
inventories, cross-references, counts, and per-repo shell recipes that no
canonical check governs. That is not a criticism of the codebase — it is where the
next audit should be pointed, and it is the mechanised form of this thread's
oldest lesson: **a claim nothing executes is a claim nothing maintains.**

**The practical corollary, for whoever opens next:** stop re-verifying the code
paths listed above as clean — they are measured and dated. Point the instruments
at documents, citations, and cross-repo configuration instead.

### `overseer-jdo` HAS STILL NOT ABSORBED THE REPORT — re-measured 2026-08-01T09:16Z

`updated_at` is **2026-07-31T03:14:09Z**, unchanged since the previous session
measured it. So everything under "WHAT `overseer-jdo` IS MISSING" is still
outstanding, and there is now a THIRD item, which reframes jdo's central premise:

**jdo treats "this flake always presents as a COVERAGE failure rather than a test
failure" as a curiosity of the signature. The masking above EXPLAINS it — and
inverts what it means.** The coverage-visible cases are the only ones caught at
all: when the flaky test dies mid-body its later lines go uncovered and the target
fails, which is the sighting everyone has seen; when it fails at an assert whose
lines are already covered, coverage holds at 100% and the board goes green with a
red test. **jdo's acceptance bar is statistical (20 consecutive clean runs), and
it cannot be measured at all while the gate can hide the failures it is
counting.** Folding this in is a ledger write on another track's item — still not
this thread's to make.

**SESSION OF 2026-07-31T14:40Z — still true, and step 3 was followed again.** The
ledger was re-measured first: no slice is filed or assigned to the worker,
`overseer-yho.3` and `overseer-bak` are unchanged at `backlog`, and nothing is
assigned to anyone. So this session audited what the thread owns, exactly as step
3 directs, and it found two things worth a cold open's attention:

- **`overseer-jcw` is CLOSED** — a duplicate of `overseer-jdo` (P1, open), closed
  2026-07-30T22:24Z by another track's worker. Two claims in THIS half were
  stale as a result, including one that flatly denied the close; both are
  corrected below. **And jdo is missing this thread's two newest mechanism-2
  findings** — see "WHAT `overseer-jdo` IS MISSING". That is the highest-value
  item this session produced and it needs a ledger write this thread must not
  make.
- **The correction-count gap this file called ungated is now gated** — see "This
  session's gate". **PR #440**, tests-only, `just check` 65/65 locally and at
  pre-push, CI 62 success / 0 failures.
- **The eleven detectors' REACH is now declared** — seven line-scoped, four
  document-scoped, measured by injection. **PR #441**, tests-only. See "THE ELEVEN
  DETECTORS DO NOT ALL MEAN THE SAME THING BY 'CLEAN'".
- **The comparator no longer SKIPS the third anchor spelling** — **PR #446**.
  `tests/test_plan_thread_records_agree.py` read two spellings; a charter using
  homelab's third form extracted nothing and hit the loop's `continue`, so the
  gate whose job is catching a stale anchor reported a clean repo over a charter
  it never examined. The table/executable pair stays MANDATORY — only a charter
  using neither falls through. **A broader "looks like a declaration but did not
  extract" guard was designed and REJECTED**: it would have reddened
  `plan/fabro-review-classifier-defect/supervisor-handoff.md`, which discusses
  the ledger anchor in prose while declaring none. That real line is now the
  fixture that stops the rejected design being re-attempted blindly. Still a
  LOCAL gate — the fleet-ready comparator remains `overseer-bak`'s scope
  decision, untouched.
- **The GENERATOR's own prose is now gated** — the charter gate scanned charters
  already EMITTED; nothing scanned the file they are emitted FROM. **PR #445**,
  tests-only. Measured clean on all eleven classes first, so it lands green as a
  REGRESSION gate. This is the same widening that paid last time: when the glob
  finally reached `.ai/supervisor-protocol.md`, that file was carrying the (h)
  defect. **The prose was the last unscanned surface and the most upstream one** —
  a defect reintroduced there ships to every adopter and is caught here only once
  somebody regenerates a charter and commits it, which nothing schedules. The
  contract module checks what must be PRESENT, not what must be ABSENT, and the
  cold-open gate checks that blocks EXECUTE, which a defective-but-runnable block
  does. **`overseer.md` is deliberately OUT**, with the reasoning recorded in the
  module: its single (a) hit is the operator console's copy-pasteable
  `switch-client` jump command, which the daemon emits bare on purpose and under
  test — class (a) exists because a `send-keys` prefix match types into the wrong
  live session silently, whereas a mis-targeted `switch-client` moves a human's
  view, which they see and undo. The rationale does not transfer.

- **The charter gate's SCOPE is now a rule, not a floor** — **PR #452**.
  `test_this_repo_has_charters_to_scan` asserts only NON-EMPTY, so it passes with
  one charter of eight: it catches a glob matching nothing, never one that quietly
  stopped matching most things. Demonstrated — dropping the archive glob removes
  FOUR of eight charters and the existing guard stays **GREEN** while the new rule
  goes RED. Keyed on the property (every charter-shaped file on disk is scanned)
  rather than a count, so it self-adjusts as threads come and go.

**All five PRs are left OPEN deliberately**: merging is the supervisor's lane
per Boundaries. Their worktrees are still on disk for the same reason — reap them
only after they land. **#440 is the ONLY one touching this file.** #441 and #445 each add a NEW
module and #446 edits `tests/test_plan_thread_records_agree.py` and #452 edits
`tests/prompts/test_charters_carry_no_known_defects.py`, each touched by no other
branch — so the five file-sets are DISJOINT and none can conflict with another.
(#441 IMPORTS from the module #452 edits, which is not a textual conflict; #452
adds tests and changes no name #441 imports.) #440 and #441 are based on `a8d3d38` and are BEHIND the pin bumps (not
diverged — `a8d3d38` is an ancestor of `origin/master`), so they may want a
rebase before merge; #445 is on `22f0d53` and #446 on `3a42837`.

Baseline measured before any edit: `just check` **65/65 green** on the clean tree
at `a8d3d38`.

**CORRECTION, AND IT REVERSES WHAT THIS PARAGRAPH SAID ALL SESSION.** It read
"mechanism 2 did not fire" and was updated several times to say it still had not,
across roughly forty green aggregates. **It fired at 2026-08-01T05:30Z** — a
NEW SIGHTING for `overseer-jdo`, worth carrying because it is P1 and its
acceptance is statistical.

- **On a DOCS-ONLY change**, one markdown paragraph, no Python touched. That is
  jdo's original description almost word for word.
- `just check` failed `check-per-file-coverage` + `check-coverage`;
  `just check-per-file-coverage` **standalone passed at 100%**; a re-run of the
  full aggregate passed **65/65**. Run-alone passes, in-aggregate flakes.
- **I CANNOT ATTRIBUTE IT TO MECHANISM 2, and will not pretend otherwise.** I
  piped the failing run through `grep` for the summary and did not keep the body,
  so the `FAILED` line is gone. The signature matches jdo; whether it was the
  watcher timing premise, a socket collision, or something else is UNKNOWN.
- **THE OPERATIONAL LESSON, which cost the attribution: capture the FULL output
  of a failing aggregate BEFORE re-running.** The re-run destroys the evidence,
  and the fix for a flake is the one thing you only get one chance to observe.
  Redirect to a file; grep the file, not the pipe. Knowing to "read for `FAILED`"
  did not help, because by then there was nothing left to read.

### `just check` CAN REPORT "All 65 targets passed" WITH A FAILING TEST — found 2026-08-01T08:05Z

**This is the most important thing in this section, and I found it by doubting my
own result.** I reported "0 of 8 failed" from the block below. **That was wrong.**
Run 2 of 8 contained:

    FAILED tests/prompts/test_repo_containment_discriminates.py::test_the_rigs_socket_is_not_shared_with_a_concurrent_run
    1 failed, 781 passed in 16.13s

…and `just check` **continued to the next target and exited 0, printing "All 65
targets passed"**. The failure was swallowed.

**THE MECHANISM IS ONE MISSING CHARACTER**, `justfile:589`:

```bash
check-per-file-coverage:
    #!/usr/bin/env bash
    set -uo pipefail          # <- no -e
    uv run pytest -n {{test_nprocs}} --cov ...
    uv run python -m livespec_dev_tooling.checks.per_file_coverage
```

There is no `-e`, so a non-zero `pytest` does not abort the recipe, and the
recipe's status is the LAST command's — the coverage check. **A test failure in
this target is therefore invisible to the aggregate whenever per-file coverage
still reaches 100%.**

**WHY THIS REFRAMES `overseer-jdo`.** jdo records that this flake always presents
as a COVERAGE failure rather than a test failure, and treats that as a curiosity
of the signature. It is not: **the coverage-visible cases are the only ones that
are caught at all.** When the flaky test dies mid-body its later lines go
uncovered, coverage drops, and the target fails — that is the sighting everyone
has seen. When it fails at an assert whose lines are already covered, coverage
holds at 100% and **the board goes green with a red test**. So every green-run
count on this host, including my own eight, is an unreliable denominator, and
jdo's statistical acceptance cannot be measured with the gate in this state.

**THE FIX IS `set -euo pipefail`, and I have NOT applied it**, deliberately: it
makes the gate strictly stronger, which means the next occurrence of this flake
turns master RED — and master CI feeds the Dispatcher's "latest master is green"
pre-flight, so it can halt fleet dispatch. Landing that before jdo is resolved is
a sequencing decision with fleet-wide consequences, not a repair. **Strongly
recommended, and the supervisor's call.** Evidence is retained at
`tmp/overseer/supervisor-prompt-quality/` (gitignored) as `jdo/run-2.log`.

**AND THE HAZARD THAT ALMOST BURIED IT: a log with stray NUL bytes makes `grep`
go BINARY and silently count nothing.** `run-2.log` carries 4 NULs from icdiff's
colour codes, so `file` calls it `data` and every counting `grep` over it
returned EMPTY rather than `0` — which read as "this run is unremarkable". Only
`grep -a` sees it. **Use `grep -a` on any captured tool output**; this is the
grep-matches-nothing hazard with a fourth vector — not a wrong pattern, not a
shell alias, but the file being classified as binary.

**THE 8-RUN BLOCK, RESTATED HONESTLY: 1 of 8 runs contained a failing test**,
which the aggregate reported as green. Stated as a
NEGATIVE result, because that is what it is, and jdo's own note already does this
arithmetic: 8 greens is consistent with the defect being completely unchanged.

    if the true per-run rate is 1/7  -> P(8 consecutive green) = 29.1%
    if the true per-run rate is 1/40 -> P(8 consecutive green) = 81.7%

**The 1/40 figure is the one this session actually supports**: roughly forty-odd
full aggregates on this host today with **one** failure. That is a far weaker
per-run rate than the ~1-in-7 both original sightings suggested — worth recording
because jdo's acceptance is statistical and its bar (20 consecutive clean for 95%
against p >= 1/7) was set against the older, higher estimate. **If the real rate
is nearer 1/40, twenty clean runs proves much less than the packet assumes**, and
the acceptance arithmetic should be redone against a measured rate rather than
the first two sightings.

**THE HARNESS IS THE REUSABLE PART, and it is four lines:** loop N times, redirect
`just check` to `run-$i.log` FIRST, branch on `$?`, and grep the FILE on failure.
Any future session can run it unchanged and add to the count instead of starting
the sample over.

**EVERY HEADLINE NUMBER THIS SESSION PUBLISHED WAS RE-CONFIRMED ON A SECOND,
INDEPENDENT PASS AT SESSION CLOSE — 14 of 14** (2026-07-31T18:30Z): 19 role-level
Corrections and 1 thread-specific; 11 shipped detectors over 8 charters scoring
**0**; the contract's 31 requirements, the shared layer's 4 misses alone, the
exemplar's **0** combined, and the prose's single documented exemption; the
fleet's **117** with the orchestrator at 56 and this repo at 0; and the
orchestrator shared layer's 10 going to **0** on one binding line. Written as a
list of assertions rather than prose so the next session can re-run it rather
than re-derive it.

**WHAT WAS CHECKED AND FOUND SOUND**, recorded because a negative result nobody
writes down gets re-derived: the charter counts (19 C-entries, 1 T-entry) agree
with the prose; all **eleven** detectors have positive controls and none is
blind; the charter glob is COMPLETE (the only unscanned charter-shaped file is in
gitignored `tmp/`, and `.ai/` holds exactly the one shared layer); the
stale-cache module is NOT host-dependent (its artifacts are vendored byte-exact
precisely because CI has no plugin cache); and the fleet's **117 reproduced
exactly**, every per-repo figure identical. **Do not re-derive these.**

**WHERE THE THREE OPEN ITEMS STAND, as of 2026-07-31T14:36Z** (re-verified at
session end; the fleet costing was re-run from the evidence dir and still reads
117 → 25 / 92 cleared with its control at 117). All three sit with the
maintainer, each with its numbers, and none is filed or closed:

| item | state |
|---|---|
| `overseer-yho.3` | Fully COSTED. The fleet edit is near-mechanical (117 → 25 demonstrated in memory, all of class (a) cleared); the highest-leverage fix is ONE line clearing 10 defects in a shared layer; option 3 reaches 94 of 117 because `homelab` consumes no pin. **Needs a decision, not a number** — and the decision is now MAKEABLE FROM THIS FILE: the four options were cited in five places and defined nowhere outside a gitignored packet, and are now carried in full under "THE FOUR OPTIONS THEMSELVES". Option 3's portability is verified standalone; the one-line 10 → 0 fix is re-verified with its control. |
| `overseer-jcw` → **`overseer-jdo`** | **jcw is CLOSED** (2026-07-30T22:24Z, as a DUPLICATE of `overseer-jdo`; re-measured 2026-07-31T14:40Z). jdo is P1, open, and the single live home. Mechanism 1 (shared tmux socket) FIXED and gated. Mechanism 2 COSTED here — but **jdo's notes predate both the severity correction and the costing**, see "WHAT jdo IS MISSING" below. **Needs a contract decision.** |
| `overseer-bak` | Gap real and reproduced from both directions; **incidence nil** — re-verified 2026-07-31T16:20Z, every figure reproduced (12 threads, 7 declaring, 0 disagreeing), including after another track rewrote its own handoff. Two local static gates landed; **PR #446** stops the comparator silently skipping the fleet's third anchor spelling. Live-only is 12 threads; with archives it is 26, so a comparator must say which population it means. **Needs a scope decision.** |

The only defect this thread found in itself is fixed: the charter's `ledger_anchor`
pointed at a closed bug and now points at `overseer-yho`, gated by
`tests/test_plan_thread_records_agree.py`.

**NOTHING WAS IN FLIGHT AT THE END OF THE 2026-07-30/31 SESSION** — but **five PRs
are open now** (#440, #441, #445, #446, #452), all from the 14:40Z session above,
so this paragraph is no longer the current picture and is kept as that session's
record. (It said "PR #440 is open now" until the sweep below caught it: I wrote
that when there was one, and four more landed after it without the sentence
moving. **Appending never revisits what it contradicts** — the same mechanism the
correction-count gate exists for, in a paragraph I had already edited once to fix
exactly this.) **That session landed 13
PRs / 15 commits and ALL ARE MERGED** (#411, #413, #418, #419, #421, #424, #425, #426, #427, #429,
#432, #434, #437 — counted from the forge, not from memory, after a first tally of
"12 PRs / 32 commits" proved wrong in both figures) — no open branch, no open PR,
no worktree, no background job of mine, and **zero ledger writes all session**. So a cold open inherits a clean tree
at `origin/master`, not a half-finished change. What that session produced, if you
need to find it: the charter anchor fix + its gate (#421, #425); `overseer-jcw`
mechanism 1 fixed in two modules + a property gate (#418); and the rest are this
file — the `yho.3` costing, the jcw mechanism-2 costing, the `bak` measurement,
four hazards, and the four-stale-claims record below. **Every number in this file
below the separator was re-measured at session end and still holds** (7 of 7), and
the full aggregate passed at the then-current `livespec-dev-tooling` pin `v1.13.6`
(**now `v1.13.8`** — another track landed `v1.13.7` and `v1.13.8` mid-session on
2026-07-31; re-verified 65/65 at `v1.13.8`, so the bump is clean here),
which another track bumped while that session was finishing.

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

   **WHAT ACTUALLY WORKED, TWICE — four moves, in the order that paid.** Step 3
   has now been followed by two sessions (7 PRs, then 5). Both times the value came
   from the same four moves, and none of them needs permission, a ledger write, or
   another track:

   1. **Point an EXISTING instrument at a corpus it has never been run against.**
      The single most productive move both times. The eleven detectors had never
      been run over the generator prose (→ PR #445), over every charter by
      injection (→ the reach map, PR #441), or over the fleet from a standalone
      copy. The contract validator had never been run over this repo's own
      charters or the fleet's (→ two instruments independently naming the same
      dominant defect). **The instruments already exist and are cheap; the corpora
      they have not been pointed at are where the findings are.**
   2. **Compare two records that describe the same thing.** The charter against
      the handoff (→ the anchor defect), the handoff against the ledger (→ jcw
      closed), a document's timestamps against the findings that postdate it (→
      what `overseer-jdo` is missing). Nothing in the fleet does this
      automatically, so it is always unexamined.
   3. **Check that anything CITED actually exists durably.** This file referenced
      "the four costed options" five times and defined them nowhere outside a
      gitignored packet, which made the one open decision unmakeable from the
      handoff. A citation is a dependency; a gitignored one is a dangling
      dependency.
   4. **Execute a claim instead of reading it.** The provenance block was
      extracted and RUN rather than reasoned about; the gate module was COPIED
      outside the repo and run under system python. Both confirmed prose that
      would otherwise have stayed an assertion.

   **And the discipline that stopped four bad gates shipping: measure the whole
   corpus before writing any rule.** Three plausible gates died that way this
   session (see Hazards), each with a false positive already sitting in the tree.
   **A gate is not justified by being correct on the example that motivated it.**

   The original prohibition still stands and is not weakened: **do not file, do not
   transition, do not close, and do not touch another track.**
   `codex-parity-and-rollout-safety` and `daemon-liveness-truth` (`overseer-x29`)
   have their own sessions. But "no slice is queued" is not "there is no work" —
   it means the work is verification, measurement, and preparing decisions rather
   than execution. **Ask what this thread has ASSERTED that nobody has CHECKED.**

**Do not merge release PR #360** or any Release Please PR. It now reads
**0.16.0**, not the 0.15.1 this line used to name: Release Please RETITLES the
same PR as commits land, so a version written into a standing instruction ages
even though the PR number it points at never moves. Re-measured 2026-07-31T14:45Z
— `plugin.json` and the newest tag both still read **0.15.0**, so nothing has
shipped and the provenance HALT below still stands.

**One live consequence to expect, which looks like a bug and is not:** this
repo's own charter now HALTs its provenance precondition, naming two different
digests. That is correct — see "Provenance" below — and it clears when #360
ships. Do not re-stamp the digest to silence it.

## WORKER RESUME STATE — first measured 2026-07-30 19:40Z; large parts RE-VERIFIED 2026-07-31

**Sections below carry their own dates and the later one wins.** Re-verified on
2026-07-31: the fleet's 117 (reproduced exactly, per-repo identical), the
one-line 10 → 0 fix with its on-disk control, `overseer-bak`'s whole table, the
provenance HALT (executed, not inferred), and the gitignored artifact inventory.
Nothing re-measured was found wrong; what changed is that `overseer-jcw` closed
and the four remediation options are now carried here.

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
half. That option post-dates the costed options, which are now carried in full
below under "THE FOUR OPTIONS THEMSELVES" rather than left in a gitignored file.

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

**RE-VERIFIED 2026-07-31T17:30Z from a fresh invocation, and it is exactly as
recorded.** 10 findings, **all of class (a)**; the file uses `"$WORKER_TARGET"`
ten times and carries **ZERO** bindings of it; inserting the one line takes it to
**0**; and the control — re-scoring the on-disk file afterwards — still reports
**10**, so nothing leaked to disk. This is the most decision-relevant single
number under `overseer-yho.3` and it has now been reproduced twice, a day apart,
by different code paths (the second from a standalone copy of the module running
outside this repo entirely).

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

### THE FOUR OPTIONS THEMSELVES — carried here 2026-07-31T17:15Z because NOTHING DURABLE DEFINED THEM

**This file cited "option 3", "option 4" and "the four costed options" in five
places and defined them NOWHERE.** They existed only in the gitignored
`GAP-no-remediation-slice.md`. So the single decision this thread says is
outstanding — the one it insists needs "a decision, not a number" — **could not
be made from this handoff at all**, and a fresh clone would have inherited five
dangling references to a document it does not have. The numbers were carried out
of that file and the choices they price were left behind.

| # | option | original cost | verdict after the 2026-07-30 re-measure |
|---|---|---|---|
| 1 | **A remediation sweep** — rewrite every emitted charter to `-t '=<name>:'` | spans 5 repos, so mostly cross-repo ROUTING, not local work; the one-slice/one-ledger model fragments it | **Cheaper than it reads.** Routing being ~all the cost is CONFIRMED and quantified; the edit itself is near-mechanical (117 → 25 in memory, all of class (a) cleared). |
| 2 | **Per-repo routing items** — one finding per owning track, no local slice | five conversations; no single place shows whether the fleet is clean | Unchanged. |
| 3 | **A recurring CHECK instead of a sweep** — `tests/prompts/test_charters_carry_no_known_defects.py` (NOT the gitignored `blast_radius.py` prototype it was costed against) runs in each repo's CI | needs the tool productionised AND adopted per repo | **Half discharged.** The tool IS productionised, eleven classes, green here, and imports and runs unmodified from outside this repo. What remains is per-repo ADOPTION, not construction. **But it reaches only 94 of 117** — `homelab` consumes no pin. |
| 4 | **Accept it** — the generator is fixed; instances decay as threads regenerate | an unbounded tail | **Weaker than when written.** 51 of 117 (44%) sit in `plan/archive/`, which NEVER regenerates, so waiting cannot reach nearly half the exposure. And the tail is now known to be mostly mechanical, so accepting it buys little. |

**A fifth shape the packet never costed, which the measurement points at:**
**3-for-pin-consumers + 1-for-homelab** — the check adopted by pin bump where a
pin exists, a one-off sweep for the 23 defects in `homelab`. And a **phased first
cut** is cheapest by a wide margin: `livespec-orchestrator-beads-fabro` alone is
56 of 117 (48%), and its single highest-leverage fix is **one line in one shared
file** clearing 10.

The packet's own standing recommendation was **3 + 1** — the check makes the
population visible and stops it growing, the sweep then drains what it exposes.
**That recommendation is the packet author's, not a decision**, and it predates
both the homelab-reach finding and the archive finding.

**Still nothing filed, nothing cut, no other repo written to.**

**OPTION 3's LOAD-BEARING CLAIM, VERIFIED THE HARD WAY — 2026-07-31T17:25Z.**
"Productionised and portable" was asserted from a run INSIDE this repo. Re-tested
properly: the module was COPIED outside the repo entirely and executed under the
system `python3` (**3.13.7**, no venv, no `uv`, none of this repo's deps). It
imports `re` and `pathlib` and nothing else, and it ran. Against
`livespec-orchestrator-beads-fabro/.ai/supervisor-protocol.md` it returned **10
findings** — independently reproducing the "one line clearing 10 defects in a
shared layer" result from a standalone copy. **So option 3 needs no packaging
work: the artefact is a single stdlib-only file.**

**ONE ADOPTION CAVEAT, and it is cheap but real.** `_REPO_ROOT` is derived from
`__file__` depth (`parent.parent.parent`) and `_CHARTER_GLOBS` hang off it, so a
copy placed at a different depth scans NOTHING — the standalone run returned an
empty charter set. An adopter must either put it at `tests/prompts/` or adjust
`_REPO_ROOT`. **This fails LOUDLY, not silently**: `test_this_repo_has_charters_to_scan`
asserts the set is non-empty precisely for this, so a mis-placed adoption reddens
instead of reporting a clean repo. That vacuity guard is the difference between a
cheap caveat and a silent no-op, and it is worth seeing that it paid off in a
scenario nobody wrote it for.

### HOW FAR THIS REPO'S CHARTERS ARE FROM THE CONTRACT — measured 2026-07-31T17:55Z, and it is MUCH closer than it looks

Never measured locally before. The contract carries **31** requirements. Run over
each charter ALONE the misses look alarming — 13 to 26 — but that is the wrong
reading: the two-layer split moved most of the contract into
`.ai/supervisor-protocol.md`, so a binder is not supposed to carry it. **Combined
with the shared layer the real distance is 0 to 4.**

| charter | missing (combined with the shared layer) |
|---|---|
| `supervisor-prompt-quality` (the exemplar) | **0 — fully conformant** |
| `codex-parity-and-rollout-safety` | 2 — `pane-pid-empty-verdict`, `generator-provenance-self-check` |
| `fabro-review-classifier-defect` | 2 — same two |
| `background-shell-supervision-liveness` (archived) | 1 — `generator-provenance-self-check` |
| `supervise-plan-residual-gaps` (archived) | 2 |
| `ship-overseer-to-fleet` (archived) | 3 |
| `cutover-and-shipping` (archived) | 4 — the worst, adding `readlink-empty-guard` |

Across all seven: **`generator-provenance-self-check` 6×, `pane-pid-empty-verdict`
5×, `supervisor-agent-proof` 2×, `readlink-empty-guard` 1×.**

**WHY THIS MATTERS FOR THE OPEN DECISION.** Option 4 rests on "instances decay as
threads regenerate". This says regeneration would have little left to do — the
non-exemplar charters are **two requirements** from conformant, not twenty — so
the cost of closing the gap by hand is far lower than the "alone" figures imply,
and the leverage is again in the SHARED layer, the same shape as the
orchestrator's one-line 10 → 0. It also localises `overseer-bak`'s "provenance
reaches 1 charter in 12": here it reaches **1 in 7**, and the six that lack it
simply predate `overseer-yho.2` and were never regenerated. That IS the
nothing-schedules-regeneration thesis, quantified at home.

**ONE ROLE-LEVEL GUARD IS STRANDED IN THE EXEMPLAR'S BINDER — reported, not fixed.**
Four requirements are supplied ONLY by this thread's binder and not by the shared
layer: `readlink-empty-guard`, `pane-pid-empty-verdict`, `supervisor-agent-proof`
and `generator-provenance-self-check`. Three of those four are fine on inspection:

- `generator-provenance-self-check` **must** be per-charter — its value is a
  digest resolved per generation (see below).
- `readlink-empty-guard` and `supervisor-agent-proof` are absent from the shared
  layer but the two other live charters **satisfy them independently**, so
  nothing is missing in practice.

**`pane-pid-empty-verdict` is the one that is actually missing**, from BOTH other
live charters. It is a role-level rule — guard `pane_pid` non-empty before using
it, exactly C2's empty-string false-pass in another command — and every
supervisor should run it, yet it exists only here. Moving it to the shared layer
would hand it to every thread in this repo at once: **the same
one-line-in-a-shared-layer leverage as the orchestrator's 10 → 0**, applied at
home.

**Why I did not do it, and it is not only the boundary.** The block is
thread-bound in a way that is easy to miss: its HALT message hardcodes
`'supervisor-prompt-quality'`, so relocating it means PARAMETERISING that string,
not moving lines. And `.ai/supervisor-protocol.md` is read by every thread's
supervisor including other tracks', so changing it reaches
`codex-parity-and-rollout-safety` and `fabro-review-classifier-defect`. That is a
maintainer's call, not an audit's.

**This is the same defect class this thread already recorded in the reference
adopter** — homelab's acting-daemon prohibition sitting in a per-thread binder
instead of the shared layer, leaving 5 of 6 threads without a role-level rule.
Finding one instance at home, in the hardened exemplar, is the useful part: the
layering defect is not something only other repos have.

**THE PROSE'S OWN SINGLE "MISS" IS NOT A DEFECT — do not go fix it.**
`missing_requirements` reports `generator-provenance-self-check` against the
generator prose, and that is correct and asserted deliberately: the value is a
DIGEST resolved per generation, so it cannot exist in a template, and must not,
because an example digest is something a generator would copy verbatim. The
exemption is pinned as an EXACT one-item list rather than a filter, so it cannot
become a hole — if the prose stopped instructing any other requirement the list
would grow and the test would fail. The prose-level half is checked separately by
`test_the_generator_prose_mandates_the_provenance_record`. **Measured, read, and
left alone.**

### THE SAME MEASUREMENT ACROSS THE FLEET — 2026-07-31T18:05Z, and TWO INSTRUMENTS AGREE

The contract validator runs unmodified over other repos' charters, so the local
number above has a fleet counterpart. Combined with each repo's shared layer
where one exists:

| repo | charters | shared layer? | median miss | worst |
|---|---|---|---|---|
| **livespec-overseer** | 7 | yes | **2** | 4 |
| livespec-orchestrator-beads-fabro | 5 | yes | 29 | 32 |
| livespec | 4 | **no** | 30 | 31 |
| livespec-dev-tooling | 3 | **no** | 32 | 36 |
| livespec-console-beads-fabro | 1 | **no** | 33 | 33 |
| homelab | 6 | yes | 39 | 47 |

**READ THE CAVEAT BEFORE THE NUMBERS.** The contract holds **31** requirements,
yet misses run to 47 — so the returned list is NOT bounded by the requirement
count and "39 of 31" is meaningless. `non-exact-tmux-target:*` reports **one entry
per offending command**, so a charter with eight bare targets contributes eight.
Requirement-level and instance-level entries are mixed in one list. This repo's
0-4 figures are purely requirement-level because it has no instance violations at
all, which is exactly why the two columns are not comparable across rows.

**THE FINDING THAT SURVIVES THE CAVEAT, and it is the useful one: TWO INDEPENDENT
INSTRUMENTS NAME THE SAME DOMINANT DEFECT.** The contract validator's top miss in
the three worst repos is `non-exact-tmux-target:capture-pane` / `:send-keys` /
`:has-session` — which is **detector class (a)**, the 92-of-117 finding, arrived
at by a completely different mechanism. The eleven-detector gate and the
31-requirement contract were written separately, key on different things, and
agree on where the exposure is. That is real corroboration for
`overseer-yho.3`'s costing, and it is the first time the two have been pointed at
the same corpus.

**SIZING THAT LEVER — and it CORRECTS the sentence below.** Simulated by combining
each shared-layer-less repo's charters with THIS repo's shared layer. Stated
approximation: ours carries role-level contract text plus our own bindings, so
this is the CEILING of the lever, not a drop-in result.

| repo with no shared layer | median now | with one | delta |
|---|---|---|---|
| `livespec` | 30 | **4** | −26 |
| `livespec-dev-tooling` | 32 | **4** | −28 |
| `livespec-console-beads-fabro` | 33 | 13 | −20 |

**But HAVING a shared layer is not the same as having a CONFORMANT one, and that
is the real finding.** Measuring what each existing shared layer already carries
for its own repo:

| repo | median alone | with its OWN shared layer |
|---|---|---|
| `livespec-overseer` | 19 | **2** |
| `livespec-orchestrator-beads-fabro` | 32 | 29 |
| `homelab` | 31 | **39 — WORSE** |

So "three of six repos have a shared layer" **overstates it**: the orchestrator's
buys 3, and homelab's is net NEGATIVE. **Effectively ONE repo in the fleet has a
shared layer that carries the contract.**

**WHY HOMELAB GOES UP, because the metric is the reason and it is a limit on
everything above.** `non-exact-tmux-target:*` is INSTANCE-level, so adding text
adds violations: homelab's shared layer brings its own bare targets with it. The
miss count is therefore **NOT MONOTONIC** and cannot be compared across
configurations that change how much text is being read. The −26/−28/−20 deltas
are clean only because OUR shared layer contributes zero bare targets; they
measure "a conformant shared layer satisfies the role-level requirements", not
"any shared layer helps". **Do not quote these numbers without that sentence.**

**THAT ASSUMPTION WAS VERIFIED, NOT ASSERTED — with a control.** Our shared layer
scored alone: **4 misses, of which ZERO are instance-level bare-target entries**.
And the decisive check, run per charter: adding our layer to a foreign charter
introduced **0** new bare-target entries in `livespec`, **0** in
`livespec-dev-tooling`, **0** in `livespec-console-beads-fabro`. So the deltas are
clean by measurement rather than by argument. The two shared layers that DO carry
bare targets are the orchestrator's (**8** instance entries) and homelab's
(**9**) — which is precisely why those two repos gain nothing, or lose, from
their own split.

**AND A THIRD INSTRUMENT LANDS ON THE SAME FILE.** The orchestrator's shared
layer showing 8 bare-target entries under the CONTRACT validator is the same
`.ai/supervisor-protocol.md` that the DETECTOR gate scores at 10 and that one
added binding line takes to 0. Different instruments, different counting
granularity (8 vs 10 — the contract groups by command, the detector reports per
line), same file, same defect, same remedy. **The single highest-leverage edit in
the fleet has now been found independently three times.**

**SECOND FINDING: only THREE of six repos have a shared layer at all.**
`livespec`, `livespec-dev-tooling` and `livespec-console-beads-fabro` carry no
`.ai/supervisor-protocol.md`, so every one of their charters must carry the whole
contract alone. That is a structural reason their numbers cannot improve the way
this repo's did — **a CONFORMANT two-layer split is the single biggest lever in the
measurement, and five of six repos have not taken it** — three have no shared
layer, and two have one that carries little or none of the contract. No option in the packet
mentions it. Not a recommendation, and not mine to cut — but a maintainer
choosing between the four options should know the cheapest local win here was
architectural, not a sweep.

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

### THE PROVENANCE HALT IS LIVE AND CORRECT — executed 2026-07-31T16:45Z

Not inferred from the prose: the charter's own block was EXTRACTED AND RUN. It
HALTs at rc=1 naming both digests — recorded `eaebe06065b3…`, installed
`9ca18d5677…` — the cache ref `013d35d48cde` still holds the released prose, and
the cache carries the same ELEVEN refs the stale-cache module's premise records.
So the "expect a HALT here, and do NOT re-stamp to silence it" guidance above is
accurate and still current. Nothing to do.

**AND A GATE I TALKED MYSELF OUT OF, recorded so the next session does not build
it.** The obvious way to catch the forgery that guidance warns about — someone
re-stamping `generator_prose_md5` to the cache's value to go quiet — is to assert
`generator_prose_md5 == md5(.claude-plugin/prose/supervise-plan.md)`. It is
static, needs no cache, would run in CI, and it PASSES TODAY (both are
`eaebe06065b3…`). **It is still wrong.**

A charter's provenance is a HISTORICAL record of what produced it. When generator
prose lands without the charter being regenerated, the charter legitimately
records the OLDER digest — it is behind, not incorrect. That gate would redden
master on every prose change and the cheapest way to green it would be to
re-stamp the digest WITHOUT regenerating, which is precisely the forgery the
guidance forbids. **A gate whose easiest remedy is the defect it exists to
prevent is worse than no gate.** The honest conclusion is that provenance
correctness cannot be checked statically without knowing whether the charter was
regenerated, and that fact is not recorded anywhere else.

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

**RE-VERIFIED 2026-07-31T16:20Z, and every figure reproduced exactly**: 12
threads carrying both records, 7 declaring (homelab 5, orchestrator 1, this repo
1), 5 uncomparable, **0 disagreeing**, 1 of 12 with provenance. That re-run
matters more than a routine one because the `codex-parity-and-rollout-safety`
track rewrote its own handoff (70 insertions) in between, and a fresh edit to one
of a thread's two records is exactly when they diverge. They did not. **The
nil-incidence finding survives contact with a live edit.**

**NEW, AND IT CHANGES THE COMPARATOR'S SIZING: the 12 is LIVE THREADS ONLY.**
Including `plan/archive/*/`, **26** threads carry both records — and the extra 14
all declare no anchor, so the declaring count stays 7 while the uncomparable
population grows from 5 to 19. Whoever builds the comparator should say which
population they mean: scoped to live threads it covers 7 of 12, scoped to
everything it covers 7 of 26.

### `overseer-jcw` HAS TWO MECHANISMS. ONE IS FIXED; THE OTHER IS NOT — 2026-07-30T23:55Z

Diagnosed and half-fixed by this thread because `tests/prompts/` is this thread's
own deliverable. **This thread wrote no ledger entry — but jcw IS now closed**,
and this paragraph used to deny it. Re-measured 2026-07-31T14:40Z: closed
2026-07-30T22:24:12Z by the `codex-parity-and-rollout-safety` worker as a
DUPLICATE of `overseer-jdo` (P1, open), which is now the single live home for
this defect. The close reason is careful and worth reading — it folded this
item's evidence into jdo FIRST and read it back before closing.

**The claim was true when written and stopped being true the same evening**,
which is the failure this file names on every other page: a status sentence in a
durable record ages silently while its neighbours get re-measured. It survived
two later edits to this very section (the 03:43Z correction and the 04:50Z
costing) because those appended below it and never re-read the paragraph above.

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
  FIRST. Measured 2026-07-31: SEVEN for seven, now across two sessions.** This is
  the synthesis of the individual entries below, and it is worth more than any of
  them, because EVERY apparent defect that a check reported turned out to be the
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
  5. **2026-07-31, second session.** A grep for `new-session` reported FIVE
     `tests/prompts/` modules driving real tmux against this file's claim of
     four, which looked like exactly the count-drift this thread hunts. The fifth
     was `test_rig_sockets_are_run_unique.py`, whose own docstring says **"this
     module drives no tmux and therefore has no socket to misname"** — every hit
     was in its prose ABOUT the defect. It is a static scanner with zero
     subprocess calls. **The claim of four was right.** Note the shape: the
     module is itself a detector built to avoid being fooled by prose that
     mentions the defect, and my check was fooled by that module's prose. Had I
     "corrected" the four to five I would have falsified an accurate record.
  6. **The rule working, in-session.** A sabotage-verification predicate asserted
     `t.count('"g":')==1` after deleting one of three `"g":` lines, so it read
     as "the sabotage did not produce the defect" when the sabotage was fine and
     the arithmetic was mine. Different vector from the five above — not a scan
     over artifacts but the CHECK ON A CHECK — and the reason it cost a minute
     rather than a working gate is that the assertion fired BEFORE the verdict
     was read, which is the operational form below doing its job.
  7. A fleet record-agreement scan reported **2** charters declaring an anchor
     against a true **7**, with a control I had deliberately built from a
     FOREIGN spelling passing — because I fed that spelling to the wrong
     extractor. Detailed as its own bullet below, because the mechanism is
     distinct from the six above and knowing them did not prevent it.
  And a seventh, in the other direction: a module with SEVEN tests beside a claim of
  "all four of its states" looked like drift, and was not — four were cache states
  and three were charter-shape checks. **Correcting it would have falsified an
  accurate record and destroyed the distinction the module is built around.**

  The operational form, because "be careful" is not a rule: **before reporting a
  defect a check found, reproduce it by hand on the artifact itself.** Open the
  file you just claimed was empty. Read the test NAMES before trusting their
  count. Ask what population a number counts before deciding it is wrong. Every
  one of the five above dissolved in under a minute of looking directly, and each
  had already survived a control that I believed.

- **AND THE SHARPER FORM, WHICH CAUGHT ME 2026-07-31 ON THE VERY MEASUREMENT
  BELOW: A CONTROL CAN EXERCISE THE RIGHT SPELLING AGAINST THE WRONG EXTRACTOR.**
  Re-running the record-agreement scan I asserted the homelab bullet spelling in
  a control, watched it pass, and still reported **2** charters declaring an
  anchor against a true **7** — the identical wrong number this thread recorded
  the first time. The reason: that spelling belongs to CHARTERS, and I was
  applying it to `handoff.md` while the charter extractor still read only two
  spellings. So the control proved "this regex matches this string" when the
  claim needed was "this regex runs over the file that contains this string".
  **A control must be routed through the SAME call path as the measurement**,
  not merely fed the same text. Knowing the hazard below did not save me — I had
  read it, quoted it, and walked into it anyway, which is the argument for
  reproducing a suspicious count by hand rather than trusting any control.
- **THREE PLAUSIBLE GATES DIED THIS SESSION, ALL KILLED BY MEASURING THE REAL
  CORPUS BEFORE WRITING THEM — and that is the pattern, not the three.** Each
  looked obviously correct, each would have passed on the day it was written, and
  each had a false positive already sitting in the tree:
  1. **`generator_prose_md5 == md5(repo prose)`**, to catch someone re-stamping
     the digest to silence the provenance HALT. Static, CI-able, green today —
     and **its easiest remedy is the forgery it exists to prevent**: a charter's
     provenance legitimately lags after a prose change, so the gate reddens on
     every prose change and the cheapest fix is re-stamping without regenerating.
  2. **A "looks like a declaration but did not extract" guard**, to catch any
     future unknown anchor spelling. It would have reddened
     `plan/fabro-review-classifier-defect/supervisor-handoff.md`, which discusses
     the ledger anchor **in prose** while declaring none.
  3. **"No ISO-8601 `Z` timestamp under `plan/` may be in the future"**, to catch
     the ambient-date hazard at commit time. The premise was that a full
     `…T…:…Z` stamp is a MEASUREMENT. It is not: the one future stamp in the
     tree is the **Codex access-token expiry**
     (`2026-08-08T17:37:28Z`), which is legitimately in the future and uses the
     identical form. Intent is not in the text, so no regex separates them.
     (Bare dates are hopeless for a different reason — there are **319**.)
  **The common shape: the false positive was always data or prose that
  legitimately RESEMBLES the defect** — the same family the charter gate's
  fenced-code-only rule exists for. **A gate is not justified by being correct on
  the example that motivated it. Run it over the whole corpus first, and read
  what it flags.** All three were killed in under five minutes each; shipping any
  of them would have cost a red board and a bad lesson.
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
  **THIRD INSTANCE 2026-08-01, WITH A WORSE TAIL: the rejection was an `--amend`
  ON AN ALREADY-PUSHED COMMIT.** The hook printed 🥊 rather than ✔️, HEAD stayed on
  the pre-fix commit, the fix sat STAGED — and because the branch was already
  pushed, **the REMOTE was left holding the broken version** while the local tree
  looked like it had a pending edit. A clean retry of the identical amend
  succeeded, then `git push --force-with-lease` was required. **After a rejected
  amend, check what the REMOTE has, not just `git status`** — three states can
  disagree at once (HEAD, index, origin), and only the third is invisible locally.
- **A CONDITIONAL WHOSE FALSE BRANCH CANNOT BE TAKEN IS AN AUTOMATIC COVERAGE
  FAILURE HERE.** `if shared.is_file():` over a file that always exists left one
  partial branch (`663->666`) and dropped the file to 99%, failing `fail-under=100`
  on both coverage targets. The headline read "Coverage failure", which is exactly
  the signature `overseer-jdo` warns is easy to misread as someone else's flake —
  it was mine, and reading for the `Missing` column rather than the headline said
  so in seconds. **The fix is to remove the branch, not to cover it**: a glob over
  an absent path yields nothing and needs no conditional.
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
  **IT IS GETTING WORSE, AND HERE IS THE NEW DATA POINT.** Measured 2026-07-31 at
  **63** worktrees: the second creation of the session took **14 attempts** —
  eight consecutive 141s, then five more, succeeding on the fourteenth. The first
  creation that same session took one. So the coin is no longer fair: at 56
  worktrees it was 4-of-8, and the "retry three or four times" shape this bullet
  used to describe now understates it badly. **Budget more retries than you think,
  and do not read a long run of 141s as a different fault** — each failure still
  leaves NO partial state (verified again: no branch, no directory). Since the
  porcelain output grows with every worktree, reaping orphans is the only thing
  that improves the odds, and `just worktree-reap` cannot see rebase-merged
  branches (`overseer-btt`).
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

  **IT RECURRED EXACTLY ONE DAY LATER, AT THE SAME MINUTE — caught live.** At
  local `2026-08-01T00:02:59 CEST` the harness announced "Today's date is now
  2026-08-01" while **UTC was `2026-07-31T22:02:59Z`**. The first sighting was
  local `2026-07-31T00:03`, UTC `2026-07-30T22:03Z`. **This is not an anomaly to
  note once — it is DETERMINISTIC, and it fires every night for the two hours
  between local midnight and UTC midnight.** Any session running in that window
  and trusting the ambient date stamps everything a full day ahead, in the
  direction that looks newest, so a reader sorting by date puts it after work
  that actually followed it. Every stamp in this session was taken from `date -u`
  and reads 2026-07-31, which the check above confirms is correct. **The rule is
  cheap and absolute: never take the date from the harness — take it from
  `date -u` or `datetime.now(timezone.utc)`, every time.**

### STALE CLAIMS ABOVE THE SEPARATOR — reported, NOT fixed, not mine to fix

**This heading said "FOUR" until 2026-08-01, when a fifth was found and the
number did not move on its own.** It is now a list rather than a count, for the
reason this thread has already written down twice: a total drifts on every
addition and a property does not. The correction-count gate (#440) exists for
exactly this failure, and it does not reach this heading.

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
| 5 | ~114 | prior art at `livespec-dev-tooling` `plan/worktree-location-enforcement/supervisor-handoff.md` | **ARCHIVED** (`968c8b7`) — intact at `plan/archive/worktree-location-enforcement/…`; insert `archive/`. Found 2026-08-01; see "EVERY CITATION IN THIS FILE, CHECKED MECHANICALLY" |

**On (3)** — it conflates a total with a property, so no single number fixes it.
The four that drive real tmux are `test_repo_containment_discriminates`,
`test_supervisor_liveness_discriminates` and `test_watcher_wake_discriminates`
(shared fixture) plus `test_emitted_commands_discriminate` (its own rig).
`test_charter_boot_and_ledger_commands` and `test_cold_open_generation_gate`
deliberately STUB tmux, and a stub is not a drive;
`test_generated_supervisor_handoff_contract` is inspection-only (0 subprocess
calls).

**DO NOT ADOPT A BARE NUMBER HERE — the suggestion I first wrote was stale on
arrival.** It read "twelve modules, four of which drive real tmux", and this
session's own PRs (#441, #445) take `tests/prompts/` to **fourteen** the moment
they land. The tmux figure is the stable half: both new modules are static
scanners driving none, so **four** still holds. That is the whole lesson of the
correction-count gate one section down, arriving unprompted in the very
paragraph proposing a fix: **a total drifts on every addition, a property does
not.** Suggested instead, and phrased so it cannot rot: *"`tests/prompts/`
carries several modules, four of which drive real tmux"* — or, if a total is
genuinely wanted, gate it the way the correction counts now are, because nothing
reads this one.

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

### WHAT `overseer-jdo` IS MISSING — measured 2026-07-31T14:40Z, and it is the two NEWEST findings

**The single most useful thing in this file may be invisible to the person who
will act on it.** jcw is closed; `overseer-jdo` (P1, open) is the live home. Its
notes are 32,100 characters and genuinely well kept — the close reason's claim
that jcw's evidence was folded in FIRST and read back is TRUE, verified by
reading jdo rather than trusting the reason. jdo carries mechanism 1 in full (the
socket, `tmp_path.name`, PR #418, the `test_rig_sockets_are_run_unique` gate),
SIGHTING 3 and SIGHTING 4, the retirement of jcw's three guessed causes, and
mechanism 2's CONCLUSION that the fix is a contract choice.

**What it does not carry is everything this thread learned after 03:14Z.** jdo
was last updated **2026-07-31T03:14:09Z**. The severity correction in this file is
stamped **03:43Z** (29 minutes later) and the costing **04:50Z** (96 minutes
later). The fold-in was diligent; it simply happened first.

| missing from jdo | measured | why it changes what a fixer does |
|---|---|---|
| the **03:43Z severity correction** | jdo's mechanism-2 note still reads "0 of 8 alone, 0 of 8 under light paired load, 2 of 8 under two FULL concurrent suites" | It frames mechanism 2 as needing a CONTRIVED DOUBLE LOAD. The correction overturns exactly that: it fires in the **ordinary `just check` aggregate with no external load**, caught on a pre-push on `[gw3]` minutes after a foreground run of the identical tree passed 65/65. A P1 reader triages "reproduce it by running two suites at once" instead of "run the gate normally". |
| the **04:50Z arithmetic and option table** | zero occurrences of `_POLLS`, `_STABLE_TO_IDLE` or "starv" anywhere in jdo's 32,100 chars | jdo says the fix is a contract choice but not WHICH alternatives are already dead. The arithmetic (`_POLLS=4`, `_STABLE_TO_IDLE=3`, `stable` resets on any change ⇒ ~450ms unchanging pane ⇒ ~9 missed 50ms ticks) proves **"tick faster" CANNOT work** — a descheduled process does not tick at any rate — and records **"reduce parallelism" as a LEVER ALREADY SPENT** (`test_nprocs` is deliberately 25% of cores and it fires anyway). Those are the first two instincts, and both would look like a fix until they flaked again. |

**Nothing was written to the ledger.** Folding these into jdo is a ledger write
and jdo belongs to another track; both are outside this thread's lane. This is a
REPORT. The supervisor decides whether jdo absorbs it.

**The general shape, because it will recur:** an item can be superseded *between*
your diagnosis and your write-up, and a fold-in is a SNAPSHOT — it captures the
record as of the close, not as of the last thing you learn. When work migrates to
another id, the newest findings are the ones most likely to be stranded, because
they are the ones written after everybody stopped looking.

### This session's gate: a correction count that cannot rot silently

`tests/test_charter_correction_counts_are_current.py` — **PR #440, OPEN and NOT
YET MERGED.** This file said "**Prefer a rule that recounts over a number that
ages**... Nothing gates this — the count sits in prose that no test reads." That
stops being true when #440 lands, not before: **the rule recounts only once the
PR is merged, and on master today nothing still reads this count.** (Re-tensed
2026-08-01. It read as though the gate were already in force, while the same file
says five PRs are deliberately open — the two statements could not both be true,
and a fresh clone has neither the module nor the protection.)

It compares the counts asserted in this handoff against the entries actually
present in both charter layers, plus contiguity from 1 (an append that reuses or
skips a number would satisfy a length check alone). Measured when written: **19
role-level entries C1–C19, 1 thread-specific entry T1** — both agreeing with the
prose. Keyed on the ENTRY form `^- **C<n>`, never on a MENTION: the protocol
carries an indented `**C14 IS NOW DEMONSTRATED**` note and this handoff discusses
C19 by name, so a rule anchored to any `C<n>` at line start reports **21** where
the truth is 19 — wrong in the direction that looks like MORE evidence. Matched
over whitespace-COLLAPSED prose, because the count and the noun it counts sit on
opposite sides of a line break.

**Seven sabotages, each RED, each asserting the defect existed BEFORE the verdict
was read** (stated count 19→16; stated range end C19→C18; append C20; renumber
C19→C21; append T2; delete the counting sentence; relax the entry pattern to
match mentions). All files restored from BYTE COPIES and verified byte-identical,
never `git checkout --`.

**That sentence said "Six" until the last edit of this session, and the drift is
worth more than the gate.** A seventh sabotage was added, the module was
reformatted, and the number describing them did not move — the *exact* mechanism
this module exists to stop, inside the paragraph announcing it, within one
session. It was caught only because the sabotage suite was RE-RUN after the
module changed rather than trusted from the earlier run. **Evidence produced
against an artifact you then edit is stale evidence.**

**Line counts are deliberately NOT gated**, and the omission is the point: they
change on every edit to either file, so gating them would redden unrelated work
and train the reflex of editing a number until the gate goes green. A correction
count changes only on append.

**Appending C20 will redden this.** That is correct — update the one sentence in
this file that states the count. Do not relax the rule.

### THE ELEVEN DETECTORS DO NOT ALL MEAN THE SAME THING BY "CLEAN" — measured 2026-07-31T15:30Z

**SEVEN are line-scoped; FOUR are document-scoped**, and nothing said so until
now. Measured by injecting each defect into every real charter in this repo (8
charters, in memory, read-only, using the shipped module):

| classes | fired in |
|---|---|
| (a) (b) (c) (d) (f) (g) (k) | **8 of 8** |
| (i) (j) | 7 of 8 |
| (h) | 6 of 8 |
| (e) | **3 of 8** |

**No detector is blind** — every one fires on its own defect in isolation, which
is the control that makes the rest of this readable. The four that fire less
often are DOCUMENT-scoped: they return nothing once the correct property appears
anywhere in the file's fenced blocks, however many defective lines sit beside it.
That is DELIBERATE, and each of the four docstrings argues for it: the correct
form is a helper detected once and called later by name, so a per-line rule would
flag the correct call site. **This is not a bug report.** Three consequences of it
were simply written down nowhere:

1. **A charter absorbs NEW defects of a document-scoped class once it holds the
   correct form once.** A genuinely wrapper-less `bd` call added to
   `.ai/supervisor-protocol.md` — **half of every deployed charter** — produces
   no finding at all, because a wrapper already appears elsewhere in it.
2. **The hardened exemplar masks four of the eleven classes**, and is the ONLY
   charter masking (i) and (j). So `test_the_hardened_exemplar_is_clean` cannot
   fire for those four however broken they become. That control proves the
   detectors do not FALSE-POSITIVE; it can never prove they still fire. The most
   thoroughly hardened file is the most immunised one, precisely BECAUSE it
   demonstrates every correct form.
3. **A count of a document-scoped class counts FILES LACKING A PROPERTY, not
   defective lines.** For (e), (h), (i) and (j) that number is not a line count
   and does not mean what the other seven classes' numbers mean.

**AND ITS MAGNITUDE, BECAUSE THE POINT ABOVE OVERSTATES ITSELF WITHOUT ONE.**
Re-measured fleet-wide 2026-07-31T15:50Z: the four document-scoped classes
contribute **5 of 117 (4%)**, and only **2, 1, 1 and 6 of 29** fleet charters
are immune to (h), (i), (j) and (e) respectively. So the distinction is
architecturally real and numerically minor. **It does NOT move `overseer-yho.3`'s
costing** — class (a) alone is still 92 of 117 (79%) and the remediation shape is
unchanged. Recorded with its size so nobody re-opens a settled measurement over
a 4% effect.

**That run also RE-VERIFIED the fleet numbers independently**, which is worth
more than the new finding: 29 charters, **117** defects, 12 dirty, per-repo
56 / 23 / 18 / 15 / 5 with this repo at **0** — every figure identical to the
2026-07-30 19:40Z table below, reproduced from a separate invocation of the
shipped module. The recorded costing input is sound.

**THE RISK IS LATENT, NOT LIVE — measure before you go hunting.** Each masked
class has EXACTLY ONE instance in the file that masks it, and in every case the
correct property genuinely applies to that instance: the two `bd` invocations in
`.ai/supervisor-protocol.md` and in the exemplar are the documented-correct
`ledger_show()` shape (wrapper call plus the bare fallback an adopter without a
wrapper needs), and the exemplar's single (i) read carries its truncation notice
and its single (j) test its non-empty guard. **Nothing is hidden today.** The
exposure begins the moment a file already holding the property gains a SECOND
instance that is defective — that one arrives unreported. Stated this way round
deliberately: read as "there are hidden defects", this would send the next
session hunting for something that is not there.

**Written as `tests/prompts/test_detector_scope_is_declared.py`, PR #441 — OPEN,
NOT YET MERGED** (re-tensed 2026-08-01; it said "Landed as", and the file is not
on master, so a fresh clone looking for it finds nothing). Its
load-bearing assertion is registry COVERAGE: a twelfth detector cannot land
without declaring its scope in writing — the decision that was never made
explicitly for the first eleven. Five sabotages, each RED against its own test.

**Why a registry rather than another pair of cases.** This generalises
`test_remediating_f_does_not_disarm_e`, which pins the ONE pair caught disarming.
The deeper lesson is that **a synthetic control cannot see a reach problem,
because it supplies the surrounding context itself** — which is exactly how (e)
stayed green while going blind on real charters. Every control in the charter
gate is synthetic, so this class of failure was invisible to all of them.

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

**THAT INVENTORY WAS INCOMPLETE — audited 2026-07-31T17:05Z, and the answer is
reassuring.** The directory holds ELEVEN files plus `evidence/` and
`pending-ledger-edits/`; the list above names six. An incomplete inventory of
"what evaporates" is the one place an omission is invisible by construction, so
each unlisted item was opened and read:

| unlisted | state |
|---|---|
| `pending-ledger-edits/` (4 files) | **APPLIED 2026-07-28, and RE-VERIFIED TODAY by reading both items back**: `overseer-t7qqik` carries "IS NOW 5 OF 6" and `overseer-f2lqj6` carries "HAD NO DRIVER". Both closed. Audit trail only — **do not re-apply**, it would duplicate the block. |
| `NEW-VALVE-tmux-in-ci.md` | **CLOSED.** Maintainer chose the base image. Verified from the ARTIFACT, not the ledger: tmux is in `livespec-dev-tooling/docker/fabro-sandbox/base/Dockerfile:77-80`, carrying the valve's own rationale in its comment. (The cited ledger id is in another tenant and is NOT readable through this repo's wrapper — the Dockerfile is the better evidence anyway.) |
| `LIVE-EXPOSURE-rop-sweep.md` | Self-corrected within the hour; historical. |
| `REVISED-S1-S2-acceptance.md` | S1 and S2 both closed; superseded. |
| `groom-decision-packet.md` | The groom that produced the filed slices; historical. |

**So nothing undelivered is sitting in the gitignored tree.** Every unlisted file
carries an explicit resolved banner at its top, which is why the omission cost
nothing this time — and is also the only reason it was cheap to check. Recorded
rather than merely fixed, because the next reader needs the CONCLUSION ("nothing
was lost"), not a longer list they would have to re-audit themselves.
