# Mechanism — what the foreman should print, and from what evidence

**Ledger anchor:** epic `overseer-7jskz4`. All mutable plan state — status,
next action, handoff entries — lives on that epic and its child items; this
note is write-once research and is never authoritative about what remains.

Everything here is a claim measured 2026-08-15 in a live foreman session on the
`vps` box; re-measure before trusting the module paths.

## The gap

The foreman tick already gathers everything needed to see that an open plan
thread has no worker or no supervisor tmux session, but it reports that state
only as prose findings inside the LLM tick's summary. The maintainer then
hand-derives the attach commands. Measured 2026-08-15: 7 open threads, 8
missing sessions (2 workers, 6 supervisors) — every one of the 8 commands was
composed by hand from the gather document plus `tmux list-sessions`.

## The naming convention (the whole computation)

For an open plan thread `plan/<topic>/`:

- **worker session** — tmux session named exactly `<topic>`
- **supervisor session** — tmux session named exactly `<topic>-supervisor`

"Open" means the directory is directly under `plan/`, excluding `plan/archive/`.
This matches the daemon's own registry convention (`_supervisor_prompts.py`
computes `plan/<topic>/handoff.md` and `plan/<topic>/supervisor-handoff.md`
from the same topic string) and the fleet-wide session naming observed across
every repo on this box (`<topic>` / `<topic>-supervisor` pairs).

## The output contract (maintainer-specified, 2026-08-15)

One command per missing session, no bullets, alphabetical by topic; within a
topic's pair the supervisor line precedes the worker line; only MISSING
sessions are printed. A supervisor ATTACH line is printed ONLY when the topic
has a supervisor defined. The discriminator (per the supervise-plan contract
shipped 2026-08-15): the plan's ledger epic carries at least one handoff entry
ATTRIBUTED to the plan's supervisor entity — attribution, not prose, is what
marks an entry as the supervisor binder. During migration a legacy committed
`plan/<topic>/supervisor-handoff.md` also counts (existing plans still carry
them; new plans never will). When the supervisor session is missing AND no
supervisor is defined by either evidence, print instead (maintainer directive,
2026-08-15):

```text
no supervisor for <topic>, run /livespec-overseer:supervise-plan <topic> to create one
```

The worker line has no such condition: it prints whenever the worker session
is missing.

```text
ssh -t vps 'cd workspace/livespec-overseer && tmux new -A -D -s <topic>-supervisor'
ssh -t vps 'cd workspace/livespec-overseer && tmux new -A -D -s <topic>'
```

The `cd` path is the repo's path RELATIVE TO the home directory
(`workspace/livespec-overseer` resolves to the primary checkout via symlink,
measured 2026-08-15). The `vps` host alias and the relative-path shape are
presentation concerns of THIS box's operator; keep both derivable (host from
config or hostname, path via `os.path.relpath(repo, home)`) rather than
hard-coding.

`tmux new -A -D` attaches if the session exists and creates it otherwise, so
the printed command is idempotent and safe to print even if the session
appears between gather and print.

## Where it belongs

The foreman loop is the right carrier because it already holds both inputs at
every tick:

- the open-thread set — the gather document's snapshot rows carry every
  registry-tracked topic for this repo, and `plan/` enumeration covers
  threads not yet registry-tracked;
- tmux occupancy — the wrapper already shells `tmux list-sessions` for the
  classifier's `occupied_tmux_sessions` preflight (added in build
  b4054f3bb6bf).

Printing is OBSERVATION, not mutation: it needs no `foreman-act` proposal, no
whitelist entry, and does not consume the one-bounded-action-per-tick budget.
It belongs in the deterministic wrapper's tick output (beside the runtime JSON
line) or in the gather rendering — NOT in the LLM tick, so it prints even on
converged token-free ticks.

## Boundary notes

- The printed command creates an EMPTY shell session, not a supervised agent.
  Booting an agent onto a handoff stays with the overseer lifecycle /
  `foreman-act` (`supervisor_pair_start` exists since build b4054f3bb6bf and
  launches `claude` onto `plan/<topic>/supervisor-handoff.md`). This feature
  only surfaces the attach commands for the maintainer; it must not grow into
  auto-starting sessions.
- A topic whose supervisor session is missing may also have no supervisor
  defined at all (measured 2026-08-15: only `plan/foreman/` carried a legacy
  `supervisor-handoff.md`). That case gets the `no supervisor for <topic>, run
  /livespec-overseer:supervise-plan <topic> to create one` line, never the
  attach command — attaching a supervisor session with no binder to follow
  staffs a pane onto nothing.
- The ledger leg of the discriminator is a CREDENTIALED read: `bd` in this
  tenant requires the fleet credential wrapper, so the epic-entries check
  cannot be a bare deterministic stat the way the legacy-file leg is. When the
  ledger is unreachable at tick time, supervisor-definedness is UNKNOWN for
  every topic without a legacy file: print a single diagnostic line naming the
  failed read instead of guessing — an attach line for an undefined supervisor
  staffs a pane onto nothing, and a pointer line for a defined one tells the
  maintainer to recreate a binder that already exists.
- This shipped with `planning-lane-redesign` (livespec core, epic
  `livespec-zsn2xh`): plans hold write-once research on the filesystem and all
  handoff state as attributed, timestamped entries on their ledger epic. The
  `plan` operation now refuses to author `handoff.md` at all, and
  `supervise-plan` publishes the supervisor binder as epic entries, not a
  file.
