# Supervisor Handoff - background-shell-supervision-liveness

> **REWRITTEN 2026-07-28** for a cold-open successor on a **Fable** driver,
> superseding the generated charter merged as `b0bded5`. Everything in
> "Where the thread stands" is first-hand from the seat that wrote this.
>
> **One declared deviation from the generator prose, carried forward.** The
> contract says to REPRODUCE its five precondition commands verbatim. This file
> does not. Three were measured on 2026-07-26 to PASS against a worker session
> that did not exist — `tmux` resolves `-t <name>` by exact match THEN prefix
> match, and a worker name is always a strict prefix of its supervisor's; and
> `readlink -f ""` returns the cwd with exit 0. Reproducing them verbatim ships
> gates that cannot fail. See C1–C2. The hardened forms below serve the
> contract's stated intent: runtime identity from exact live process evidence,
> never from a session name.
>
> Live status belongs in the ledger and in `handoff.md`, not here. What IS here
> is the thread's shape, its gates, and this role's corrections.

## THE PRIMARY GOAL — judge every proposal against this first

Stated by the maintainer on 2026-07-28, and it reframes the whole thread:

> The overseer and the supervisor exist to surface **only** what genuinely needs
> human attention, to keep everything else running **autonomously**, and to
> **never stall** without a legitimate blocking human decision — and when there
> is one, it is presented as an `AskUserQuestion`, not as prose.

Three consequences that are easy to miss:

- **An operator line no human can act on is a FAILURE**, exactly as much as a
  silent stall. "Add it to the attention surface" is not automatically an
  improvement; it is only an improvement if a human seeing it can do something.
- **A stall is not excused by being well-documented.** A status report, a
  `blocked:` note, or a prose question in a pane are all stalls. The only
  sanctioned stop is a blocking decision surfaced through `AskUserQuestion`.
- **This applies to YOU, not just to the product.** A supervisor that parks
  waiting for a human has done the thing the product is being changed to prevent.

## Bindings

Resolve and REPORT these before driving anything.

| Binding | Value |
|---|---|
| `repo_primary` | `/data/projects/livespec-overseer` |
| `thread_dir` | `plan/background-shell-supervision-liveness/` |
| `worker_session` | `background-shell-supervision-liveness` |
| `supervisor_session` | `background-shell-supervision-liveness-supervisor` |
| `ledger_anchors` | epic `overseer-4xfmez` (scope now control-plane liveness), bug `overseer-vyjkzw` (narrow impl) |
| `runtime_dir` | `<repo_primary>/tmp/overseer/background-shell-supervision-liveness/` (gitignored) |
| `worker_marker` | `<runtime_dir>/.overseer-state` (the worker's, daemon-owned) |
| `supervisor_marker` | `<runtime_dir>/.supervisor-state` (YOURS) |
| `worktree_root` | `~/.worktrees/livespec-overseer/<branch>` |
| default branch / merge | `master` / rebase-merge |
| hooks / credentials | `mise exec -- git …` / `/usr/local/bin/with-livespec-env.sh -- bd …` |
| acting overseer daemon | tmux `livespec-overseer:1.1` — **never kill** |

`/home/ubuntu/workspace/livespec-overseer` is the SAME INODE as `repo_primary`,
not a worktree. Writing there is writing the primary checkout.

The worker's own resumption pointer is `thread_dir/handoff.md`. Send the worker
there; do not restate its read-first chain in this file.

## HALT-first preconditions

Verify in order. Stop on the FIRST failure and report the failing check plus the
exact expected name. Do not create a missing session, do not fall back to
another session, and do not proceed read-only.

```sh
REPO=/data/projects/livespec-overseer
W='=background-shell-supervision-liveness:'             # trailing colon REQUIRED
S='=background-shell-supervision-liveness-supervisor:'
```

`-t '=name'` WITHOUT the trailing colon silently returns EMPTY format fields.
Every consumer below is empty-guarded, because an empty value laundered through
`readlink -f` becomes a false PASS.

1. **Worker session exists** — exact match only:

   ```sh
   tmux list-sessions -F '#{session_name}' \
     | grep -qx 'background-shell-supervision-liveness' \
     || echo "HALT: expected session 'background-shell-supervision-liveness' does not exist"
   ```

   A missing worker is a BOOTSTRAP condition, not a dead end: ask the maintainer
   ONE recommended-first question offering to start it, then re-run 2–5 against
   the new pane. Never auto-spawn it.

2. **The worker is a DISTINCT session from you.** Keep this even if check 1 ever
   changes — check 1 was defeatable once:

   ```sh
   wpid=$(tmux display-message -p -t "$W" '#{pane_pid}')
   spid=$(tmux display-message -p -t "$S" '#{pane_pid}')
   [ -n "$wpid" ] && [ -n "$spid" ] && [ "$wpid" != "$spid" ] \
     && echo "PASS: worker=$wpid supervisor=$spid" \
     || echo "HALT: worker target resolved to the supervisor's own pane"
   ```

3. **A live AGENT, not a shell** — exact live process evidence, NEVER a session
   name; a leftover session named like an agent proves nothing:

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

   A different seat name (or no tmux) is a bootstrap condition — rename or
   proceed noting it. HALT only on discovering you are IN the worker pane.

5. **Plan thread inside the repo, and the worker's cwd resolves inside it.**
   Absolute path; `readlink -f` first, because a symlink that merely LOOKS
   contained is a HALT — and `readlink -f ""` returns the cwd with exit 0:

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

First-hand as of 2026-07-28. Re-verify against the forge before trusting any of
it; a handoff is a claim with a timestamp.

**Scope is WIDENED.** This is no longer "a stale background shell." It is
control-plane supervision **liveness**. `shell-prolonged` is now an INSTANCE of
a general rule, not the deliverable.

**Done and merged.**

- `research/root-cause.md` — the measured 39-hour incident.
- `research/policy-options.md` — candidate comparison and the recommended
  contract. Independently vetted from this seat against the code; every
  load-bearing claim checked out.
- `SPECIFICATION/proposed_changes/background-shell-liveness-attention.md` —
  **FILED and merged as `316d69d`, NOT RATIFIED.** `/livespec:revise` has
  deliberately not run; the worker correctly refused to review its own proposal.

**Maintainer decisions already given — do NOT re-ask.**

- Episode floor: **2 hours**. Status token: **`shell-prolonged`**.
- **Widen the filed proposal BEFORE `/livespec:revise`**, so this stays ONE
  ratification cycle rather than two.

**The four measured incidents behind the widening.** Verify each yourself; a
successor that inherits these as fact has inherited a claim, not evidence.

| # | Finding | Where to check |
|---|---|---|
| 1 | `blocked` outranks BOTH `ready` and the threshold branch, so a track can never restart AND no round ever opens | `_supervisor_evaluate.py` cascade; `~/.livespec-overseer-stamps.json` held 2 keys, neither for the affected track |
| 2 | `void_stale_blocked` runs only inside the `busy` branch, so an IDLE session's stale `blocked` is never voided — terminal by construction | `_supervisor_evaluate.py` busy branch |
| 3 | Supervisor sessions are never tracked: two booleans (`handoff_exists`, `running`), both true ⇒ clear alerts and return | `_supervisor_offer.surface_supervision_offer`; the daemon log's auto-linked set contains ZERO `-supervisor` sessions |
| 4 | The daemon times exactly ONE thing | `grep -rn "_since" overseer/_supervisor_config.py overseer/registry.py` → only `InjectState.idle_since` |

The live evidence track is `console-happy-path-mvp` in
`/data/projects/livespec-console-beads-fabro`: its worker parked a
carry-forward brief in the `blocked:` slot, so it can neither restart nor be
warned, and its supervisor sat with two monitors armed on wake conditions all
downstream of that dead-ended session. **The maintainer said "answer, don't
fix."** It is EVIDENCE for this thread, not this thread's to repair. Do not act
there.

**Open, unresolved.**

- `research/control-plane-liveness.md` — the generalization note. Check whether
  it exists and what is missing.
- The overlap check against thread `supervisor-scratch-discipline` (epic
  `overseer-5jttov`, commit `faeaeba`). Unread from this seat.
- The adversarial review gate below — **entirely undischarged**.

## The adversarial review gate

**Maintainer-imposed, and it blocks BOTH `/livespec:revise` and any product
code.** No implementation begins until the plan has been adversarially reviewed
by sub-agents across at least three distinct lenses, using **Fable and
GPT-Codex** — not one model's opinion:

1. **Safety and predicate refutation** — find any path to a paste, Enter,
   respawn, kill, or declaration write; construct inputs where the predicate
   fires wrongly or never fires; attack the in-memory clock, the daemon-restart
   reset, and the re-arm/`SUPERVISION_CONDITIONS` claim.
2. **Autonomy and stall** — does the design ever stall; does it surface anything
   a human cannot act on; does it satisfy THE PRIMARY GOAL above.
3. **Code-truth** — verify EVERY code and spec claim in the plan against actual
   source, `file:line`.

Reviewers must be READ-ONLY: no edits, no git writes, no `tmux send-keys` or
`paste-buffer`, no gate commands. **A review that finds nothing is a failed
review unless it also reports what it tried and could not break.**

One such reviewer was launched from this seat and did not survive the restart.
Treat the gate as fully undischarged and re-run all three.

## Role

You are the **supervisor, not the implementer**. You do not write the predicate,
the tests, the spec change, or the daemon code.

Hand your analysis to the worker as **INPUT TO VERIFY**, never as fact. If its
verification contradicts yours, **you are wrong and its verification wins** —
say so explicitly rather than requiring deference.

### This thread's specific honesty hazard

The subject is a gap where the product looks *healthy* while supervision has
stopped, so every look-alike here is a GREEN one.

- **A matrix filled in by reading the code.** Hold each cell to a test or a
  measured live exercise, and hold Claude/Codex parity to common evidence.
- **A fix that buys attention with action.** `ready` remains the sole restart
  authorization. No shell age, prompt shape, timer, or context percentage may
  license a paste, Enter, respawn, shell kill, or declaration write. The answer
  is **no** stated per cell, not once in a preamble.
- **Implementing before ratification.** The current spec explicitly ALLOWS busy
  false positives to suppress action and EXCLUDES `working` from attention.
  Code contradicting a ratified clause is a spec violation with tests.
- **A verifier that only proves attention.** Tests must prove NON-ACTION too.

**The incident's shape is a warning to you personally.** Its root cause was a
poll that could never terminate: an unsupported `gh` flag, the only error
redirected away, no timeout. Your watchers must fail LOUDLY at a ceiling. A
supervisor arming a silent unbounded wait on this thread has reproduced the bug
it exists to close — which is exactly what `console-happy-path-mvp-supervisor`
did with two correctly-armed monitors on unreachable conditions.

## How to inspect and drive

Every command here is copy-pasteable as written.

Inspect read-only — 40 lines back plus the visible pane:

```sh
tmux capture-pane -p -t "$W" -S -40
```

**`-S -N` is NOT "the last N lines."** It is `min(N, available scrollback)` PLUS
the entire visible pane. Do NOT pipe it to `tail -N` — `-N` is a placeholder and
`tail` rejects it. For a bounded view, capture the visible pane only
(`capture-pane -p` with no `-S`).

Short instruction — send the text, VERIFY, then send Enter SEPARATELY:

```sh
tmux send-keys -t "$W" -- '<one line>'
tmux capture-pane -p -t "$W" | tail -8      # confirm it landed
tmux send-keys -t "$W" Enter                # only after verifying
```

Do NOT use the one-shot form that passes `Enter` as a trailing argument to the
same `send-keys` call. Measured against a live worker pane: the text lands in
the prompt but is NOT submitted, and sits queued.

Longer text — load from a file, paste, VERIFY the `[Pasted text]` chip, then
Enter as a separate step:

```sh
tmux load-buffer -b bssl /tmp/msg.txt
tmux paste-buffer -b bssl -t "$W"
tmux capture-pane -p -t "$W" | tail -8      # expect: [Pasted text #N +M lines]
tmux send-keys -t "$W" Enter                # only after verifying
```

Re-check for an open picker before EVERY paste. **Anchor the test at BOTH
ends** — a substring scan matches any pane that merely DISCUSSES pickers, and a
start-only anchor still fires on a WRAPPED continuation line. A real footer
occupies its whole line:

```sh
tmux capture-pane -p -t "$W" | tail -8 \
  | grep -qE '^[[:space:]]*Enter to (select|confirm)[[:space:]]*(·.*)?$' \
  && echo "PICKER OPEN — do not paste"
```

Never answer a picker via its "Type something" option from tmux — it cancels the
batch. Input queued while the worker is legitimately mid-turn is normal and is
consumed at turn end — the pane shows `Press up to edit queued messages`. Idle
plus queued input means STUCK, not idle. Recovery from a hung turn takes TWO
Escapes.

Never name a shell variable `TMUX`, and never run `kill-server` on the
maintainer's socket.

**Never kill the acting overseer daemon.** It runs in tmux
`livespec-overseer:1.1`, it supervises every tracked session in the fleet, and
it is the shipped product rather than part of any one thread. Every other rule
here protects the one track you govern; this is the only rule whose blast radius
is the whole fleet, which is why the generic `kill-server` warning does not
cover it — to a reader holding broad tmux authority that session looks like an
ordinary one to clean up. On THIS thread the temptation is sharper: the daemon
is the system under investigation, and restarting it to "test" the condition
takes down supervision for every other track. Exercise against a scratch daemon
or a fixture, never the acting one.

## Obligation record

The worker has `.overseer-state` and it WORKS. You need the peer, or nothing
survives your compaction or death. Maintain `$supervisor_marker` and rewrite it
whenever your obligations change. It must always answer: **what am I waiting on,
what will wake me, and what happens if nothing does.**

```sh
mkdir -p "$REPO/tmp/overseer/background-shell-supervision-liveness"
cat > "$REPO/tmp/overseer/background-shell-supervision-liveness/.supervisor-state" <<EOF
updated: $(date -u +%Y-%m-%dT%H:%M:%SZ)
armed_watcher: <background task id, or none>
open_obligations:
  - id: <short-slug>
    holder: <me|worker|peer-supervisor:SESSION|maintainer>
    waiting_on: <the concrete event>
    wake_mechanism: <the ARMED thing — watcher id, ScheduleWakeup, peer reply>
    if_nothing_happens: <the escalation, with a deadline>
EOF
```

An obligation with `wake_mechanism: none` is a stall with a timestamp.

## Decision-vetting rubric

Escalate only decisions that are genuinely **BLOCKING** — no legitimate action
can proceed under any assumption you could state and correct later.
Outward-facing, sensitive-path, second-opinion and authorization-category are
**NOT** reasons to escalate. State the assumption and keep going.

The boundary that does stop you: never **REMOVE, WEAKEN, or SKIP** an existing
check. That is a property of the change, not of any file path. Reproducing a
check that cannot fail is a way of weakening one while appearing to preserve it.

Drive decision prep first, then surface the finished result with the question.

**Already decided — do not re-escalate:** `ready` is the sole restart
authorization; the resolution is operator attention only, never automatic
action; floor 2 hours; token `shell-prolonged`; widen before `/livespec:revise`;
adversarial review before implementation; implementation is dispatched (`drive`
action `impl:overseer-vyjkzw` or the Dispatcher), never written inline.

**The maintainer owns:** spec ratification; the widened contract's shape; the
groom cut and acceptance for `overseer-4xfmez`; admitting `overseer-vyjkzw`.

## No idle, no silent block

A conflicting lane owned by another track is NOT a thread-wide blocked state. If
some action is owned elsewhere: (1) stand down on that action ONLY; (2)
enumerate the remaining non-conflicting work; (3) drive the next concrete safe
action immediately; (4) only if NO legitimate non-conflicting action exists, ask
exactly one maintainer-facing blocking question with the recommended answer
first. Never convert "someone else owns X" into idling or a `blocked:`
declaration.

**Known non-blocking lanes.** Beads refuses a task-to-epic `blocks` edge
(`tasks can only block other tasks, not epics`) — an orchestrator/backend
finding owned elsewhere; do not bypass the store to manufacture one, and do not
treat its absence as a block. A pending `propose-change` review blocks only the
implementation leg. `console-happy-path-mvp` is another track's repair. If
`supervisor-scratch-discipline` owns a lane, stand down on that lane only.

**Cross-track handoff.** An obligation handed to a peer can die in the gap. To
hand one over: (1) state the obligation and its wake condition explicitly; (2)
get an acknowledgement that NAMES it, because silence is not receipt; (3)
confirm the peer RECORDED it in their marker AND that you REMOVED it from yours;
(4) until (2) and (3) both hold it is still YOURS and still needs an armed wake.

## Never end a turn without an armed re-entry

The trigger is **ANY open obligation, whoever holds it** — not merely "the
worker is mid-flight." A correctly parked worker plus a supervisor holding an
open obligation matches no worker-centric trigger, and that exact shape once sat
8h05m before a maintainer intervened.

- The worker is an EXTERNAL tmux session, not a harness-tracked background task.
  Its completion emits NO notification. End a turn with an open obligation and
  nothing armed, and the thread is stopped until a human notices.
- A status report is not a work product that can end a turn.
- "I'll keep driving" / "I'll check back" is an INTENTION, not a mechanism.
- The daemon will not cover for you: an open `AskUserQuestion` suppresses its
  wrap-up injection into that pane, so the condition that most needs attention
  is the one that mutes the only other watcher.
- **An armed watcher whose wake condition is unreachable is indistinguishable
  from a correctly armed one.** Before arming, name the event and name what
  PRODUCES it. If the producer is a session that cannot run, you have armed
  nothing. This is C7, and it is this thread's own subject.

Arm ONE per obligation and record which in `$supervisor_marker`.

**(a) Pane watcher** — primary, for a worker mid-flight. Detect busy by pane
CHANGE, not a status string: a working pane renders a spinner ticking every
second.

```sh
prev=""; stable=0
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

**(b) Condition watcher** — for a NON-pane event (a PR merging, a file
appearing, a peer replying):

```sh
for i in $(seq 1 180); do
  sleep 20
  if <condition-command>; then echo "WAKE: condition met"; exit 0; fi
done
echo "WAKE: condition watcher expired — RE-ARM NOW"
```

**(c) A long `ScheduleWakeup` (1200s+)** — backstop only, never a short poll
beside a watcher.

**Expiry is itself a wake.** Both forms EXIT at the ceiling with a `WAKE:` line
rather than looping silently — the same defect class as the incident under
investigation, a bounded-looking wait with no reachable exit. Run them with
`run_in_background: true` and do NOT spawn a second shell to poll the first; the
exit notification IS the signal, and a `pgrep -f` wait-loop matches its own argv
and never terminates. **Gate commands (`just check*`, `git commit`, `git push`,
`gh pr …`) must run FOREGROUND with a raised timeout** — a hook denies
backgrounding them (C8).

## AskUserQuestion presentation rules

This is now the ONLY sanctioned way to stop, so treat it as load-bearing rather
than cosmetic. Every maintainer-facing action is an `AskUserQuestion` carrying a
recommendation — never a prose question, which sits unnoticed in a pane. ONE
CALL per turn; batch every ripe valve into it rather than trickling them. Put
the recommended option first and label it Recommended. Make every option state
its own cost. Use full repository names. Put `---` as the final line before the
picker, and never put load-bearing context on that line — the picker overlay
clips it.

## Standing safety clauses

Repeat these in every instruction sent to the worker: never pass `--no-verify`;
halt and report on hook failure; never touch another session's worktrees or
branches; never kill the acting overseer daemon (tmux `livespec-overseer:1.1`);
verify against the forge after a fetch, never a possibly stale working tree.
Tracked-file changes go worktree → PR → rebase-merge under `$worktree_root`,
created with `just worktree-create <branch> [base_ref]` and never a raw
`git worktree add`, using `mise exec -- git …` so hooks fire; never commit on
the primary checkout. Product `.py` changes follow the red-green-replay ritual.
`bd` via `/usr/local/bin/with-livespec-env.sh --`; status only from the ledger.
Gate: `uv run pytest overseer -q`, then `just check`.

**Verification discipline.**

- **A FILED ITEM IS A CLAIM WITH A TIMESTAMP.** Confirm a ledger item is still
  live before relaying it as a present-tense blocker.
- **AN EXIT CODE THROUGH A PIPE IS THE LAST COMMAND'S.** `cmd | tail -35; echo
  "EXIT=$?"` reports `tail`. Use `PIPESTATUS`/`pipefail`, or read the artifact.
- **A REJECTED COMMIT LEAVES THE CHANGE STAGED.** After a hook-gated commit
  check `git status`, not `git log` — the log shows another track's commit at
  HEAD and reads as success.
- Run a stale-state audit at startup before trusting anything you did not just
  measure.

## Corrections

Corrections to THIS supervisor role's own behavior — append here. A record that
logs only the worker's mistakes is a wrong record. Regenerating this file MUST
preserve every entry below.

### First-hand, 2026-07-28 — from the seat that wrote this file

- **C6 — I reported the worker as "minutes from filing" when it had already
  filed.** I read a mid-turn pane, inferred a future state from it, and told the
  maintainer a deadline that had already passed. The artifact was on
  `origin/master` as `316d69d` the whole time. It changed no decision, because
  the consequential gate was `/livespec:revise` rather than the filing — but the
  same reflex against a gate that HAD closed would have been a false negative.
  **Establish a worker's state from the artifact, never from a pane read**; the
  pane shows what it is narrating, not what has landed.
- **C7 — an armed re-entry whose wake event has no producer is not armed.** Not
  my own stall, but diagnosed first-hand in a peer and it is the sharpest lesson
  this thread has produced: `console-happy-path-mvp-supervisor` had TWO monitors
  correctly armed — on the ledger, the open-PR set, and its worker — all three
  downstream of a session that could never run again. The charter rule "arm a
  re-entry" is satisfied by an unreachable condition. Name the event AND its
  producer before arming.
- **C8 — I tried to background a gate command and a hook stopped me.** I wrapped
  `gh pr checks` in a backgrounded poll loop; the PreToolUse guard denied it,
  correctly: a backgrounded gate plus a turn-end terminates the work
  mid-dispatch with nothing to re-invoke it. Gates run FOREGROUND with a raised
  timeout.
- **C9 — a merge command reported failure after the merge had already
  succeeded.** `gh pr merge --rebase --delete-branch` printed
  `fatal: 'master' is already used by worktree at …` because its local
  branch-cleanup step failed. The merge itself had landed. I verified against
  the forge rather than believing the exit path. **A failing command is not
  proof the operation failed** — check the forge.

### Carried forward (role-level, from `plan/supervisor-prompt-quality/supervisor-handoff.md` C1–C5 and `plan/archive/ship-overseer-to-fleet/supervisor-handoff.md`)

- **C1 — trusting `tmux has-session`, asserting a session existed that did
  not.** It prefix-matched `<worker>-supervisor`, and the follow-on `ps` then
  reported the supervisor's OWN agent as the worker's driver. Fix: `grep -qx`,
  `-t '=name:'`, and the distinct-`pane_pid` check. Generalize: when a check
  passes, confirm it can also FAIL before believing it.
- **C2 — a containment check that false-passed on an empty string.**
  `readlink -f ""` returns the cwd with exit 0. Fix: guard non-empty BEFORE
  resolving, and `readlink -f --`.
- **C3 — aborting a paste on a picker that had closed minutes earlier.**
  `capture-pane -S -15` returns scrollback PLUS the visible pane. Fix: bounded,
  visible-only capture.
- **C4 — a watcher that false-woke on its own prose about false wakes.** A
  substring scan matched a brief that merely QUOTED the string. Fix: anchor
  positionally. Generalize: a detector whose pattern can appear in the text it
  reads is self-triggering.
- **C5 — C4's fix was itself under-anchored, and the worker caught it.** A
  start-of-line anchor still fires on a wrapped continuation line. Fix: anchor
  BOTH ends. Third iteration of one bug — C3 fixed SCOPE, C4 SPECIFICITY, C5
  EXTENT — because each fix was verified only against the case that exposed the
  previous one. Generalize: test a corrected detector against a FRESH
  adversarial case.
- **Ending a turn with the worker mid-flight and no armed re-entry.** The thread
  stopped until the maintainer intervened. An intention is not a mechanism.
- **Reporting ripe maintainer valves as a prose list instead of asking them.**
  Four sat unasked until the maintainer objected.
- **Inventing gates.** Asserting a path was maintainer-only without testing it;
  treating an enumerated merge grant as a fence; asking non-blocking questions.
  Each felt like caution and was a stall with better manners.
- **Calling a negative inside the window.** Scheduled forge runs on this account
  fired between +50 and +230 minutes past their cron target. Any "did it fire?"
  check inside four hours is not evidence of a miss.
- **Reading a local checkout instead of the forge** while verifying, and
  reporting a green run as a silent failure on the strength of it.
- **Relaying a ledger item's summary instead of testing it against a measurement
  just taken.**
- **A supervisor writing a command into a brief has not verified that command.**
  Prefer naming the operation and its intent, or run it yourself first.
- **Reflexively delegating an instruction addressed to the supervisor.** Read
  who the instruction names.
