# Supervisor Handoff - daemon-liveness-truth

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

**As of 2026-08-02T23:20Z there is no marker at that path and no `runtime_dir`
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
| `thread_dir` | `plan/daemon-liveness-truth/` |
| `topic` | `daemon-liveness-truth` |
| `worker_session` | `daemon-liveness-truth` |
| `supervisor_session` | `daemon-liveness-truth-supervisor` |
| `WORKER_TARGET` | `'=daemon-liveness-truth:'` |
| `SUPERVISOR_TARGET` | `'=daemon-liveness-truth-supervisor:'` |
| `runtime_dir` | `<repo_primary>/tmp/overseer/daemon-liveness-truth/` |
| `supervisor_marker` | `<runtime_dir>/.supervisor-state` |
| `wait_channel` | `<runtime_dir>/worker-status.log` |
| `ledger_anchor` | `overseer-x29` |

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

**THIS CHARTER PASSES ITS OWN PROVENANCE CHECK ON THIS HOST, AND THAT IS A
CHANGE FROM ITS PREDECESSOR — measured 2026-08-02T23:20Z.** The `0.16.0` release
landed, so the cached generator prose at ref `c530c70860d8` is now
byte-identical to `.claude-plugin/prose/supervise-plan.md` in this repo
(`eaebe06065b3efa0053d6ea5932d52c0` both ways). The hardened exemplar carries a
valve saying its provenance check WILL HALT because the repo was ahead of the
released plugin; that condition has cleared for this charter. **A HALT here is
therefore a real signal, not the known-benign one** — do not read the exemplar's
valve as covering this file.

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

- **THIS THREAD'S SUBJECT MAKES KILLING THE DAEMON UNIQUELY TEMPTING. DO NOT.**
  The acting overseer daemon runs in tmux `livespec-overseer:1.1`, supervises
  every tracked session in the fleet, and is the shipped product rather than
  part of this track. This thread is about the daemon's own liveness model, so
  "just restart it and watch" is the obvious next step at almost every turn, and
  it is the one action here whose blast radius is fleet-wide. The shared layer
  states the rule; this valve exists because this topic is where it will
  actually be tested.
- **THE `handoff.md` IS STALE ABOUT `overseer-mkx`, AND IT SAYS THE OPPOSITE OF
  THE TRUTH.** It reads *"What remains on `overseer-mkx` is the token-vocabulary
  decision … Nothing about mkx was touched."* Measured 2026-08-02T23:19:45Z:
  `overseer-mkx` is **closed**, at 2026-08-02T23:09:01Z, via PR **#477**
  (`6b58092ef`, merged 2026-08-02T18:29:26Z). The handoff was last written
  before that close. Read the ledger, not this sentence, and re-measure both
  before believing either.
- **PR #477 CORRECTS `overseer-mkx`'S OWN ACCOUNT OF THE DEFECT, which is worth
  more than the close.** mkx claimed a torn-down track renders as *hung
  mid-wrap-up*; measured, it does not — the non-responder alert requires a LIVE
  pane at danger context, so a gone session never reaches it. The real symptom
  was sharper: the track reported `session-gone`, the only red status,
  indefinitely. The fix reads a discriminator already on disk (a session that
  wound down declared `winding-down` first; one that died working declared
  nothing) and reports the non-red wound-down state for the former. Three
  controls ship with the RED — gone with no declaration, gone while blocked,
  gone holding `ready`, all still red. **So mkx's acceptance was met by
  correcting its premise, not by satisfying its words.** That distinction is the
  thread's, and it should not be smoothed over in any later summary.
- **mkx OPTIONS 1 AND 3 WERE LEFT OPEN DELIBERATELY AND ARE NOT FORECLOSED.**
  Option 1 is a teardown path that clears the state file; option 3 is the
  missing terminal token meaning *"complete, parked, nothing wanted"*. Option 3
  is a change to `overseer/marker-protocol.md`, the cardinal contract document,
  and is therefore the maintainer's call rather than a worker's. The merged
  commit records that both compose with what landed. Closing mkx did not decide
  them; if they matter they need their own filing.
- **`overseer-j1r` IS CLOSED AND FIXED — PR #468.** Measured
  2026-08-02T23:19:45Z. Root cause was registry-name provenance, NOT the shared
  root the handoff hypothesises: a manually-started Claude AUTO-derives its
  registry name from the repo directory (`"nameSource":"derived"`) while a
  daemon-spawned one is given `-n <topic>`, and the daemon matched on topic
  equality in two places, so a derived name failed both and degraded straight to
  `session-gone`. `nameSource` is the discriminator. The identity gate is
  UNTOUCHED — the fix is a reporting softener, never an act gate.
- **THE HANDOFF'S "root they probably share" SECTION IS A HYPOTHESIS AND IT IS
  WRONG FOR `j1r`.** The handoff says so itself, above that section. Do not
  re-derive the shared-root theory; the measurement went the other way and the
  contrast is the finding.
- **EPIC `overseer-x29` IS `backlog` WITH ONE LIVE CHILD.** Measured
  2026-08-02T23:20:22Z: `j1r` closed, `mkx` closed, `overseer-oydugu`
  **blocked / needs-human**. The epic's own status has not been advanced to
  match its children — that is a ledger-hygiene valve, not a defect in the work.
- **`overseer-oydugu` IS THE ONLY REMAINING WORK, AND ITS `blocked` VERDICT IS
  CORRECT RATHER THAN AN OVERSIGHT.** It is rung 3 of the supervision ladder —
  observing a supervisor READING a charter clause and doing otherwise — and it
  needs a human design call before it can be dispatched. **The design problem is
  the whole difficulty:** a detector keying on "prose + question mark + no
  picker" also flags the LEGITIMATE answering turn, because answering the
  maintainer is prose while asking them is a picker, and both appear in one
  turn. Intent is not reliably in the text. Acceptance must be RED against the
  recorded 2026-08-02 four-valves-as-prose turn and **GREEN against the recorded
  answering turn in that same session** — that control is load-bearing and a
  gate without it must not land. **A negative result is an acceptable outcome;
  do NOT weaken the picker rule to make a gate pass.**
- **`overseer-oydugu`'S EPIC EDGE IS PROSE-ONLY AND THAT IS NOT AN OVERSIGHT.**
  `bd dep add overseer-oydugu overseer-x29 --type blocks` is refused — *"tasks
  can only block other tasks, not epics"*. Cite the link; do not go looking for
  the edge.
- **THE WORKER IS RUNNING UNDER A STANDING AUTONOMY INSTRUCTION — CHECK IT
  BEFORE YOU ESCALATE.** Observed in the worker pane 2026-08-02T23:20Z: the
  maintainer directed it to proceed autonomously through all phases, to avoid
  obvious questions, and to route genuine uncertainty to a Codex subsession
  first to test whether the answer is obvious enough to continue on. That raises
  the bar for surfacing anything to the maintainer on this thread specifically.
  It does **not** lower the bar for the shared layer's own escalation
  boundary — never REMOVE, WEAKEN or SKIP an existing check — which is a
  property of the change and is not delegable to a subsession.
- **`just worktree-create` IS EFFECTIVELY BROKEN IN THIS REPO AND THE FAILURE IS
  SILENT WHEN REDIRECTED.** `dev-tooling/worktree-lib.sh:89` pipes
  `git worktree list --porcelain` into an `awk` that exits on first match,
  closing the pipe while git is still writing; git takes SIGPIPE, `pipefail`
  propagates 141, and `set -e` aborts before any output. It worsens with the
  worktree count: 65 consecutive failures at 77 worktrees on 2026-08-02.
  **Re-measured for this charter 2026-08-02T23:21Z at 82 worktrees: still exit
  141.** The recorded fix is one line in `livespec-dev-tooling`'s package source
  (`livespec-dev-tooling-zi4q`); never hand-edit the gitignored `dev-tooling/`
  copy. **THE RESCUE PATH, used to produce this charter:**
  `git worktree add <path> -b <branch>` then `just install-worktree-pack` inside
  it. That pack install writes a `worktree_discipline` key into the TRACKED
  `.livespec.jsonc`; it only makes the existing default explicit, so
  `git checkout --` it unless you mean to land it.
- **A CHANGE TO ANY FILE UNDER `overseer/` REQUIRES A PAIRED CHANGE UNDER
  `tests/**`** (`commit_pairs_source_and_test`). The beside-tests in `overseer/`
  are themselves SOURCE to that check, so a beside-test alone does not satisfy
  it. `tests/conftest.py` puts `overseer/` on `sys.path`, so a module moves to
  `tests/` verbatim with no import changes.
- **`just check` PASSING LOCALLY IS NOT EVIDENCE ABOUT THE TREE YOU PUSHED.**
  The pre-push hook skips the aggregate on a green-token match keyed to the
  tree, so after MOVING or RENAMING a file the previous green describes a tree
  that no longer exists and the post-move tree is never fully checked locally.
  This cost this thread a red CI on `_supervisor_offer.py:177`. Re-run
  `just check` after any move or rename, before pushing.
- **A LITERAL DOUBLE-BRACE INTERPOLATION TOKEN IN A WORK-ITEM'S TEXT MAKES THE
  ITEM UNDISPATCHABLE.** `drive.py` interpolates item text into fabro's
  templated `goal`, so the token parses as a fabro template variable, finds no
  binding, and the graph is rejected before any agent runs — leaving a PHANTOM
  `active`/`fabro` claim with no run behind it. `fabro ps` is the evidence,
  never `ACTIVE`. Describe such a construct in words; never write it literally.
  Do NOT fix it by editing the work item — that corrupts the item's own evidence
  and hides a defect that recurs (`bd-ib-vv9y`, P1, orchestrator tenant).
- **`date -u -r <file>` DOES NOT APPLY `-u` ON THIS HOST.** It runs uutils
  coreutils, not GNU: the command prints LOCAL time, and local is CEST, so a `Z`
  appended to it is a silent two-hour lie. Derive any mtime that will enter a
  published claim through `datetime.fromtimestamp(ts, timezone.utc)`. This is
  role-level correction **C19** and it cost a sibling thread a false accusation
  against a colleague's work. Detector `(k)` in
  `tests/prompts/test_charters_carry_no_known_defects.py` gates the form in
  fenced charter code, which is why the hazard is stated here in prose.
- **CONFIRMING A PASTE BY GREPPING THE PANE FOR ITS TEXT CANNOT WORK**
  (role-level correction **C21**). Claude Code renders a multi-line paste as a
  bracketed `Pasted text` placeholder and a single-line paste inline, so a
  content grep returns zero on a paste that landed. Confirm by the placeholder
  OR a non-empty prompt line, accept either shape, and **re-capture rather than
  re-sending** — the render lags after both `paste-buffer` and `Enter`.
- **`bd` NEEDS THE FLEET CREDENTIAL WRAPPER HERE** — a bare `bd` returns
  `Access denied` against this repo's tenant. The Verification Discipline block
  below DETECTS it rather than hard-coding a path, so an adopter without a
  wrapper can still re-measure.
- The shared layer `.ai/supervisor-protocol.md` carried role-level corrections
  through **C22** when this charter was generated (2026-08-02T23:20Z). That is a
  count with a timestamp, not a standing fact: the section is append-only, so
  re-read it rather than trusting this number. Note that
  `tests/test_charter_correction_counts_are_current.py` gates count claims for
  the `supervisor-prompt-quality` records ONLY — it does not read this file, so
  nothing will tell you when this sentence goes stale.
- Full narrative state, including corrections to this supervisor's own conduct
  that are not yet role-level, belongs in the supervisor marker at
  `tmp/overseer/daemon-liveness-truth/.supervisor-state`. Read it at boot; treat
  every status line in it as a claim with a timestamp and re-measure.

## Verification Discipline

Re-measure the filed work item from the ledger before carrying forward any status
or acceptance claim from this file, the plan thread, or a marker:

```sh
ledger_anchor='overseer-x29'
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

`overseer-x29` is an EPIC, so that reading reports the cut and not the work. Its
children carry the state that matters — re-measure each by id rather than
inferring child status from the epic's own field, which lagged its children by
two closes on 2026-08-02.

When a command's own success is the verdict, capture that status before any pipe
used only to filter or display its output:

```sh
WORKER_TARGET='=daemon-liveness-truth:'
pane_pid=$(tmux display-message -p -t "$WORKER_TARGET" '#{pane_pid}')
tmux_rc=$?
[ "$tmux_rc" -eq 0 ] \
  || { echo "HALT: tmux pane lookup failed for 'daemon-liveness-truth'"; echo "REMEDY: re-check the exact target before filtering its output"; exit 1; }
printf '%s\n' "$pane_pid" | head -1
```

Inspect read-only before driving anything — a bounded scrollback sample plus the
whole visible worker pane:

```sh
WORKER_TARGET='=daemon-liveness-truth:'
tmux capture-pane -p -t "$WORKER_TARGET" -S -40
```

`-S -40` starts 40 lines back in history and then includes the entire visible
pane. It is NOT "the last 40 lines", and its history must never feed the picker
test or the pane diff — a picker that closed minutes ago is still in the buffer.

## HALT-first preconditions

Worker session `daemon-liveness-truth`; supervisor session
`daemon-liveness-truth-supervisor`; target repo `/data/projects/livespec-overseer`.
Verify both sessions AND the live agent driver in each before doing anything
else. Stop on the FIRST failure and act on the labelled `REMEDY:`. Runtime
identity comes from exact live process evidence, NEVER from a session name — a
leftover session named like an agent proves nothing, and on this thread in
particular a session that merely EXISTS is exactly the thing under investigation.

```sh
WORKER_TARGET='=daemon-liveness-truth:'
tmux has-session -t "$WORKER_TARGET" \
  || { echo "HALT: expected worker session 'daemon-liveness-truth'"; echo "REMEDY: ask the maintainer whether to start that worker session"; exit 1; }
pane_pid=$(tmux display-message -p -t "$WORKER_TARGET" '#{pane_pid}')
[ -n "$pane_pid" ] \
  || { echo "HALT: empty pane_pid for 'daemon-liveness-truth'"; echo "REMEDY: re-check the exact worker target and stop if it still resolves empty"; exit 1; }
ps -o pid=,comm=,args= --ppid "$pane_pid" --pid "$pane_pid" -H
# PASS only if a live `claude` or `codex` process appears in that tree.
# A lone shell (zsh/bash) with no agent child is a HALT.
# REMEDY: if no live agent appears, ask the maintainer whether to restart the worker.

SUPERVISOR_TARGET='=daemon-liveness-truth-supervisor:'
tmux has-session -t "$SUPERVISOR_TARGET" \
  || { echo "HALT: expected supervisor session 'daemon-liveness-truth-supervisor'"; echo "REMEDY: switch to the correct supervisor session or ask the maintainer to bootstrap it"; exit 1; }
supervisor_pane_pid=$(tmux display-message -p -t "$SUPERVISOR_TARGET" '#{pane_pid}')
[ -n "$supervisor_pane_pid" ] \
  || { echo "HALT: empty pane_pid for 'daemon-liveness-truth-supervisor'"; echo "REMEDY: re-check the exact supervisor target and stop if it still resolves empty"; exit 1; }
[ "$supervisor_pane_pid" != "$pane_pid" ] \
  || { echo "HALT: supervisor and worker resolve to the SAME pane"; echo "REMEDY: re-check both exact targets — a prefix match puts both names on one pane, and the worker's agent then reads as the supervisor's"; exit 1; }
ps -o pid=,comm=,args= --ppid "$supervisor_pane_pid" --pid "$supervisor_pane_pid" -H
# PASS only if a live `claude` or `codex` process appears in that tree.
# A lone shell (zsh/bash) with no agent child is a HALT.
# REMEDY: if no live agent appears, ask the maintainer to start the agent in that session.

test -d "/data/projects/livespec-overseer/plan/daemon-liveness-truth" \
  || { echo "HALT: missing plan thread /data/projects/livespec-overseer/plan/daemon-liveness-truth"; echo "REMEDY: create or choose the correct plan topic before supervising"; exit 1; }
pane_cwd=$(tmux display-message -p -t "$WORKER_TARGET" '#{pane_current_path}')
[ -n "$pane_cwd" ] \
  || { echo "HALT: empty pane_current_path for 'daemon-liveness-truth'"; echo "REMEDY: re-check the exact worker target and stop if it still resolves empty"; exit 1; }
case "$(readlink -f -- "$pane_cwd")" in
  /data/projects/livespec-overseer|/data/projects/livespec-overseer/*) echo "PASS: $pane_cwd" ;;
  *) echo "HALT: pane cwd $pane_cwd is outside the target repo"; echo "REMEDY: move the worker into the target repo or start the correct worker session"; exit 1 ;;
esac
```

Report which driver was found. The containment check resolves an ABSOLUTE repo
path on purpose: a check rooted at the bare `plan/` directory is cwd-relative
and PASSES while pointed at the wrong repository. The non-empty guard runs
BEFORE the resolution because `readlink -f ""` returns the CWD at exit 0 on this
host's uutils coreutils, which renders as a `PASS:` against the repo root — that
is role-level correction **C2**.

## Corrections

Thread-specific corrections live here. Regenerating this binder MUST preserve
this section byte-for-byte, from the `## Corrections` heading through the end of
the section. Preserve spelling, punctuation, code formatting, blank lines, and
ordering exactly.

This section is EMPTY at generation (2026-08-02T23:20Z), and that is a real
state rather than an omission: this is the thread's first charter and no
supervisor has yet acted under it. Role-level corrections C1 onward already
apply and live in `.ai/supervisor-protocol.md` — do not copy them down here.
Record a `T<n>` entry the first time THIS supervisor gets something wrong on
THIS thread, and record it about your own conduct; a section that logs only the
worker's mistakes is a wrong record.
