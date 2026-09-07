# Foreman Codex and Pi runtime support — initial research

## Observed failure

Running the installed `livespec-overseer:foreman` skill from a real Codex tmux
session named `livespec-console-beads-fabro-foreman` in
`/data/projects/livespec-console-beads-fabro` fails its deterministic entry gate
with `runtime registry mismatch`. The tmux-name and cwd legs pass. The failing
leg is that `bin/foreman-runtime` calls `claude_sessions.read_live_sessions()`
only; `foreman_runtime_identity.entry_gate()` accepts only that Claude registry
list.

## Existing Codex capability

`overseer/codex_sessions.py` already provides a structural, named live-session
join: a `codex` process holding a rollout file is linked by rollout filename to
`~/.codex/session_index.jsonl`, yielding `pid`, `thread_name`, and cwd without
reading transcript contents. Its `CodexSession` mirrors the identity fields
needed by the foreman gate. The planned work should consume this established
reader rather than duplicate discovery or weaken the exact name-plus-repository
identity check. Tests must prove Claude and Codex positive controls, wrong-name
and wrong-cwd refusal, and an unindexed Codex session refusing safely.

## Pi boundary

The overseer already ships a Pi binding at
`.claude-plugin/.pi-plugin/skills/livespec-overseer-foreman/SKILL.md`; its
release acceptance recorded the Pi package as installed and registered. That
binding reads the same shared foreman prose and invokes the same deterministic
runtime, so its surface alone does not make a live Pi session pass the current
Claude-only entry gate. No `pi_sessions` reader exists in `overseer/` today.

The plan must establish, from Pi's supported runtime metadata and without
reading session transcript contents, how a named live Pi session is joined to
its exact tmux session and repository. It must then extend the common foreman
identity gate to accept Claude, Codex, and Pi evidence with the same fail-closed
semantics. If Pi lacks a durable machine-readable named-session identity, that
is a specification/driver contract gap to route to `livespec-driver-pi`; it must
not be bridged by a heuristic or an unchecked tmux name.

## Scope and acceptance direction

The target repository owns foreman runtime identity and its Claude/Codex/Pi
plugin bindings. `livespec-driver-pi` owns any Pi driver runtime contract or
metadata change discovered as necessary. The plan will first determine whether
the required Pi identity carrier is already available. It will then route
ratified implementation slices to their owning repositories, keeping any
cross-repository driver work as a separately tracked child or explicit
cross-repo successor.

Acceptance requires real interactive tmux exercises of all supported runtimes:
correctly named sessions enter the wrapper; renamed, wrong-repository, and
unindexed/identity-unavailable controls refuse; and the runtime still binds to
the exact repository rather than accepting a tmux name alone.
