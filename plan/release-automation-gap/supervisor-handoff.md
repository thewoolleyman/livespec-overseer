# Supervisor Handoff - release-automation-gap

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
**C19**.

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

**As of 2026-08-02T23:55Z there is no marker at that path and no `runtime_dir`
on disk.** The block above reports that as a NOTE and continues, which is
correct: absence at first boot is not a failure. Create the marker as soon as
you hold your first obligation — the shared layer's `## Obligation record`
section owns its schema.

## Bindings

Resolve and REPORT these before driving anything. Startup bindings only — no
live status, no next actions, and no date-gated behavior.

| Binding | Value |
|---|---|
| `repo_primary` | `/data/projects/livespec-overseer` |
| `thread_dir` | `plan/release-automation-gap/` |
| `topic` | `release-automation-gap` |
| `worker_session` | `release-automation-gap` |
| `supervisor_session` | `release-automation-gap-supervisor` |
| `WORKER_TARGET` | `'=release-automation-gap:'` |
| `SUPERVISOR_TARGET` | `'=release-automation-gap-supervisor:'` |
| `runtime_dir` | `<repo_primary>/tmp/overseer/release-automation-gap/` |
| `supervisor_marker` | `<runtime_dir>/.supervisor-state` |
| `wait_channel` | `<runtime_dir>/worker-status.log` |
| `ledger_anchor` | `overseer-oijk3d` |

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

**THIS THREAD IS THE ONE MOST LIKELY TO INVALIDATE THIS CHECK, AND THAT IS THE
POINT.** The recorded ref `c530c70860d8` is the `0.16.0` release, and this
thread's entire purpose is to make the release train run unattended again. The
moment the next release lands, a refreshed cache appears under a NEW ref
directory and this block HALTs. **That HALT will be CORRECT** — it is the
mechanism working, not a defect — and the remedy is to regenerate the charter or
to re-stamp `generator_ref` and `generator_prose_md5` deliberately from the newly
installed ref. Do not pre-emptively loosen it to avoid the interruption; a
provenance check that cannot fire on this thread is a provenance check that
cannot fire at all.

A MISSING CACHE ROOT AND A MISSING REF ARE DIFFERENT CONDITIONS. No cache root
at all means this is not a charter-generating host — a CI runner, or another
checkout — so provenance is UNVERIFIED and the check continues; HALTing there
would make this file unreadable anywhere but the machine that produced it. A
cache root that no longer holds the recorded ref means the generator has been
REPLACED, which is exactly how a refresh shows up, and that HALTs.

## Thread-specific Valves

Every claim below is a measurement with a timestamp. Re-measure before carrying
any of it forward — that is the shared layer's first rule and this section is
not exempt from it.

- **THE SCOPE IS BOTH DEFECTS, AND THE SLUG READS NARROWER THAN HALF OF IT.**
  The maintainer chose the slug deliberately. `overseer-sf0` is the missing
  auto-merge workflow; `overseer-dtl` is seven — now ten, see below — files over
  an LLOC soft ceiling reddening the `Release tag` gate. `dtl` is not
  off-topic: **this repo's release train runs unattended and nothing notices
  when it breaks.** One half had no actor to press merge; the other has an actor
  shouting daily into a void. Do not let a successor treat half the thread as
  someone else's problem because the slug does not name it.

- **`overseer-dtl`'s ENUMERATED FILE LIST IS STALE, AND ACTING ON IT AS WRITTEN
  LEAVES THE GATE RED.** The item names **seven** soft-band files. Measured
  2026-08-02T23:53:24Z with the release-tier lever set — the exact configuration
  `Release tag` runs — the failing set is **TEN**:

  | file | LLOC | in the filed list? |
  |---|---|---|
  | `overseer/_supervisor_evaluate.py` | 250 | yes — AT the hard ceiling |
  | `overseer/test_claude_sessions.py` | 250 | **NO** — AT the hard ceiling |
  | `overseer/claude_sessions.py` | 241 | **NO** |
  | `overseer/test_overseer_start.py` | 227 | yes |
  | `overseer/_supervisor_pair.py` | 222 | yes |
  | `overseer/_supervisor_attention.py` | 221 | yes |
  | `overseer/codex_sessions.py` | 220 | yes |
  | `overseer/test_supervisor_background_subshell_live.py` | 218 | **NO** |
  | `overseer/_supervisor_discovery.py` | 204 | yes |
  | `overseer/test_supervisor_warned_stamp_written.py` | 201 | yes |

  **A run that decomposes exactly the seven filed files and stops will report
  success while `Release tag` stays RED on the other three** — which is
  precisely the "a fix that appears to land and changes nothing" shape this
  thread exists to stop, arriving from the direction nobody was watching. The
  population GREW between filing and dispatch, so it can grow again during the
  work.

  **THEREFORE: ACCEPTANCE FOR `dtl` IS THE MEASURED COMMAND, NOT THE FILED
  LIST.** The bar is that this exits 0:

  ```sh
  LIVESPEC_FAIL_IF_LLOC_SOFT_WARNINGS_EXIST=1 just check-no-lloc-soft-warnings
  ```

  Re-run it at the END of the work, not only at the start. Do NOT amend the item
  to add the three files as a substitute for measuring — an enumerated list is
  a snapshot and this valve is the evidence that a snapshot goes stale.

- **THE `.claude-plugin/overseer/` MIRROR WARNS BUT DOES NOT FAIL, AND THE
  DIFFERENCE IS A PHASE FLAG, NOT A CEILING.** Same measurement,
  2026-08-02T23:53:24Z: six mirrored copies (`_supervisor_attention`,
  `_supervisor_discovery`, `_supervisor_evaluate`, `_supervisor_pair`,
  `claude_sessions`, `codex_sessions`) report `"phase": "0-warn"` and
  `"failing": false`, with the check's own message stating they *"hard-fail once
  this repo is flipped to the hard gate in Phase 2"*. So they are NOT part of
  today's red and must not be counted into it — but they are also not safe to
  ignore, and note the mirror carries no `test_*.py` copies, so its set is a
  strict subset. Decomposing the source should propagate; verify that it did
  rather than assuming the mirror follows.

- **DO NOT RAISE THE CEILING, UNSET THE LEVER, OR EXCLUDE THE FILES.** Carried
  from the item verbatim in intent and not negotiable. That converts a working
  detector into one that cannot fail and ratifies three releases' worth of
  drift instead of repaying it. The research note states the general form:
  **making the check stop reporting is not making the condition go away.** This
  is also the one boundary the shared layer's decision rubric refuses to let you
  cross on your own judgement — never REMOVE, WEAKEN or SKIP an existing check.

- **`overseer-sf0` HAS LANDED, AND ITS ACCEPTANCE BAR IS STILL OPEN. THESE ARE
  DIFFERENT FACTS.** Measured 2026-08-02T23:52-53Z:
  `.github/workflows/auto-enable-merge.yml` merged to master as PR **#520**
  (`4c16379`), and **#520 was itself merged by `app/livespec-pr-bot`** at
  `2026-08-02T23:52:25Z` — the workflow armed its own PR. That is a real
  positive control and it proves the App credential path works in this repo.
  **It is NOT the acceptance criterion.** The bar the thread set is a
  RELEASE-PLEASE PR reaching `MERGED` with `mergedBy == app/livespec-pr-bot` and
  no human or agent pressing merge. Reporting `sf0` complete on #520 alone would
  substitute the easy half of the evidence for the half that was in doubt.

- **THE LIVE ACCEPTANCE TEST IS PR #516, AND IT NEEDS A FRESH EVENT — DO NOT
  MERGE IT BY HAND.** Measured 2026-08-02T23:52:56Z: #516
  (`chore(master): release 0.16.1`) is `OPEN`, `mergeStateStatus: CLEAN`,
  `autoMergeRequest: null`. The workflow fires on pull-request events, and #516
  was opened BEFORE the workflow existed on master, so nothing has re-evaluated
  it. A later release-please run that updates the PR is the ordinary way the
  event arrives. **Merging #516 by hand destroys the only acceptance evidence
  this thread can produce** — it recreates the exact ambiguity the research note
  identifies, where a hand-merge and an automated merge are the same `mergedBy`
  string. If the event genuinely never arrives, that is a finding to record, not
  a reason to press merge.

- **`overseer-zxy`'s TRIGGER HAS FIRED — IT IS NOW ACTIONABLE.** The item says
  NOT ACTIONABLE YET, gated on a release PR merging such that `origin/release`
  carries the launcher. Measured 2026-08-02T23:54:56Z: `v0.16.0` is the latest
  release, `origin/release:.claude-plugin/plugin.json` reports `0.16.0`, and
  `origin/release:.claude-plugin/bin/overseer-start` is **PRESENT** (it was
  ABSENT at filing; `origin/master` carries it too, as it did then). Re-verify
  A3/A4/l6b at `--ref release` using the COMMITTED harness at
  `plan/archive/codex-parity-and-rollout-safety/research/daemon-adoption-harness.md`
  — do not re-derive it, it encodes two gotchas that make a naive version
  silently prove nothing. Carry its safety constraints forward verbatim,
  including: if the only remaining route requires stopping the acting daemon,
  the honest outcome is "not observable" — report that and stop.

- **THE WORKER ON THIS THREAD IS CODEX, NOT CLAUDE CODE.** Measured
  2026-08-02T23:47Z: the worker pane's process tree holds
  `bun … codex --dangerously-bypass-approvals-and-sandbox`, running
  `gpt-5.6-sol`. The supervisor pane holds `claude`. This matters because
  several role-level rules are harness-specific and were written from the Claude
  side: **C21** — that a paste renders as a bracketed placeholder so a content
  grep returns zero on a paste that landed — describes Claude Code's renderer,
  and Codex's pane does not render that way. `overseer-816` tracks that the send
  idiom is stated as harness-neutral when it is not. **Confirm a send by what
  the pane actually shows, and re-capture rather than re-sending.** The
  verify-then-`Enter`-separately discipline still holds for both.

- **THE WORKER IS UNDER A STANDING AUTONOMY INSTRUCTION — CHECK IT BEFORE YOU
  ESCALATE.** The maintainer has directed this track to proceed autonomously
  through every phase to implementation and archive, to avoid obvious questions,
  and to route genuine uncertainty through a Codex subsession first to test
  whether it is answerable without them. That raises the bar for surfacing
  anything to the maintainer here. It does **not** lower the shared layer's own
  escalation boundary — never REMOVE, WEAKEN or SKIP an existing check — which
  is a property of the change and is not delegable to a subsession.

- **`ACTIVE` IS NEVER EVIDENCE OF A RUN; `fabro ps` IS.** Measured
  2026-08-02T23:50Z, two runs live in this repo: `01KZ2CECKH83`
  (`overseer-3u7bbw`) and `01KZ2CJ3YX43` (`overseer-dtl`). Note that
  `overseer-3u7bbw` — release-please leaving the shipped plugin `version.json`
  stale — is NOT this thread's item but is in the SAME release lane, so its
  changes and `dtl`'s can collide. A literal double-brace interpolation token
  anywhere in a work-item's text makes that item undispatchable and leaves a
  PHANTOM `active`/`fabro` claim with no run behind it; describe such a
  construct in words and never write it literally, and do NOT repair it by
  editing the item (`bd-ib-vv9y`, P1, orchestrator tenant).

- **`just worktree-create` IS BROKEN IN THIS REPO AND FAILS SILENTLY WHEN
  REDIRECTED.** `dev-tooling/worktree-lib.sh` pipes `git worktree list
  --porcelain` into an `awk` that exits on first match; git takes SIGPIPE,
  `pipefail` propagates 141, and `set -e` aborts before any output. It worsens
  with the worktree count — 9/9 failures on 2026-08-02. **The rescue path, used
  to produce this charter:** `git worktree add <path> -b <branch> origin/master`
  then `just install-worktree-pack` inside it. That pack install writes a
  `worktree_discipline` key into the TRACKED `.livespec.jsonc`; it only makes
  the existing default explicit, so `git checkout --` it unless you mean to land
  it. A worktree without that pack can neither commit a `.py` change nor push at
  all.

- **THIS THREAD'S `handoff.md` DECLARED ITS ANCHOR IN A SPELLING THE GATE DOES
  NOT READ, AND THE CHARTER PR HAD TO FIX IT.** `tests/test_plan_thread_records_agree.py`
  extracts a handoff's declaration with a pattern keyed on *ledger anchor*; this
  handoff said `Epic anchor:`, which extracts nothing. A thread with a charter
  and no extractable declaration is an OFFENCE, not a skip — so adding this
  charter alone would have turned master red. Measured 2026-08-02T23:54Z, two
  further live threads carry the same latent trap: `shell-evidence-truth` and
  `supervisor-wrapup-citizenship` both declare zero anchors under that pattern,
  so generating a charter for either reddens master the same way. Filed as
  `overseer-jtc`; related standing item `overseer-403`. The failure message
  misroutes the reader — it names the brand-new CHARTER beside an empty list,
  while the file that needs changing is the HANDOFF.

- **`bd` NEEDS THE FLEET CREDENTIAL WRAPPER HERE** — a bare `bd` returns
  `Access denied` against this repo's tenant. The Verification Discipline block
  below DETECTS it rather than hard-coding a path, so an adopter without a
  wrapper can still re-measure.

- **NEVER KILL, STOP OR RESTART THE ACTING OVERSEER DAEMON** (tmux
  `livespec-overseer:1.1`). It supervises every tracked session in the fleet and
  is the shipped product rather than part of this track. The shared layer states
  the rule; it is repeated here because this thread touches the release lane
  that ships that daemon, which makes "just restart it to pick up the new build"
  an inviting step.

- Full narrative state, including corrections to this supervisor's own conduct
  that are not yet role-level, belongs in the supervisor marker at
  `tmp/overseer/release-automation-gap/.supervisor-state`. Read it at boot; treat
  every status line in it as a claim with a timestamp and re-measure.

## Verification Discipline

Re-measure the filed work item from the ledger before carrying forward any status
or acceptance claim from this file, the plan thread, or a marker:

```sh
ledger_anchor='overseer-oijk3d'
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

`overseer-oijk3d` is an EPIC, so that reading reports the cut and not the work.
Re-measure `overseer-sf0`, `overseer-dtl` and `overseer-zxy` BY ID rather than
inferring child status from the epic's own field — measured 2026-08-02T23:49Z
the epic sat at `backlog` while two of its children were `active`, so the epic
field lags and cannot be read as a summary.

The release lane's own state is a forge fact, never a working-tree fact. Check
terminal state from the authoritative field FIRST — `state` before any derived
field such as `mergeStateStatus` — and make the acceptance question explicit:

```sh
gh pr view 516 --json number,state,mergeStateStatus,isDraft,autoMergeRequest,mergedBy \
  --jq '{number,state,mergeStateStatus,isDraft,autoMergeBy:.autoMergeRequest.enabledBy.login,mergedBy:.mergedBy.login}'
date -u '+MEASURED_AT: %Y-%m-%dT%H:%M:%SZ'
# ACCEPTANCE for overseer-sf0 is state == MERGED AND mergedBy == app/livespec-pr-bot
# on a RELEASE-PLEASE PR. Any other login — including the maintainer's, which is
# also what agents authenticate as — is a FAILED acceptance, not a pass.
# An unrecognized state must be REPORTED, never silently treated as "keep waiting".
```

When a command's own success is the verdict, capture that status before any pipe
used only to filter or display its output:

```sh
WORKER_TARGET='=release-automation-gap:'
pane_pid=$(tmux display-message -p -t "$WORKER_TARGET" '#{pane_pid}')
tmux_rc=$?
[ "$tmux_rc" -eq 0 ] \
  || { echo "HALT: tmux pane lookup failed for 'release-automation-gap'"; echo "REMEDY: re-check the exact target before filtering its output"; exit 1; }
printf '%s\n' "$pane_pid" | head -1
```

Inspect read-only before driving anything — a bounded scrollback sample plus the
whole visible worker pane:

```sh
WORKER_TARGET='=release-automation-gap:'
tmux capture-pane -p -t "$WORKER_TARGET" -S -40
```

`-S -40` starts 40 lines back in history and then includes the entire visible
pane. It is NOT "the last 40 lines", and its history must never feed the picker
test or the pane diff — a picker that closed minutes ago is still in the buffer.

## HALT-first preconditions

Worker session `release-automation-gap`; supervisor session
`release-automation-gap-supervisor`; target repo `/data/projects/livespec-overseer`.
Verify both sessions AND the live agent driver in each before doing anything
else. Stop on the FIRST failure and act on the labelled `REMEDY:`. Runtime
identity comes from exact live process evidence, NEVER from a session name — a
leftover session named like an agent proves nothing.

```sh
WORKER_TARGET='=release-automation-gap:'
tmux has-session -t "$WORKER_TARGET" \
  || { echo "HALT: expected worker session 'release-automation-gap'"; echo "REMEDY: ask the maintainer whether to start that worker session"; exit 1; }
pane_pid=$(tmux display-message -p -t "$WORKER_TARGET" '#{pane_pid}')
[ -n "$pane_pid" ] \
  || { echo "HALT: empty pane_pid for 'release-automation-gap'"; echo "REMEDY: re-check the exact worker target and stop if it still resolves empty"; exit 1; }
ps -o pid=,comm=,args= --ppid "$pane_pid" --pid "$pane_pid" -H
# PASS only if a live `claude` or `codex` process appears in that tree.
# A lone shell (zsh/bash) with no agent child is a HALT.
# REMEDY: if no live agent appears, ask the maintainer whether to restart the worker.

SUPERVISOR_TARGET='=release-automation-gap-supervisor:'
tmux has-session -t "$SUPERVISOR_TARGET" \
  || { echo "HALT: expected supervisor session 'release-automation-gap-supervisor'"; echo "REMEDY: switch to the correct supervisor session or ask the maintainer to bootstrap it"; exit 1; }
supervisor_pane_pid=$(tmux display-message -p -t "$SUPERVISOR_TARGET" '#{pane_pid}')
[ -n "$supervisor_pane_pid" ] \
  || { echo "HALT: empty pane_pid for 'release-automation-gap-supervisor'"; echo "REMEDY: re-check the exact supervisor target and stop if it still resolves empty"; exit 1; }
[ "$supervisor_pane_pid" != "$pane_pid" ] \
  || { echo "HALT: supervisor and worker resolve to the SAME pane"; echo "REMEDY: re-check both exact targets — a prefix match puts both names on one pane, and the worker's agent then reads as the supervisor's"; exit 1; }
ps -o pid=,comm=,args= --ppid "$supervisor_pane_pid" --pid "$supervisor_pane_pid" -H
# PASS only if a live `claude` or `codex` process appears in that tree.
# A lone shell (zsh/bash) with no agent child is a HALT.
# REMEDY: if no live agent appears, ask the maintainer to start the agent in that session.

test -d "/data/projects/livespec-overseer/plan/release-automation-gap" \
  || { echo "HALT: missing plan thread /data/projects/livespec-overseer/plan/release-automation-gap"; echo "REMEDY: create or choose the correct plan topic before supervising"; exit 1; }
pane_cwd=$(tmux display-message -p -t "$WORKER_TARGET" '#{pane_current_path}')
[ -n "$pane_cwd" ] \
  || { echo "HALT: empty pane_current_path for 'release-automation-gap'"; echo "REMEDY: re-check the exact worker target and stop if it still resolves empty"; exit 1; }
case "$(readlink -f -- "$pane_cwd")" in
  /data/projects/livespec-overseer|/data/projects/livespec-overseer/*) echo "PASS: $pane_cwd" ;;
  *) echo "HALT: pane cwd $pane_cwd is outside the target repo"; echo "REMEDY: move the worker into the target repo or start the correct worker session"; exit 1 ;;
esac
```

Report which driver was found — and on this thread expect them to DIFFER: the
worker is Codex and the supervisor is Claude, measured 2026-08-02T23:47Z. The
containment check resolves an ABSOLUTE repo path on purpose: a check rooted at
the bare `plan/` directory is cwd-relative and PASSES while pointed at the wrong
repository. The non-empty guard runs BEFORE the resolution because
`readlink -f ""` returns the CWD at exit 0 on this host's uutils coreutils, which
renders as a `PASS:` against the repo root — that is role-level correction **C2**.

## Corrections

Thread-specific corrections live here. Regenerating this binder MUST preserve
this section byte-for-byte, from the `## Corrections` heading through the end of
the section. Preserve spelling, punctuation, code formatting, blank lines, and
ordering exactly.

- **T1 (2026-08-02) — I nearly shipped this charter with an anchor its handoff
  could not be read as declaring, which would have reddened master.** I checked
  that `overseer-oijk3d` was the right epic and stopped there, treating "the id
  is correct" as "the record agrees". The gate does not compare ids; it compares
  a charter's `ledger_anchor` against what a REGEX can extract from `handoff.md`,
  and this handoff's `Epic anchor:` spelling extracts nothing. I caught it only
  by running the extractor against the real file before committing. Generalize:
  **when a gate reads two files for agreement, run its actual extractor over
  both — a fact being true in prose is not the same as a check being able to see
  it.** The same run found two sibling threads carrying the identical latent
  trap, which a spot-check of my own thread alone would never have surfaced.
