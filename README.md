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
   plugin marketplace entry so the interactive commands
   `/livespec-overseer:overseer`, `/livespec-overseer:foreman`, and
   `/livespec-overseer:grooming` are available.
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

An entry may also be an object, which is how a repo carries settings of its own:

```jsonc
{
  "repos": [
    "/data/projects/livespec",
    { "path": "/data/projects/some-other-repo", "idle_nudge": false }
  ]
}
```

Both shapes mix freely in one file, so an existing bare-string declaration keeps
working untouched. `idle_nudge` switches the idle-with-context keep-going nudge
for every track in that repo which sets none of its own; omitting it means "no
override" rather than "off", leaving the daemon-wide `--idle-nudge` in charge.

**Listing a repo with no session assigned yet is the normal case, not an
oversight** — that is exactly how a plan with no session surfaces as
`unassigned` and therefore ready to start. The watch-set is deliberately
*declared* rather than derived from the tool's own mapping store; deriving it
would make a brand-new plan invisible until someone had already assigned a
session to it.

There is no `--repos` / `--manifest` / `--store` / `--stamp` flag. The
invocation surface is deliberately knob-free; all durable state lives in `$HOME`
beside the declaration above.

## The foreman and grooming panes

Beside the overseer pane, the plugin ships two **per-repository operator
surfaces**. Each runs in its own tmux pane as an ordinary tracked session — the
same `.overseer-state` file, the same three tokens, the same cardinal rule — but
neither is a plan track: both use a reserved session name and have no
`plan/<topic>/` directory of their own, so no plan worker can collide with them.

- **the foreman pane** — a session named `<repo-slug>-foreman` in both tmux and
  the runtime registry, driven by invoking `/livespec-overseer:foreman` in that
  pane. It is the **bounded operator loop** for one checkout: on a recurring
  tick it gathers a fresh status document from the daemon, emits one roster row
  per active plan, and proposes **at most one** whitelisted action per tick
  through its own actuator. It never mutates anything directly, never performs a
  track's own deliverable, and its handling of a human valve is
  configuration-gated — report-only by default.
- **the grooming pane** — a session named `<repo-slug>-grooming`, driven by
  invoking `/livespec-overseer:grooming` in that pane. It is a **bounded one-shot
  drain pass**, not a loop: it measures the whole work-item tenant, drains the
  pending spec-proposal lane, triages untriaged backlog items, buckets unparented
  work into coherent plan threads within a plan budget, hands missing sessions to
  the foreman, reports what it queued, and exits. It routes work; it does not
  implement, dispatch, approve, archive, or restart anything.

Neither surface may restart a tracked session, and the cardinal rule is
unchanged for both of them: each writes its own `ready` declaration and is
restarted by the daemon only once it has.

## Relationship to the rest of livespec

This is a **Control-Plane** member of the livespec fleet, repo class
`control-plane-tool` — a **peer** of the operator console
(`livespec-console-beads-fabro`), never a component of it. The console ships the
cockpit *application*; this ships an operator *tool*.

It depends on **nothing** in the fleet: no imports from livespec core, no
Driver, no orchestrator. It observes the agent runtimes and understands that a
plan's handoff timeline is **ledger-held** — the handoff comments on that plan's
epic. The daemon names that epic in the resume line by repository path and epic
id and never opens it, exactly as it never opens anything under `plan/`; it
enumerates `plan/*/` directories and derives no path into one.

A legacy `plan/<topic>/handoff.md` is **historical migration input only**. The
plan operation no longer authors one, so it is read only where an old tree has to
be interpreted: an assignment-time anchor lookup falls back to it when a topic has
no `epic.md`, and a stored resume override still naming that retired path is
rewritten to the ledger-epic resume. A third party can run the tool with no
livespec install at all.
