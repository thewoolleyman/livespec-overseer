# Background-shell supervision liveness — policy options

## Purpose

Use this note to compare and select the smallest safe contract change that
prevents a stale background shell from shielding a low-context track
indefinitely. Preserve the measured facts and governing constraints in
`root-cause.md`; do not turn this file into a work queue or a copy of ledger
status.

## Evidence matrix to complete

For both Claude registry `shell` and Codex descendant-shell fallback, record
the daemon's current and proposed behavior for each combination:

| Prompt/state evidence | Context evidence | Shell episode | Daemon restart | Current behavior | Proposed attention behavior |
|---|---|---|---|---|---|
| Empty input prompt | Above threshold | Young | No | | |
| Empty input prompt | At/below threshold | Young | No | | |
| Empty input prompt | At/below threshold | Prolonged | No | | |
| Empty input prompt | At/below danger line | Prolonged | No | | |
| Generating | At/below threshold | Any | No | | |
| Structured gate / waiting | At/below threshold | Any | No | | |
| Empty input prompt | At/below threshold | Prolonged | Yes | | |
| Empty input prompt after shell/status transition | At/below threshold | New episode | No | | |

For every proposed attention cell, state explicitly whether the daemon pastes,
sends Enter, respawns, kills a process, or writes a session declaration. The
required answer for all five is **no**.

## Candidate A — low context + empty prompt + continuous shell age

Define an in-memory continuous shell episode. When the pane has a verified
empty input prompt, context is at or below the wind-down threshold, and the
same kind of shell evidence remains continuously true past a bounded floor,
retain action suppression but add operator attention.

Questions:

- What floor protects an ordinary long build?
- Does generation reset the episode or merely suspend the timer?
- Does a registry transition from `shell` to `busy` and back create a new
  episode?
- For Codex, can process identity distinguish one shell episode from another?
- Is resetting on daemon restart acceptably fail-safe, or does it make the
  condition indefinitely avoidable?

## Candidate B — low context + shell age regardless of prompt

Surface attention after a bounded shell episode whenever context is low,
without requiring an empty prompt.

Risk to test: a genuinely active generation or an agent supervising a real
long build may become noisy even though no operator action is useful. Confirm
whether existing `busy`/gate evidence should suppress attention as well as
action.

## Candidate C — status-preserving attention note

Keep raw status `working`, attach a distinct machine-readable note/condition,
and teach `needs_attention` plus alert edge-triggering to recognize it.

Questions:

- Can attention membership rely on a note without making free-form text a
  control signal?
- What stable condition key clears and re-arms correctly?
- Does green row coloring remain misleading once the row is in `NEEDS YOU`?

## Candidate D — explicit non-destructive status

Introduce a dedicated status for a prolonged low-context background shell.
The status authorizes no act; it exists only for table color, `NEEDS YOU`, and
coordinate-rich edge-triggered alerting.

Questions:

- What token names the operator condition without claiming the shell is
  semantically stale?
- Which specification, scenario, docs, rendering, and tests must enumerate
  it?
- How does it coexist with `blocked:human`, `danger`, and real generation
  precedence?

## Rejected class — automatic action

Reject any proposal that uses shell age, prompt shape, context, or a timer to:

- inject the wrap-up while the track remains classified busy;
- send Enter;
- terminate the shell;
- write `winding-down` or `ready`; or
- respawn the session.

Those signals may justify operator attention only. They never prove that work
is safe to interrupt or that the session is ready to restart.

## Recommendation requirements

The final recommendation must specify:

1. the exact deterministic predicate;
2. the episode start, reset, clear, and re-arm transitions;
3. daemon-restart behavior;
4. Claude/Codex parity or a measured reason for divergence;
5. row status, note, color, attention membership, and alert condition key;
6. tests that prove non-action as well as attention;
7. the current specification clauses to revise through
   `livespec:propose-change`; and
8. rejected alternatives and their failure modes.

Do not implement from this note. Once the contract is accepted and the ledger
item is admitted, implementation goes through `drive` action
`impl:overseer-vyjkzw` or the Dispatcher.
