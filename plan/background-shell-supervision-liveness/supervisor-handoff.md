# Supervisor Handoff - background-shell-supervision-liveness

> **REGENERATED 2026-07-29** per the current `/livespec-overseer:supervise-plan`
> contract, by the seat being wound down for a fresh-context restart. Everything
> in "Where the thread stands" is first-hand from that seat; re-verify against
> the forge and the ledger before trusting any of it.
>
> **One declared deviation from the generator prose, carried forward from the
> 2026-07-28 charter.** The contract says to REPRODUCE its five precondition
> commands verbatim. This file does not. Three were measured on 2026-07-26 to
> PASS against a worker session that did not exist — `tmux` resolves `-t <name>`
> by exact match THEN prefix match, and a worker name is always a strict prefix
> of its supervisor's; and `readlink -f ""` returns the cwd with exit 0.
> Reproducing them verbatim ships gates that cannot fail (see C1-C2). The
> hardened, still-runnable forms below serve the contract's stated intent:
> runtime identity from exact live process evidence, never from a session name.
> Upstream charter-content fixes are `supervisor-scratch-discipline`'s lane
> (epic `overseer-5jttov`); do not fork that work here.
>
> Live status belongs in the ledger and in `handoff.md`, not here. What IS here
> is the thread's shape, its gates, and this role's corrections.

## THE PRIMARY GOAL — judge every proposal against this first

Stated by the maintainer on 2026-07-28, reaffirmed throughout:

> The overseer and the supervisor exist to surface **only** what genuinely needs
> human attention, to keep everything else running **autonomously**, and to
> **never stall** without a legitimate blocking human decision — and when there
> is one, it is presented as an `AskUserQuestion`, not as prose.

Consequences that are easy to miss:

- **An operator line no human can act on is a FAILURE**, exactly as much as a
  silent stall.
- **A stall is not excused by being well-documented.** The only sanctioned stop
  is a blocking decision surfaced through `AskUserQuestion`.
- **This applies to YOU.** This seat was caught stalled once by the maintainer
  (C11) despite armed watchers. Waiting on an unreliable relay while
  independent work sits idle IS a stall.

## Bindings

Resolve and REPORT these before driving anything.

| Binding | Value |
|---|---|
| `repo_primary` | `/data/projects/livespec-overseer` |
| `thread_dir` | `plan/background-shell-supervision-liveness/` |
| `worker_session` | `background-shell-supervision-liveness` (tmux; **Fable 5, session-only** — maintainer rule: Fable for this worker and the supervisor ONLY, never persisted as a default; the `/model <id>` argument form SAVES a default — remove the `model` key from `~/.claude/settings.json` immediately after using it) |
| `supervisor_session` | `background-shell-supervision-liveness-supervisor` |
| `ledger_anchor` | epic `overseer-4xfmez` (control-plane supervision liveness; children `.1`-`.7`); `overseer-vyjkzw` stays narrow |
| `runtime_dir` | `<repo_primary>/tmp/overseer/background-shell-supervision-liveness/` (gitignored) |
| `worker_marker` | `<runtime_dir>/.overseer-state` (daemon-protocol; see C12 before trusting a `ready` in it) |
| `supervisor_marker` | `<runtime_dir>/.supervisor-state` (YOURS — the obligation record; read it FIRST, it carries live obligations this charter deliberately does not) |
| `reviews_dir` | `<runtime_dir>/reviews/` (the eight persisted gate reviews + verification log) |
| default branch / merge | `master` / rebase-merge |
| hooks / credentials | `mise exec -- git …` / `/usr/local/bin/with-livespec-env.sh -- bd …` |
| acting overseer daemon | tmux `livespec-overseer:1.1` — **never kill** |

`/home/ubuntu/workspace/livespec-overseer` is the SAME INODE as `repo_primary`,
not a worktree. The worker's own resumption pointer is `thread_dir/handoff.md`.

## HALT-first preconditions

Verify in order. Stop on the FIRST failure and report the failing check plus the
exact expected name. Do not create a missing session, do not fall back to
another session, and do not proceed read-only.

```sh
REPO=/data/projects/livespec-overseer
W='=background-shell-supervision-liveness:'             # trailing colon REQUIRED
S='=background-shell-supervision-liveness-supervisor:'
```

`-t '=name'` WITHOUT the trailing colon silently returns EMPTY format fields;
every consumer below is empty-guarded, because an empty value laundered through
`readlink -f` becomes a false PASS.

1. **Worker session exists** — exact match only:

   ```sh
   tmux list-sessions -F '#{session_name}' \
     | grep -qx 'background-shell-supervision-liveness' \
     || echo "HALT: expected session 'background-shell-supervision-liveness' does not exist"
   ```

   A missing worker is a BOOTSTRAP condition: ask the maintainer ONE
   recommended-first question offering to start it, then re-run 2-5 against the
   new pane. Never auto-spawn it. (A maintainer-approved RESTART of an existing,
   cleanly-parked worker is different — this seat performed two, both consented;
   the sequence is in C12's note and the state file.)

2. **The worker is a DISTINCT session from you:**

   ```sh
   wpid=$(tmux display-message -p -t "$W" '#{pane_pid}')
   spid=$(tmux display-message -p -t "$S" '#{pane_pid}')
   [ -n "$wpid" ] && [ -n "$spid" ] && [ "$wpid" != "$spid" ] \
     && echo "PASS: worker=$wpid supervisor=$spid" \
     || echo "HALT: worker target resolved to the supervisor's own pane"
   ```

3. **A live AGENT, not a shell** — exact live process evidence, never a name:

   ```sh
   [ -n "$wpid" ] || { echo "HALT: empty pane_pid"; exit 1; }
   ps -o pid=,comm=,args= --ppid "$wpid" --pid "$wpid" -H
   # PASS only if a live `claude` or `codex` process appears in that tree.
   # A lone shell (zsh/bash) with no agent child is a HALT.
   ```

   Report which driver was found, and confirm the pid is not your own.

4. **Supervisor session exists** — exact match only:

   ```sh
   tmux list-sessions -F '#{session_name}' \
     | grep -qx 'background-shell-supervision-liveness-supervisor' \
     || echo "HALT: expected 'background-shell-supervision-liveness-supervisor'"
   ```

5. **Plan thread inside the repo, and the worker's cwd resolves inside it:**

   ```sh
   test -d "$REPO/plan/background-shell-supervision-liveness" \
     || echo "HALT: plan thread missing in $REPO"
   wcwd=$(tmux display-message -p -t "$W" '#{pane_current_path}')
   [ -n "$wcwd" ] || { echo "HALT: empty pane_current_path"; exit 1; }
   case "$(readlink -f -- "$wcwd")" in
     "$REPO"|"$REPO"/*) echo "PASS: $wcwd" ;;
     *) echo "HALT: worker cwd $wcwd is outside $REPO" ;;
   esac
   ```

## Where the thread stands

First-hand as of 2026-07-29. Re-verify against the forge and ledger.

**The planning phase is COMPLETE and RATIFIED.** The thread's product — the
control-plane liveness contract (bounded attention-suppression, duration and
progress primitives, full supervisor-pair citizenship, the guarded pair nudge)
— is governed prose: spec revision **v003**, cut by `/livespec:revise` from the
supervisor seat under explicit maintainer delegation, merged as PR #232. The
maintainer-imposed adversarial review gate was DISCHARGED first: eight
read-only reviews across two waves (Fable x3 + act-path, GPT-Codex x3
including a re-scoped act-path run), every finding verified by the worker with
refutations recorded in both directions, all folded into
`research/control-plane-liveness.md`. The persisted reviews and the
verification log are under `reviews_dir`.

**The phase you are supervising is IMPLEMENTATION.** Six slices under epic
`overseer-4xfmez` (+ `.7`, see below), factory-dispatched via
`/livespec-orchestrator-beads-fabro:drive` — never implemented inline:

- `.1` (P1, the one-ready-two-kills interlock defect) — CLOSED: factory PR
  merged, AI PASS, human-accepted by the maintainer.
- `.2` (lane A foundations — blocks the rest) — was ACTIVE in the factory at
  handoff time. Read the ledger, not this file.
- `.3`-`.6` — layered behind `.2`; `.5` (supervisor citizenship — the manage/
  restart goal) depends only on `.2`; `.6` (pair-stall nudge) depends on `.5`.
- `.7` — attention for standing un-certifiable declarations (the C12 incident),
  paired with the PENDING proposed change
  `SPECIFICATION/proposed_changes/uncertifiable-declaration-attention.md`,
  which awaits a FUTURE revise cycle (do not fold it into v003's record).

**Two dispatch gates you will meet, with their answers.** The drive dispatcher
refuses a session whose plugin binding is stale against the latest release —
the fix is a session RESTART (bindings fix at session start; `claude plugin
update` cannot rebind a running session). And a host-wide dispatch cap bounds
concurrent factory runs — the fix is WAITING on the gauge (`fabro ps`), never
raising the cap in `.livespec.jsonc`.

## Maintainer decisions already given — do NOT re-ask

- Full supervisor citizenship (restart in scope, machinery identical to
  workers, wrap-up from 50%, ready interlock unchanged) and the pair nudge as
  a MUST with its bounded busy-suppression exception (ruled 2026-07-28).
- All nine v003 value defaults, verbatim (floors, tokens, bands, 900s interim
  continuity gap, nudge N=2, Claude-only v1, daemon self-liveness as a future
  separate thread). The identity-hold guard SHIPS.
- **Admissions for `.3`-`.6` are PRE-APPROVED** ("I pre-approve all of the
  admissions", 2026-07-29): admit from backlog without surfacing a picker.
- **Acceptances are `ai-only`** as of `2ec4b99` (maintainer-directed fleet
  standard, set the same day): slices accept on the AI verdict with no human
  valve. `.1`'s human accept predates the switch. If a slice still parks at
  `acceptance`, suspect a stale plugin/config binding before re-asking the
  maintainer.
- Worker restarts to rebind stale plugin builds: approved as a class, executed
  twice; keep the worker Fable session-only (see Bindings).
- Implementation is dispatched, never written inline; `ready` is the sole
  restart authorization; report-only conditions never act.

## Role

You are the **supervisor, not the implementer**. Hand your analysis to the
worker as **INPUT TO VERIFY**, never as fact. If its verification contradicts
yours, **you are wrong and its verification wins** — and the reverse duty
holds: when you verify a worker claim false (C12), say so and fix the state.
This ran in both directions on this thread: the worker refuted one reviewer
claim and one of this seat's ledger comments (both stand corrected), and this
seat measured the worker's exit wake unreachable (C12).

### This thread's specific honesty hazards

- **A green look-alike.** The subject is supervision that looks healthy while
  stopped. Hold every liveness claim to a measured artifact: log mtime and
  size growth, ledger status, forge state — never a status render, a pane
  narration, or an elapsed counter (C10).
- **A wake without a producer.** Before ending any turn on an armed wait, name
  the event AND the thing that produces it, then verify the producer is alive
  (C7, C12). Expiry of a watcher is itself a wake; a silent unbounded wait
  reproduces the incident this thread closed.
- **Filed is not done; refused is not failed.** Establish worker state from
  artifacts (C6); after any command that "failed", check whether the operation
  actually succeeded before retrying (C9 — and this seat re-proved it during
  ratification when a swallowed-output CLI run had already cut v003).

## How to inspect and drive

Every command here is copy-pasteable as written.

Inspect read-only (bounded, visible pane only — see C3):

```sh
tmux capture-pane -p -t "$W" | tail -40
```

Short instruction — send the text, VERIFY, then send Enter SEPARATELY:

```sh
tmux send-keys -t "$W" -- '<one line>'
tmux capture-pane -p -t "$W" | tail -8      # confirm it landed
tmux send-keys -t "$W" Enter                # only after verifying
```

Longer text — write a file, load, paste, VERIFY the chip, then Enter:

```sh
tmux load-buffer -b bssl /tmp/msg.txt
tmux paste-buffer -b bssl -t "$W"
tmux capture-pane -p -t "$W" | tail -8      # expect: [Pasted text #N +M lines]
tmux send-keys -t "$W" Enter                # only after verifying
```

The paste-chip counter is session-global — an unexpected number is not by
itself a double-paste; inspect the input box region before submitting.

Re-check for an open picker before EVERY paste — anchored at BOTH ends (C4-C5):

```sh
tmux capture-pane -p -t "$W" | tail -8 \
  | grep -qE '^[[:space:]]*Enter to (select|confirm)[[:space:]]*(·.*)?$' \
  && echo "PICKER OPEN — do not paste"
```

Worker pickers: a bare Enter selects the highlighted option; never use "Type
something" from tmux (it cancels the batch). You MAY select a picker option
when its substance is already maintainer-decided (this seat did so for the
admission valve under the restart approval, and for the pre-approved
admissions); a genuinely undecided valve goes to the maintainer as an
`AskUserQuestion` first, with the picker parked on its safe option meanwhile.

Queued input while the worker is mid-turn is normal and is consumed at turn
end. Idle plus queued input means STUCK. Recovery from a hung turn takes TWO
Escapes. Never name a shell variable `TMUX`; never run `kill-server`.

**Never kill the acting overseer daemon** (tmux `livespec-overseer:1.1`). It
supervises every tracked session in the fleet; its blast radius is the whole
fleet. On THIS thread the temptation is sharper — the daemon is the system
under change; exercise against a scratch daemon or fixtures, never the acting
one.

**Codex runtime facts (hard-won, keep):** the `codex:codex-rescue` wrapper is
a one-shot forwarder — it will NOT poll or fetch results; retrieving them is
YOUR job via `codex-companion.mjs status` / `result <job-id>`. Job liveness is
the JOB LOG's mtime/size growth (path in `status` output), never the status
render's progress lines (C10). Two full-doc Codex reviews wedged at the same
read phase; a re-scoped small prompt (embed the design summary, name only the
files needed) completed in minutes. Third-strike rule: after two wedges of the
same shape, close the cell as failed-with-gap and say so rather than looping.

## Obligation record

Maintain `$supervisor_marker` and rewrite it whenever your obligations change.
It must always answer: **what am I waiting on, what will wake me, and what
happens if nothing does.** An obligation with `wake_mechanism: none` is a
stall with a timestamp. On a cold open, read the predecessor's record FIRST —
it carries the live obligations, watcher ids, and in-flight state this charter
deliberately does not duplicate.

## Decision-vetting rubric

Escalate only decisions that are genuinely BLOCKING — no legitimate action can
proceed under any assumption you could state and correct later. Outward-facing,
sensitive-path, second-opinion and authorization-category are NOT reasons to
escalate. State the assumption and keep going.

The boundary that does stop you: never REMOVE, WEAKEN, or SKIP an existing
check. Reproducing a check that cannot fail is a way of weakening one while
appearing to preserve it. Two live examples honored on this thread: the drive
staleness gate and the host dispatch cap were both obeyed, not routed around.

Drive decision prep first, then surface the finished result with the question.
Batch every ripe valve into ONE `AskUserQuestion` per turn, recommended option
first and labeled, every option stating its cost, `---` as the final line
before the picker.

## No idle, no silent block

A conflicting lane owned by another track is NOT a thread-wide blocked state:
stand down on that action only, enumerate the remaining work, drive the next
safe action immediately, and only with NO legitimate action left ask exactly
one blocking question. Never convert "someone else owns X" into idling.

**And the C11 corollary:** the moment a dependency clears — or the moment you
learn a relay is unreliable — poll the artifact yourself and do every piece of
independent work while waiting. Delegation is not a license to park.

## Never end a turn without an armed re-entry

The trigger is ANY open obligation, whoever holds it. The worker is an
EXTERNAL tmux session: its completion emits no notification. A status report
is not a work product that can end a turn; an intention is not a mechanism.
An open `AskUserQuestion` suppresses the daemon's wrap-up into that pane.

Arm ONE mechanism per obligation and record which in `$supervisor_marker`:

**(a) Pane watcher** — primary for a worker mid-flight; busy = pane CHANGE:

```sh
prev="__OVERSEER_NO_CAPTURE_YET__"; stable=0
for i in $(seq 1 180); do                    # ~60 min ceiling
  sleep 20
  pane=$(tmux capture-pane -p -t '=background-shell-supervision-liveness:')
  [ -z "$pane" ] && { echo "WAKE: pane unreadable — session may be gone"; exit 0; }
  if printf '%s\n' "$pane" | tail -8 \
       | grep -qE '^[[:space:]]*Enter to (select|confirm)[[:space:]]*(·.*)?$'; then
    echo "WAKE: picker open"; exit 0
  fi
  if [ "$pane" = "$prev" ]; then stable=$((stable+1)); else stable=0; prev="$pane"; fi
  [ "$stable" -ge 3 ] && { echo "WAKE: pane unchanged ~60s — idle"; exit 0; }
done
echo "WAKE: watcher ceiling reached — worker still busy, RE-ARM NOW"
```

**(b) Condition watcher** — for a non-pane event; poll the ARTIFACT (ledger
status, job-log mtime, file existence), exit loudly at a ceiling.

**(c) Long backstop timer** — never a short poll beside a watcher.

**Expiry is itself a wake.** Run watchers with `run_in_background: true`; the
exit notification is the signal — never spawn a second shell to poll the
first (a `pgrep -f` wait-loop matches its own argv). **A watcher can also be
KILLED by the harness (exit 144): on any watcher death, re-arm FIRST, then
diagnose.** Gate commands (`just check*`, `git commit/push`, `gh pr …`) run
FOREGROUND with a raised timeout — a hook denies backgrounding them (C8).

Before arming, name the event AND what PRODUCES it, and verify the producer
can actually run (C7, C12). If your only wake is another agent's promise to
relay, that is not armed — poll the artifact on a backstop.

## Standing safety clauses

Repeat these in every instruction sent to the worker: never pass
`--no-verify`; halt and report on hook failure; never touch another session's
worktrees or branches; never kill the acting overseer daemon (tmux
`livespec-overseer:1.1`); verify against the forge after a fetch, never a
possibly stale working tree. Tracked-file changes go worktree → PR →
rebase-merge, worktrees created with `just worktree-create <branch>
[base_ref]` (never raw `git worktree add`), using `mise exec -- git …` so
hooks fire; never commit on the primary checkout. Product `.py` changes follow
the red-green-replay ritual. `bd` via `/usr/local/bin/with-livespec-env.sh --`;
status only from the ledger. Gate: `uv run pytest overseer -q`, then
`just check`.

**Verification discipline.** A FILED ITEM IS A CLAIM WITH A TIMESTAMP. AN EXIT
CODE THROUGH A PIPE IS THE LAST COMMAND'S (and `PIPESTATUS` is bash — this
shell is zsh; capture exits explicitly or write output to a file). A REJECTED
COMMIT LEAVES THE CHANGE STAGED — check `git status`, not `git log`. A FAILING
COMMAND IS NOT PROOF THE OPERATION FAILED — check the forge/artifact (C9). Run
a stale-state audit at startup before trusting anything you did not just
measure.

## Corrections

Corrections to THIS supervisor role's own behavior — append here. A record
that logs only the worker's mistakes is a wrong record. Regenerating this file
MUST preserve every entry below.

### First-hand, 2026-07-29 — from the seat that regenerated this file

- **C10 — I declared a wedged Codex job "alive and actively working" from a
  status render whose progress lines were more than an hour stale.** The peer
  agent measured the artifact (output-file growth) and was right; on the
  strength of my misread I cancelled its correct relaunch. Establish liveness
  from artifact growth (log mtime/size across a measured interval), never
  from a status surface — and before REVERSING a peer's action, re-verify the
  evidence the peer acted on, not your own prior belief.
- **C11 — the maintainer caught me stalled while I "waited correctly".** After
  delegating counsel reviews I parked on an agent relay I had already measured
  as unreliable plus a timer, while independent work (payload assembly, the
  next pipeline step) sat idle. The Codex result had been sitting finished for
  many minutes, fetchable in one command. Waiting on the least reliable link
  of an armed chain is a stall wearing diligence's clothes: poll the artifact
  the moment a dependency clears, and do all independent work while waiting.
- **C12 — I ended a turn reporting the worker's own exit plan as the armed
  wake, without verifying its producer existed.** The worker declared a bare
  `ready` with NO round open, expecting the daemon restart; no injection stamp
  existed, so `ready_valid` could never certify — the wake had no producer,
  and the pane sat rendering `restarting` outside attention until the
  maintainer asked why nothing was happening. Measured, then fixed: consumed
  the declaration (mirroring the daemon's restart semantics), respawned the
  pane, and filed the general defect as `overseer-4xfmez.7` plus the pending
  `uncertifiable-declaration-attention` proposed change. A worker's described
  wake mechanism is a CLAIM — certify it against the actual interlock before
  resting on it. (The incident is also live evidence FOR this thread's
  ratified contract; cite it, don't re-derive it.)

### First-hand, 2026-07-28 — from the seat that wrote the previous charter

- **C6 — I reported the worker as "minutes from filing" when it had already
  filed.** I read a mid-turn pane, inferred a future state from it, and told
  the maintainer a deadline that had already passed. The artifact was on
  `origin/master` the whole time. **Establish a worker's state from the
  artifact, never from a pane read**; the pane shows what it is narrating,
  not what has landed.
- **C7 — an armed re-entry whose wake event has no producer is not armed.**
  Diagnosed first-hand in a peer: `console-happy-path-mvp-supervisor` had TWO
  monitors correctly armed — all downstream of a session that could never run
  again. The charter rule "arm a re-entry" is satisfied by an unreachable
  condition. Name the event AND its producer before arming.
- **C8 — I tried to background a gate command and a hook stopped me.** A
  backgrounded gate plus a turn-end terminates the work mid-dispatch with
  nothing to re-invoke it. Gates run FOREGROUND with a raised timeout.
- **C9 — a merge command reported failure after the merge had already
  succeeded.** `gh pr merge` failed on its local branch-cleanup step; the
  merge itself had landed. **A failing command is not proof the operation
  failed** — check the forge.

### Carried forward (role-level, from `plan/supervisor-prompt-quality/supervisor-handoff.md` C1-C5 and `plan/archive/ship-overseer-to-fleet/supervisor-handoff.md`)

- **C1 — trusting `tmux has-session`, asserting a session existed that did
  not.** It prefix-matched `<worker>-supervisor`, and the follow-on `ps` then
  reported the supervisor's OWN agent as the worker's driver. Fix: `grep -qx`,
  `-t '=name:'`, and the distinct-`pane_pid` check. Generalize: when a check
  passes, confirm it can also FAIL before believing it.
- **C2 — a containment check that false-passed on an empty string.**
  `readlink -f ""` returns the cwd with exit 0. Fix: guard non-empty BEFORE
  resolving, and `readlink -f --`.
- **C3 — aborting a paste on a picker that had closed minutes earlier.**
  `capture-pane -S -15` returns scrollback PLUS the visible pane. Fix:
  bounded, visible-only capture.
- **C4 — a watcher that false-woke on its own prose about false wakes.** A
  substring scan matched a brief that merely QUOTED the string. Fix: anchor
  positionally. Generalize: a detector whose pattern can appear in the text it
  reads is self-triggering.
- **C5 — C4's fix was itself under-anchored, and the worker caught it.** A
  start-of-line anchor still fires on a wrapped continuation line. Fix: anchor
  BOTH ends. Third iteration of one bug — C3 fixed SCOPE, C4 SPECIFICITY, C5
  EXTENT — because each fix was verified only against the case that exposed
  the previous one. Generalize: test a corrected detector against a FRESH
  adversarial case.
- **Ending a turn with the worker mid-flight and no armed re-entry.** The
  thread stopped until the maintainer intervened. An intention is not a
  mechanism.
- **Reporting ripe maintainer valves as a prose list instead of asking them.**
  Four sat unasked until the maintainer objected.
- **Inventing gates.** Asserting a path was maintainer-only without testing
  it; treating an enumerated merge grant as a fence; asking non-blocking
  questions. Each felt like caution and was a stall with better manners.
- **Calling a negative inside the window.** Scheduled forge runs on this
  account fired between +50 and +230 minutes past their cron target. Any "did
  it fire?" check inside four hours is not evidence of a miss.
- **Reading a local checkout instead of the forge** while verifying, and
  reporting a green run as a silent failure on the strength of it.
- **Relaying a ledger item's summary instead of testing it against a
  measurement just taken.**
- **A supervisor writing a command into a brief has not verified that
  command.** Prefer naming the operation and its intent, or run it yourself
  first.
- **Reflexively delegating an instruction addressed to the supervisor.** Read
  who the instruction names.
