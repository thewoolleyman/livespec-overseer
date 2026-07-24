# livespec-overseer

The **Control-Plane operator tool** for the livespec fleet: a two-pane tmux
supervisor that keeps multiple parallel sessions moving.

- **`overseerd`** — a deterministic daemon that watches every tracked tmux
  session's remaining context, injects an escalating wrap-up at threshold, and
  atomically restarts a session **only once that session has declared itself
  ready**.
- **the overseer pane** — a thin interactive surface that starts the daemon,
  manages the tracked-session list, and relays what needs attention.

## The cardinal rule

**The daemon never restarts a session that has not declared itself ready.** Only
the session knows whether it is safe to kill. A session that declares nothing is
*reported* as not responding and otherwise left alone — never force-killed.

Declaration is out-of-band on the filesystem — a single `.overseer-state` file
valued `ready`, `blocked: <reason>`, or `winding-down` — never scraped from pane
text.

## Requirements

**Linux with tmux.** This is a declared requirement, not an aspiration: the
supervisor reads `/proc/<pid>/stat` (macOS has no `/proc` at all), drives real
tmux across every module, and reads the agent runtimes' own session files. The
host boundary is deliberately **not** abstracted — that was considered and
rejected as speculative generality. `overseerd` refuses to start on an
unsupported host and names the failed precondition.

Claude Code and/or OpenAI Codex as the supervised agent runtimes.

## Installation For An Adopter Family

Install both shipped surfaces for the family that will run the overseer:

1. Install the `livespec-overseer` Claude Code plugin from this repository's
   plugin marketplace entry so the interactive command
   `/livespec-overseer:overseer` is available.
2. Install the `livespec-overseer` Python package into the operator
   environment so the `overseerd` and `overseer-start` entry points are on
   `PATH`.

Run the installed tool against that family's own `$HOME` declarations. The
watch-set is `~/.livespec-overseer-repos.json`; the mapping store is
`~/.livespec-overseer.jsonl`. The daemon never discovers repos from
`.livespec-fleet-manifest.jsonc`, and an adopter-family install must not point
at this development fleet's manifest, credentials, or repos. That D5 boundary
is part of the product contract: the fleet's manifest is only for fleet
self-application, not shipped overseer discovery.

## The watch-set

Which repos it supervises is declared in **`~/.livespec-overseer-repos.json`**:

```jsonc
// JSONC — comments are fine.
{
  "repos": [
    "/data/projects/livespec",
    "/data/projects/some-other-repo"
  ]
}
```

A listed repo is watched only if its checkout exists and has a `plan/` dir.

**Listing a repo with no session assigned yet is the normal case, not an
oversight** — that is exactly how a plan with no session surfaces as
`unassigned` and therefore ready to start. The watch-set is deliberately
*declared* rather than derived from the tool's own mapping store; deriving it
would make a brand-new plan invisible until someone had already assigned a
session to it.

There is no `--repos` / `--manifest` / `--store` / `--stamp` flag. The
invocation surface is deliberately knob-free; all durable state lives in `$HOME`
beside the declaration above.

## Relationship to the rest of livespec

This is a **Control-Plane** member of the livespec fleet, repo class
`control-plane-tool` — a **peer** of the operator console
(`livespec-console-beads-fabro`), never a component of it. The console ships the
cockpit *application*; this ships an operator *tool*.

It depends on **nothing** in the fleet: no imports from livespec core, no
Driver, no orchestrator. It observes the agent runtimes and understands the
`plan/<topic>/handoff.md` convention. A third party can run it with no livespec
install at all.
