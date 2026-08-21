# Overseer — maintenance guide (for the developer editing it)

This is guidance for **editing the overseer**, not for running it. It is a
DIFFERENT document from the runtime operator contract:

- `.claude-plugin/prose/overseer.md` = the overseer **at runtime** ("when
  invoked, do X"). **(Corrected 2026-07-26: this pair used to name `SKILL.md`
  on both counts. Since the prose was extracted, `overseer/SKILL.md` is a
  15-line compatibility pointer that explicitly says "Do not add behavior or
  operator prose here" — so a reader sent there for the runtime contract lands
  on a stub.)**
- this file = guidance for the developer **changing** the overseer ("when you
  change X, preserve invariant Y, watch gotcha Z, verify via W").

The overseer is a **deterministic multi-track supervisor**: a stdlib-Python
daemon (`supervisor.py`, the top pane) that watches parallel livespec plan
tracks across tmux sessions, plus a thin interactive Claude bottom pane
(`.claude-plugin/prose/overseer.md`). The daemon acts and renders a live table; it holds NO semantic
judgment. Every "am I done / blocked?" decision is made by the tracked
session's own LLM and expressed out-of-band on the filesystem — ONE state file
(`<repo>/tmp/overseer/<topic>/.overseer-state`) holding one of three values
(`ready` / `blocked: <reason>` / `winding-down`); the daemon only pattern-matches
deterministic tmux signals and that file.

## Why it exists / history

Two prior failure modes shaped this design, and they MUST NOT recur:

1. **Inline-worker context blowup.** A session ran the overseer window as an
   inline worker (did the track work itself), blew up its own context, and
   autocompacted. → The mechanics now run in a dumb, token-free Python process
   that cannot blow up a context; the interactive pane stays thin.
2. **Frozen top-pane snapshot.** A `/clear` does not kill tmux panes, so a prior
   overseer's dashboard kept rendering an hours-old "everything idle" snapshot
   while nothing was live. → The table is re-rendered from live captures every
   tick (and time-stamped), so it can never freeze on a stale snapshot.

Status: **PERMANENT** — a human-supervised alternate to autonomous mode (the
Beads/Dolt + Fabro Dispatcher / dark factory), not a stopgap awaiting a
replacement. The two are standing peers: autonomous mode runs *ready work-items*
unattended through the ledger; the overseer keeps *interactive plan tracks*
moving in parallel under a human driver, automating only the context-% wrap-up +
restart mechanics. Maintain it in place. It now lives in the standalone
`livespec-overseer` control-plane-tool repo, has its own `SPECIFICATION/`, and
participates in the livespec fleet as an ordinary pin-consuming member. Do NOT
copy it back into livespec core, the plugin, or the copier template.

## Loop-Parked Factory Dispatch

When a tracked session may end its turn with `ScheduleWakeup` / dynamic `/loop`,
multi-minute Fabro dispatch must not depend on the harness's background Bash
task tracker. The old `run_in_background: true` plus task-notification pattern
is retired for this shape: measured 2026-08-16 (`overseer-za32`), those
background tasks are reaped about 6-15s after loop parking, silently killing
the dispatcher.

Use the repo helper and make the disk verdict the record:

```
run_dir="$PWD/tmp/overseer/detached-dispatch/<item>-$(date -u +%Y%m%dT%H%M%SZ)"
scripts/detached-dispatch.sh "$run_dir" -- \
  python3 /absolute/path/to/drive.py --action impl:<id> ...
```

`scripts/detached-dispatch.sh` launches the command with `setsid` + `nohup`,
writes combined output to `$run_dir/output.log`, writes the launcher pid to
`$run_dir/pid`, and atomically replaces `$run_dir/verdict.env` with
`status=succeeded|failed` plus `exit_code=N` when the command exits. A parked
session should arm a wake, then read the disk files and the normal Fabro/forge
surfaces on wake; a task-notification is not the completion record.

## Launch Profile Preservation

Restarts preserve the runtime launch profile recorded for the tracked session,
not just the topic name. The daemon captures and refreshes each track's
`model_profile` from live process state, then restart/recovery planning in the
`_supervisor_launch_profile*` tree re-asserts the recorded harness, model, and
wrapper. Enumerate the current modules from the tree before editing this
subsystem; this paragraph names the behavior, not a complete inventory.
The current split keeps live `/proc` capture in
`_supervisor_launch_profile_capture.py` and command/env planning in
`_supervisor_launch_profile.py`; keep that boundary when changing only one side.

The bare Claude command (`claude --dangerously-skip-permissions -n <topic>`) is
only the fail-soft path for a mapping row with no recorded profile. A profile
with no wrapper relaunches with `--model <model>`; a wrapper profile relaunches
through the wrapper and sets the recorded model in the controlled environment.
Every profile-aware relaunch SETS OR SCRUBS the controlled Claude environment
(`ANTHROPIC_MODEL`, `ANTHROPIC_SMALL_FAST_MODEL`,
`CLAUDE_CODE_DISABLE_1M_CONTEXT`, `CLAUDE_CODE_MAX_CONTEXT_TOKENS`) so stale
inherited values cannot silently change the runtime/model. A stale or corrupt
profile is a surface-and-skip condition, never permission to fall back to a bare
default launch.

### How the WRAPPER half of a profile is captured — and the cross-repo contract it rests on

The model half of a profile is read from the supervised process itself
(`--model` in argv, else `ANTHROPIC_MODEL` in its environ). The wrapper half
cannot be, and the reason is worth holding onto because two P1s came out of
getting it wrong.

**A wrapper leaves no process to find.** Every canonical wrapper in repo
`local-llm` ends in `exec`, which REPLACES the wrapper's process image with the
client's. So by the time the daemon looks, there is no wrapper anywhere in the
parent chain — the exec'd `claude` hangs directly off the tmux server — and even
if a wrapper process did survive, its `argv[0]` is `/bin/bash` and the
shell filter would skip it. Walking parents for the wrapper therefore CANNOT
work for the wrappers this fleet actually ships. Confirmed live on a real
tracked pane 2026-08-19.

**So the wrapper identifies itself in the environment, which survives `exec`.**
Each wrapper exports `LIVESPEC_LOCAL_LLM_WRAPPER` with its own resolved ABSOLUTE
path immediately before its `exec`, and `_wrapper_from_local_router` reads that
key first. The parent-chain walk remains only as a fallback for a hypothetical
non-`exec` wrapper; it is not the path the shipped ones take.

**THIS IS A CROSS-REPO CONTRACT, and it is the fragile part.** The exporting
side lives in repo `local-llm` (`bin/claude-local-llm`, `bin/codex-local-llm`,
`bin/pi-local-llm`, documented under its `SPECIFICATION.md` §"Client wrapper
contract"). Nothing in THIS repo can enforce it, and no test here can reach that
repo. If someone drops or renames that export, wrapper capture does not error —
it silently falls through to the parent chain, finds nothing, and records
`wrapper: null`. A local track then relaunches on the **cloud** arm with the
Anthropic env scrubbed and a local model token the cloud API will reject. That
is the exact defect this subsystem was built to prevent, re-created silently.

The read stays **one-directional**: this repo reads a marker `local-llm`
publishes and never writes to it. When changing either side, change the
documentation on both.

**Do not "fix" a capture problem by asking `local-llm` to stop using `exec`.**
That was considered and rejected: the daemon must read what is actually there.

**A hardcoded path table is not an acceptable substitute either**, and the
reasoning is recorded because it looked reasonable for one release. Keying a
wrapper path off the harness alone, reached whenever `ANTHROPIC_BASE_URL` is
merely non-Anthropic, mis-records a track pointed at ANY other proxy — and
because the hardcoded path exists on this host, the relaunch-time existence check
does not catch it, so it mis-launches instead of degrading safe. It was removed
outright rather than narrowed.


## The evaluate() state machine

`Supervisor.evaluate(track)` re-classifies each tracked session **from scratch
every tick** into exactly one status. Its only inputs are the pane capture, the
parsed `Ctx: N% left`, Claude's registry `status`, and the out-of-band
`.overseer-state` file (`ready` / `blocked` / `winding-down`, all
**session-written**). It is a **precedence cascade** — the FIRST matching guard
wins — not a persistent FSM: a session moves between statuses only by changing
those inputs (its own work, its own declaration, its context dropping). The
per-state side-effects (after the `·`) and the `(act)` guard fire ONLY when
`act=True` (the daemon loop); the read-only `list` path (`act=False`) classifies
without acting.

```mermaid
stateDiagram-v2
    direction TB

    [*] --> tick
    state "evaluate(track) — one tick" as tick

    tick --> unassigned: is_unassigned
    tick --> cGone: no managed pane (gone / foreign / shell)
    tick --> cBusy: live and ours

    state cGone <<choice>>
    cGone --> live_outside_tmux: live Claude, no tmux
    cGone --> session_gone: no live Claude

    state cBusy <<choice>>
    cBusy --> working: non-shell busy, or shell busy above threshold / with ready
    cBusy --> cGate: not busy, or shell-only eligible for low-context guard

    state cGate <<choice>>
    cGate --> blocked_human: gate or 'blocked'
    cGate --> cIdle: neither

    state cIdle <<choice>>
    cIdle --> settling: not idle-prompt
    cIdle --> cStream: empty idle prompt

    state cStream <<choice>>
    cStream --> working: still streaming (act)
    cStream --> cReady: settled

    state cReady <<choice>>
    cReady --> restarting: fresh 'ready'
    cReady --> cCtx: no valid ready

    state cCtx <<choice>>
    cCtx --> cBand: eff_ctx ≤ threshold
    cCtx --> cRoom: above threshold

    state cRoom <<choice>>
    cRoom --> idle_ctx_left: free to continue
    cRoom --> idle: Claude 'waiting' / prior declaration

    state cBand <<choice>>
    cBand --> winding_down: fresh ACK
    cBand --> danger: eff_ctx ≤ 20
    cBand --> warned: otherwise

    working: working  ·  voids stale blocked (ready stays armed)
    blocked_human: blocked:human  ·  alerts operator
    settling: settling  ·  wait, re-read next tick
    restarting: restarting  ·  _do_restart (ONLY path; runtime-dispatched claude/codex)
    warned: warned  ·  injects escalating wrap-up
    danger: danger  ·  alerts NOT RESPONDING, never restarts
    winding_down: winding-down  ·  ACK, stop re-warning
    idle_ctx_left: idle-with-context-left  ·  one keep-going nudge
    live_outside_tmux: live-outside-tmux  ·  unmanaged, not an alarm

    note right of idle_ctx_left
      One "keep going" nudge per idle episode. The daemon WRITES the
      idle-with-context-left marker to edge-trigger the nudge (its only
      self-authored token) and clears it when the session next goes
      non-idle, re-arming a later episode. A session genuinely waiting on
      a human writes `blocked: &lt;reason&gt;` instead.
    end note

    note right of restarting
      THE CARDINAL RULE: a respawn is reachable ONLY via a fresh
      session-written 'ready'. The daemon never infers it from
      idleness, a timer, or how low ctx has fallen.
    end note
```

Every branch is a leaf: the tick ends there and the next tick re-enters
`evaluate()` from the top. The cross-tick lifecycle a session actually walks is
`working → … → warned` (daemon injects the wrap-up) `→ winding-down` (session
ACKs) `→ restarting` (session declares `ready`) `→` a fresh `working` after the
respawn — each arrow driven by the SESSION's own declaration, never a daemon
guess. `unassigned` / `session_gone` / `live_outside_tmux` are structural pre-checks
(no live managed pane to read); `settling` is a one-tick "wait and re-read". The
diagram is drawn Claude-first, but **a Codex track is a full citizen
(maintainer-declared 2026-07-17)** and flows through the SAME branches with
runtime-appropriate mechanics: `is_codex_idle_input` (not Claude's `❯` box) drives its
`idle`, the wrap-up and keep-going nudge are pasted with a Codex submit-verify (the pane
goes busy, not an emptied `❯` box), and `restarting` dispatches to `codex resume <id>`
rather than the claude launch command (see invariant 7 and the load-bearing mechanics).
Discovery's live-session adoption is split into `_supervisor_discovery_adoption.py`,
and liveness attention keeps observation in `_supervisor_attention_observe.py` while
`_supervisor_attention.py` owns the status decision surface; keep those boundaries
cohesive when changing either path.
The `cGone` choice splits the no-managed-pane case: when there
is no pane the daemon can drive but a live Claude registry session for the topic is
running with NO tmux pane (a bare SSH shell), the row is the informational
`live-outside-tmux` (alive, but the daemon cannot capture/inject/respawn it) — NOT
the alarming `session-gone`, and it is kept out of the `NEEDS YOU` block. A live
session that resolves to a DIFFERENT tmux session stays `session-gone` (re-mapping
is a separate concern; `_live_session_outside_tmux`).

**`cGone` is reached THREE ways, and they must answer identically
(`_no_managed_pane_row`; 2026-07-16).** The mapped tmux session is gone; OR it survives
but its Claude **exited to a bare shell** (the ordinary end of a track's life); OR the
mapping points at a genuinely FOREIGN pane (another program, a Claude in a different
repo). All three are the same fact about the track — no pane the daemon can drive — so
all three route through the one helper (`session-gone`, or `live-outside-tmux` when a
live session for the topic runs with no tmux pane); only tmux housekeeping differs.
**`not_claude` is DELETED (maintainer-declared 2026-07-17: "What the hell is
not-claude?").** It was the identity gate's return value leaking into the UI — it named a
check's output, not anything an operator needs — and it made a bare terminal (`livespec1`)
look like a tracked pane. Do NOT reintroduce it. The identity gate (`_pane_is_managed`,
covering BOTH runtimes) is unchanged and still governs every ACT — the change was purely
what the operator is TOLD, never a relaxation; a shell / foreign pane is still never
pasted into. **Why it mattered:** reporting an exited-to-shell track as `not-claude` left
finished tracks sitting red in `NEEDS YOU` claiming a live tmux mapping (found live
2026-07-16: `fabro-ci-image-factoring` → `livespec1`, a bare zsh), and it skipped the
live-outside-tmux fallback entirely — hiding a Claude alive outside tmux behind an alarm.

Reading notes: `threshold` = the track's `ctx_threshold` override, else the
daemon-wide `warn_percent` (default 50). A malformed `.overseer-state` token is
surfaced as a row note and treated as **no declaration** (fail-closed) — it never
authorizes an ACT (restart / injection), though it is not inert: the `BAD state file`
note puts the row in `NEEDS YOU`, and (being a non-null `declared`) it suppresses the
keep-going nudge on an idle-above-threshold session, which then renders plain `idle`
(both the safe direction). Two act-only guards are folded for clarity: `cStream →
working` (drawn) skips a tick when an "idle" frame is still streaming, and an
identical post-settle identity re-check (not drawn) routes a pane that has
exited to a shell to `settling` (a one-tick "the pane changed under us"; the next
tick re-enters at the top gate and renders the settled `session-gone`). The `cRoom`
choice guards the
`idle-with-context-left` nudge: an idle session ABOVE threshold reaches it, and
takes the `idle_ctx_left` leg only when it is not `waiting` on a human and has
made no declaration of its own (or already carries the marker — so the nudge is
sent once, not every tick); otherwise it is a plain `idle` leaf. See invariant 9
for the marker's edge-triggered lifecycle.

## Architecture invariants that must not regress

1. **The supervisor owns mechanics only.** Semantic judgment ("am I done / am I
   blocked?") stays in the tracked session's LLM, expressed via the **out-of-band
   state file** — NEVER inferred from printed pane text (prompt-echo, model
   quotation, scroll, and line-wrap all corrupt pane text; see the adversarial
   review). If you ever find yourself parsing a "the session says it's done"
   sentinel out of a pane capture, stop — that is the exact anti-pattern the
   state-file protocol replaced.

   **The overseer NEVER touches files under `plan/`.** It touches ONLY its own
   config (the mapping store, the injection-stamp sidecar, the watch-set declaration)
   and temp files (`<repo>/tmp/overseer/<topic>/`). Everything under
   `plan/<topic>/` is the SESSION's own workflow — the overseer never reads,
   writes, or hashes it. Discovery enumerates `plan/*/` DIRECTORIES only and
   derives NO path into one; the resume line *points* the session at the plan's
   LEDGER-HELD PLAN STATE, named by repository path and by the `epic` id the
   mapping store records, which the daemon holds as an OPAQUE LOCATOR and never
   reads; markers live under `tmp/`, never `plan/`. The daemon `git check-ignore`-validates each watched repo's
   `tmp/overseer/` at startup (`Supervisor.unignored_tmp_repos`) and REFUSES to
   run if any is not gitignored, so a marker can never dirty a tracked tree. If
   you ever add code that opens, writes, or stats a FILE under `plan/`, stop —
   that violates this invariant.
2. **The overseer stays thin.** The interactive bottom pane never does track
   work inline and never polls the tracked sessions from the Claude pane on a
   timer. Watching is the daemon's job.
3. **Surface-only for UNASSIGNED plans.** The daemon NEVER auto-spawns a session
   for a plan that has none. Launching a plan is a deliberate act (`start`,
   user-initiated); a discovered plan with no session shows as `unassigned`,
   flagged ready to start — never started automatically. This scopes the FIRST
   launch ONLY. It is a DIFFERENT rule from invariant 7 (which governs whether an
   ALREADY-TRACKED session may be restarted, and answers: only on its own `ready`
   declaration). Neither one licenses the other: "surface-only" is not a reason to
   ignore a `ready` declaration, and invariant 7 is not a reason to spawn a
   session for an unassigned plan.
4. **Discovery-driven list; JSONL = mapping only.** The track list is
   re-discovered from each watched repo's `plan/*/` every tick. The JSONL store
   (`~/.livespec-overseer.jsonl`) holds ONLY facts that cannot be rederived from
   the filesystem (topic↔tmux mapping, custom resume line, threshold override).
   Do NOT regress to a hand-maintained plan list.
5. **Cross-repo by construction; sessions are named after the BARE plan topic
   (maintainer-declared 2026-07-19).** Rows are repo-scoped, but a tmux session is
   named after its **bare plan topic** (`registry.tmux_id` → `<topic>`), because
   that is the name the operator reads and navigates by — NOT the old
   repo-qualified `<repo-slug>--<topic>`. A repo prefix is added ONLY on a genuine
   cross-repo collision — when the SAME topic exists in ≥2 watched repos
   (`registry.colliding_topics`, computed from discovery) — and then as
   `<repo-slug>-<topic>` with a **single** dash (the double-dash form is retired).
   tmux session names are global while topics are unique only per repo, so the
   single-dash prefix disambiguates exactly the clashing topics and nothing else.
   The collision set is recomputed each tick and cached on `self.colliding_topics` (set at
   the top of `build_rows`, before adopt / auto_link / evaluate), and threaded into
   every session-name derivation (`_session_of`, `auto_link`) plus the CLI
   (`_cli_colliding` for `add` / `start`) so a session is named identically wherever
   it is derived. Never hardcode `/data/projects/livespec`. The daemon's per-tick
   `auto_link` links a live session to a discovered plan ONLY when the derived
   session (bare topic, or `<slug>-<topic>` on collision) exists AND its
   `#{pane_current_path}` resolves inside the row's repo — the cwd check, not the
   name, is what prevents two repos sharing a topic from cross-linking.
6. **Two-pane bootstrap + `adopt` (the `/overseer` startup, 2026-07-13).** The
   skill resolves and runs the `overseer-start` executable FIRST — and ONLY the
   skill does: it is skill-invoked, never a standalone launcher, and does NOT
   start Claude or Codex (it splits the daemon pane beside the SAME agent session
   that ran `/overseer`, which then resumes in the bottom pane). So it REFUSES
   before splitting unless process ancestry shows a supported Claude Code or
   Codex runtime — a hand-run from a plain terminal would otherwise leave a
   daemon pane + a bare-shell bottom pane (no agent), the exact broken state that
   guard prevents. It (a) detects the skill's OWN pane via `$TMUX_PANE`
   (Claude Code and Codex inherit it — do NOT re-derive tmux membership by hand;
   that improvisation is what falsely reported "not inside a tmux window" and grabbed a
   separate session), (b) splits THAT window
   (`tmuxio.split_window_top` targeting `$TMUX_PANE`, idempotent via a pane titled
   `overseer-daemon`) to run `overseerd` in a TOP pane while focus stays on the
   bottom pane, and (c) runs `Supervisor.adopt_sessions`. **`adopt` matches each
   live Claude session's registry `name`** — NOT the tmux session name (those are
   generic: `livespec`, `livespec1`), NOT the `#{pane_title}` terminal title
   (Claude DRIFTS it to a task summary), and NOT a screen-scrape of the input-box
   border (which vanishes whenever the pane shows a prompt — the failure that
   retired the border scrape). Claude Code writes each session's display `name` +
   `cwd` (+ live `status`) to `~/.claude/sessions/<pid>.json`; the maintainer's
   sessions run `claude --dangerously-skip-permissions` and are renamed at runtime,
   so the name is ONLY in that registry, never argv. `claude_sessions.py` reads the
   registry (keeping live PIDs — alive AND `/proc` start-time == recorded
   `procStart`, defeating PID reuse) and joins each to its tmux session by walking
   the claude PID up to a tmux pane PID (`tmuxio.pane_pid_sessions`). A session is
   adopted when its registry `cwd` is in a fleet repo AND its `name` is an ACTIVE
   discovered topic there; registry membership already proves it is a Claude
   process, so there is no worker-command guard. **Adopt runs EVERY tick** (in
   `build_rows(act=True)`), not just at bootstrap — so a session that was mid-prompt,
   renamed, or launched later is picked up within one interval (the fix for "the
   daemon never re-adopted after the prompt cleared"). It maps to the bare session
   name (`tmux == session`), never double-adds, and — distinct from invariant 5's
   `auto_link`, which links only the `registry.tmux_id` session the daemon itself
   launches (the bare topic, or `<repo-slug>-<topic>` on a cross-repo collision).
   **Codex sessions ARE adopted the same tick, through the
   SAME code path** (`adopt_sessions` sums `claude_sessions.map_named_sessions(...)` +
   `codex_sessions.map_codex_sessions(...)`, both emitting the `(tmux, name, cwd)` triple)
   — they are not in Claude's registry, but `codex_sessions.py` supplies the equivalent
   join (see the next bullet). (Per-session pane reads —
   `pane_id`/`pane_current_command`/`pane_current_path` — go through `list-panes`, not the
   flaky-for-detached-sessions `display-message`.)

   **Codex session discovery (`codex_sessions.py`; 2026-07-16).** The Codex twin of
   `claude_sessions`, returning the same `pid` / `name` (= the plan topic) / `cwd`
   shape so adoption can treat both runtimes uniformly. Codex keeps no pid-keyed
   registry, which is why this looked like the hard part — but a running codex
   process **holds its own rollout file OPEN**, and the rollout FILENAME embeds the
   session id, which `session_index.jsonl` maps to the `thread_name`:
   `pid --comm=="codex"--> /proc/<pid>/fd/* --> rollout-<ts>-<id>.jsonl --> id
   --index--> thread_name`, with `/proc/<pid>/cwd` giving the repo. **Exact, not a
   heuristic** — no cwd+recency guessing. `claude_sessions.resolve_tmux_session` is
   already runtime-agnostic and joins the pid to its tmux session unchanged.
   Load-bearing details, each pinned by a beside-test:
   - **Only NAMED sessions are indexed** (67 of 259 rollouts, live) — an unnamed
     session carries no topic anywhere and is dropped. Codex adoption depends on a
     naming convention exactly as Claude's does via `claude -n <topic>`. This is the
     one real precondition; it is not a defect to engineer around.
   - **`comm == "codex"`, and an open rollout is REQUIRED.** The `bun` launcher is
     the codex process's PARENT and holds NO rollout fd, so the fd requirement
     excludes it structurally.
   - **No `procStart` liveness check is needed** (unlike Claude's registry, whose
     files outlive their process): the pid came from a `/proc` scan this instant and
     must still hold an open rollout — a fd cannot go stale.
   - **`Codex Companion Task: …` threads are NOT filtered here** (38 of 69 index
     records) — they fail the "is this an ACTIVE plan topic?" test at adoption, so
     the noise filters itself and the module stays a pure, dumb join with no policy.
   - **The join NEVER reads a rollout's contents** — rollouts are full session
     transcripts. `codex_sessions.py` needs only the filename + `/proc`; it opens NO
     rollout body at all. (Keep it that way — see the Ctx% note.)

   **Codex Ctx% comes from the STATUSLINE, NOT the rollout (2026-07-16, corrected).**
   Codex renders `Context N% left` in its statusline (verified live) — its OWN computed
   number — and `signals.parse_ctx_remaining` reads it exactly as it reads Claude's
   `Ctx: N% left` (`_CTX_RE` matches BOTH forms), so Codex needs NO ctx code of its own.
   An earlier cut computed ctx from the rollout's `token_count` events
   (`rollout_ctx_remaining`) and was **WRONG by 2–4 points** against Codex's own display,
   because it reimplemented codex-rs's private occupancy formula (subtracts a ~12k
   baseline, excludes reasoning tokens) — an internal that drifts with any Codex release.
   That function was REMOVED; `codex_sessions.py` reads no rollout body. **Never
   reintroduce a local occupancy formula.** This matters because the escalating wrap-up is
   the daemon's ONLY lever now that nothing is force-killed — and a Codex track now
   RECEIVES that wrap-up (and is restarted on `ready`) as a full citizen; it is no longer
   a monitor-only passenger (see invariant 7 and the load-bearing mechanics below).
7. **THE CARDINAL RULE — never restart a session that has not declared itself
   `ready` (maintainer-declared 2026-07-14).** The session's own `ready`
   declaration in its state file (`signals.ready_valid`) is the **SOLE**
   authorization for a restart, and `Supervisor._do_restart` has exactly ONE
   caller: the `ready` branch of `evaluate`. The daemon NEVER infers readiness —
   not from idleness, not from a timer, not from how low the context has fallen.

   **Why this is a correctness rule, not a courtesy.** A timer cannot know whether
   a session is safe to kill. **"Idle + settled" is NOT "at a safe stopping
   point"**: a session can be idle while a background build runs, while a sub-agent
   works, or while it waits on a human in another pane. Only the session knows, so
   only the session may authorize the restart. A session that declares NOTHING is
   **reported to the human as not responding** (`_alert_non_responder`) and
   otherwise **left alone** — that is a bug in the SESSION (which was told,
   escalatingly, exactly what to write), never a licence for the daemon to guess.

   **This REPLACED a previously-shipped invariant that said the opposite.** An
   earlier version of this list asserted the auto-restart was NON-NEGOTIABLE and
   that a warned track stalling idle at the danger line was **FORCE-restarted**
   after a grace (`_danger_or_force_restart` / `_STALL_RESTART_GRACE` /
   `InjectState.danger_idle_since`). That was a **severe bug** — the daemon killed
   sessions it had no way to prove were safe to kill — and all of it is **deleted
   from the code**. If you find yourself re-adding a timer, a grace, or any
   daemon-side judgment that ends in a respawn, STOP: you are reintroducing it.

   The restart **mechanics** are still required — only the **trigger** moved to
   the session's declaration. `_do_restart` is **RUNTIME-DISPATCHED** (`is_codex`
   selects the arm); the Claude arm is:

   - **(a) exit + restart** — the ATOMIC `respawn-pane -k` (kill the pane's process
     and launch the new one in a single tmux op), NOT a `/exit` followed by a scrape
     for the shell prompt. The `❯` glyph is ambiguously BOTH the Claude idle prompt
     and the zsh prompt, so a mis-timed "the shell is back" would type into the
     still-live session.
   - **(b) a launch-profile-aware command** — no recorded `model_profile` keeps
     the fail-soft bare command `claude --dangerously-skip-permissions -n
     <topic>`; a profile with no wrapper relaunches with `--model <model>`; a
     wrapper profile relaunches through the wrapper and sets the recorded model in
     the controlled environment. The daemon SETS OR SCRUBS the controlled Claude
     env vars on every profile-aware relaunch, and a stale/corrupt profile is
     surfaced with the restart skipped rather than falling back to a default.
     `--dangerously-skip-permissions` and `-n <topic>` remain load-bearing.
   - **(c) the resume line** — `resume plan epic <epic> in repository <repo>; read
     its ledger-held plan state`, bracketed-pasted AND verify-submitted once the
     fresh TUI is up (`_supervisor_prompts.resume_for_track` + `_submit_prompt`).
     It names the repository path and the recorded epic id LITERALLY, so a
     cold-open successor can resolve what to read without opening any plan-tree
     file. A track with NO recorded `epic` is not respawned at all: the `ready`
     declaration is PRESERVED and the track surfaced, exactly as for a respawn
     that failed, so a declaration is never spent on a prompt the fresh session
     cannot resolve. A `claude "<prompt>"` argv only
     PRE-FILLS the box without submitting — which is why the resume line is pasted
     after launch rather than passed on the command line. **The submit is
     SELF-HEALING (R1, 2026-07-18):** a freshly-respawned TUI can DROP the Enter
     while still drawing its welcome screen, leaving the fresh session live but idle
     with the resume UN-submitted (proven live 2026-07-17 — fabro / autonomous-mode /
     overseer-rewrite each stranded this way, autonomous-mode for 9h until a human
     pressed Enter). So `_do_restart` waits for the box to render first
     (`_await_input_box`) and, if the submit STILL does not land, does NOT clear the
     `ready` marker or log success — it marks a round-scoped `resume_pending`
     (`registry.set_resume_pending`) and alerts. The next tick's `evaluate` intercepts
     the still-open round BEFORE the busy/idle cascade and retries the SUBMIT ONLY
     (`_resend_enter` — re-send Enter, NEVER a re-respawn, so it can never escalate to
     a kill; a fresh `ready` is still the sole respawn trigger), closing the round only
     once the box clears or the pane goes busy. The stranded row stays a NEEDS-YOU
     report (`RESUME_PENDING_NOTE`) until it resumes. See invariant 7's B5 discipline:
     "is the fresh Claude up?" and "did the resume submit?" are now SEPARATE facts —
     conflating them (the old `_clear_state` + "restarted" log on a failed submit) is
     the exact discarded-marker bug this replaced.

   **The Codex arm (`_do_codex_restart`) is the ONE place the destructive bug lives,
   and the dispatch is what prevents it.** `claude -n <topic>` aimed at a codex pane
   would REPLACE the codex session with a claude one; so a Codex track respawns
   `codex resume --dangerously-bypass-approvals-and-sandbox <session-id> "<resume line>"`
   (`_codex_launch_command`) instead — NEVER the claude command. The
   `--dangerously-bypass-approvals-and-sandbox` flag is the codex twin of the Claude arm's
   REQUIRED `--dangerously-skip-permissions` (maintainer-declared 2026-07-17): without it
   the resumed session uses codex's default INTERACTIVE approval and stalls at a `› 1.`
   approval picker on its first tool call, so the restart is not hands-off (codex documents
   the flag as "solely for externally-sandboxed environments", which this local-only host
   is). It is otherwise SIMPLER than the Claude arm (proven live 2026-07-17): `codex resume`
   takes the kick as an ARGUMENT and AUTO-SUBMITS it, so there is no separate paste (no
   `_submit_prompt`) and no fresh-TUI submit race; and it resumes by the exact UUID, which
   reattaches the SAME rollout so the `thread_name` — hence adoptability — survives by
   construction. The await polls `pane_is_codex` (`_await_pane`) not `pane_is_claude`, and
   the round is closed (`_clear_state`) only after the await CONFIRMS the codex pane came up
   — a failed respawn or await keeps the `ready` marker so the restart retries (B5, pinned
   by the codex marker-kept tests). The sabotage-verified guard test
   (`…never_issues_the_claude_command`) pins that the routing holds; if you touch this
   area, re-sabotage (route codex → the claude command) and confirm it goes red.

   **Reboot recovery is RUNTIME-DISPATCHED (defect #5, 2026-07-18).** `recover_missing_sessions`
   (startup only) no longer always launches the claude command. A dead codex process is absent
   from the live `self.live_codex` map (no rollout fd at cold start), so the runtime is derived from
   the PERSISTENT codex index instead — `session_index.jsonl` SURVIVES the session's death. If
   the track's TOPIC names a session there (`codex_sessions.latest_session_for_thread_name`, the
   most-recent by `updated_at`), the track is CODEX: `_recover_codex_track` resumes the SAME
   rollout via `codex resume <id>` (option c) when it still exists on disk
   (`codex_sessions.rollout_exists`), else skips + surfaces (option b) — NEVER mis-recreating it
   as claude (rollout-orphaning). A topic absent from the index is a Claude track and recovers as
   before. The `session_exists` gate still means only a genuinely ABSENT session is recreated, so
   no live session is killed. Verified live 2026-07-18: `codex resume` reattached a 26-day-old
   session with its thread_name intact (so the daemon re-adopts it); the reverse-index + rollout
   gate resolve correctly against the real `~/.codex`; the latest-by-`updated_at` pick is
   unambiguous (distinct timestamps per id in real index data). Two interstitials seen live and
   both self-healing (a `› N.` gate → `blocked:human` → operator clears): codex's directory-trust
   prompt appears only for a repo codex has NOT trusted — in recovery `track.repo` is where the
   codex session originally ran, so it is already trusted and the resume is clean; and the
   working-dir picker appears only when the pane cwd ≠ the session's recorded cwd — recovery sets
   cwd to `track.repo`, which matches. See the `recover_missing_sessions` docstring.

   The abrupt kill is safe **because of** the declaration: the session asserted it
   is at a clean stopping point, and `respawn-pane -k` replaces the PROCESS — every
   file, worktree, and commit on disk survives it.

   **With the force-restart gone, the ESCALATION is the only lever.** So it has to
   actually sharpen: `wrapup_message` sends a SUGGESTION above `_INSIST_AT` (30%
   remaining) and an insistent "STOP AND WIND DOWN NOW" at 30 / 20 / 10. Re-sending
   identical text five times is repetition, not escalation. If you touch the wrap-up
   text, keep that gradient — it is load-bearing now.
8. **Notify, never block (maintainer-declared 2026-07-14).** **A question may only
   be asked by the actor that OWNS the decision, and the overseer must NEVER block
   on a question it does not own.** A tracked session's decision belongs to that
   session and is already displayed in ITS pane; re-asking it in the interactive
   bottom pane created a duplicate surface — the maintainer answered in the tracked
   session's pane, the overseer's modal stayed blocking, and the whole console
   wedged on it (a single point of failure). So:

   - **Track decisions → non-blocking TEXT.** The bottom pane relays
     `blocked:human`, a non-responding `danger` track, and a malformed state file as
     reported text; the operator answers **in the tracked session's own pane**. It
     NEVER raises `AskUserQuestion` on a track's behalf.
   - **Overseer-OWNED decisions → `AskUserQuestion` is still right** (add / remove /
     unassign / start a track, a threshold) — nobody else can answer those.
   - **It self-heals.** `blocked:human` is re-derived from the live pane every tick,
     so when the human answers in the tracked pane the alert simply stops. Nothing
     needs to be dismissed.
   - **Therefore every track-scoped alert MUST name WHERE to act.** Because the
     overseer never prompts on a track's behalf, the alert line is the operator's
     ONLY handover, so it must be self-sufficient: plan topic, repo, tmux SESSION,
     PANE, and a copy-pasteable `tmux switch-client -t <session>` jump command. That
     is what `Supervisor.alert` guarantees — route EVERY new track-scoped alert
     through it, never a bare `surface` with an f-string of `repo::topic` (which
     told the operator WHAT was stuck but not WHERE to go). `surface` remains for
     DAEMON-level notices with no track coordinates (a failed paste retry, a
     respawn failure, the singleton-lock refusal, the gitignore refusal).
9. **ONE state file with a VALUE — never two presence-markers.** The declaration is
   `<repo>/tmp/overseer/<topic>/.overseer-state`, whose first non-empty line is
   `<token>` or `<token>: <detail>`. There are **three SESSION-written tokens**
   (`ready`, `blocked`, `winding-down` — `signals.STATE_TOKENS`) plus
   **DAEMON-written tokens** (`idle-with-context-left` and diagnostic states in
   `signals._DAEMON_TOKENS`); `signals.valid_token` accepts either set. The predecessor pair
   `.overseer-ready` + `.overseer-blocked` is GONE: two presence-markers carried a
   built-in ambiguity — nothing stopped BOTH existing, and their precedence was
   incidental rather than designed. One file with a value makes that state
   unrepresentable. A malformed/typo'd token is **surfaced** and treated as **no
   declaration** (fail-closed, `signals.valid_token`); do not "helpfully" coerce or
   fuzzy-match it. If you ever add a second signal file, stop — you are re-creating
   the ambiguity this collapsed.

   **`idle-with-context-left` is the ONE token the daemon writes to itself, and it
   never authorizes a restart.** It is a marker, not a declaration: when a session
   goes idle while still ABOVE the wind-down threshold and is not waiting on a human
   (and has made no `ready`/`blocked`/`winding-down` declaration of its own), the
   daemon sends exactly ONE "keep going, don't stop with context left" nudge and
   stamps this token so it does not re-nudge every tick. **The nudge fires ONLY after
   the session has been CONTINUOUSLY idle for at least `IDLE_NUDGE_AFTER` (1 hour;
   maintainer-declared 2026-07-18: it was "too aggressive, TOO SOON" and interrupted
   sessions merely between turns).** The continuous-idle clock is in-memory
   (`InjectState.idle_since`), stamped on the first cleanly-idle tick (empty prompt AND
   not busy — `busy` folds in Claude's registry `busy`/`shell`, so a sub-agent or
   background command resets it) and cleared the moment the session is non-idle; a daemon
   restart resets it, which only ever DELAYS a nudge (the safe direction). The row still
   reads `idle-with-context-left` immediately (descriptive, not an attention status); only
   the keystroke waits for the 1-hour floor. It is EDGE-TRIGGERED: the
   nudge fires once per idle episode, and the daemon CLEARS the token the moment the
   session goes non-idle again (busy / gate / blocked branches call
   `_clear_idle_nudge_state`), re-arming a fresh nudge for a later episode. The
   clear only unlinks the file when it still holds `idle-with-context-left`, so it
   can never clobber a session's own `ready`/`blocked`/`winding-down`. This is NOT a
   crack in the cardinal rule (invariant 7): the marker gates a text NUDGE, never a
   respawn — the sole restart trigger is still a session-written `ready`. The
   nudge's own text tells the session it may instead write `blocked: <reason>` if it
   is genuinely waiting on a human (the escape hatch for a YOLO-mode session that can
   only say so in prose).

   **v019 wind-down expiry is SESSION-side; do not move it into the daemon.**
   `SPECIFICATION/spec.md` §"Wind-down expiry on context recovery" requires a
   recovered session to clear its own stale `winding-down` / `ready` declaration
   before resuming work. Once it does, the daemon sees no session declaration and
   the ordinary idle-with-context-left nudge can fire again after the continuous-idle
   floor. Until the session clears that file, though, the daemon treats the standing
   token as a declaration however stale: it does NOT auto-clear it, does NOT
   reinterpret it as absent for the nudge guard, and does NOT restart from it unless
   a fresh `ready` passes the existing interlock. **Why it mattered:** the sibling
   case explicitly left for daemon-side recovered-round text is a recovered session
   that never woke up to clear its stale declaration. Nudging through that state
   would keystroke into a pane still carrying session-authored wind-down/restart
   intent, so the current fail-safe behavior is plain non-nudging until the session
   or a future ratified daemon rule clears the composition question.
10. **The DAEMON owns "what needs attention"; the bottom pane must never be a status
    display (maintainer-declared 2026-07-14).** Current state is rendered ONLY by the
    daemon — the table plus its `NEEDS YOU` block (`Supervisor._attention_lines`,
    `needs_attention`, `ATTENTION_STATUSES`) — because that render is rebuilt from live
    captures every tick and costs no tokens, so it *cannot* go stale and *can* refresh
    forever. An LLM pane can do neither: it prints text ONCE, and that text then ages
    silently.

    **This is the frozen-snapshot failure (history #2) recurring in the other pane.** The
    bottom pane printed "two tracks want you", went idle, and kept showing it while both
    were resolved minutes later; the maintainer acted on a dead report. The original fix
    (re-render each tick + stamp it) had only ever been applied to the top pane.

    The split that resolves it — and that you must not blur:

    - **The table is STATE** (what is true *now*; self-correcting — a resolved track
      disappears from the block on the next tick).
    - **The log is HISTORY** (`tmp/overseer/daemon.log`; what happened and *when*). The
      bottom pane SHOULD know it and its format — answering questions from it is its job
      (maintainer 2026-07-14: "it should still know about the log and its format so it can
      answer questions with its data"). What it must not do is answer *"what needs
      attention?"* from it.

    Consequences that are load-bearing, not cosmetic:

    - **Every log line is timestamped** (`log` / `surface` prefix `iso_now()`) — a
      history you cannot date cannot answer "when?".
    - **Track alerts are EDGE-TRIGGERED** (`alert`'s `alerted` dict; re-armed in
      `evaluate` when the row goes healthy). Re-emitting an unchanged alert every tick
      buried the history under thousands of identical lines (a track blocked overnight →
      ~3,000) *and* made `tail`ing the log look like a current-state read, which is the
      bug. If you make alerts repeat per-tick again, you have reintroduced it.
    - **The badge must be able to CLEAR.** `_refresh_window_name` drops back to `overseer`
      when the count is 0 — a badge that could only be set would be one more stale
      indicator.
    - **`unassigned` is not attention.** It is startable, not stuck, and it outnumbers the
      real rows ~10:1; including it re-buries the signal.

    If you find yourself putting the bottom pane on a timer to keep it fresh, STOP: that
    burns tokens forever to duplicate a surface that is already correct and free, and it
    walks back into history #1 (the context-blowing inline worker). The answer is fewer
    LLM refreshes, not more.

11. **Foreman entities are a reserved-worker-topic pattern (`overseerd-auto-restart`,
    2026-08-18), generalized from the existing `-supervisor` pattern rather than
    given a parallel evaluate() branch.** `signals._RESERVED_WORKER_SUFFIXES`
    already carried both `-supervisor` and `-foreman` before this track, and three
    call sites already treated both as reserved — the actual gap was that nothing
    ever created a `registry.Track` row for the canonical `<repo-slug>-foreman`
    identity (`foreman_runtime_identity.canonical_session_name`), and
    `signals.supervisor_topic` mis-truncated a `-foreman` topic if ever called on
    one. `evaluate()` itself needed NO new branch: a foreman track flows through
    the SAME cascade as any other track — busy/gate/idle/ready/threshold are all
    topic-agnostic — with only the message-selection and binder-certification
    LEAVES branching on `signals.is_foreman_topic`
    (`foreman_wrapup_message`/`foreman_resume` in `_supervisor_prompts.py`, a
    binder-certification guard parallel to `_handle_uncertified_supervisor_binder`
    in `_supervisor_restart.py`). Registration
    (`foreman_runtime.register_foreman_track`) runs idempotently by existence on
    every `foreman-runtime` step, independent of any `plan/` directory: one row
    exists afterwards for the canonical foreman topic/repo/tmux, and an existing
    row's durable contents are preserved. Invariant 1 holds by construction, not
    by a new guard. The trigger is UNCHANGED: the
    existing ctx-threshold `maybe_inject` path. `ForemanRuntime`'s own
    `hard_tick_budget`/`converged` exit reasons and the `foreman-heartbeat-stale`
    alert (`_supervisor_foreman.py`) remain daemon-observed SUGGESTIONS at most —
    NEITHER is nor may become a restart trigger; invariant 7's cardinal rule is
    not narrowed for this entity shape. Full contract in `marker-protocol.md`'s
    "Foreman entities" section, including the recorded 2026-08-18 finding that
    THIS repo's own live foreman session still runs under the legacy ad-hoc
    `foreman` plan-topic rather than the canonical `livespec-overseer-foreman`
    identity — a follow-up migration, not done inline against a live session.

12. **Lifecycle helper inventory, updated narrowly 2026-08-21
    (`overseer-hgq4wi.3.2`).** The restart/liveness/stall-watch trio is no
    longer wholly inside the three legacy aggregate modules. `_supervisor_restart`
    keeps the runtime-dispatched respawn path and imports the escalating
    low-context paste from `_supervisor_wrapup_injection`. `_supervisor_liveness`
    keeps blocked and picker-stall alert surfacing, re-exporting shared duration
    primitives from `_supervisor_liveness_time` and uncertifiable-ready surfacing
    from `_supervisor_ready_alerts`. `_supervisor_stall_watch` coordinates the
    evaluation monitors and imports the pane-still watch from
    `_supervisor_pane_still`. This is a local map for these lifecycle helpers,
    not a refreshed inventory of every `_supervisor_*.py` module.

## Load-bearing mechanics + gotchas

- **Pane sizing + the window badge (`tmuxio.set_pane_height_percent` / `rename_window`).**
  The daemon pane gets **2/3** of the window (`overseer-start`'s
  `_DAEMON_PANE_HEIGHT_PERCENT = 66`) because it carries the table + `NEEDS YOU` block —
  the surfaces that answer "what needs my attention?"; the bottom pane is a command
  prompt and needs less. `overseer-start` normalizes the stack (`select_layout_even`)
  and THEN resizes, resolving the daemon pane **by title** (`pane_by_title`) so the
  idempotent re-run path — where the pane already existed and its id was never held —
  resizes it too. Percentage sizes (`resize-pane -y 66%`) are a real tmux feature
  (verified on 3.5a), so the split survives a terminal resize without recomputing rows.
  **`rename_window` MUST also set `automatic-rename off`** — tmux otherwise re-derives a
  window's name from its foreground command on the next tick and silently overwrites the
  badge; pinning is part of renaming, not an optional extra.
- **Row color is a TTY-only, whole-LINE affordance (`row_color` / `_STATUS_COLOR`;
  2026-07-15).** `render` tints each DATA row by its raw status so the operator scans
  the list by hue — green = actively working (`working`/`winding-down`/`restarting`/
  `settling`), yellow = idle (`idle`/`idle-with-context-left`) / waiting on a human
  (`blocked:human`) / low on context (`warned`/`danger`), red = broken
  (`session-gone` — `not-claude` is DELETED, no longer a status), default (uncolored,
  terminal white/gray) = `unassigned`, `live-outside-tmux` (informational — alive but
  unmanaged, deliberately NOT tinted so it reads as neither healthy nor broken), and any
  other unmapped status. Two invariants keep it
  safe: (a) the ANSI codes wrap the **already-padded whole line**, never a cell, so the
  column widths — still computed on plain-text `len` — stay aligned; and (b) color is
  emitted **only to a TTY** (`render` gates on `out.isatty()`), so a piped
  `supervisor.py list` and the beside-tests' plain `StringIO` get NO escape codes and
  every `row.split()` assertion stays valid. The header + separator are never tinted.
  If you add a status token, add it to `_STATUS_COLOR` too (an unmapped status is legal
  — it just renders in the default color).
- **Session-authored notes are ELIDED on EVERY surface (`elide`; 2026-07-16).** A note
  is SESSION-authored free text — a `blocked:` reason or the live-outside-tmux detail —
  that can be arbitrarily long AND multi-line, and a raw 705-byte `blocked:` value once
  blew the whole Status column out (the table sizes each column to its widest cell) and
  broke row alignment. `elide` flattens the note to one line (`" ".join(split())`,
  collapsing newlines) and truncates with an ellipsis, applied at THREE call sites so no
  surface can be overrun: the table Status cell (`MAX_NOTE_IN_TABLE`, 48 — tightest,
  because the column width is load-bearing), and the `NEEDS YOU` block line + the
  edge-triggered `alert` daemon.log line (both `MAX_REASON_IN_ALERT`, 160 — a longer
  preview, since the FULL reason is in the tracked pane the line's jump command points
  at). Never render `row.note` raw onto any surface — route it through `elide`.
- **`command tmux` semantics (`tmuxio.py`).** Every tmux call is
  `subprocess.run([...], shell=False)` with an argv LIST — no shell is spawned,
  so a user's zsh `tmux` function shim is bypassed (the `command tmux` effect).
  Never build a shell string for word-splitting.
- **Bracketed paste, never line-by-line.** Multi-line payloads (the wrap-up, the
  resume line) go in via `load-buffer -` + `paste-buffer -p` so the receiving
  Claude TUI takes the whole blob as ONE pasted input that cannot fragment into
  separate submitted prompts. `send-keys -l` typing a multi-line payload would
  fragment it — do not.
- **Bracketed-paste submission (`_submit_prompt`) — verified-submit loop, RUNTIME-AWARE.**
  Paste (`load-buffer` + `paste-buffer -p`, single- or multi-line, atomic — never type a
  payload key-by-key), then re-send `Enter` until submission is CONFIRMED, up to
  `SUBMIT_MAX_ENTERS`. Verified live (2026-07-13): on a STEADY idle session a single
  `Enter` submits; but a freshly-`respawn`-ed session is often still drawing its
  welcome/news screen when the first `Enter` arrives and DROPS it, leaving the payload
  un-submitted. The verify loop fixes that (an extra `Enter` on an already-empty prompt is
  a harmless no-op). The confirm signal is **runtime-specific** (`expect_codex`) because
  the two TUIs render differently: **Claude** confirms on the empty `❯` box returning
  (`signals.input_box_ready`); **Codex** confirms on the pane going BUSY
  (`signals.is_busy` — Codex's `esc to interrupt` / `Working …`), because Codex has no
  `❯` box and its empty box shows a grey rotating PLACEHOLDER indistinguishable from typed
  text in an ANSI-stripped capture, so "box cleared" is not usable; "the model started
  responding" is (verified live 2026-07-17, busy within ~1s of Enter). This is NOT the old
  `send-keys -l` key-by-key collapse — the paste is always atomic; it is submit TIMING.
- **Codex idle / gate detection is STRUCTURAL, and its own (`signals.is_codex_idle_input`
  / `codex_prompt_present`; 2026-07-17).** A Codex track is a full citizen that gets the
  wrap-up pasted in and is restarted on `ready`, so its idle read must be as safe as
  Claude's `is_idle_input`, not the coarse "not busy". Codex idle = a `›` input line above
  its statusline (`… · Context N% left · …`), not busy, and NOT a picker — so a booting
  pane or a Codex approval/directory-trust picker is never keystroked into. That picker
  uses a `›` cursor (`› 1.`), NOT Claude's `❯`, which is why `is_structured_gate`'s cursor
  regex accepts BOTH glyphs (`[❯›]`); reverting it to `❯`-only lets a wrap-up paste into
  the Codex chooser (sabotage-verified by `test_a_codex_approval_gate_suppresses_the_wrapup`).
- **Anchored, fail-closed Ctx% parse (`signals.parse_ctx_remaining`).** Scan only
  the last FEW non-empty pane rows (`_CTX_TAIL_ROWS`), ANSI-stripped, taking the
  LAST `Ctx: N% left` match. The statusline is the SECOND-to-last row — a footer
  hint (`⏵⏵ …` / `? for shortcuts`) renders BELOW it (verified live 2026-07-13) —
  so reading only the LAST row misses `Ctx:` entirely. NEVER scan the whole
  capture — page content (including the overseer design doc itself) contains
  `Ctx: N% left` and would yield a false reading; the small bound keeps that
  anti-false-match intent. No match ⇒ **unknown**, which keeps the last known
  value and NEVER counts as a threshold crossing. This is the one coupling: if
  the statusline stops emitting `Ctx: N% left`, ctx reads unknown and the daemon
  degrades safely (the table shows a dash).
- **Busy detection (`signals.is_busy` + the daemon's settled-delta).** The live
  TUI (verified 2026-07-13) renders NO persistent busy string while streaming
  tokens — the input box looks idle and the response accumulates above it — so
  single-capture markers are insufficient. `signals.is_busy` fires on the real
  active-generation spinner (`✻ … (… · Ns · ↓ tokens)` / `(running … hook…)`),
  `esc to interrupt` (older layouts), and `Waiting for N background`; it
  deliberately does NOT fire on the lingering completed-turn summary
  (`✻ Brewed for 25s`). Because streaming shows no spinner in the captured
  region, the daemon ALSO runs a two-capture **settled-delta**
  (`Supervisor._pane_settled`) before injecting/restarting an apparently-idle
  track: two captures `SETTLE_DELAY` apart that DIFFER ⇒ actively working ⇒
  treated as `working` and skipped. Over-firing busy is the SAFE direction.
- **Claude registry `status` is AUTHORITATIVE for an adopted Claude session
  (`claude_sessions.status_by_tmux_session`; 2026-07-15).** Claude Code writes a live
  `status` into each session's registry file (`~/.claude/sessions/<pid>.json`), and its
  four values map cleanly onto the daemon's model — recomputed each tick into
  `Supervisor.claude_status_by_session` (`{tmux_session: status}`) by `_refresh_claude_status`, read
  in `evaluate`, and matched against `CLAUDE_BUSY_STATUSES = {"busy", "shell"}`:
  - **`busy`** — actively generating, OR running an in-process sub-agent (Task tool). A
    sub-agent spawns NO descendant shell and need not repaint the pane, so
    `has_active_subshell` AND `is_busy` both miss it — but Claude reports `busy`, so the
    daemon marks it `working` (note `"sub-agent (Claude busy)"`). [fixed false-idle]
  - **`shell`** — at the prompt with a live `Bash(run_in_background)` command. This is
    Claude's OWN, accurate background-work signal. Above the wind-down threshold it
    remains `working (background shell)`; at/below the threshold it may coexist with
    the guarded wrap-up only when every idle-input, settle, declaration, gate,
    human-wait, generation, sub-agent, and immediate recheck guard passes. It still
    counts as busy for restart, so a `ready` declaration cannot respawn until shell
    evidence has cleared. [fixed the autonomous-mode false-idle: a real background
    dispatch mis-read as idle]
  - **`waiting`** — at a gate/prompt for the human. **`idle`** — nothing pending. Neither
    is busy; the session falls through to the gate/idle branches.
  For an adopted session the daemon therefore **IGNORES the process-tree shell-walk
  entirely** and trusts `status`: it is strictly better than the walk, which both MISSED
  sub-agents (false-idle) and false-fired on lingering/transient shells that Claude was
  not actually using (false-`working (background shell)` on a session sitting at a user
  prompt). Getting this right took two iterations — the first fix folded only `busy` in
  and made everything else ignore the shell, which then mis-read a genuine `shell`-status
  background dispatch as idle; the authoritative-`status` model (this bullet) is the
  root-cause fix.
- **Background-shell detection (`claude_sessions.has_active_subshell`) — the
  runtime-agnostic FALLBACK, Codex-only.** A descendant shell (`sh`/`bash`/`zsh`/…) under
  the pane process marks a session busy ONLY for a session with NO Claude registry entry
  (`claude_status is None` — Codex). It is the only busy signal that covers Codex. Its
  ORIGINAL job — blocking a force-restart of a live `Bash(run_in_background)` build — is
  still load-bearing for the restart interlock: `ready` never respawns while descendant
  shell evidence remains. For low-context Codex only, the same shell-only evidence may
  coexist with the guarded wrap-up when the structural Codex prompt/statusline is present,
  the pane settled, and the immediate pre-paste re-observation still agrees. For Claude
  the `shell` status supersedes it exactly and more accurately. The `/proc` readers
  (`proc_children`/`proc_comm`) are injected (`children_of`/`comm_of`) so the beside-tests
  fake them. Above threshold, when it is the SOLE reason a track isn't idle, the row
  `note` is `"background shell"`.
- **Idle-input detection (`signals.is_idle_input`).** The real idle prompt is an
  EMPTY `❯` between two horizontal rule lines (`────…`), statusline + hint below
  — NOT a `╭─╮` box with `? for shortcuts` (verified live 2026-07-13). Detect
  that structural shape (glyph/hint-independent); require the prompt EMPTY so the
  daemon never injects over existing input; gate with not-busy + not-gate.
- **State-file declaration (`signals.read_state` / `valid_token` /
  `ready_valid`).** The ONE state file lives at
  `<repo>/tmp/overseer/<topic>/.overseer-state` (the repo's gitignored temp dir —
  NEVER under `plan/`); its first non-empty line is `<token>` or
  `<token>: <detail>`. The restart interlock (`ready_valid`) fires ONLY when: an
  injection stamp exists for this round, the token is **exactly `ready`**, AND its
  mtime is strictly newer than that stamp (this round, not a stale declaration).
  Beyond the token, **contents are NOT inspected** (no plan-state hash): the plan state
  and everything under `plan/` is the session's own business, which the overseer
  must never read or hash. Any missing/unreadable/other-valued file ⇒ False
  (fail-closed). The daemon writes the injection stamp BEFORE pasting the wrap-up
  (so a subsequent declaration has `mtime > stamp`) and replaces `ready` with a
  daemon diagnostic (`restarted: <detail>`) as it restarts (`_clear_state` — so a
  declaration can never re-trigger, while the consumed edge remains on disk).
  **`ready` is the SOLE restart authorization — never reshape this into "the daemon
  may decide for itself"** (invariant 7). The full contract is in
  `marker-protocol.md`; keep
  it and `_supervisor_prompts.py`'s `_WRAPUP_SUGGEST_HEAD` /
  `_WRAPUP_INSIST_HEAD` / `_WRAPUP_BODY` in sync. Supervisor-entity prompt variants
  live in `_supervisor_prompts_supervisor.py`; expiry notices and legacy path builders
  live in `_supervisor_prompts_notices.py`; standalone nudge text lives in
  `_supervisor_prompts_nudges.py`.
- **Self-healing resume-submit (`registry.set_resume_pending` / `read_resume_pending`,
  `_resend_enter`; R1, 2026-07-18).** The restart respawns the fresh session and pastes the
  resume line, but a freshly-respawned TUI can DROP the Enter while still drawing its
  welcome screen — the fresh session then sits live but IDLE with an un-run resume prompt
  (proven live 2026-07-17 four times in one day; autonomous-mode stranded 9h). The OLD code
  cleared the `ready` marker and logged "restarted" anyway, so the daemon never retried.
  Now `_do_restart` separates two facts it used to conflate — "is the fresh Claude up?"
  (await) and "did the resume submit?" (the Enter): on a FAILED submit it keeps the marker
  + stamp, marks a round-scoped `resume_pending` flag on the injection-stamp dict, and
  alerts (no clean "restarted" log). The next tick's `evaluate` sees `resume_pending` and
  intercepts BEFORE the busy/idle cascade — a box holding the un-submitted resume reads as
  "not idle" and would otherwise fall to `settling` and never retry. The retry branches on
  the BOX STATE, NOT on `busy` (review SF3): an empty box means the resume left the box
  (submitted / never pasted) → close the round; a box holding text means the Enter dropped →
  re-send Enter ONLY (`_resend_enter`, NEVER a re-paste, NEVER a re-respawn). `busy` is NOT a
  "submitted" signal — a fresh session can be busy for SessionStart-hook reasons unrelated to
  the resume, so a `busy` shortcut would false-close the round. And a fresh TUI that comes up
  on a PICKER is never keystroked (review SF4): both `_do_restart` and the retry branch check
  `is_structured_gate` first and report `blocked:human`, keeping the round open until the
  human clears the gate. **The re-respawn stays gated on a fresh `ready` alone**,
  so the retry can never escalate to a `respawn-pane -k` (the loop-safety property the
  Codex-#2 reasoning protected; pinned by `test_submit_retry_never_kills_the_fresh_session`
  and `test_idle_pane_with_resume_pending_closes_the_round_instead_of_respawning`). The flag
  is round-scoped by construction: `clear_injection_stamp` (round close) and
  `write_injection_stamp` (fresh round) both drop it, so it can never outlive its round.
  Codex never sets it (`codex resume` auto-submits its kick, no separate paste). Harden:
  `_await_input_box` waits for the box to render before the FIRST paste so most restarts
  never need the retry at all.
- **Claude identity gate `topic in names` parity + stale-mapping re-point
  (`_pane_is_managed_claude`, `claude_names_by_session`, `registry.repoint_tmux`; R2, 2026-07-18).**
  The Codex gate is pane-scoped (`_is_codex_track` requires `live.name == topic`); the
  Claude gate checked only process + cwd, so a generic reused tmux window (`livespec1`…
  cycled across topics) the store mapped to topic A but now running topic B's Claude —
  SAME repo — passed the gate and got A's wrap-up injected into B, then a `ready`
  respawn-KILLED B as A. The gate now ALSO requires a live Claude named for THIS topic to be
  present in the pane's tmux session (`self.claude_names_by_session`, from `names_by_tmux_session` —
  the SET of ALL live Claude names in that tmux session, so a HELPER Claude sharing the
  session cannot shadow the track's own name and flap it to `session-gone`; review SF5). It
  is POSITIVE-mismatch only: reject only when the tmux session has live Claude names but NOT
  this topic's; an UNKNOWN tmux session (empty set — registry miss, or a direct-`evaluate`
  test that did not populate the map) preserves the prior process+cwd gate — fail-soft, so a
  transient miss never flaps a live track to `session-gone`. Do NOT widen this to "reject
  unless proven `topic in names`" (that reintroduces the flap). Separately,
  `adopt_sessions` now RE-POINTS a stale mapping: when a topic's live named session resolves
  to a tmux session different from the store's `tmux` field, it rewrites the row
  (`repoint_tmux`, idempotent + guarded so a steady-state tick never touches the store)
  instead of freezing the binding — the "re-mapping is a separate concern" the old code
  deferred was the concern.
- **Ready arms until idle (`READY_ARM_MAX_AGE`).** A session that declares `ready`
  may still emit final narration or stop-hook output before its pane settles. That
  activity does NOT void the declaration anymore: the restart branch still requires a
  verified idle input state, a settled pane, no busy markers, and a live identity match,
  so the daemon cannot kill mid-work merely because the file exists. The declaration
  remains armed and fires at the first verified settled-idle observation.
- **Ready EXPIRY (`_supervisor_state.expire_aged_ready`).** Staleness is bounded by
  `READY_ARM_MAX_AGE` (30m) measured from the declaration's own mtime. Past that the
  row surfaces `ready-uncertifiable` with a max-age note, the daemon does not restart,
  and the declaration EXPIRES: the deterministic expiry instant (`mtime + max age`,
  never a fresh clock reading) is recorded into the round's sidecar and THEN the state
  file is replaced with `ready-expired: <detail>` — that order fails closed across a
  crash. Expiry clears the declaration ONLY; the round's key, notified bands and open
  status all survive, and an
  expiry seen under a live identity differing from the round-open identity raises no
  floor and is surfaced. The call sits in `evaluate` right AFTER the observation is
  gathered, so precondition 3's own age backstop judges the declaration uncertifiable in
  the very tick that expires it. Both writes failing in one observation is surfaced as
  `ready-expiry-both-writes-failed`.
- **The expiry-notice (`_supervisor_threshold_expiry.maybe_send_expiry_notice`,
  re-exported by `_supervisor_threshold`).** One notice per DELIVERED round, however
  many declarations expire, under the same guarded-paste predicate as a wrap-up but
  triggered by the expiry rather than by context. The once-per-round bound is durable
  (`expiry_notice_sent` in the sidecar), a failed paste leaves it due for a later
  observation, and a round closed as recovered first sends none.
- **Stale-`blocked` voiding (`_void_stale_blocked`; 2026-07-16).** Nothing else retires a
  `blocked:`. `_clear_state` runs only on the daemon's own restart path, so a pane replaced
  OUT-OF-BAND (a hand-restarted session, a `/clear`) INHERITS its predecessor's declaration
  — found live: a fresh `overseer-rewrite` session rendered `working (awaiting maintainer
  next-step decision — Codex…)`, a reason written by a session that no longer existed. Left
  alone the dead reason also fires a false `blocked:human` the moment the session goes idle.
  So a `blocked:` is voided when the session is **GENERATING** and the declaration is past
  `MARKER_VOID_GRACE`. **This is not the daemon judging semantics (invariant 1):** it does
  not guess the session is unblocked, it observes that the session is PRODUCING TOKENS,
  which is incompatible with waiting for an answer. Two bounds, each pinned by a test —
  widen neither:
  - **`generating`, not merely `busy`.** Busy via a live `Bash(run_in_background)` command
    alone (Claude `shell`) means the session is AT ITS PROMPT and may legitimately be
    awaiting a human while a build runs → never voided, however old. Only a real generation
    spinner (`is_busy`) or Claude `busy` (generating / in-process sub-agent) qualifies.
  - **The same tail grace shape.** The declaring turn's own final text streams 10–60s
    AFTER the write, so a young blocked declaration must survive its own busy tail.
  An IDLE blocked session is never touched: it keeps its declaration and keeps alerting
  until the session itself retracts it. Note the note-default coupling — `note` defaults to
  the blocked reason, so the void runs BEFORE the note is derived and the note is re-derived
  after; the reason only ever reached a `working` row via the spinner path anyway (the
  shell / sub-agent branches overwrite the note), which is exactly the provably-stale case.
- **The `winding-down` ACK (`ACK_STALE_AFTER`).** A FRESH `winding-down` (≤ 900s
  old) suppresses further wrap-up injections — the daemon must never keystroke into
  a session that is actively wrapping up — and shows as the `winding-down` row
  status. A STALE one resumes the escalation and re-reports the track (an ACK must
  not become an infinite stall), but it STILL never authorizes an act: only `ready`
  does.
- **Reporting a non-responder (`_alert_non_responder`).** This is the WHOLE response
  to a session that declared nothing at/below `DANGER_CTX_REMAINING` (20%): say so,
  loudly, with the tmux coordinates to go fix it — and do nothing else. It is a
  DEFECT REPORT about that session (it got an escalating wrap-up telling it exactly
  what to write), not a chore for the operator to work around. The fix is to make
  the session honour the protocol; it is NEVER to have the daemon guess on its
  behalf.
- **State precedence** (`evaluate`, top to bottom). `working` and `blocked:human`
  are evaluated FIRST, so an injection/keystroke is suppressed while a pane is
  generating, sub-agent-busy, non-shell busy, carrying a `ready` while any busy
  evidence remains, or showing a structured gate (permission prompt / picker) —
  never keystroke into a gate. Shell-only evidence is the narrow exception to the
  busy short-circuit: at/below threshold it may continue to the low-context branch,
  but only through the same idle-input and settle gates plus an immediate pre-paste
  re-observation of identity, runtime/busy kind, capture, declaration/ACK/gate state,
  and input predicate. Any changed, unknown, malformed, conflicting, generating,
  sub-agent, non-shell busy, human-waiting, declared, gated, or typed-input evidence
  cancels that tick. Then `settling` / identity re-check, then `restarting` (a fresh
  `ready`), then the threshold branch (`winding-down` on a fresh ACK, else `danger`
  at/below 20%, else `warned`), else the idle branch. `restarting` is checked BEFORE
  `warned`: a fresh `ready` means the session already declared it is done, so it
  supersedes any re-warn only after busy evidence has cleared. The idle branch itself
  splits: an idle session still ABOVE threshold, not `waiting` on a human, and
  carrying no session declaration (or already holding the marker) becomes
  `idle-with-context-left` and gets ONE keep-going nudge; anything else is plain
  `idle` (see invariant 9 for the marker lifecycle).
- **Atomic restart via `respawn-pane -k`, proven by `#{pane_current_command}`.**
  Restart replaces the pane's process in one step (`respawn-pane -k -c <repo>
  '<launch-profile-aware command>'`) — NEVER `/exit` then screen-scrape a shell
  prompt. The command is bare only for rows with no recorded profile; recorded
  profiles re-assert the wrapper/model and stale/corrupt profiles surface and
  skip the restart. The `❯` glyph is ambiguously BOTH the Claude idle prompt and
  the zsh prompt, so a mis-timed "shell is back" could type `claude …` into the
  still-live session. Wait for the fresh TUI by polling
  `#{pane_current_command}` → `node`/`claude` (`signals.pane_is_claude`), never by
  scraping `❯`. There is exactly ONE restart path and its abrupt kill is safe
  because of the DECLARATION: the session itself asserted it is at a clean stopping
  point, and the kill destroys only the PROCESS (files, worktrees, branches, and
  commits on disk survive). Every tmux step is a hard gate: a failed respawn, or a
  pane that never becomes a live Claude, SURFACES and returns WITHOUT clearing the
  round — the `ready` declaration is preserved and the restart retried, never
  silently destroyed.
- **`claude --dangerously-skip-permissions -n <topic>`** is the launch command
  (`_launch_command`), and BOTH flags are load-bearing.
  `--dangerously-skip-permissions` makes the restarted session AUTONOMOUS — without
  it the fresh session stalls on its first permission prompt and the auto-restart
  silently accomplishes nothing (invariant 7b). `-n <topic>` sets the session's
  display name in the prompt box, the `--resume` picker, AND the terminal title
  (which tmux surfaces) — a cleaner equivalent of typing `/rename`. The resume line
  is then pasted as the first prompt (a `claude "<prompt>"` argv only pre-fills, no
  auto-submit — which is why it is pasted after launch, not passed on the command
  line). Related `claude` flags to know: `--session-id` and `--resume`.
- **A raw `grep -c` against the daemon log is NOT an event count, and the obvious
  fix has its own trap.** The daemon RE-RENDERS ITS WHOLE TABLE EVERY TICK, so one
  standing condition contributes hundreds of matching lines. Measured 2026-08-19 on
  a live log: `grep -c restarted` returned **784** against what collapsed to **3**
  distinct lines — essentially two underlying situations, one of them a single
  blocked pane contributing 383 lines. Anyone triaging from raw counts will report
  a storm that is not happening. So collapse before concluding — but **collapse on
  the FULL line**. Truncating for readability (`cut -c1-110`) before de-duplicating
  destroys any discriminator beyond the cut, and the discriminator between "one
  condition re-rendered" and "an escalation ladder walking" is routinely a small
  counter or age stamp at the END of the line. Same log, same day: lines with an
  age-labelled tail collapsed to **149** distinct on the full line but only **5**
  when truncated first — a thirtyfold undercount, reached by someone who *did*
  collapse and was therefore confident. The cheap diagnostic is to collapse the same
  match set BOTH ways and compare: close numbers mean genuine re-rendering, while a
  large gap means the tail carries the signal and the RAW count is nearer the truth
  than the collapsed one. Truncate only for display, after counting.

## Build / toolchain facts

- **Stdlib-only Python, host-only.** No third-party imports; **eight** substantive
  module SURFACES (`registry.py`, `signals.py`, `tmuxio.py`, `supervisor.py`, `jsonio.py`,
  `start.py`, plus the session readers `claude_sessions.py` and
  `codex_sessions.py`) plus `__init__.py` / `daemon.py` / `streams.py` /
  `version.py` and the beside-tests. **(Corrected 2026-07-26: this said "six
  modules" and omitted `jsonio.py` and `start.py`. Eight is also the count the
  repo-root `.claude/CLAUDE.md` states, so the two documents now agree.)**
  **Two of those eight surfaces are FAÇADES over a group of private collaborator
  modules**, split when each crossed the 250-LLOC hard ceiling — so the eight is a
  count of consumer-visible SURFACES, not of files on disk:
  - `registry.py` → `_registry_core` / `_registry_store` / `_registry_discovery` /
    `_registry_stamps`.
  - `supervisor.py` → `_supervisor_core` (the `Supervisor` class) and a GROUP
    THAT IS NO LONGER ENUMERABLE HERE — see the correction immediately below.

  > **THIS LIST WAS FIVE MODULES AND THE TRUTH IS FIFTY-FIVE (re-measured
  > 2026-08-19; it was 26 on 2026-08-01). Do not trust an enumeration in this
  > section.** It named
  > `_supervisor_core` / `_supervisor_config` / `_supervisor_prompts` /
  > `_supervisor_view` / `_supervisor_records`; `ls overseer/_supervisor_*.py`
  > returns **55**. That pair of numbers is the stable claim — re-derive both from
  > the tree, never from this prose.
  >
  > **FOURTH RE-MEASURE, 2026-08-19, AND THE GAP IS GROWING FASTER THAN IT IS
  > DOCUMENTED.** Same scope as the 2026-08-01 figures below, so the two are
  > comparable:
  >
  > | | 2026-08-01 | 2026-08-19 |
  > |---|---|---|
  > | `_supervisor_*.py` on disk | 26 | **55** |
  > | named in none of the three docs | 22 | **37** |
  > | unnamed lines | 4,069 | **5,004** |
  >
  > Against this note's own residue the comparison is sharper still: naming seven
  > subsystems inline dropped the figure to 15 modules / 1,968 lines the day it was
  > written, so the debt went **15 → 37 modules** and **1,968 → 5,004 lines** in
  > eighteen days. Wider scope, all private `overseer/_*.py`: 75 on disk, 51
  > unnamed, 6,798 lines.
  >
  > **The RULE below is still right; only the NUMBER aged** — which is exactly what
  > it predicted. Nothing was added to the list, deliberately: re-adding one would
  > recreate the artifact that drifted four times. Note also that nothing GATES
  > this figure (`tests/test_module_docs_match_the_repo.py` gates only the `.ai/`
  > tense premise), which is how it doubled unnoticed — so re-derive rather than
  > trusting any number in this prose, including these.
  >
  > As measured against the docs AS THEY STOOD BEFORE THIS NOTE, **22** private
  > modules totalling **4,069 lines** were named nowhere in any of the three,
  > including whole subsystems: `_supervisor_evaluate` (390),
  > `_supervisor_discovery` (324), `_supervisor_observe` (322),
  > `_supervisor_restart` (289), `_supervisor_pair` (267),
  > `_supervisor_attention` (261), `_supervisor_liveness` (248).
  >
  > **Naming those seven here dropped the figure to 15 modules / 1,968 lines the
  > instant this note was written, and that is worth seeing rather than hiding.**
  > A count measured against a document you then edit is stale on arrival — the
  > same trap this file's correction-count history records — which is exactly why
  > the durable claim above is "5 named vs 26 on disk" and not a residue count.
  >
  > **Why this is worse than an out-of-date list.** The repo-root
  > `.claude/CLAUDE.md` instructs agents to read these three documents as
  > authoritative *before changing anything in `overseer/`*, so a maintainer
  > arrives with a five-item map of a twenty-six-module subsystem and no signal
  > that the rest exists. The unlisted modules trace to real shipped features
  > (`feat: cover pair-stall supervisor nudge`, `feat: escalate blocked
  > declarations by age band`, `feat: surface uncertifiable ready declarations`),
  > so this is a documentation gap, not dead code.
  >
  > **The measurement is recorded rather than the list repaired, deliberately.**
  > This section has already drifted once and been patched at the surface level
  > ("Corrected 2026-07-26: this said six modules") while the collaborator list
  > beneath it drifted four times further — which is this repo's own lesson that
  > **a rule that recounts beats a number that ages**. Enumerate from the tree
  > (`ls overseer/_supervisor_*.py`); do not re-add a hand-written list here.
  > Describing what those 4,069 lines DO belongs to whoever owns the daemon's
  > liveness/attention work (`plan/archive/daemon-liveness-truth/`, archived
  > 2026-08-03), not to the audit that
  > measured them.

  Each façade re-exports its whole group, so `import registry` / `import supervisor`
  is still the entire consumer surface and no caller changed. The collaborators are
  `_`-prefixed (a private-helper MODULE is exempt from mirror-test pairing) while their
  shared members are PUBLIC — pyright-strict's `reportPrivateUsage` rejects importing
  an `_`-prefixed name across modules, so a helper shared between siblings cannot stay
  underscore-named once it leaves one file.

  **Reach a constant through the module that DEFINES it, never through the façade.**
  A façade re-export can be `monkeypatch.setattr`-ed successfully while the real
  reader keeps its own binding — a green test over a live default. That is not
  theoretical: it appended rows to the maintainer's real `~/.livespec-overseer.jsonl`
  during the registry split.
  Precedent for host-only Python under `.claude/`:
  `.claude/hooks/livespec_footgun_guard.py`. Stdlib-only is now **load-bearing
  for the invocation surface too**: the `overseerd` executable carries a
  `#!/usr/bin/env -S uv run --script --no-project` shebang, so it runs with an
  isolated interpreter and **no dependencies** — a third-party import would break
  the shebang launch (there is no project sync to satisfy it).
- **Invocation surface (daemon vs module split; 2026-07-13).** Two homes:
  - **`overseerd`** — the dedicated daemon **executable** (uv shebang above +
    `chmod +x`). Run it with NO subcommands; its ONE option is `--warn-percent N`
    (an int in [1, 99], the daemon-wide default wind-down threshold — a per-track
    `ctx_threshold` override still wins; `overseer-start` threads it through). It calls
    `supervisor.run_daemon()`, which watches the whole fleet. It pins its own dir
    onto `sys.path` so `import supervisor` (and supervisor's siblings) resolve
    from any cwd. This is the ONLY thing the `/overseer` skill launches in the top
    pane.
  - **`supervisor.py`** — a **plain module** (NO shebang, NOT executable). It is the
    FAÇADE over `_supervisor_core` (which holds the `Supervisor` class) and holds
    `build_supervisor()` + `run_daemon()` + the one-shot track-management CLI
    (`list` / `add` / `remove` / `unassign` / `start`, `--repo` / `--topic`
    keyword flags). It carries NO `daemon` subcommand (a dedicated executable has
    no business being a subcommand of a track CLI). The skill invokes it as
    `uv run --no-project python overseer/supervisor.py <cmd>` — a
    module invoked from the skill, never a supported bare `python3` path.
    **That invocation is why `main` and the `__main__` guard stay in the façade**
    rather than moving to a `_supervisor_cli` collaborator: the shipped operator
    surface executes this exact file as a script, and a collaborator holding `main`
    would need the façade to import it, closing an import cycle.
  Beyond `--warn-percent`, there are **no config knobs**: store
  (`~/.livespec-overseer.jsonl`) and injection-stamp
  (`~/.livespec-overseer-stamps.json`) paths are hard-coded via the `registry`
  defaults, and the watch-set is read from `~/.livespec-overseer-repos.json`
  (an absolute `$HOME` path, so it works from any cwd AND from any install
  location — it is deliberately NOT derived from the module's own position) —
  no `--store` / `--stamp` / `--repos` / `--repos-only` /
  `--manifest`, and `overseerd` takes no `--interval` / `--once` / `--recover`
  (surface-only: no startup auto-recovery). The `Supervisor` dataclass keeps
  `store_path` / `stamp_path` / `watch_repos` / `manifest_path` injectable, but
  **only the beside-tests inject them** (they redirect `DEFAULT_STORE_PATH` on
  `_registry_core` — the module that both DEFINES and RESOLVES it — for CLI
  isolation; patching the `registry` façade instead sets an attribute nothing reads)
  — neither `overseerd` nor the module CLI exposes them.
- **Inside this repo's product gates.** Relocation made `overseer/` an ordinary
  first-party package in this repo. `pyproject.toml` includes `overseer` plus the
  extensionless `overseer-start` and `overseerd` executables in strict pyright,
  pytest collects `overseer`, and coverage measures the product modules with
  100% statement and branch requirements while omitting only tests and
  environment/cache paths. Ruff and the pinned `livespec-dev-tooling` checks are
  part of the `just check` aggregate as usual for this repo class.
- **The beside-tests ARE the product test suite here.** They are hermetic
  (FakeTmux, a fake `/proc`, seam-injected Codex discovery) and run in seconds.
  Run them directly while iterating:

  ```bash
  uv run pytest overseer -q
  ```

  (`conftest.py` puts the folder on `sys.path` so `import registry` / `import
  signals` / `import tmuxio` resolve when pytest collects the beside-tests.)
  The full local, pre-push, and CI gate is still `just check`.
- **The COMBINED-master-state failure mode, and what now catches it.** Two overseer
  branches can merge git-clean and still leave the folder red: a concurrent change
  to shared surface (e.g. the `TMUX_TMPDIR`/`exec` wrap once added to
  `_launch_command` — since REMOVED by `plan/tmux-fleet-visibility/`)
  can invalidate the OTHER branch's assertions, which passed on its own base.
  Proven live 2026-07-18 (the codex-reboot-recovery branch was green on its base,
  red on combined master; fixed by PR #1373). CI's `push: branches: [master]` leg
  runs against combined master after every merge, so this is
  caught rather than silent. **(Corrected 2026-07-26: this named a
  `check-overseer` recipe, which does NOT exist in this repo — verified absent
  from both the `justfile` and `ci.yml`. The protection is real but its carrier
  is different: `ci.yml` does trigger on `push: branches: [master]`, and the
  beside-tests run inside the ordinary `just check` aggregate / CI matrix. The
  substance survived the relocation; only the recipe name was carried over from
  livespec core, where the overseer used to live.)** It is caught AFTER the merge, though — auto-merge
  lands a PR before the master run finishes. So when landing an overseer change
  while another overseer branch is in flight, still re-run the beside-tests against
  the combined state yourself rather than trusting either PR's own green.
- **Codex discovery is seam-injected end-to-end, so the suite is hermetic even
  with a live codex on the host (test-isolation, 2026-07-18).** `codex_sessions` was
  already injectable at the FUNCTION level, but the `Supervisor` only threaded
  `ppid_of` into it — so `adopt_sessions` / `_refresh_codex_sessions` still read the
  real `/proc` `comm==codex` scan and the real `~/.codex/session_index.jsonl`, a host
  coupling in a unit suite (a running codex could in principle perturb a test). The
  `Supervisor` now carries `codex_home` + `codex_pids_of_comm` / `codex_fd_targets_of`
  / `codex_cwd_of` fields (default real, mirroring the Claude `sessions_dir` + `/proc`
  seams) and threads ALL of them into BOTH codex call sites. The beside-tests' `_sup`
  factory defaults `codex_pids_of_comm` to an empty scan + `codex_home` to a
  non-existent dir, so no adopt/refresh test touches real host state (with an empty
  pid scan the fd/cwd readers are never reached). A codex-behavior test injects the
  seams to SIMULATE a session end-to-end
  (`test_refresh_and_adopt_route_codex_through_injected_seams`) — the proof the
  threading holds; sabotage either call site's seams and it goes red.
- **Adding a `.py` here?** Keep it stdlib-only. The ruff `**` exclude covers new
  files automatically, and new beside-tests are picked up by the ordinary
  `just check` aggregate (pytest collects `overseer`) with no wiring of their
  own. **(Corrected 2026-07-26: this said `just check-overseer`, a recipe that
  does not exist here.)**
- **The nested `.claude/CLAUDE.md -> ../AGENTS.md` symlink beside this file** is
  the repo's per-directory nested-memory convention (so Claude Code loads this
  guide when working in the folder). No structural or coverage check objects to
  a nested `.claude/` dir inside a skill folder.

  > **The citation that used to back that sentence was wrong in three ways, and
  > is removed rather than repaired (2026-07-26).** It read: *"verified against
  > `tests/test_plugin_distribution.py` (which only asserts
  > `.claude-plugin/skills/` is absent and the repo-root `.claude/skills` is not
  > a symlink)"*. Measured: (1) no such file exists — the real one is
  > `overseer/test_plugin_structure.py`, a different directory AND a different
  > basename; (2) that test asserts nothing about `.claude/skills` being a
  > symlink — it pins the marketplace entry and both skill bindings resolving to
  > their single-source prose; and (3) the description is BACKWARDS —
  > `.claude-plugin/skills/` is not absent, it EXISTS and ships both
  > `overseer/` and `supervise-plan/`. A test asserting its absence would be red.
  > The claim above still holds; it simply has no such verifier behind it.

## How to exercise it live

The **beside-tests are the primary, complete gate** for the acting mechanics
(inject → declare → restart, archive-GC, reboot recovery, and the RB1
declaration / round timing) — they drive a FAKE tmux deterministically, so they
own that coverage. Run them first (see "Build / toolchain facts"). Since the CLI
no longer has a `--repos` / `--store` escape hatch, there is no scratch-repo
sandbox: live exercise runs against the **real fleet** (maintainer decision
2026-07-13). That is safe because the daemon is **surface-only** — nothing is
restarted unless a real track crosses threshold AND declares `ready` AND is idle.

For a change to the invocation / config surface (this file's usual subject), the
end-to-end check is the discovery + render path, exercised safely read-only:

1. Run a **read-only render** against the real fleet:
   `uv run --no-project python overseer/supervisor.py list` — it
   calls `tick(act=False)`, so it discovers every declared repo's `plan/*/`,
   joins the mapping, and prints the `Status · Topic · tmux · Ctx% · Repo` table
   **without injecting or restarting anything**. This exercises the whole reshaped
   surface (module invocation, fixed store path, fleet-only watch-set) with zero
   mutation risk.
2. Optionally observe a **brief live daemon** (`overseer/overseerd
   2>> tmp/overseer/daemon.log`, stopped after a render or two) to confirm the loop
   renders and refreshes. Surface-only means it will not act on any real session
   unless that session is genuinely at threshold + certified + idle.

   **Isolation tip for exercising `overseerd` safely off the real fleet — this
   got MUCH simpler, and the old recipe is obsolete.** The watch-set is now an
   absolute `$HOME` path, so isolation is just a scratch `HOME` plus the real
   session registries:

   ```bash
   SCRATCH_HOME=/tmp/ov/home
   mkdir -p "$SCRATCH_HOME" /tmp/ov/projects/demo/plan/demo-topic
   ln -s ~/.claude "$SCRATCH_HOME/.claude"
   ln -s ~/.codex  "$SCRATCH_HOME/.codex"
   ln -s ~/.cache  "$SCRATCH_HOME/.cache"
   printf '{"repos": ["/tmp/ov/projects/demo"]}' > "$SCRATCH_HOME/.livespec-overseer-repos.json"
   HOME="$SCRATCH_HOME" .venv/bin/python3 overseer/supervisor.py list
   ```

   That redirects the watch-set AND the mapping store AND the stamp sidecar in
   one move, since all three are `$HOME`-anchored. Session discovery is
   `$HOME`-anchored too (`~/.claude/sessions` for Claude Code and `~/.codex`
   for Codex), so the symlinks keep adoption able to see live sessions without
   giving it permission to touch real tracks. Adoption is bounded by the
   watch-set, not by the registry: `adopt_sessions` builds its active topic map
   from `registry.discover_plans(watch_repos=resolve_watch(...))`, and a session
   is adopted only when its registry `cwd` resolves inside a watched repo and
   its `name` is an active discovered topic there. A scratch watch-set therefore
   cannot reach a real track even with the real registries visible.
   Verified 2026-07-20: it renders exactly one row, `unassigned  demo-topic`,
   which also demonstrates the invariant the design turns on — a plan with NO
   assigned session is still discovered, because the watch-set is declared
   rather than derived from the mapping store's existing rows. Do not use an
   all-`unassigned` render as an adoption proof by itself: it is ambiguous
   between correct isolation and a pure scratch `HOME` that blinded session
   discovery. For the full adoption harness and blast-radius proof, see
   `plan/archive/codex-parity-and-rollout-safety/research/daemon-adoption-harness.md`.

   **Gotcha: do NOT wrap this in `mise exec` / `uv run`.** `mise` reads its own
   config out of `$HOME`, so overriding `HOME` makes it fail with
   "Config files in /home/ubuntu/mise.toml are not trusted" before your code
   runs at all. Invoke the venv interpreter directly, as above.

   The SUPERSEDED recipe was to copy this whole folder into a scratch repo tree
   with a scratch `.livespec-fleet-manifest.jsonc` beside it, because the manifest
   was resolved by walking up from the module file — so the only way to change the
   watch-set was to physically move the code. Do not do that any more; it works by
   accident at best. Two gotchas from that era still apply:
   - **Do NOT point `HOME` at a fresh empty dir to isolate the store.** `uv run`
     keys its cache off `$HOME/.cache/uv`; an empty HOME forces uv to cold-rebuild
     its whole environment and **hangs** (looks exactly like a daemon bug — it is
     not). If you must isolate the store off `~`, symlink the warm cache in first
     (`ln -s ~/.cache "$SCRATCH_HOME/.cache"`), as the recipe above does.
   - The render flushes each tick but `uv run` may swallow piped stdout when the
     process is `timeout`-SIGTERM-killed; capture with a decent timeout and read
     the streamed lines, or observe the pane directly. (Direct `python`/venv-python
     runs the same body identically; the beside-tests remain the primary gate.)

The daemon's diagnostics + `overseer[SURFACE]:` alerts go to stderr; redirect
them to a log under `tmp/overseer/` (maintainer-owned scratch root — use a
scoped subdir, never `rm` the root).

**Timing-sensitive behavior (the RB1 lesson) is covered by the beside-tests, not
a hand-driven loop.** The regression that once slipped through a live re-test —
the "void the `ready` declaration when busy" logic racing the declaring turn's own
busy tail (final streaming + stop hooks keep the pane busy 10–60s AFTER the file
is written) — is what the arm-until-idle redesign retired outright, and the
replacement max-age expiry is pinned by deterministic fake-tmux tests
(`tests/integration/test_post_expiry_certification_floor.py`,
`tests/integration/test_expiry_notice.py`,
`overseer/test_supervisor_ready_expiry_edges.py`). The invariant-7/8/9
behaviors are pinned the same way
(`test_idle_at_danger_with_no_declaration_is_never_restarted`,
`test_winding_down_ack_suppresses_the_rewarn`,
`test_stale_winding_down_ack_resumes_escalation_but_still_never_acts`,
`test_malformed_state_value_is_surfaced_and_never_restarts`,
`test_every_track_alert_names_the_tmux_session_and_pane`). Do NOT try to reproduce
any of it by manufacturing a threshold crossing on a real working session — the
daemon exercises the full inject → declare → restart cycle live only when a real
track naturally reaches it (its steady-state job); the deterministic tests own that
coverage, and hand-spaced ticks would mask the timing anyway.

### The RELAUNCH COMMAND is the one thing the beside-tests structurally cannot own

The paragraph above is right about **timing**: do not hand-drive the inject →
declare → restart cycle to check interlock behavior, because the fake-tmux tests
own it and hand-spaced ticks mask the very races you would be looking for.

It leaves a gap, and a P1 shipped through it. The beside-tests assert the
**rendered launch command and env delta as strings**. Nothing ever *executes*
them. So a relaunch string that is exactly what the code intends to write, and
is also unrunnable, passes every gate at 100% coverage. That is precisely what
happened: every wrapper-arm relaunch rendered its env delta with the assignment
ahead of the unset flags, which GNU `env` rejects, so the relaunch died with
status 127 — and because a tmux pane whose command exits is *closed*, a
single-pane tracked session was destroyed rather than merely mis-launched.
Green suite, shipped on master, found only by running it.

**So the carve-out is narrow and worth stating exactly.** Live exercise here is
not for the interlock and not for timing. It is for the two questions the string
assertions beg:

- does the rendered command actually **execute**, and
- does the fresh process's `/proc` show the **profile that was recorded**?

Read the answer from `/proc/<pid>/cmdline` and `/proc/<pid>/environ` of the
**fresh** process. Never from the statusline — that is a display-name surface and
the spec already restricts it to verification only.

**Use throwaway tracks and a scratch `HOME`, not the real fleet.** The isolation
recipe above already redirects the watch-set, the mapping store and the stamp
sidecar in one move, and it is the right base here — a scratch-`HOME` `overseerd`
of your own cannot reach a real track even with the real session registries
symlinked in, so the cardinal rule is protected structurally rather than by care.
(Recorded because a 2026-08-19 exercise did it the hard way instead: it added a
throwaway repo to the **real** watch-set and let the **fleet** daemon adopt it.
Nothing was harmed and every artifact was torn down, but it put exercise rows in
front of every operator and foreman for half an hour for no reason. The scratch
`HOME` was already documented directly above. Use it.)

Launch two throwaway tracks in the scratch tree — one cloud, one through the
local wrapper — so both relaunch arms are covered:

```bash
tmux new-session -d -s ex-cloud -c "$EX" \
  'claude --model sonnet --dangerously-skip-permissions -n ex-cloud'
tmux new-session -d -s ex-local -c "$EX" \
  '/data/projects/local-llm/bin/claude-local-llm --dangerously-skip-permissions -n ex-local'
```

Pick the cloud model to **differ from `~/.claude/settings.json`'s `model`**, and
check what that is on the day rather than trusting any doc — otherwise a profile
that was silently dropped and one that was correctly preserved look identical in
`/proc`. (The epic's own text said the default was `sonnet`; measured
2026-08-19 it was `opus[1m]`.)

**"CHECK IT ON THE DAY" IS NOT STRICT ENOUGH — IT MOVES WITHIN A DAY.** Three
distinct values were observed on **2026-08-19 alone**: `opus[1m]` (the measurement
recorded in the line above), `claude-fable-5[1m]` at 14:19Z, and plain `opus` from
19:51:07Z. The parenthetical above therefore aged inside its own day, which is the
cheapest possible demonstration of the point.

This matters beyond the live exercise, because the default is one half of every
divergence judgement: whether a session is "on the default" or "silently converted"
is a COMPARISON, and a comparison has two sides. A live reading of a pane compared
against a remembered default is not a measurement, it is a measurement against a
guess — and it fails in the direction that looks authoritative, because the half you
refreshed is the half you were thinking about. **Re-derive BOTH sides in the same
breath**: read `~/.claude/settings.json` at the moment you read the panes, never
from memory, a doc, or an earlier step of your own session.

Two corollaries paid for the same day. The alias is not self-interpreting — `opus`
renders as plain `Opus 5`, NOT the 1M variant, and the picker offers both, so resolve
it by launching a disposable scratch session and reading what it actually inherits
rather than by reasoning about the alias table. And a partition computed against a
stale default inverts rather than merely drifting: the same sweep data yielded 25
diverged against one baseline and 22 against the correct one, with sessions moving in
BOTH directions across the boundary.

**Four things will waste your time in this order. All four were paid for once.**

1. **A track parked on Claude's trust-folder gate adopts with NO profile, and
   says nothing about it.** A fresh scratch repo always shows that gate. The
   daemon adopts the session, writes the mapping row, and `_profile_for_adoption`
   quietly returns `None` because the session has not registered yet. Clear the
   gate first, then confirm the row actually carries `model_profile`.
2. **A profile is captured at ADOPTION or when a wrap-up round OPENS — nowhere
   else.** There is no per-tick refresh. To get a profile onto a row that already
   exists, `remove` the row and let the daemon re-adopt it.
3. **The tmux SESSION name must keep carrying the mapped identity.** The stall
   watcher re-resolves its target from the mapped session after an apparent
   daemon bounce. Pane titles are deliberately not an identity: live Claude panes
   carry activity prefixes and may drift to task summaries.
4. **A `ready` file with no open round restarts nothing** — `ready_valid`
   requires the declaration's mtime to beat the round's certification floor. Open
   a round on demand with the per-track `--ctx-threshold` knob set just above the
   track's current remaining context. Note that `overseer add` **upserts**, so it
   drops the `model_profile` the adoption just captured; set the threshold first,
   or re-record the profile afterwards with `registry.record_model_profile`.

Have the session declare for itself (`overseer-declare ready`) rather than
writing the state file on its behalf. It costs one turn and keeps the exercise
honest — the whole point of the cardinal rule is that the declaration comes from
the session.

**A local-wrapper track has a small context window** (the wrapper pins
`CLAUDE_CODE_MAX_CONTEXT_TOKENS`), so a long instruction can exhaust it before it
can declare anything, and the wrap-up body is not short. Keep every paste to that
track minimal.

## Recovering + restoring sessions after a reboot or tmux crash/kill

When the tmux server dies (a crash, a `kill-server`, a host reboot) every tracked
pane's Claude process dies with it. This is the runbook to bring the tracks back
**with their prior conversations intact** — the exact procedure, plus the three
launch commands that are WRONG for it, each learned the hard way (2026-07-18: two
consecutive wrong relaunches before the right one).

### What survives the crash, and what does not

| Survives (on disk) | Dies with the tmux server |
|---|---|
| The JSONL mapping `~/.livespec-overseer.jsonl` — one row per assigned track (topic ↔ tmux name ↔ repo ↔ plan ledger `epic` ↔ optional operator resume override). It emits NO `handoff` key; a legacy row carrying one is read without error and rewritten without it. | Every tmux session / window / pane (no `tmux-resurrect` / `tmux-continuum` is installed — a server death loses the whole layout). |
| Each Claude session's **conversation transcript**: `~/.claude/projects/<cwd-slug>/<session-id>.jsonl`, where `<cwd-slug>` is the repo path with every `/` rewritten to `-` (e.g. `/data/projects/livespec` → `-data-projects-livespec`). | Claude Code's pid-keyed live registry `~/.claude/sessions/<pid>.json` (keyed by the now-dead pid). |
| Each Codex session's **rollout** (`~/.codex/sessions/YYYY/MM/DD/rollout-<ts>-<id>.jsonl`) AND the **codex index** (`~/.codex/session_index.jsonl`, mapping id → thread_name = topic). This is what lets `recover_missing_sessions` reverse-look-up a dead codex track's id by topic and `codex resume` it AUTOMATICALLY (defect #5) — no manual step for codex. | The running codex process + its held-open rollout fd (the LIVE signal `self.live_codex` derives from — gone at cold start, which is why recovery uses the surviving INDEX instead). |
| Each plan's ledger-held plan state (the entries on its ledger epic). | The daemon process + its in-memory round state. |

The transcript is what makes a TRUE resume possible: the tmux pane is gone, but the
conversation was streamed to disk continuously, so it can be re-attached by session
id. Nothing in tmux persists — the only durable identity is that transcript file.

### The daemon does NOT do this for you

`overseerd` is **surface-only** — it never auto-spawns a session (invariant 3), and
its startup `recover_missing_sessions` is **split by runtime** (defect #5, 2026-07-18):
a **Claude** track is relaunched with the LAUNCH command + a resume-prompt paste, **not**
`--resume`, so it restores a *plan-state re-read*, never the *live conversation*; a
**Codex** track IS resumed by `codex resume <id>`, which reattaches the *live rollout*
(the codex conversation restores automatically — the Claude gap this section works
around does not apply to codex). So this **manual, human-driven** procedure is the way
to restore the actual **Claude** conversations (see invariant 7 and the
`recover_missing_sessions` docstring). (SKILL.md's "Cold-start / crash recovery"
section describes the `start`-based path, which is the plan-state-re-read one; THIS
section is the Claude conversation-restore one, and they are different outcomes.)

### The three launch commands that are WRONG (each was tried and failed)

1. **`claude -n <topic>`** — a BRAND-NEW session. `-n` only sets the display name;
   there is no resume. This is the overseer's OWN `_launch_command`, correct ONLY
   when *followed by a paste* of the resume prompt. With nothing pasted you
   get a fresh, context-free session — the tracks lose all their state.
2. **`claude --resume` with NO value** — opens the interactive picker and leaves
   every pane stuck on it. `--resume` resumes directly ONLY when given a session id;
   bare `--resume` is by definition the picker.
3. **`claude --continue`** — resumes the single most-recent conversation in the cwd.
   WRONG whenever a repo holds more than one track (e.g. `livespec` holds ~6): every
   pane would race for the same one conversation. And right after a botched attempt
   the "most recent in cwd" is your own junk session, not the real one.

### The RIGHT command

```
claude --resume <session-id> --dangerously-skip-permissions -n <topic>
```

- **Carry NO tmux env scoping — no `unset TMUX`, no `TMUX_TMPDIR` export.** The
  former L1 env-inversion prefix (`unset TMUX; export TMUX_TMPDIR=…; exec …`)
  was REMOVED by `plan/tmux-fleet-visibility/` (2026-07-19): it blinded every
  scoped agent to the real fleet (`tmux ls` returned a clean, plausible, wrong
  "no server running", producing repeated false session-liveness claims) while
  silently failing open whenever its tmpfs-backed directory vanished. The L2
  `PreToolUse` command guards are the sole mechanical fleet-kill control — they
  are the only layer that can distinguish a listing from a teardown. A restored
  session's bare `tmux ls` MUST tell the truth; do not re-add a scoping prefix
  here or in `supervisor.py` (`test_claude_launch_command_carries_no_tmux_scoping`
  and its codex twin pin the absence). An earlier version of this bullet said the
  prefix was "NOT optional" — that guidance is REVERSED, deliberately.
- `--resume <session-id>` re-attaches THAT exact conversation, no picker.
- `--dangerously-skip-permissions` — required so the resumed session is autonomous
  (the whole fleet runs with it; without it the session stalls on its first
  permission prompt).
- `-n <topic>` — keeps the display name equal to the plan topic, which is what the
  daemon adopts on (`names_by_tmux_session`); belt-and-suspenders, since the resumed
  transcript already carries the topic as its `customTitle`.

### Step-by-step

**0. Re-establish the daemon top pane.** From the bottom (Claude) `/overseer` pane,
re-run `overseer/overseer-start` (idempotent; splits the daemon pane,
re-attaches to the surviving mapping, adopts sessions).

**1. Read the surviving mapping** — it is the recipe (which topics, which tmux names,
which repos):
```
cat ~/.livespec-overseer.jsonl
```

**2. List the live tmux sessions and note which to LEAVE ALONE.** Never respawn a
session a human is actively using (e.g. a crash-investigation shell). Confirm the
current set first:
```
command tmux list-sessions -F '#{session_name}'
```

**3. Compute topic → correct session-id.** The transcript filename is the id; the
`-n <topic>` name is stored inside as `customTitle` (also `agentName`); `sessionId`
repeats it. THE TRAP: your own fresh/junk relaunches and picker respawns ALSO carry
`customTitle=<topic>`, so "most recent with this title" can select junk. Filter by
SIZE (real pre-crash conversations are hundreds of KB to several MB; a fresh/junk
session is a few KB) and take the most-recent above the threshold. This snippet
prints the candidates so you can eyeball them:
```
python3 - <<'EOF'
import json, os, glob, time
now = time.time()
# {cwd-slug: [topics]} — fill from the mapping read in step 1.
TARGETS = {
    "-data-projects-livespec": ["fabro-ci-image-factoring", "autonomous-mode"],
    "-data-projects-livespec-orchestrator-beads-fabro": ["codex-factory-telemetry"],
    "-data-projects-livespec-dev-tooling": ["fleet-plan-lifecycle-enforcement"],
}
base = os.path.expanduser("~/.claude/projects")
def title_of(path):
    ct = None
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for i, line in enumerate(fh):
            if i > 25:
                break
            try:
                o = json.loads(line)
            except Exception:
                continue
            if isinstance(o, dict) and o.get("customTitle"):
                ct = o["customTitle"]
    return ct
for slug, topics in TARGETS.items():
    d = os.path.join(base, slug)
    recs = [(f, title_of(f), os.path.getsize(f), os.path.getmtime(f))
            for f in glob.glob(d + "/*.jsonl")]
    for t in topics:
        cands = sorted([r for r in recs if r[1] == t and r[2] > 100_000],
                       key=lambda r: r[3], reverse=True)
        print(f"\n### {slug} :: {t}  ({len(cands)} real candidate(s))")
        for f, ct, sz, mt in cands[:4]:
            print(f"   {os.path.basename(f)[:-6]}  {sz/1e6:6.2f}MB  {(now-mt)/60:6.1f}min ago")
EOF
```
The top row per topic is the one to resume. CROSS-CHECK it before trusting it:
`claude --resume` (the picker) shows each conversation's size + age + PR number; the
chosen transcript's size/age must match the picker row for that topic. The correct
target is the one last-written **at the crash moment** — every crash-time session
shares roughly the same mtime, which clusters them apart from older, larger
predecessors carrying the same title.

**4. Canary ONE pane first.** Do not batch all of them at once — a wrong command
wastes every pane. Respawn one and confirm the actual conversation loaded:
```
command tmux respawn-pane -k -c <repo> -t '=<tmux-name>:' \
  "claude --resume <session-id> --dangerously-skip-permissions -n <topic>"
sleep 15
command tmux capture-pane -p -t '=<tmux-name>:' | tail -30
```
SUCCESS looks like the prior conversation's tail + an empty `❯` box + a statusline
reading `── <topic> ──` and `Ctx: N% left`. FAILURE looks like the picker (`Search…`
/ `show all projects`), a fresh welcome banner, or the wrong topic. A big
conversation can take 10–25s to render — wait and re-capture before judging it
failed (`#{pane_current_command}` == `claude` while the screen is still blank means
it is still loading, not broken).

**5. Batch the rest** once the canary is verified — one
`respawn-pane -k … --resume <id> … -n <topic>` per remaining track, each with its
own computed id.

**6. KICK each restored track — restoring it does NOT make it run.** A `--resume`d
pane comes back with its conversation loaded but its last turn already FINISHED, so
it sits at an idle `❯` doing nothing until something prompts it. This step is the
difference between "the tracks are back" and "the tracks are working"; skipping it
is the single most common way a recovery is reported complete while the whole fleet
sits idle. Paste a kick and submit it (`load-buffer -` + `paste-buffer -p`, then
`Enter` — the same atomic-paste discipline the daemon uses; never type it key-by-key):

```
Your tmux session was killed at <time> by an external fleet-wide tmux kill-server
(not caused by anything you did, and not a maintainer decision). The session has now
been restored with your full conversation intact. Re-read your plan's ledger-held plan state
to re-ground yourself, then continue exactly where you left off.
```

**Say explicitly that the kill was external.** A restored pane renders its dead
sub-agents as `Agent "…" was stopped by user` and its dead background commands as
`Background command "…" was stopped` — a resumed session reads those as the
MAINTAINER having cancelled its work and will abandon it. Name what died in the kick
(live 2026-07-19: `rop-sweep-fleet-policy`'s Fable review and `codex-yolo-sandbox`'s
factory dispatch both had to be corrected this way).

**DO NOT kick a track in any of these four states — read the pane FIRST, one at a
time.** A kick is arbitrary text submitted into whatever is focused, so kicking a
waiting session ANSWERS its question on the maintainer's behalf:

| State | How it looks | What to do instead |
|---|---|---|
| **Structured gate** | an `AskUserQuestion` picker, permission prompt, or trust prompt (`❯ 1.` / `› 1.`) | Leave it. Report the tmux session + pane; the maintainer answers IN THAT PANE. |
| **Prose question to the human** | the turn ENDS asking the maintainer something ("Want me to X, or leave it?") | Leave it. This has no picker and no gate — only reading the tail catches it. |
| **Declared `blocked: <reason>`** | `<repo>/tmp/overseer/<topic>/.overseer-state` reads `blocked:` | Leave it. It is waiting on a human by its own declaration. |
| **Already self-continuing** | it died mid-turn and resumes on its own; pane goes busy with no prompting | Leave it. A kick would queue a redundant turn. |

Both waiting states occurred in ONE recovery (2026-07-19): `autonomous-mode` had
ended its turn asking the maintainer a question, and `tmux-fleet-kill-prevention`
sat on a 3-option `AskUserQuestion` picker. A blind kick-everything sweep would have
silently answered both. Checking the four states costs one `capture-pane` per track.

**7. Verify all — by the REGISTRY, not by the pane.** Read
`~/.claude/sessions/<pid>.json` (`status` is `busy` / `shell` / `waiting` / `idle`)
rather than grepping the pane for a spinner: a streaming Claude renders NO busy
marker in the captured region, and the lingering completed-turn summary
(`✻ Baked for 3h 43m`) false-matches a naive `✻` grep — so pane-scraping reports
working tracks as idle AND idle tracks as working, in both directions at once
(live 2026-07-19). A kicked track must read `busy`; a deliberately-unkicked one
reads `waiting` or `idle`. Each pane's statusline should also name its own topic
and show no unexpected picker; the daemon re-adopts each within a tick.

### Two post-resume states are BOTH correct

- **Small sessions** load straight to an empty `❯` prompt — ready to continue.
- **Large sessions** (high token count) show Claude's own guard first:
  `Resume from summary (recommended) / Resume full session as-is / Don't ask me
  again`. **ALWAYS select 2. Resume full session as-is** — `Down` then `Enter`
  (maintainer-declared 2026-07-19: this is a STANDING rule, not a per-incident
  choice; do not re-ask it). Recovery exists to restore exact state, and Claude's
  own "recommended" summary option silently compacts away the in-flight detail a
  killed-mid-turn track needs. CANARY the keystroke: send `Down`, re-capture and
  CONFIRM the cursor moved to option 2 before sending `Enter` (the first capture
  often lags the redraw), so you never confirm the wrong choice.

  This REPLACED a directly contradictory instruction. An earlier version of this
  bullet said to "leave it for the human; do NOT keystroke a selection", while the
  paragraph below it said you MUST clear the modal to get the track working — a
  reader following the first sentence would restore the fleet into a frozen state
  and report success. If you find yourself re-adding "leave the modal alone", stop:
  that is the contradiction, not a safety rule. (The modal is NOT universal — it is
  the large-session case only. In the 2026-07-19 recovery all five restored tracks
  came back at 43–74% context and none showed it; every one landed idle at `❯` and
  needed step 6's kick instead. Expect the kick path far more often than this one.)

While a picker OR that resume-choice prompt is open, the daemon reads the pane as a
structured gate and classifies it `blocked:human`, so it will not inject or restart
it. That self-heals the moment the human answers.

**A large session sitting on that modal is LOADED-BUT-NOT-RUNNING — that is what
"restored but still stuck" looks like (live 2026-07-19).** Restoring five Claude
tracks with `--resume` re-attached every conversation correctly, yet all five then
sat frozen on the summary-vs-full guard: the operator reads "not restarted." The
conversation IS back (verify by the pane's real tail + the token count matching the
transcript size), but nothing runs until the modal is answered. Clear it as the
bullet above says (`Down` → confirm → `Enter`, always option 2).

**LOADED IS NOT RUNNING — and that is true whether or not a modal appeared.** After
the modal is cleared (or when none appeared at all) the pane either self-continues,
because it died mid-turn, or lands idle at a ready `❯`, because its last turn had
finished. The second case is the common one, and it is what step 6's kick is for:
an idle restored track will sit there indefinitely. "Every conversation re-attached
correctly" is NOT the success condition for this runbook — "every track is `busy` in
the registry, or is deliberately left waiting on the maintainer" is.

### tmux gotchas that bit during this procedure

- **Use `command tmux`, never bare `tmux`.** A zsh `tmux` function shim errors
  `zsh: command not found: _zsh_tmux_plugin_run`; `command tmux` bypasses it (the
  same reason `tmuxio.py` shells out with an argv list rather than a shell string).
- **`respawn-pane -t` rejects `=name` but ACCEPTS `=name:` — use the trailing
  colon, never a bare name. (CORRECTED 2026-08-01: this bullet used to send
  operators to the bare form, which is the unsafe one.)** The old text's first
  half was right and is worth keeping, because someone will rediscover it:
  `=livespec1` really does fail, with `can't find pane: =livespec1`. But the
  exact-match form the charter gate mandates is `'=name:'` **with the trailing
  colon**, and that works on every subcommand this runbook and `tmuxio.py` use —
  `respawn-pane`, `capture-pane`, `list-panes`, `send-keys`, `paste-buffer`,
  `has-session` (all measured on this host's tmux, 2026-08-01).

  **Why the old advice was dangerous — measured, not argued.** A bare `-t`
  PREFIX-MATCHES. With only `canary-two` alive, `respawn-pane -k -t canary`
  returned **rc=0 and ran its command inside `canary-two`**: a destructive
  respawn landing in the wrong live session, silently. `-t '=canary:'` refuses
  the same call (rc=1, `can't find session: canary`). tmux prefers an exact match
  when one exists, so this fires precisely when the session you meant is GONE —
  which is the state this entire runbook exists for. The collision is not
  hypothetical: this host currently runs **14** session-name pairs where one name
  extends another, including `supervisor-prompt-quality` /
  `supervisor-prompt-quality-supervisor` and `livespec` / `livespec-overseer`.

  **THE DAEMON IS ALREADY PROOF AGAINST THIS, AND THE CONTRAST IS THE POINT.**
  `tmuxio.py` does pass a bare `-t <session>` to `capture-pane`, `send-keys`,
  `paste-buffer`, `respawn-pane` and `list-panes` — and that is SAFE BY DESIGN,
  not by luck. `TmuxIO.session_exists` deliberately uses **exact membership in
  `list-sessions`** rather than `has-session -t <name>`, precisely because a bare
  `-t` prefix-matches (adversarial-review blocker B1, verified live 2026-07-13;
  pinned by `test_session_exists_is_exact_membership_not_prefix`). Once that
  exact-membership gate says the session is live, every later `-t <session>` call
  resolves to it, because **an exact session name takes precedence over a prefix
  match** — the same precedence measured above. The only residue is an inherent
  TOCTOU window if the session dies between the check and the call.

  **So the hazard this bullet describes is a RUNBOOK hazard, not a daemon one, and
  that is exactly why the fix above matters.** A human following these steps types
  a session name straight into `respawn-pane -k` with **no `session_exists` gate
  in front of it** — during a recovery, when the session they are naming may well
  be gone. The daemon earned its safety with a deliberate, tested design decision;
  this procedure never had one. Use `'=<name>:'` and it does.
- **Fresh session vs. existing pane.** If the tmux session is GONE, recreate it
  first (`command tmux new-session -d -s <name> -c <repo>`), then `respawn-pane -k …`
  — this mirrors the daemon's own `new_session` + `respawn_pane` split, so the shell
  / env behavior matches what works in production. If the pane already exists (e.g. a
  prior wrong-command attempt), `respawn-pane -k …` alone replaces it.

### Known gap worth closing — now CLAUDE-only (codex is closed)

For **codex**, `recover_missing_sessions` now DOES restore the live conversation: it
resumes by `codex resume <id>`, the id recovered from the surviving codex index by plan
topic (defect #5, 2026-07-18). For **claude**, the gap remains — `start` /
`recover_missing_sessions` relaunch fresh + paste a resume prompt rather than `--resume`. If
native "restore the live CLAUDE conversation after a crash" is wanted, that is where it
would go: a `claude --resume <id>` arm that looks the topic's id up by `customTitle` in
`~/.claude/projects/<cwd-slug>/` (the exact computation step 3 automates) — the direct
analogue of the codex reverse-index lookup just landed. Until then, this manual runbook
is the procedure for Claude tracks.

### Session-restart learnings (live-verified 2026-07-19)

A dedicated log of what actually bit while restarting tracks, so the next operator
does not re-learn it. Append here — do NOT scatter these.

- **`start` / `add` `--repo` MUST be the full ABSOLUTE path, never the bare slug.**
  `start --repo livespec --topic <t>` silently launches the session in `$HOME`: the
  bare `livespec` is a RELATIVE path, so tmux's `-c livespec` fails to that repo and
  falls back to home, the repository path named in the resume line is wrong,
  and `_do_launch` then fails at the await/submit while claude boots in the wrong cwd
  — reported only as a generic `start FAILED to launch`. Always pass
  `--repo /data/projects/<repo>`. (`repo_slug`/`tmux_id` still produce the right
  session NAME from a bare slug, which is why the failure is silent — only the cwd and
  resume path are wrong.)
- **A `--resume`d large session FREEZES on the summary-vs-full modal** — see "Two
  post-resume states are BOTH correct" above. Loaded ≠ running; answer the modal to
  make it run, canarying the `Down`→confirm→`Enter` keystroke.
- **Renaming a session out-of-band SELF-HEALS in the store — no manual store edit.**
  Renaming `<repo-slug>--<topic>` → the plain `<topic>` (or any name) with
  `command tmux rename-session` is safe: the daemon adopts the live claude by its
  REGISTRY name (the topic), independent of the tmux session name, and `adopt_sessions`
  re-points the mapping row's `tmux` field to the new name within one tick (R2 repoint).
  Verified live: renaming all six live sessions to bare topic names left the store
  auto-repointed and every row still tracked.
- **`overseerd` NEVER runs `recover_missing_sessions` — this runbook is the ONLY
  path back.** Recovery is gated behind `run_daemon`'s `recover` parameter, and the
  `overseerd` executable passes no `--recover` flag (it is surface-only). So a
  restarted daemon will NOT bring dead tracks back, and — the useful corollary —
  it also cannot CLOBBER a manual `--resume` restore that is in progress. The
  "Recovering + restoring" section's talk of "its startup `recover_missing_sessions`"
  describes the function, not something the shipped daemon actually invokes.
- **The codex index can hold a STALE NAMESAKE — never classify a track's runtime by
  topic alone.** `autonomous-mode` appeared in `~/.codex/session_index.jsonl` (so a
  reverse-index lookup calls it a Codex track and would `codex resume` it), while its
  REAL live track was a Claude session whose transcript sat in the crash-moment
  cluster; the index entry was a 6-day-old namesake. Cross-check the index hit's
  `updated_at` against the Claude transcript cluster and prefer the crash-moment
  evidence. Conversely, a topic NAMED for codex is not a codex track:
  `codex-yolo-sandbox` is a Claude session whose SUBJECT is codex.
- **A mapped track may have NEVER LAUNCHED — that needs `start`, not `--resume`.**
  `cockpit-ux-docs-release` was in `~/.livespec-overseer.jsonl` but had no transcript
  with that `customTitle` ANYWHERE on the host (and its repo had been untouched for
  ~9 days): it was registered and never started, so there was nothing to resume.
  Distinguish it from a killed track by the absence of ANY titled transcript, then
  launch it with the CLI (`supervisor.py start --repo <ABSOLUTE path> --topic <t>`),
  which pastes and auto-submits the resume line for you — no manual kick needed.
- **The crash-moment mtime cluster is the reliable id selector.** All six killed
  tracks' transcripts shared the same mtime to within a rounding minute, which
  separated them cleanly from older same-title predecessors. Trust that cluster over
  "most recent with this title"; a topic with 16 title-matching candidates resolved
  unambiguously this way.
- **`overseerd` keeps running the OLD code until you restart it.** The daemon is a
  long-lived process; editing `supervisor.py`/`_supervisor_*.py`/`registry.py` and
  merging does NOT change
  a running daemon's behavior. After landing an overseer code change, restart the daemon
  (re-run `overseer-start`, or kill the daemon pane and relaunch) to load it. The
  one-shot track CLI (`list`/`add`/`start`) DOES pick up new code immediately (fresh
  process per invocation).
- **The relocated repo's gates run the overseer suite.** The old warning that CI
  and Fabro did not run the beside-tests is obsolete. `just check` is the single
  local, pre-push, and CI gate; it collects the overseer tests, applies strict
  pyright to the package and extensionless executables, and enforces coverage.
  Run `uv run pytest overseer -q` while iterating, then `mise exec -- just check`
  before handing off.

## Pointers

- `.claude-plugin/prose/overseer.md` — **the** runtime bottom-pane operator
  contract, and the single source for it.
- `SKILL.md` (beside this file) — **a 15-line compatibility POINTER, not a
  contract.** It says so itself: *"Do not add behavior or operator prose here."*
- `marker-protocol.md` — the escalating wrap-up + the ONE-state-file declaration
  contract (`ready` / `blocked: <reason>` / `winding-down`) and the restart
  interlock.

> **Two pointers in this list were DEAD and are removed (2026-07-26).** Both
> pointed outside this repo and neither survived the relocation:
>
> - **`design.md` "beside the plan at `plan/overseer-rewrite/`"** — that plan
>   directory does not exist here, and `git ls-files` finds no `design.md`
>   anywhere in the repo. It described the pre-relocation design doc, including
>   its "Adversarial review (2026-07-12)" section.
> - **the root `AGENTS.md`'s `.ai/agent-disciplines` topic** — there was no
>   `.ai/` directory in this repo when this pointer was removed, and the root
>   `AGENTS.md` still carries no RESOLVABLE `.ai/<topic>.md` reference
>   (re-measured 2026-07-30; it does now mention `.ai/` in prose, which this
>   check does not resolve and must not). A
>   `.ai/` directory EXISTS today, added by `7e246e0` for the layered supervisor
>   prompt, and holds only `supervisor-protocol.md`; the `agent-disciplines`
>   topic still does not exist, so this removal stands. Naming that topic with
>   its `.md` extension HERE would break `check-agents-ai-references-resolve`,
>   which resolves `.ai/<topic>.md` paths in any file called `AGENTS.md` — the
>   same check this note goes on to discuss. Measured: it does.
>   Note that `doctor-agents-ai-reference-resolution` PASSES: it
>   validates `.ai/<topic>.md` paths in the format the root file uses, and this
>   file's prose-style mention was never in its scope. A green doctor run was not
>   evidence for this pointer.
>
> `marker-protocol.md`'s Pointers section carried the same two and is corrected
> alongside. Both are recorded rather than silently deleted, because a reader
> arriving from the archived predecessor thread will look for them.

Note the third correction in this list: `SKILL.md` was described as "the runtime
bottom-pane contract". It has not been that since the prose was extracted to
`.claude-plugin/prose/overseer.md` — following the old description lands a reader
on a stub.
