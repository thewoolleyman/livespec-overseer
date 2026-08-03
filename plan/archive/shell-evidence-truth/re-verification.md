# Post-deployment re-verification — and the half that did not clear

Independent verification pass run 2026-08-03T00:50–00:58Z by the
`shell-evidence-truth-supervisor` session, AFTER this thread closed and
archived. It re-measures `completion.md`'s claims rather than carrying them
forward, and it changes one of them.

## What holds

Every deployment claim in `completion.md` re-measured true.

| Claim | Re-measured 2026-08-03T00:50Z |
|---|---|
| The fix is in `master` | `git merge-base --is-ancestor f8e56e5 origin/master` → PASS |
| The moving `release` ref carries it | `refs/heads/release` → `4b3a300` (v0.17.0), which contains `f8e56e5` → PASS |
| The acting daemon runs the new code | pane `livespec-overseer:1.1` → PID 3865177, started 2026-08-03T00:26Z, running `/data/projects/livespec-overseer/.venv/bin/overseerd` against this tree; `claude_sessions.has_active_subshell` carries the `starttime_of` seam and `STARTUP_SHELL_MARGIN_TICKS = 1000` |

Note the release ref has ADVANCED past the v0.16.1 tag `completion.md` names —
it now resolves to v0.17.0. Adopters consuming the moving ref therefore hold a
build newer than the one recorded, and it still contains the fix. That is the
moving ref working as designed, not drift.

**The regression boundary was re-proven live against real `/proc`, with a
control that can fail.** `completion.md` asserts both halves; this pass
constructed them from scratch rather than reading them off live sessions, so
the negative result is trustworthy:

| Shape | Reading |
|---|---|
| runtime + wrapper shell born with it, observed at +3s | `False` |
| the SAME tree, aged well past the 1000-tick margin | `False` — birth time, not age |
| a task shell spawned past the margin | `True` |

The first attempt at that control returned `False` on all three legs and was
WRONG, not the detector: `bash -c 'sleep 900'` exec-optimises into `sleep`, so
no shell ever entered the tree. Recorded because a control that silently tests
nothing is the exact failure this repo's `## An empty result is not a finding`
rule exists to catch, and it produced a false negative here before it was
caught.

## What does not hold

**The owed re-verification named the `beads-v1-1-2-upgrade` worker/supervisor
PAIR. `completion.md` reports the worker half only, and the supervisor half is
still falsely busy.**

Measured 2026-08-03T00:55Z against the released detector, pane
`beads-v1-1-2-upgrade-supervisor` (repo `livespec-orchestrator-beads-fabro`,
Codex), `root_pid` 773747 → `has_active_subshell` returns **`True`**:

```text
runtime baseline ticks: 177954986      (bun/codex runtime, elapsed 3-14:35)

shell 2730702  bash  +503 ticks        elapsed 3-14:14  -> startup, ignored
shell 839891   bash  +23049767 ticks   elapsed 22:12    -> LATE, counted busy
shell 857561   sh    +23051054 ticks   elapsed 22:12    -> LATE, counted busy
```

The two LATE shells are not task work. Their argv is byte-identical to the
ignored startup shell's — `with-homelab-env.sh` wrapping
`npx -y mcp-remote https://mcp.cloudflare.com/mcp` — and their subtrees
terminate in the same long-lived infrastructure (`op run`, and
`node mcp-remote`). It is the SAME MCP server relaunched mid-session, 64 hours
after the runtime started, so the start-time cut reads it as work.

**This is not a defect in what shipped.** `overseer-3rk`,
`false-busy-mechanism.md` and `spec-bearing-verdict.md` item 3 all name the
mid-session relaunch as the known hard case and deliberately resolve it to busy
under fail-soft. What changed is that it stopped being hypothetical: it is
occurring in the fleet, on the exact session pair whose 54-hour
`shell-prolonged` alarms motivated this thread's owed re-verification. Before
the daemon reload that pane was surfacing
`wind-down starved (15h): winddown starved 15h; background shell 15h` on a
repeating cycle through 2026-08-02T21:50Z. Its absence from the log since the
00:26Z reload is NOT evidence it cleared — a 15-hour duration counter cannot
re-arm in 27 minutes.

Filed as **`overseer-q3f`** (P2 bug, this repo's tenant). That record carries
the tree, the operational cost, and the two deterministic discriminators this
tree now supports which start time alone could not: subtree termination in a
long-lived MCP/node server, and argv identity with a chain already classified
as startup infrastructure under the same runtime. Both ADD evidence that a
shell is infrastructure, so neither weakens the fail-soft direction, and a
genuine task shell matches neither.

## Why this note exists rather than a reopened thread

The epic, the defect and the implementation child are all closed and the
delivered fix is correct within its stated boundary. Reopening would misreport
completed work. But `completion.md` records the re-verification as discharged
when half of it was never run, and an archived record that overstates its own
coverage is still a wrong record — being archived does not make it right. The
correction belongs beside the record it corrects, with the follow-up carried by
a live ledger item.
