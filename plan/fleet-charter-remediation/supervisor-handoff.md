# Supervisor Handoff - fleet-charter-remediation

## Shared Protocol

Read `.ai/supervisor-protocol.md` before driving. Validate this binder together
with that shared layer; this binder is intentionally thin and is not complete by
itself.

Regenerating this file MUST preserve two Corrections sections byte-for-byte:

- `.ai/supervisor-protocol.md` `## Corrections` for role-level corrections.
- This file's `## Corrections` for thread-specific corrections.

Preserve spelling, punctuation, code formatting, blank lines, and ordering
exactly; do not normalize markdown or code spans. A presence check is not enough
— a prior live regeneration silently reformatted a correction by turning a bare
identifier into a code span, and that would have passed a substring check.

Live thread status is NOT in this file. It lives in the ledger, in `handoff.md`,
and in `$supervisor_marker`. Read those first on a cold open — **all three**. On
2026-07-30 a supervisor on a sibling thread read two of the three, skipped
`handoff.md`, and the skipped file held the exact hazard that made it publish a
false accusation against the worker's own work. That is role-level correction
**C19**. On THIS thread `handoff.md` is the more dangerous omission of the
three, because it is the only record carrying the maintainer's already-decided
scope cut — and the standing temptation here is to re-derive that cut.

```sh
test -f ".ai/supervisor-protocol.md" \
  || { echo "HALT: missing shared supervisor protocol .ai/supervisor-protocol.md"; echo "REMEDY: regenerate the two-layer supervisor handoff before driving"; exit 1; }
printf '%s\n' "BOOT: read .ai/supervisor-protocol.md, this binder, and the supervisor marker if it exists"
[ -n "${supervisor_marker:-}" ] \
  || { echo "HALT: supervisor_marker is unset or empty"; echo "REMEDY: resolve it from the Bindings table below before running this block — an unset marker makes the read display NOTHING and still exit 0"; exit 1; }
if [ ! -f "$supervisor_marker" ]; then
  printf '%s\n' "NOTE: no supervisor marker at $supervisor_marker yet — nothing to read."
else
  marker_lines=$(wc -l < "$supervisor_marker")
  if [ "$marker_lines" -le 400 ]; then
    cat "$supervisor_marker"
  else
    sed -n '1,160p' "$supervisor_marker"
    printf '\n*** TRUNCATED: lines 161-%d of %d NOT SHOWN (%d hidden). A claim above may be RETRACTED in the hidden range. Read %s in full before acting on anything above. ***\n\n' \
      "$((marker_lines - 160))" "$marker_lines" "$((marker_lines - 320))" "$supervisor_marker"
    sed -n "$((marker_lines - 159)),${marker_lines}p" "$supervisor_marker"
  fi
fi
```

The read is WHOLE-FILE up to 400 lines and head-and-tail beyond, and the
truncation notice is MANDATORY whenever anything is hidden. A constant cap is
stale tomorrow — a sibling thread's marker went 528 lines, then 697 within hours,
so no constant survives an append-only file. And truncation SEVERS RETRACTIONS
FROM CLAIMS: that marker carried an `OPEN OBLIGATIONS` block assigning
`holder: worker` inside the visible window while its retraction sat below the
cut, so a cold-open reader was handed a discharged obligation as live work.
Silently showing less is not the harm; manufacturing a false assignment is.
Corrections land at the END of an append-only file, which makes a head-only read
the worst possible cut.

**As of 2026-08-02T23:47Z there is no marker at that path and no `runtime_dir`
on disk.** The block above reports that as a NOTE and continues, which is
correct: absence at first boot is not a failure. Create the marker as soon as
you hold your first obligation — the shared layer's `## Obligation record`
section owns its schema. On this thread the first obligation arrives EARLY and
from OUTSIDE this repo: a cross-repo notice sent to another track's live session
is an obligation with a `waiting_on` and no automatic wake.

## Bindings

Resolve and REPORT these before driving anything. Startup bindings only — no
live status, no next actions, and no date-gated behavior.

| Binding | Value |
|---|---|
| `repo_primary` | `/data/projects/livespec-overseer` |
| `thread_dir` | `plan/fleet-charter-remediation/` |
| `topic` | `fleet-charter-remediation` |
| `worker_session` | `fleet-charter-remediation` |
| `supervisor_session` | `fleet-charter-remediation-supervisor` |
| `WORKER_TARGET` | `'=fleet-charter-remediation:'` |
| `SUPERVISOR_TARGET` | `'=fleet-charter-remediation-supervisor:'` |
| `runtime_dir` | `<repo_primary>/tmp/overseer/fleet-charter-remediation/` |
| `supervisor_marker` | `<runtime_dir>/.supervisor-state` |
| `wait_channel` | `<runtime_dir>/worker-status.log` |
| `ledger_anchor` | `overseer-yho.3` |

Placeholder classes declared by this binder:

- Concretely bound: `repo_primary`, `thread_dir`, `topic`, `worker_session`,
  `supervisor_session`, `WORKER_TARGET`, `SUPERVISOR_TARGET`, `ledger_anchor`.
- Composed bindings resolved to a fixed point: `runtime_dir`,
  `supervisor_marker`, `wait_channel`.
- Runtime slots intentionally left for later commands: `<condition-command>`,
  `<short-slug>`, `<branch>`.
- Illustrative placeholders appear only in prose that discusses a form, not in
  fenced commands.

The session names are the BARE topic and the topic plus `-supervisor`, per the
ratified `SPECIFICATION/spec.md` "Session-name derivation" rule: repo-qualified
names are for a genuine cross-repository topic collision, and this topic has
none.

**`ledger_anchor` is `overseer-yho.3`, NOT `overseer-c45`, and that is
deliberate.** Both items live on this thread and both are children of
`overseer-yho`, but `handoff.md` declares only `overseer-yho.3`, and
`tests/test_plan_thread_records_agree.py` requires this binding to equal the
LAST anchor its handoff declares. Re-measure `overseer-c45` by id — the
Verification Discipline block below takes an id argument for exactly that
reason — and do not re-point this binding to reach it.

## Generator provenance

This charter was produced from the generator prose whose digest is recorded
below. Run this before driving: a charter emitted from a stale plugin cache
carries defects the current generator no longer emits, and until this record
existed nothing about a charter said which generation produced it.

The DIGEST is the identity. The plugin, ref and version are companions for a
human reader — six releases shipped byte-identical prose, so a version would
report six generators where there is one, and the ref directory name is
sometimes a commit sha and sometimes a version string.

```sh
generator_plugin='livespec-overseer'
generator_ref='c530c70860d8'
generator_version='0.16.0'
generator_prose_md5='eaebe06065b3efa0053d6ea5932d52c0'
cache_root="$HOME/.claude/plugins/cache/$generator_plugin/$generator_plugin"
generator_prose="$cache_root/$generator_ref/prose/supervise-plan.md"
if [ ! -d "$cache_root" ]; then
  printf '%s\n' "UNVERIFIED: no plugin cache at $cache_root, so this is not a host that generates charters and provenance cannot be checked here. Recorded generator: $generator_prose_md5"
elif [ ! -f "$generator_prose" ]; then
  echo "HALT: the cache at $cache_root no longer holds ref $generator_ref, so the generator that emitted this charter has been replaced"
  echo "REMEDY: regenerate this charter with supervise-plan, or re-point generator_ref at the installed ref and re-stamp generator_prose_md5 from it"
  exit 1
else
  installed=$(md5sum "$generator_prose")
  digest_rc=$?
  [ "$digest_rc" -eq 0 ] \
    || { echo "HALT: cannot digest the installed generator prose at $generator_prose"; echo "REMEDY: fix read access before trusting anything this charter says about its own currency"; exit 1; }
  installed_md5=${installed%% *}
  [ "$installed_md5" = "$generator_prose_md5" ] \
    || { echo "HALT: this charter was emitted by generator $generator_prose_md5 but the installed generator is $installed_md5"; echo "REMEDY: regenerate this charter before driving, or re-stamp generator_prose_md5 deliberately after reading what changed between the two"; exit 1; }
  printf '%s\n' "PASS: charter provenance matches the installed generator ($installed_md5)"
fi
```

**Measured 2026-08-02T23:46Z: the cached generator prose and this repo's own
`.claude-plugin/prose/supervise-plan.md` are byte-identical
(`eaebe06065b3efa0053d6ea5932d52c0` both ways), so this charter PASSES its own
provenance check on this host.** A HALT here is therefore a real signal. The
hardened exemplar in this repo carries a valve saying its provenance check WILL
halt because the repo was ahead of the released plugin; that condition cleared
with the `0.16.0` release and it does NOT cover this file.

A MISSING CACHE ROOT AND A MISSING REF ARE DIFFERENT CONDITIONS. No cache root
at all means this is not a charter-generating host — a CI runner, or another
checkout — so provenance is UNVERIFIED and the check continues; HALTing there
would make this file unreadable anywhere but the machine that produced it. A
cache root that no longer holds the recorded ref means the generator has been
REPLACED, which is exactly how a refresh shows up, and that HALTs.

## Thread-specific Valves

Every claim below is a measurement with a timestamp. Re-measure before carrying
any of it forward — that is the shared layer's first rule and this section is
not exempt from it. On THIS thread that rule has teeth the others lack: the
thread's entire subject is a NUMBER, and the number moved between the handoff's
reading and this charter's.

- **THE CORPUS IS 120, NOT THE 117 THE HANDOFF RECORDS. Re-measured
  2026-08-03T00:02:31Z** by importing the shipped module
  (`tests/prompts/test_charters_carry_no_known_defects.py`) and calling
  `defects_in`, never a grep, over the same three globs the gate itself uses:

  | repo | charters | defects |
  |---|---|---|
  | `livespec-orchestrator-beads-fabro` | 6 | **56** |
  | `homelab` | 7 | 26 |
  | `livespec-dev-tooling` | 5 | 18 |
  | `livespec-console-beads-fabro` | 1 | 15 |
  | `livespec` | 6 | 5 |
  | `livespec-overseer` | 9 | **0** |
  | **total** | **34** | **120** |

  By class: (a) 95, (c) 7, (d) 7, (b) 5, (f) 2, (e) 1, (h) 1, (i) 1, (j) 1,
  (g) 0, (k) 0, (l) 0.
- **THE NUMBER DRIFTS ON TWO INDEPENDENT AXES, AND BOTH MOVED DURING THIS
  CHARTER'S OWN GENERATION.** Do not conflate them.
  - **The CORPUS drifts.** Fifteen minutes earlier the same call returned
    **124**, and two days earlier the handoff recorded **117** over 29 charters.
    Live threads keep generating charters, so the denominator grows on its own.
  - **The GATE drifts too, and that is the axis nobody was watching.** The 124
    was scored by an ELEVEN-detector set. While this charter was being written,
    detector (h) was parameterised off its hardcoded wrapper name and detector
    (l) was added, so the current set is TWELVE. The (h) fix alone removed four
    FALSE POSITIVES, all in `homelab` (30 → 26), and took (h) from 5 to 1
    fleet-wide. **So 124 → 120 is not four defects being fixed; it is four
    defects that were never there.** A count is meaningless without naming the
    detector set that produced it — always say which, as this bullet does.
- **DETECTOR (l) SCORES ZERO FLEET-WIDE AND THAT ZERO IS CONTROLLED.** Injecting
  the historic defective busy test into a REAL fleet charter in memory makes (l)
  fire once; the corrected `rop-railway-enforcement` charter scores 0; a re-read
  from disk afterwards still scores 0, so nothing leaked. Reported as absence
  only because the query was first proven able to produce a positive.
- **PHASE 1 IS UNCHANGED BY EITHER DRIFT, WHICH IS WHY THE CUT SURVIVES.**
  `livespec-orchestrator-beads-fabro` is still **56**, still 5 of its 6
  charters, under both detector sets. What changed is the REMAINDER: after
  phase 1 the fleet holds **64** across 4 repos, not the 61 the handoff states.
  Say 64, re-measured, with the detector set named, when you report what remains.
- **THE SCOPE IS DECIDED. DO NOT RE-OPEN IT.** Phased,
  `livespec-orchestrator-beads-fabro` first — the maintainer's cut, recorded in
  `handoff.md`. Re-deriving it is the single most likely way this thread wastes a
  session, because the measurement is interesting and the cut looks re-litigable
  every time the number moves. It is not.
- **THE ONE-LINE SHARED-LAYER EDIT IS REAL, BUT ITS LEVERAGE CLAIM IS FALSE AND
  `handoff.md` STATES THE FALSE VERSION.** `livespec-orchestrator-beads-fabro/
  .ai/supervisor-protocol.md` uses a worker-target variable ten times and never
  binds it; adding the binding line this repo already ships takes that file
  **10 → 0**, confirmed still 10 at 2026-08-03T00:02Z. What is NOT true is that
  a shared-layer fix therefore reaches every thread in that repo. Measured with
  a positive control: **only 1 of that repo's 5 charters
  (`plan/beads-v1-1-2-upgrade/`) references the shared layer at all.** The other
  four — including all three archived ones, which hold 43 of the 56 — reference
  it ZERO times. They are pre-layering MONOLITHS and inherit nothing. Positive
  control for the probe: the same search against
  `livespec-overseer/plan/daemon-liveness-truth/supervisor-handoff.md` returns
  7, so a zero here is a real zero and not a broken query. **So the one line is
  10 of 56 (18%), not 48% of the fleet, and it reaches exactly ONE downstream
  charter by reference.** The cut is unaffected — all five files still need
  editing — but do not repeat the leverage sentence. **Credit where it is due:
  `retire-host-dispatch-cap-supervisor` spotted this from inside the other repo
  and deliberately WITHHELD it because this thread's cross-repo notice asked for
  objections only.** A notice that invites only objections will not surface a
  correction; word the next one to invite both.
- **THIS BINDER IS ITSELF INSIDE THE CORPUS IT REMEDIATES.** `plan/*/
  supervisor-handoff.md` is one of the gate's three globs, so every edit to this
  file is scored by the same eleven detectors, in this repo's own CI, at
  `just check`. The repo's zero is not a historical fact to preserve by care —
  it is enforced, and a careless edit here turns the remediation thread into the
  thing being remediated.
- **IT TOUCHES ANOTHER TRACK'S REPO. TELL THAT TRACK BEFORE CHANGING ANYTHING.**
  A charter whose worker and supervisor sessions are both live is **ARMED**: the
  defect is dormant and fires when a session exits and the charter is next read
  cold. Check for live sessions and send a notice first. The shared layer's
  `## FILE cross-repo freely; never ADMIT or PRIORITISE in another repo's queue`
  rule governs what you may do there — filing is free, admitting is not.
- **CONFIRMING THAT NOTICE BY GREPPING THE PANE FOR ITS TEXT CANNOT WORK**
  (role-level correction **C21**). Claude Code renders a multi-line paste as a
  bracketed `Pasted text` placeholder and a single-line paste inline, so a
  content grep returns zero on a paste that landed perfectly. Confirm by the
  placeholder OR a non-empty prompt line, accept either shape, and **re-capture
  rather than re-sending** — the render lags after both `paste-buffer` and
  `Enter`. This is called out here and not left to the shared layer because
  cross-repo notices are this thread's characteristic action, so C21 is the
  correction this thread is most likely to re-earn.
- **ON COMPLETION, STATE WHAT REMAINS.** Phase 1 leaves 68 defects across 4
  repos untouched (re-measured; the handoff says 61 against the older corpus).
  Saying "the fleet is clean" after phase 1 would be false. Say the number, and
  say when it was measured.
- **DETECTOR (h) HARDCODES ONE WRAPPER NAME and therefore lies about
  `homelab`.** It keys on `with-livespec-env.sh`, so `homelab`'s correct
  `with-homelab-env.sh -- bd show` scores as a defect. That is a FALSE POSITIVE
  in the fleet total, and it fails quietly and in the wrong direction — toward
  overstating exposure. **Parameterising the wrapper name is a precondition for
  ever pointing this gate at `homelab`**; remediating homelab's charters to
  satisfy the detector as written would be corrupting a correct file to please a
  broken check, which is the inverse of this thread's job.
- **THE REMEDY IS SAFE ON EVERY TMUX SUBCOMMAND THE FLEET'S CHARTERS USE.** The
  most plausible way the rewrite could be wrong was that some subcommand rejects
  the exact-match form — and this repo's own `AGENTS.md` once asserted exactly
  that about `respawn-pane`, the one destructive operation. Measured on a
  private socket: false. The exact form **with the trailing colon** works on
  `respawn-pane`, `capture-pane`, `list-panes`, `send-keys`, `paste-buffer` and
  `has-session`. Only the form without the colon fails. Corrected in PR #456.
- **THE HONEST LIMIT OF THE MECHANICAL SWEEP, STATED.** A deliberately stupid
  in-memory rewrite re-scored by the shipped gate took the older corpus 117 → 25,
  clearing all of class (a); a control re-scan afterwards still reported 117, so
  nothing leaked to disk. That proves the corpus is mechanically CLEARABLE PER
  THE GATE, not mechanically CORRECT. **A human reads the diff.** The claim is
  that the diff is uniform and readable, not that review is unnecessary. Do not
  let a green gate stand in for that reading.
- **51 of the older 117 (44%) SAT IN `plan/archive/`, WHICH NEVER REGENERATES.**
  So "accept it and let instances decay" cannot reach nearly half the exposure —
  that option is already foreclosed by measurement, not by preference.
- **`homelab` CONSUMES NO PIN** (Rust/Nix — no `pyproject.toml`, no `justfile`,
  no `.mise.toml`), so adopting the gate per repo reaches only part of the fleet.
  The measurement points at a **3-for-pin-consumers + 1-for-homelab** shape that
  none of the four originally-costed options describes. Do not re-cost those
  four; cost this shape.
- **FOUR OF THE ELEVEN DETECTORS ARE DOCUMENT-SCOPED** ((e), (h), (i), (j)):
  they return nothing once the correct property appears anywhere in a file's
  fenced blocks. A count for those classes counts FILES LACKING A PROPERTY, not
  defective lines. Fleet-wide they are 7 of 124 — architecturally real,
  numerically minor, and it does not move the costing.
- **THE DETECTORS ARE CALIBRATED TO CHARTERS AND DO NOT GENERALISE.** Pointed at
  arbitrary fleet markdown they returned 368, of which the overwhelming majority
  were false — a mermaid node label trips (h), and one label became 13 findings.
  **Do not widen the corpus.** The three globs are the corpus.
- **`overseer-c45` DOES NOT RE-OPEN THE PHASE-1 CUT.** It is a SECOND item
  sharing this thread, not an addition to that slice, and not a precondition for
  it. Its two asks are a `tests/prompts/` detector requiring a generated
  charter's watcher idle-exit to rest on pane stability ALONE, and a membership
  question about whether the offending charter's divergent watcher is inside
  this thread's sweep. **The membership ask is cheap and worth discharging
  first** — if that watcher was session-improvised rather than written into a
  charter file, it is outside the corpus and the sweep does not cover it.
- **`overseer-c45` IS CORRECTLY ROUTED HERE AND NOT TO `daemon-liveness-truth`.**
  The symptom — a pane whose reported state diverges from reality — matches that
  thread's family, and an archived charter suggested it on that basis. Measured
  against the item's own text, both asks are charter-generator work; it names no
  daemon module and states the daemon reports TRUTHFULLY. Maintainer-decided
  2026-08-02, rationale recorded as a note on the item. Do not re-route it.
- **`overseer-yho` CLOSES WHEN THIS THREAD FINISHES AND NOT BEFORE.** Both of
  that epic's open children — `overseer-yho.3` and `overseer-c45` — now live
  here. It is open because work is open under it, not by oversight. Measured
  2026-08-02T23:45:35Z: all three are `backlog` and unassigned.
- **THE WORKER IS RUNNING UNDER A STANDING AUTONOMY INSTRUCTION — CHECK IT
  BEFORE YOU ESCALATE.** Observed 2026-08-02T23:44Z: the maintainer directed
  this track to proceed autonomously through all phases including final
  implementation, archive, and fleet-wide deployment; to avoid obvious
  questions; and to route genuine uncertainty to a Codex subsession first to
  test whether the answer is obvious enough to continue on. **That resolves the
  one valve `handoff.md` leaves open** — its "moving it onward is the
  maintainer's valve, not a supervisor's" was written before that instruction,
  and the instruction is the maintainer exercising that valve. It does **not**
  lower the shared layer's escalation boundary — never REMOVE, WEAKEN or SKIP an
  existing check — which is a property of the change and is not delegable to a
  subsession.
- **A LITERAL DOUBLE-BRACE INTERPOLATION TOKEN IN A WORK-ITEM'S TEXT MAKES THE
  ITEM UNDISPATCHABLE.** `drive.py` interpolates item text into fabro's templated
  `goal`, so the token parses as a fabro template variable, finds no binding, and
  the graph is rejected before any agent runs — leaving a PHANTOM
  `active`/`fabro` claim with no run behind it. `fabro ps` is the evidence,
  never `ACTIVE`. **This thread is unusually exposed to it**, because quoting a
  recipe as evidence is routine here and every such recipe variable has that
  shape. Measured 2026-08-02: `overseer-yho.3` is clean. Describe such a
  construct in words; never write it literally. Do NOT fix it by editing the work
  item — that corrupts the item's own evidence and hides a recurring defect
  (`bd-ib-vv9y`, P1, orchestrator tenant).
- **`just worktree-create` IS EFFECTIVELY BROKEN IN THIS REPO AND FAILS
  SILENTLY.** `dev-tooling/worktree-lib.sh:89` pipes `git worktree list
  --porcelain` into an `awk` that exits on first match, closing the pipe while
  git is still writing; git takes SIGPIPE, `pipefail` propagates 141, and
  `set -e` aborts before any output. **Re-measured for this charter
  2026-08-02T23:46Z at 82 worktrees: still exit 141.** The fix is one line in
  `livespec-dev-tooling`'s package source (`livespec-dev-tooling-zi4q`); never
  hand-edit the gitignored `dev-tooling/` copy. **THE RESCUE PATH, used to
  produce this charter:** `git worktree add <path> -b <branch>` then
  `just install-worktree-pack` inside it. That pack install writes a
  `worktree_discipline` key into the TRACKED `.livespec.jsonc`; it only makes the
  existing default explicit, so `git checkout --` it unless you mean to land it.
- **THIS THREAD WORKS IN FIVE OTHER REPOS AND EACH OWNS ITS OWN DISCIPLINE.**
  Read the target repo's `AGENTS.md` or `CLAUDE.md` and its visible command
  surface before editing there. Do not carry this repo's PR flow into another
  repo, and never touch another session's worktrees or branches.
- **A CHANGE TO ANY FILE UNDER `overseer/` REQUIRES A PAIRED CHANGE UNDER
  `tests/**`** (`commit_pairs_source_and_test`). The beside-tests in `overseer/`
  are themselves SOURCE to that check, so a beside-test alone does not satisfy
  it. `tests/conftest.py` puts `overseer/` on `sys.path`, so a module moves to
  `tests/` verbatim with no import changes. `overseer-c45`'s first ask lands in
  `tests/prompts/` and is therefore outside this pairing, but its detector must
  still ship with a RED demonstration and a discrimination leg, which is that
  directory's own standard.
- **`just check` PASSING LOCALLY IS NOT EVIDENCE ABOUT THE TREE YOU PUSHED.**
  The pre-push hook skips the aggregate on a green-token match keyed to the
  tree, so after MOVING or RENAMING a file the previous green describes a tree
  that no longer exists. Re-run `just check` after any move or rename, before
  pushing.
- **`date -u -r <file>` DOES NOT APPLY `-u` ON THIS HOST.** It runs uutils
  coreutils, not GNU: the command prints LOCAL time, and local is ahead of UTC,
  so a `Z` appended to it is a silent lie. Derive any mtime that will enter a
  published claim through `datetime.fromtimestamp(ts, timezone.utc)`. This is
  role-level correction **C19**. Detector `(k)` gates the form in fenced charter
  code, which is why the hazard is stated here in prose — and note that (k)
  scores 0 fleet-wide, a zero that was CONTROLLED by injecting the trap in memory
  into a real charter and confirming the same call returned 1.
- **`bd` NEEDS THE FLEET CREDENTIAL WRAPPER HERE** — a bare `bd` returns
  `Access denied` against this repo's tenant. The Verification Discipline block
  below DETECTS it rather than hard-coding a path, so an adopter without a
  wrapper can still re-measure.
- The shared layer `.ai/supervisor-protocol.md` carried role-level corrections
  through **C22** when this charter was generated (2026-08-02T23:47Z). That is a
  count with a timestamp, not a standing fact: the section is append-only, so
  re-read it rather than trusting this number.
  `tests/test_charter_correction_counts_are_current.py` gates count claims for
  the `supervisor-prompt-quality` records ONLY — it does not read this file, so
  nothing will tell you when this sentence goes stale.
- Full narrative state, including corrections to this supervisor's own conduct
  that are not yet role-level, belongs in the supervisor marker at
  `tmp/overseer/fleet-charter-remediation/.supervisor-state`. Read it at boot;
  treat every status line in it as a claim with a timestamp and re-measure.

## Verification Discipline

Re-measure the filed work item from the ledger before carrying forward any status
or acceptance claim from this file, the plan thread, or a marker:

```sh
ledger_anchor='overseer-yho.3'
# `bd` reaches a per-repo TENANT database and needs the fleet credential wrapper
# here; a bare `bd` returns "Access denied". DETECTED, not hard-coded, so an
# adopter without a wrapper can still re-measure.
ledger_show() {
  if command -v with-livespec-env.sh >/dev/null 2>&1; then
    with-livespec-env.sh -- bd show "$1" --json
  else
    bd show "$1" --json
  fi
}
if ! ledger_json="$(ledger_show "$ledger_anchor")"; then
  echo "HALT: cannot re-measure ledger item '$ledger_anchor'"
  if command -v with-livespec-env.sh >/dev/null 2>&1; then
    echo "REMEDY: the credential wrapper WAS used, so ledger access is not the suspect — check the anchor id is real and that this repo's tenant is reachable"
  else
    echo "REMEDY: no credential wrapper on PATH, so a BARE 'bd' ran — install/expose the fleet credential wrapper, or check the anchor id"
  fi
  exit 1
fi
# EXIT STATUS IS NOT EVIDENCE. A tool that exits 0 while printing nothing would
# let the stamp below certify a re-measurement that never happened.
[ -n "$ledger_json" ] \
  || { echo "HALT: ledger re-measure for '$ledger_anchor' exited 0 but returned NOTHING"; echo "REMEDY: do not record this as a measurement — an empty success is not a reading; confirm the anchor exists and that the ledger tool is actually reporting"; exit 1; }
printf '%s\n' "$ledger_json"
date -u '+MEASURED_AT: %Y-%m-%dT%H:%M:%SZ'
```

`ledger_show` takes the id as an argument on purpose: this thread carries TWO
items, and the second (`overseer-c45`) must be re-measured the same way even
though the binding above names only the anchor the handoff declares. Re-measure
`overseer-yho` as well when reporting the epic — its own status field lagged its
children by two closes on a sibling epic in this same tenant, so infer nothing
about children from a parent's field.

**Re-measure the DEFECT COUNT the same way you re-measure the ledger, and by the
same standard: import the shipped module and call it.** A grep is not a
measurement here — the detectors resolve variable bindings across a whole
document, strip trailing comments while respecting quotes, and dedupe two rules
that describe one defect. Every count in this charter came from `defects_in`,
and a count produced any other way is not comparable to them.

When a command's own success is the verdict, capture that status before any pipe
used only to filter or display its output:

```sh
WORKER_TARGET='=fleet-charter-remediation:'
pane_pid=$(tmux display-message -p -t "$WORKER_TARGET" '#{pane_pid}')
tmux_rc=$?
[ "$tmux_rc" -eq 0 ] \
  || { echo "HALT: tmux pane lookup failed for 'fleet-charter-remediation'"; echo "REMEDY: re-check the exact target before filtering its output"; exit 1; }
printf '%s\n' "$pane_pid" | head -1
```

Inspect read-only before driving anything — a bounded scrollback sample plus the
whole visible worker pane:

```sh
WORKER_TARGET='=fleet-charter-remediation:'
tmux capture-pane -p -t "$WORKER_TARGET" -S -40
```

`-S -40` starts 40 lines back in history and then includes the entire visible
pane. It is NOT "the last 40 lines", and its history must never feed the picker
test or the pane diff — a picker that closed minutes ago is still in the buffer.

## HALT-first preconditions

Worker session `fleet-charter-remediation`; supervisor session
`fleet-charter-remediation-supervisor`; target repo
`/data/projects/livespec-overseer`. Verify both sessions AND the live agent
driver in each before doing anything else. Stop on the FIRST failure and act on
the labelled `REMEDY:`. Runtime identity comes from exact live process evidence,
NEVER from a session name — a leftover session named like an agent proves
nothing.

```sh
WORKER_TARGET='=fleet-charter-remediation:'
tmux has-session -t "$WORKER_TARGET" \
  || { echo "HALT: expected worker session 'fleet-charter-remediation'"; echo "REMEDY: ask the maintainer whether to start that worker session"; exit 1; }
pane_pid=$(tmux display-message -p -t "$WORKER_TARGET" '#{pane_pid}')
[ -n "$pane_pid" ] \
  || { echo "HALT: empty pane_pid for 'fleet-charter-remediation'"; echo "REMEDY: re-check the exact worker target and stop if it still resolves empty"; exit 1; }
ps -o pid=,comm=,args= --ppid "$pane_pid" --pid "$pane_pid" -H
# PASS only if a live `claude` or `codex` process appears in that tree.
# A lone shell (zsh/bash) with no agent child is a HALT.
# REMEDY: if no live agent appears, ask the maintainer whether to restart the worker.

SUPERVISOR_TARGET='=fleet-charter-remediation-supervisor:'
tmux has-session -t "$SUPERVISOR_TARGET" \
  || { echo "HALT: expected supervisor session 'fleet-charter-remediation-supervisor'"; echo "REMEDY: switch to the correct supervisor session or ask the maintainer to bootstrap it"; exit 1; }
supervisor_pane_pid=$(tmux display-message -p -t "$SUPERVISOR_TARGET" '#{pane_pid}')
[ -n "$supervisor_pane_pid" ] \
  || { echo "HALT: empty pane_pid for 'fleet-charter-remediation-supervisor'"; echo "REMEDY: re-check the exact supervisor target and stop if it still resolves empty"; exit 1; }
[ "$supervisor_pane_pid" != "$pane_pid" ] \
  || { echo "HALT: supervisor and worker resolve to the SAME pane"; echo "REMEDY: re-check both exact targets — a prefix match puts both names on one pane, and the worker's agent then reads as the supervisor's"; exit 1; }
ps -o pid=,comm=,args= --ppid "$supervisor_pane_pid" --pid "$supervisor_pane_pid" -H
# PASS only if a live `claude` or `codex` process appears in that tree.
# A lone shell (zsh/bash) with no agent child is a HALT.
# REMEDY: if no live agent appears, ask the maintainer to start the agent in that session.

test -d "/data/projects/livespec-overseer/plan/fleet-charter-remediation" \
  || { echo "HALT: missing plan thread /data/projects/livespec-overseer/plan/fleet-charter-remediation"; echo "REMEDY: create or choose the correct plan topic before supervising"; exit 1; }
pane_cwd=$(tmux display-message -p -t "$WORKER_TARGET" '#{pane_current_path}')
[ -n "$pane_cwd" ] \
  || { echo "HALT: empty pane_current_path for 'fleet-charter-remediation'"; echo "REMEDY: re-check the exact worker target and stop if it still resolves empty"; exit 1; }
case "$(readlink -f -- "$pane_cwd")" in
  /data/projects/livespec-overseer|/data/projects/livespec-overseer/*) echo "PASS: $pane_cwd" ;;
  *) echo "HALT: pane cwd $pane_cwd is outside the target repo"; echo "REMEDY: move the worker into the target repo or start the correct worker session"; exit 1 ;;
esac
```

Report which driver was found. The containment check resolves an ABSOLUTE repo
path on purpose: a check rooted at the bare `plan/` directory is cwd-relative
and PASSES while pointed at the wrong repository — which on this thread is not a
hypothetical, since the work itself moves between six repositories. The
non-empty guard runs BEFORE the resolution because `readlink -f ""` returns the
CWD at exit 0 on this host's uutils coreutils, which renders as a `PASS:`
against the repo root — that is role-level correction **C2**.

## Corrections

Thread-specific corrections live here. Regenerating this binder MUST preserve
this section byte-for-byte, from the `## Corrections` heading through the end of
the section. Preserve spelling, punctuation, code formatting, blank lines, and
ordering exactly.

This section was EMPTY at generation (2026-08-02T23:47Z), which was a real state
rather than an omission: no supervisor had yet acted under it. Role-level
corrections C1 onward already apply and live in `.ai/supervisor-protocol.md` —
do not copy them down here. Record a `T<n>` entry when THIS supervisor gets
something wrong on THIS thread, and record it about your own conduct; a section
that logs only the worker's mistakes is a wrong record.

- **T1 (2026-08-03) — I SCORED A REPO AGAINST A BRANCH THAT DOES NOT EXIST, AND
  MY TOOLING REPORTED THE MISSING REF AS A CLEAN FILE.** Verifying the worker's
  `homelab` remediation, I diffed defect counts between `origin/master` and the
  PR branch. **`homelab`'s default branch is `main`.** `git show
  origin/master:<file>` returned an EMPTY STRING, my script scored empty text as
  zero defects, and the result read `0 -> 2` — which says the worker's branch
  ADDED two defects to a clean file. The true reading is `26 -> 2`. I was one
  step from sending that as a finding against a colleague's correct work.
  **This is this thread's own first rule turned back on me:** an empty result is
  not a finding, and I ran no positive control on the BASE ref — only on the
  branch ref, which was readable, which is exactly what made the failure look
  like data. The tell was there and I nearly walked past it: a repo cannot go
  from a clean shared layer to a dirty one in a remediation PR. **Two durable
  fixes, both applied.** Treat an unreadable ref as an ERROR, never as clean
  input — a scoring script must assert its inputs are non-empty before it
  compares them. And resolve a repo's default branch from the forge
  (`gh repo view --json defaultBranchRef`) rather than assuming `master`; this
  fleet has at least one repo on `main`, and the six repos this thread touches
  do not share one convention. Disclosed to the worker in the same turn, before
  it could act on anything I had said.

- **T2 (2026-08-03) — I ANSWERED `overseer-c45`'s MEMBERSHIP QUESTION WRONG, AND
  THE ERROR WAS SCOPE: A STRING IN A FILE IS NOT A CONSTRUCT IN THE CORPUS.** I
  grepped `rop-railway-enforcement`'s charter, found the defective busy regex,
  and reported that the divergent watcher WAS in a charter file — inside the
  corpus by file membership, though not among that file's scored defects. **The
  detectors read FENCED BLOCKS ONLY** (`_code_blocks` discards everything else),
  and every occurrence of that regex — 2 per revision across all 8 revisions
  that carry it — sits in PROSE: a `⛔⛔ IF YOU ADD A BUSY-MARKER REGEX` caution
  and a first-person correction entry. Prose is not in the corpus at all, so the
  sweep could never have reached it for a reason stronger than the one I gave.
  The worker's account — session-improvised, never committed as a watcher, the
  charter's only record being a pure-addition warning — was right.
  **I THEN CONTRADICTED THE WORKER AND WAS WRONG A SECOND TIME IN THE SAME
  CHECK.** Its `+81/-0` detail looked refuted by my `--numstat` read of 39/9;
  that commit touches three files and my `awk` paired the wrong stat row with
  the wrong commit. `+81/-0` is exactly this file's stat in `f93fc8a`. **The
  charter's rule held and I nearly overrode it twice in one turn:** when a
  worker contradicts a supervisor, the supervisor is wrong until the exact
  command has been re-run with a control. Both of my readings were greps I had
  not controlled — the first against the detectors' real scope, the second
  against a multi-file numstat. **Before reporting that a construct is "in the
  corpus", check the SCOPE THE GATE ACTUALLY READS, not the file.**
