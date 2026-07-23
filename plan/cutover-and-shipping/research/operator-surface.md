# Operator-surface shipping shape — DECIDED 2026-07-23: plugin + entry points

The maintainer decision for handoff scope items 3 and 6 (they pair): the
`/overseer` interactive operator surface ships as a **Claude Code plugin**,
and the executables become **public pyproject entry points**. Recorded here
as the thread's design reasoning; implementation is ledger work (filed under
epic `overseer-3wt`, groomed before dispatch), not this note's job.

## The decided shape

1. **A fleet-standard plugin** published from this repo (marketplace entry
   like `livespec-driver-claude`'s): `/overseer` is a THIN skill binding
   over repo-owned prose, the same binding-vs-prose split the
   `livespec-orchestrator-beads-fabro` plugin uses. The binding resolves
   the plugin root and reads the operator contract that today lives in
   `overseer/SKILL.md`; the contract prose moves to (or is re-exported at)
   the plugin's prose path so the skill has no behavior of its own.
2. **Public entry points** in `pyproject.toml` for the executables —
   `overseerd` (daemon) and `overseer-start` (bootstrap) — replacing the
   script-file invocations and resolving the deferred change behind the two
   demoted `reportPrivateUsage` warnings (the pinned-gate warnings recorded
   at relocation time). The `.livespec.jsonc` harness declaration's
   `canonical_command: "overseer"` names the operator surface an adopter
   invokes; the entry-point slice decides whether that is a third console
   script or the plugin skill's invocation name, and updates the
   declaration if the shape shifts.
3. **Codex stays exempt** per `.livespec.jsonc` (the daemon half is
   harness-neutral; there is no Codex operator pane), and the CORE-tenant
   items `livespec-b1uo.4`/`.5` (per-Driver thin bindings) are CONFIRMED
   unnecessary by this decision — the plugin IS the claude binding. Their
   close is staged evidence-side in livespec core per that epic's
   do-not-move ruling; nothing to do in this tenant.

## Why this shape

- **It is the fleet's existing distribution channel.** Every other
  operator-facing surface in the fleet (livespec lifecycle, orchestrator,
  drivers) ships as a plugin with thin per-runtime bindings over
  plugin-owned prose; the overseer diverging (bare local skill, or
  docs-only) would recreate the "local-only, unversioned, drifts silently"
  failure class the relocation and `overseer-zvo` just cleaned up.
- **It gives Phase 2 (D7/D8/D9) its install story.** An adopter FAMILY
  installs the plugin plus the package and runs the overseer against its
  own `$HOME` declarations — never reading `.livespec-fleet-manifest.jsonc`
  (D5). Version pinning rides the marketplace mechanism the fleet already
  trusts.
- **Entry points close a recorded debt.** The two `reportPrivateUsage`
  demotions were accepted at relocation time explicitly "until the public
  entry-point surface lands"; folding them into this shape retires that
  waiver rather than letting it calcify.

## What was rejected

- **Console-scripts only, no plugin** — simplest, but leaves the operator
  pane's contract as repo documentation with no versioned install path for
  adopters, and no slash surface in the harness that actually drives the
  interactive pane.
- **Defer to Phase 2** — the decision blocks nothing today, but every
  pre-Phase-2 change to `SKILL.md` or the executables would risk building
  in the wrong direction; deciding now is cheap and reversible on evidence.

## Boundaries this shape must not cross

- The daemon never reads the fleet manifest (D5); the watch-set stays the
  `$HOME` declaration file.
- The plugin carries the OPERATOR surface only; the supervision contract
  (`overseer/marker-protocol.md`) and the daemon stay package-owned — a
  plugin update must never be able to change daemon behavior on its own.
- Implementation slices go through the ledger (groom → valves → factory);
  this note records shape and rationale only.
