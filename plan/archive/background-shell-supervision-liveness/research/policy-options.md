# Background-shell supervision liveness — policy options

## Purpose and status

This note compares the candidate contracts for preventing a stale background
shell from shielding a low-context track indefinitely, and states the
**recommended contract**. The measured facts and the governing constraints live
in `root-cause.md`; do not restate ledger status here.

Status: **investigation complete, recommendation ready for ratification.** The
recommendation is not implemented and must not be implemented from this note.
It changes two governed clauses, so it goes through `livespec:propose-change`
first; implementation then runs through `impl:overseer-vyjkzw`.

## What the daemon can actually see

Every fact below is already gathered by `_supervisor_observe.observe`. The
recommendation adds **no new evidence source** — it only times a signal the
daemon already derives and already trusts.

| Fact | Claude (adopted, registry present) | Codex (no registry entry) |
|---|---|---|
| "a background command is live" | `claude_status == "shell"` — Claude's own authoritative self-report: at the prompt with a live `Bash(run_in_background)` command | `codex_fallback` — `claude_status is None and has_active_subshell(pane_pid)`, the runtime-agnostic descendant-shell walk |
| "the agent is generating" | `claude_status == "busy"` (generating or in-process sub-agent) | `signals.is_busy(capture)` — Codex renders `esc to interrupt` / `Working …` |
| "the pane is not visibly generating" | `not signals.is_busy(capture)` | `not signals.is_busy(capture)` |
| "waiting on a human" | `claude_status == "waiting"`, or `signals.is_structured_gate(capture)` | `signals.is_structured_gate(capture)` (the `› 1.` picker) |
| remaining context | `signals.parse_ctx_remaining` → `eff_ctx` | same parser, same field |

Two properties of that table are load-bearing for the recommendation:

- **Claude's `shell` already carries the prompt-state evidence.** The registry
  vocabulary separates `busy` (generating / sub-agent) from `shell` (at the
  prompt with a live background command). So for Claude, "not generating, at the
  prompt" is proven out-of-band and needs no pane parsing.
- **`not signals.is_busy(capture)` is exactly the guard that already sets the
  row note to `background shell`** (`_supervisor_evaluate.py:215-217`). The
  recommended predicate keys off precisely the state that renders
  `working (background shell)` today — nothing wider.

## Behavior matrix

`T` = the track's effective wind-down threshold (per-track `ctx_threshold`, else
the daemon-wide `warn_percent`, default 50). "Prolonged" = the continuous
background-shell episode has exceeded the floor. "Current" is measured against
the code as it stands.

### Claude (registry `shell`)

| # | Prompt/state evidence | Context | Shell episode | Daemon restart | Current behavior | Proposed behavior |
|---|---|---|---|---|---|---|
| 1 | Empty prompt (`status=shell`) | Above T | Young | No | `working`, note `background shell`, green, not attention | Unchanged |
| 2 | Empty prompt (`status=shell`) | At/below T | Young | No | `working (background shell)`, green, not attention; no round opens, no stamp, no wrap-up | Unchanged — below the floor, ambiguity resolves to silence |
| 3 | Empty prompt (`status=shell`) | At/below T | Prolonged | No | **The defect**: identical to #2, indefinitely | `shell-prolonged`, yellow, in `NEEDS YOU`, ONE coordinate-rich edge-triggered alert. Still no round, no stamp, no wrap-up |
| 4 | Empty prompt (`status=shell`) | At/below the 20% danger line | Prolonged | No | Identical to #2; the `danger` branch is unreachable behind busy precedence | As #3; the alert names the live remaining %. `alert_non_responder` still does NOT fire — no wrap-up was ever sent, so "not responding" would be a false claim |
| 5 | Generating (`status=busy`, or capture-busy) | At/below T | Any | No | `working`, note `sub-agent (Claude busy)` or none | Unchanged, never attention. The episode clock is CLEARED — generation is not a shell episode |
| 6 | `status=waiting`, or a structured gate | At/below T | Any | No | Not busy → falls through to the gate/idle cascade; a gate is `blocked:human` (already attention), otherwise the wrap-up fires normally | Unchanged; episode clock cleared |
| 7 | Empty prompt (`status=shell`) | At/below T | Prolonged | **Yes** | Unchanged green | Clock restarts at daemon start; attention is delayed by up to one floor, then fires exactly as #3. Never earlier than the floor |
| 8 | Empty prompt after a `shell`→other→`shell` transition | At/below T | New episode | No | Unchanged green | Clock reset by the transition; attention only after a fresh floor. The alert re-arms because the row left `NEEDS YOU` in between |

### Codex (descendant-shell fallback)

Same eight rows, same proposed behavior, with `codex_fallback` substituted for
`claude_status == "shell"`. Row 5's clearing is driven by
`signals.is_busy(capture)` rather than the registry.

**The one measured divergence, and why it does not change the policy.** The
descendant-shell walk cannot distinguish a shell Codex is USING from a lingering
or transient one — that imprecision is exactly why Claude's registry status
superseded the walk (`AGENTS.md`, "Claude registry `status` is AUTHORITATIVE").
So a Codex track's episode clock may start on a shell that is not real work,
making Codex's false-attention rate structurally higher than Claude's. That is
acceptable here and only here: the consequence of a false positive on this path
is one operator line, not an act. Parity of POLICY with divergence of EVIDENCE
is therefore justified rather than assumed, and both arms are pinned by tests.

### The five forbidden acts, in every proposed attention cell

| Act | Proposed behavior |
|---|---|
| Paste | **No** |
| Enter / submit | **No** |
| Respawn | **No** |
| Kill a shell or process | **No** |
| Write a session declaration | **No** |

The new branch sets a row status, a row note, and calls `sup.alert`. Nothing
else. The busy branch's pre-existing act-side effects (`void_stale_blocked`,
`void_if_stale`, `clear_idle_nudge_state`) run exactly as they do today and are
neither extended nor bypassed.

## Candidate comparison

### Candidate A — low context + empty prompt + continuous shell age — SELECTED, amended

Time the already-derived background-shell signal per track; require the context
to be at or below the wind-down threshold; surface attention past a bounded
floor. Retain full action suppression.

Amended in two ways before selection:

1. **The "empty prompt" evidence is taken from the registry, not the capture.**
   Requiring `signals.is_idle_input` would re-introduce a pane-text dependency
   for a fact that has an authoritative out-of-band source, and it fails toward
   silence — the same direction that let the incident run 39 hours. For Claude,
   `status == "shell"` already means "at the prompt with a live background
   command". Both runtimes additionally require `not signals.is_busy(capture)`,
   which is the guard that already produces the `background shell` note.
2. **Continuity is measured, not assumed** (see the clearing rule below).

Answers to the questions this candidate carried:

- *What floor protects an ordinary long build?* An absolute floor of two hours,
  applied identically at every band. A CI watch, a full test matrix, or a long
  build finishes well inside it; the incident ran 39 hours.
- *Does generation reset the episode or suspend the timer?* **Reset.** A
  suspend-and-resume timer would accumulate across genuinely separate episodes
  and eventually alarm on a healthy track.
- *Does `shell` → `busy` → `shell` create a new episode?* **Yes.** The evidence
  went false; that is a new episode by definition.
- *Can process identity distinguish Codex episodes?* It can, and it **must not
  be used**. A poll loop that respawns a shell per iteration is the exact
  incident shape; keying the episode on shell PID identity would reset the clock
  every iteration and defeat the detection entirely.
- *Is resetting on daemon restart fail-safe?* Yes — see "Daemon restart" below.

### Candidate B — low context + shell age regardless of prompt — rejected

Dropping the "not generating" requirement makes a track that is actively
producing tokens with a background build attached eligible for attention. The
operator has nothing to do about a working session, so the line is pure noise,
and noise in `NEEDS YOU` is the failure that block exists to prevent
(`unassigned` was excluded for the same reason). Rejected: existing busy/gate
evidence must suppress attention as well as action.

### Candidate C — status-preserving attention note — rejected

Keep `working`, attach a machine-readable note, teach `needs_attention` and the
alert to match it.

There is precedent (`BAD state file` and `RESUME_PENDING_NOTE` are both matched
by note prefix), so this is workable — but both precedents exist because those
conditions have **no status slot of their own**: a malformed state file must
ride whatever status the track otherwise has. This condition does have a slot —
the busy branch's unconditional `working`. Rejected for two concrete costs:

- The row stays **green** while sitting in `NEEDS YOU`. A green row that needs a
  human is the misleading-surface failure this repo has already fixed twice.
- Attention membership would depend on prefix-matching a display string, and
  `elide` truncates that string on two of the three surfaces it reaches.

### Candidate D — explicit non-destructive status — SELECTED

A dedicated status that authorizes no act and exists only for row color,
`NEEDS YOU` membership, and the edge-triggered alert. Selected together with
Candidate A: A supplies the predicate, D supplies the projection.

Token: **`shell-prolonged`**. It names the daemon's actual evidence — the shell
episode is long — and claims nothing about staleness, which the daemon cannot
know. Rejected names: `stalled-shell` / `shell-stalled` (asserts a stall the
daemon has not proven), `wind-down-blocked` (reads as a sibling of
`blocked:human`, which is a session-owned declaration this is not),
`not-responding` (false — the session was never asked anything).

Coexistence: it sits inside the existing busy branch, which already precedes
`blocked:human`, `restarting`, `danger`, and `warned`, so no precedence changes
and real generation still wins (row 5 clears the clock before the predicate can
be true).

### Rejected class — automatic action

Unchanged from the original framing, and reaffirmed. Reject any proposal that
uses shell age, prompt shape, context, or a timer to: inject the wrap-up while
the track remains classified busy; send Enter; terminate the shell; write
`winding-down` or `ready`; or respawn the session. Those signals may justify
operator attention only. They never prove that work is safe to interrupt or that
the session is ready to restart.

## The recommended contract

### 1. The predicate

Per track, per tick, over facts `observe` already gathers:

```text
shell_episode_now = (not signals.is_busy(capture))
                    and (claude_status == "shell" or codex_fallback)

attention = shell_episode_now
            and (now - shell_since) >= SHELL_EPISODE_ATTENTION_AFTER
            and eff_ctx is not None
            and eff_ctx <= threshold
```

`threshold` is the value the cascade already computed (per-track override, else
`warn_percent`). `eff_ctx is not None` is required: an unknown context never
counts as a crossing, per the existing fail-soft rule.

Proposed constants, in `_supervisor_config.py` beside `IDLE_NUDGE_AFTER`:

- `SHELL_EPISODE_ATTENTION_AFTER = 7200.0` (2 hours).
- `SHELL_EPISODE_CONTINUITY_GAP = 60.0` (~6 loop intervals).

### 2. Episode start, reset, clear, re-arm

Two new in-memory fields on `InjectState`, advanced in `observe` beside the
existing `idle_since` clock:

```text
if shell_episode_now:
    if shell_since is None or (now - shell_last_seen) > SHELL_EPISODE_CONTINUITY_GAP:
        shell_since = now          # start, or restart after a gap
    shell_last_seen = now
else:
    shell_since = None
    shell_last_seen = None
```

- **Start** — the first tick the evidence is true.
- **Reset** — any tick the evidence is false (generation, a gate, `waiting`,
  `idle`, the shell exiting, a restart), *or* a gap longer than
  `SHELL_EPISODE_CONTINUITY_GAP` since the last observation.
- **Clear** — the attention condition is re-derived every tick from live state,
  so it stops on its own when the shell ends **or** when context recovers above
  the threshold. Context recovery does not touch the clock: the clock times the
  shell, the predicate conjoins the context. Keeping them separate is what makes
  both halves honest.
- **Re-arm** — the alert uses
  `sup.alert(condition="prolonged-background-shell")`, so it is edge-triggered.
  When the row leaves `NEEDS YOU`, `evaluate`'s existing re-arm block drops the
  track's alert keys and a later episode reports afresh. The new condition must
  **not** be added to `SUPERVISION_CONDITIONS`, which is the exemption set that
  survives re-arm.

**The continuity gap is why no early-return path needs touching.** `evaluate`
returns before `observe` for `unassigned`, `session-gone`, `live-outside-tmux`,
and the identity-gate rejection, so those ticks advance no clock. Requiring
continuity rather than assuming it means a track that disappears and returns
starts a fresh episode automatically, with no cascade edits.

**One documented interaction.** `_supervisor_state.clear_state` pops the whole
`InjectState`, so voiding a stale `ready` on a busy tick also resets this clock.
That is delay-only (the safe direction) and fires at most once per stale
declaration, but it must be pinned by a test rather than left to be rediscovered.

### 3. Daemon restart

The clock is in-memory, so a daemon restart resets it and the earliest possible
attention is one full floor after daemon start. This is the identical model and
the identical justification as the keep-going nudge's continuous-idle clock,
which spec.md already ratifies: a restart only ever **delays**, never advances,
so it cannot produce a false alarm.

**The residual, stated rather than hidden.** A daemon restarting more often than
the floor would never surface this condition. Accepted, for two reasons. The
alternative — deriving episode age from the descendant shell's own `/proc`
start time — would make the alarm fire on kernel-durable evidence the daemon has
deliberately demoted for Claude, trading a delay for a false positive about
genuine work. And a daemon restarting every two hours is itself an
operator-visible anomaly. Durable episode state was also rejected on contract
grounds: the round sidecar is round-scoped by construction, and this condition
exists precisely when no round is open.

### 4. Claude / Codex

Parity of policy; divergence of evidence, measured and documented above. Both
arms are covered by tests — Claude via an injected `claude_status_by_session`,
Codex via the injected `/proc` seams — and each test asserts both the attention
and the non-action.

### 5. Row, color, attention, alert

| Surface | Value |
|---|---|
| Row status | `shell-prolonged` |
| Row note | `background shell <N>h — cannot wind down` |
| Color | yellow, beside `warned` / `danger` / `blocked:human` (red stays reserved for `session-gone`) |
| Attention | added to `ATTENTION_STATUSES`, so it joins `NEEDS YOU` and the window badge through the existing mechanism |
| Alert condition key | `prolonged-background-shell` |

Alert text must carry the plan topic, repo, tmux session, pane, and jump command
(supplied by `sup.alert`), plus the live remaining-context percentage, the
episode duration, and an explicit statement that the daemon has taken no action
and will not restart the session without a fresh `ready`.

### 6. Tests the implementation owes

1. Claude `status=shell`, empty prompt, ctx at/below threshold, clock advanced
   past the floor ⇒ status `shell-prolonged`, in `NEEDS YOU`, exactly one alert
   across repeated ticks.
2. The same fixture asserts the non-action: no paste, no Enter, no respawn, no
   process kill, and the state file untouched.
3. Below the floor ⇒ `working (background shell)`, not attention.
4. Above the threshold with a prolonged episode ⇒ not attention.
5. Generation mid-episode resets the clock; the floor must be re-earned.
6. Codex twin of (1) and (2) through the injected `/proc` seams.
7. Clock reset on a simulated daemon restart delays but does not prevent.
8. Clear and re-arm: the episode ends, the row leaves `NEEDS YOU`, a later
   episode alerts again.
9. Sabotage evidence: removing the attention routing makes (1) fail.

Gate: `uv run pytest overseer -q`, then `just check`. No existing check may be
weakened, removed, skipped, or exempted.

### 7. Governed clauses this changes

Route through `livespec:propose-change` before any product code:

- **`SPECIFICATION/spec.md` §"Fail-soft posture"** — the clause "Busy detection
  deliberately over-fires: a false 'busy' merely suppresses action" is the
  clause the incident falsified. Over-firing busy must continue to suppress
  **action** while no longer suppressing **attention** indefinitely.
- **`SPECIFICATION/contracts.md` §"Attention surface"** — the membership list is
  closed and must gain this member.

Explicitly **not** changed: the cardinal rule, the supervision round, the
escalating wrap-up, the restart interlock, and "Notify, never block" (the new
alert conforms to it as written).

Out of governed scope but required for coherence, at implementation time:
`overseer/AGENTS.md` (the `evaluate` state diagram, the status-precedence
bullet, the row-color bullet, the registry-status bullet),
`.claude-plugin/prose/overseer.md` (the operator status table),
`overseer/marker-protocol.md` (a note that this condition never injects), and
`SPECIFICATION/scenarios.md`.

## Open maintainer decisions

Two values are judgment calls the recommendation defaults rather than derives.
Both are safe to change without reopening the design:

1. **The floor** — recommended 2 hours. Lower is noisier, higher is slower; the
   incident is caught at any value below ~39 hours.
2. **The status token** — recommended `shell-prolonged`, with the rejected
   alternatives and their failure modes recorded above.
