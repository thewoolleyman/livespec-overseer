# Background-shell supervision liveness — incident and root cause

## Incident

On 2026-07-28, tmux session `04-convergence-loop` in
`/data/projects/homelab` showed an empty Claude input prompt with 29% context
remaining and one background shell. The acting overseer rendered:

```text
working (background shell)  04-convergence-loop  ...  29%
```

It did not inject a wrap-up or restart the session.

The live process and registry evidence agreed:

- Claude PID `3076754` was the named `04-convergence-loop` session.
- Claude's live registry reported `status: "shell"`.
- Descendant zsh PID `3915537` had run since 2026-07-26 10:37 local time.
- The shell repeatedly ran a poll equivalent to:

  ```sh
  until [ "$(gh pr checks 61 --json bucket -q \
    '[.[]|select(.bucket=="pending")]|length' 2>/dev/null)" = "0" ]; do
    sleep 30
  done
  ```

- This host's `gh pr checks` command does not support `--json`. It exits
  nonzero and prints `unknown flag: --json`; the poll redirected that error
  away, so command substitution produced an empty value and the equality
  could never become true.
- PR #61 was already merged at 2026-07-26T09:26:32Z.
- The poller's cwd, `/data/projects/homelab-hl-25m3mm`, had subsequently
  been deleted while the process retained it as a deleted cwd.

The poller was therefore live at the process level but incapable of reaching
its intended completion condition.

## Daemon decision chain

The daemon behaved consistently with the current contract and code:

1. `_supervisor_observe.observe` treated Claude's registry status as
   authoritative. `shell` is in `CLAUDE_BUSY_STATUSES`, so `busy=True`.
2. `_supervisor_evaluate.evaluate` checks `busy` before idle verification,
   `ready`, or the context-threshold branch. It returned `working` with note
   `background shell`.
3. Because the threshold branch was never reached, the current round had no
   entry in `~/.livespec-overseer-stamps.json` and no
   `<repo>/tmp/overseer/<topic>/.overseer-state`.
4. With no injection stamp and no fresh session-written `ready`, the restart
   interlock correctly refused to restart.
5. `working` is green and is not a member of `ATTENTION_STATUSES`, so the
   daemon gave the operator no `NEEDS YOU` entry or edge-triggered alert.

The daemon log proves an earlier round on the same track completed normally:
it injected at 46% and restarted the session on 2026-07-26. The failure is
specific to the new round being unable to open while the immortal shell kept
the top-precedence busy guard true.

During the investigation, the separate supervisor session sent the worker a
new task. The worker resumed generation at 28%, which independently made it
busy. That later activity does not change the earlier causal chain: before the
new task, the empty-prompt session was already shielded by the stale shell,
and the round still had no stamp or declaration.

## Classification

There are two defects at different boundaries:

1. **Supervised-session defect.** The poller used an unsupported CLI surface,
   discarded the only error, and had no failure/timeout exit.
2. **Overseer liveness/attention gap.** A process-level `shell` signal may
   remain true indefinitely. Because busy precedence suppresses both action
   and attention, one stale shell can shield a track through every context
   band while the UI continues to call it healthy work.

The missing restart is not itself a defect. Restarting without a fresh
session-written `ready` would violate the cardinal safety rule. The gap is
that an ambiguous but prolonged condition has no non-destructive attention
path.

## Governing constraints

Any resolution must preserve all of these:

- `ready` remains the sole restart authorization.
- No shell age, prompt shape, timer, or context percentage may authorize a
  paste, Enter, respawn, or shell kill.
- A genuine build or other background command remains protected from
  injection and restart.
- Pane prose is not a semantic declaration channel.
- Ambiguity resolves toward no action.
- Operator alerts remain coordinate-rich and edge-triggered.
- An attention episode clears and re-arms when its evidence clears.
- Claude registry `shell` and Codex's descendant-shell fallback must both be
  considered explicitly; parity must be justified by common evidence rather
  than assumed.

## Questions the plan must settle

- What evidence defines one continuous background-shell episode for Claude
  and Codex?
- Is an in-memory age sufficient, or must the episode survive daemon restart?
  Resetting age on restart delays attention and is safe, but may permit
  repeated indefinite shielding across daemon restarts.
- Must the track also have a verified empty input prompt and known context at
  or below threshold before it becomes attention?
- Should the status remain `working` with an attention note, or become a new
  explicit status? How do coloring, `NEEDS YOU`, and edge-trigger keys remain
  coherent?
- Is context threshold alone enough, or should an absolute shell-age floor
  prevent a newly-started real build at 20% from immediately alarming?
- What clears/re-arms the episode: registry transition away from `shell`,
  generation, shell PID identity change, prompt change, context recovery, or
  some combination?
- Which current specification clauses require a livespec proposed change
  before implementation?

## Ledger anchors

- Planning epic: `overseer-4xfmez`
- Implementation bug: `overseer-vyjkzw`

The capture operation created the bug before Beads rejected its requested
`depends_on: overseer-4xfmez` edge with:

```text
tasks can only block other tasks, not epics
```

The bug description names the epic and plan thread, but the ledger currently
has no native dependency edge between them. Do not bypass the work-item store
to manufacture one. Treat this as an orchestrator/backend integration finding
and use the supported lifecycle to repair linkage if that capability becomes
available.
