# Why session-lifetime MCP launch-chain shells must not count as background work

Reasoning note for the `shell-evidence-truth` plan thread (repo:
`livespec-overseer`). The defect record is **`overseer-3rk`** (read its
live state from the ledger); this note carries the full mechanism, the
live evidence, the boundary the fix must respect, and the open design
questions, so the implementation can be derived without re-diagnosing.

## The observable failure (2026-08-02)

Track `06-resilience-acceptance` (repo `homelab`, Codex) sat at 8%
remaining context, verifiably idle — completed task summary on screen,
empty prompt, Codex `/ps` reporting "No background terminals running" —
for 15+ hours, classified `working (background shell)` the entire time.
Consequences under the ratified contract: permanently uninjectable
(action suppression is unbounded on busy evidence), a standing
`winddown-starved` row in `NEEDS YOU` pointing the operator at
"background work" that does not exist, and the maintainer catching the
8% ride by eye — twice, a day apart, because nothing else would.

## The mechanism

`has_active_subshell` (`overseer/claude_sessions.py`) walks every
`/proc` descendant of the tmux pane's process and returns busy when any
process's `comm` is a shell name (`_SHELL_COMMS`: bash, sh, zsh, …).

**Blast radius — Codex and unadopted panes, NOT adopted Claude
sessions.** The walk's ONE consumer is the `bg_shell` fallback in
`overseer/_supervisor_observe.py` (~line 218). For an ADOPTED Claude
session the daemon ignores the walk entirely and trusts Claude's own
registry self-report (`~/.claude/sessions/<pid>.json` `status`, whose
`shell` value is Claude's OWN accurate background-work signal — the
registry does not report MCP infrastructure as `shell`). The walk
decides busy-ness only where no usable self-report exists: Codex panes
(`overseer/codex_sessions.py` delegates to it deliberately) and any
pane the registry cannot vouch for. `overseer-3rk` as first filed
overstated this as "both Claude and Codex"; a correcting comment is on
that record.

The walk's justifying premise is stated TWICE in
`overseer/claude_sessions.py`, and both statements are false for
shell-launched MCP servers — a literal fix must correct both:

> Persistent helpers (MCP servers, node) are not shells and are
> ignored.  (the `has_active_subshell` docstring)

> Persistent helpers (MCP servers) are "node", never shells.
> (the module comment above `_SHELL_COMMS`, ~lines 136-137)

That premise is FALSE whenever an MCP server is launched THROUGH a
shell. The fleet's credential-injection pattern — a
`with-<project>-env.sh` wrapper under sudo, holding a 1Password `op`
runner — does exactly that, and the wrapper shell survives as long as
the session. Live tree under pane PID 2416005 (all rows elapsed
~16h38m, the session's whole life):

```
codex (bun)
└─ codex (native)
   ├─ sudo → sudo → bash (2432053)          ← with-homelab-env.sh `bash -lc` stage
   │                └─ op                    ← 1Password runner keeps bash alive
   │                   └─ npm exec mcp-re…
   │                      └─ sh (2447936)    ← npm's spawn shell
   │                         └─ node         ← mcp-remote: the Cloudflare MCP server
   ├─ node playwright-mcp                    ← shell-free launch: correctly ignored
   └─ codex-code-mode-host
```

Two descendant processes with shell `comm`s, both **launch-chain
infrastructure**, neither background work. Every session whose MCP
config routes through a credential wrapper carries this shape from its
first second to its last, so the false positive is the NORM in this
fleet, not an edge case.

## Why the distinction is load-bearing (both directions)

- **Must stop counting:** a launch-chain shell that lives exactly as
  long as the session says nothing about work. Counting it makes
  `working (background shell)` permanent, wrap-up injection permanently
  suppressed (until the `supervisor-wrapup-citizenship` narrowing
  ratifies), the keep-going nudge unreachable (an idle session
  mislabeled `working` is never nudged), and `winddown-starved` /
  `shell-prolonged` alarms false.
- **Must KEEP counting:** a genuine background command — the
  `Bash(run_in_background)` / Codex background-terminal case — is a
  shell descendant spawned mid-session by a tool call. This is the
  evidence `overseer-vyjkzw`'s root incident was about (a stale
  `gh pr checks` poller shielding an idle track for ~39h): the fix here
  must not resurrect that by ignoring shells wholesale.

The discriminator that falls out of the two lists: **when the shell
started relative to the session runtime.** Launch-chain shells spawn
within moments of the runtime process; genuine background commands
spawn later, when a tool call runs. (Alternative or supplementary cuts
recorded in `overseer-3rk`: prune the walk at subtrees terminating in a
long-lived MCP/node server; require recent CPU activity. Start-time is
the simplest deterministic cut; the thread should pressure-test it —
e.g. an MCP server that crashes and is relaunched mid-session would
have a late-started launch chain.) Choosing the concrete margin is part
of the implementation work, not pre-decided here: the clock source is
`/proc` starttime (jiffies since boot, already read by
`claude_sessions.proc_starttime`), and the fix must state and test
whichever window it picks. The walk already injects its `/proc` readers
(`children_of` / `comm_of`); adding a `starttime_of` seam alongside them
follows the file's existing pattern, and the beside-tests in
`overseer/test_claude_sessions.py` drive the walk with fakes — the §"Why
the distinction is load-bearing" shapes land there as new arms.

## Fail-soft posture interaction

The spec's fail-soft rule — busy detection deliberately over-fires;
ambiguity resolves toward doing nothing — is about MISSING busy being
dangerous for ACTING. This thread does not weaken that: where evidence
genuinely cannot distinguish launch-chain from work, the daemon keeps
reading busy. What it removes is a systematic, *certain* false positive
(a shell provably started with the runtime), which is not ambiguity.

## Relations

- **`overseer-3rk`** — the defect record this thread anchors around
  (filed 2026-08-02, before this thread existed; cite it, do not
  re-file).
- **`overseer-blccme` / `plan/archive/supervisor-wrapup-citizenship/`** —
  complementary, deliberately separate: that thread changes what the
  daemon may DO given true busy evidence (inject at a settled,
  shell-only-busy prompt); this thread makes the evidence TRUE. Either
  fix alone would have spared `06-resilience-acceptance`; the fleet
  wants both. Neither blocks the other.
- **`overseer-vyjkzw`** — the genuine-stale-shell capture whose
  behavior must survive this fix (regression boundary above).
- **`overseer-x6d`** — report-only low-context surfacing for generating
  panes; untouched by evidence truth.
- **Owed correction, discharged in this thread's opening change-set:**
  `plan/archive/supervisor-wrapup-citizenship/contract-narrowing.md` evidence
  item 5 described this session as "busy solely on background-shell
  evidence"; that evidence is now known to be launch-chain
  infrastructure. The item is annotated rather than rewritten — the
  session being truly idle STRENGTHENS the narrowing case.
- **Re-verification owed:** the 2026-08-02 `beads-v1-1-2-upgrade`
  "background shell prolonged (54h)" alarms and its supervisor's hourly
  equivalents (repo `livespec-orchestrator-beads-fabro`, both Codex)
  are plausibly this same false positive; confirm against their
  process trees before treating those flags as real.

## Spec-bearing or implementation-only? (the thread's first decision)

The detection walk is implementation, but the shipped prose and
possibly `SPECIFICATION/contracts.md` / `scenarios.md` state "a live
background shell under its pane" as the meaning of
`working (background shell)`, and `SPECIFICATION/spec.md` §"Fail-soft
posture" speaks of "a background command observed continuously". If any
ratified clause defines the EVIDENCE (rather than the response to it),
narrowing "shell descendant" to "task shell, not launch-chain shell" is
a spec change and rides `/livespec:propose-change` first; otherwise it
is an implementation fix filed directly under this thread's epic. The
sweep that answers this is the handoff's next action.
