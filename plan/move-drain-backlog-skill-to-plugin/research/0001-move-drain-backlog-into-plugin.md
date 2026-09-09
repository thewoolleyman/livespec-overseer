# move-drain-backlog-skill-to-plugin — research

## Goal

Move the `drain-backlog` skill out of the repo-local skills tree
(`.claude/skills/drain-backlog/`) and INTO the shipped `livespec-overseer`
plugin, so it becomes a third first-class operator operation invoked as
`/livespec-overseer:drain-backlog`, alongside `overseer` and
`caam-anthropic-loop`. Maintainer-requested 2026-09-09 (thewoolleyman).

## Current state (measured 2026-09-09)

Local, self-contained skill — NOT part of the plugin:

- `.claude/skills/drain-backlog/SKILL.md` — 504 lines / ~29 KB. A single
  self-contained doctrine file (frontmatter `name`/`description` + the whole
  operating body inline). It is NOT split into a thin binding + prose the way
  the plugin operations are.
- `.claude/skills/drain-backlog/scripts/` — four scripts:
  `engine-on-green.sh`, `plan_completion.py`, `snapshot.py`, `tick.py`.
- Invocation today: `/drain-backlog [--update-snapshot] [--repo <path>]`.
  Body references scripts as `<skill-dir>/scripts/...` (relative to the skill
  dir) and durable state under `tmp/drain-backlog/` in the target repo.
- Pinned by `tests/test_drain_backlog_plan_completion.py`, which inserts
  `.claude/skills/drain-backlog/scripts` onto `sys.path` and imports
  `plan_completion` (28 KB of tests). This path MUST move in lockstep.

All five files are git-tracked. The installed marketplace clone
(`~/.claude/plugins/marketplaces/livespec-overseer/.claude/skills/drain-backlog/`)
is just the checkout of this repo and follows the repo change on reinstall.

## Target state — the plugin operation pattern

Each plugin operation ships ONE harness-neutral prose contract plus THREE thin
bindings that only resolve a plugin root and read that prose (verified against
`overseer` and `caam-anthropic-loop`):

1. `.claude-plugin/prose/<op>.md` — the harness-neutral contract (all behavior).
2. `.claude-plugin/skills/<op>/SKILL.md` — Claude binding. Frontmatter
   `name`/`description`/`allowed-tools`; body does
   `cat "${CLAUDE_PLUGIN_ROOT}/prose/<op>.md"`.
3. `.claude-plugin/.codex-plugin/skills/<op>/SKILL.md` — Codex binding.
   Frontmatter `name`/`description` only; resolves `$PLUGIN_ROOT` EXPLICITLY
   (Codex does not substitute a plugin-root token) and references
   `prose/<op>.md`.
4. `.claude-plugin/.pi-plugin/skills/livespec-overseer-<op>/SKILL.md` — pi
   binding (flat namespace → unabbreviated `livespec-overseer-` dir prefix);
   resolves the root via the shared `.pi-plugin/lib/resolve-plugin-root.sh`.

## Governance finding — this REVERSES a maintainer ruling (load-bearing)

The shipped operator surface is a **deliberately closed set of exactly two**,
asserted by SET EQUALITY (not membership) in
`tests/test_shipped_skill_surface.py`:
`SHIPPED_SKILLS = ("caam-anthropic-loop", "overseer")`, checked across all four
trees (Claude skills, nested Codex, pi, prose) AND the three manifests'
advertising text. Its docstring cites the authority: **console plan decision
D5, maintainer ruling 2026-09-06** (the "bucket-2 trim"). `CLAUDE.md` states the
same: the repo "ships exactly TWO operator surfaces, and nothing else."

Adding `drain-backlog` as a third shipped skill therefore **reverses D5**. This
is a deliberate reopening of a closed set, and updating its guards is a
FIRST-CLASS part of the work, not an afterthought — the set-equality gate makes
the whole move atomic (no tree/manifest can gain the skill without every other
tree/manifest and `SHIPPED_SKILLS` agreeing in the same change).

**This is NOT spec-change-tier.** `SPECIFICATION/README.md` states the spec
governs the SUPERVISION CONTRACT (daemon + thin pane), explicitly "not the
interactive pane's operator-cockpit surface." No `SPECIFICATION/` clause
constrains the shipped-skill count (greps for "exactly two" in the spec are
about daemon state places and honest-outs, never skill count). So the invariant
lives in `CLAUDE.md` + tests + the D5 ruling — a maintainer-ruled, test-pinned
invariant. It routes as a normal repo change, NOT through `/livespec:propose-change`.
The maintainer is the requester, so the request itself authorizes the reversal;
the plan records it explicitly rather than smuggling it.

## Change inventory (single atomic PR)

Create:
- `.claude-plugin/prose/drain-backlog.md` — the moved body, re-pathed and
  re-tensed for a plugin operation (see design decisions).
- `.claude-plugin/skills/drain-backlog/SKILL.md` — Claude binding.
- `.claude-plugin/.codex-plugin/skills/drain-backlog/SKILL.md` — Codex binding.
- `.claude-plugin/.pi-plugin/skills/livespec-overseer-drain-backlog/SKILL.md` — pi binding.
- A plugin home for the four scripts (design decision below).

Update (the guards + lockstep artifacts):
- `tests/test_shipped_skill_surface.py` — `SHIPPED_SKILLS` → three entries.
- `tests/test_bindings_reference_their_prose.py` — `OPERATIONS` → add `drain-backlog`.
- `.claude-plugin/plugin.json` + `.claude-plugin/.codex-plugin/plugin.json`
  (`description`, kept byte-identical on lockstep fields) — advertise the third op.
- `.claude-plugin/marketplace.json` (`description`, byte-identical to plugin.json).
- `tests/test_drain_backlog_plan_completion.py` — the `sys.path` insert → new
  script location.
- `CLAUDE.md` — "exactly TWO operator surfaces" → three; note the D5 reversal.
- `release-please-config.json` — already targets both `plugin.json` versions
  (no change expected; confirm no per-skill entry is needed).

Remove:
- `.claude/skills/drain-backlog/` (SKILL.md + scripts/) via `git rm`. Leave no
  stub.

Consider (verify, may need no change):
- `overseer/test_plugin_structure.py` (overseer-specific; a parallel for
  drain-backlog is optional, not required by any gate).
- `tests/test_prose_release_hygiene.py`, `tests/test_plugin_carrier_lockstep.py`,
  `tests/e2e-cli/test_codex_skill_picker.py` — enumerate/scan the prose+skill
  trees; confirm the new op passes their hygiene rules (release-note shape,
  carrier lockstep, codex picker).

## Design decisions to settle in implementation

1. **Scripts home.** Options: `.claude-plugin/scripts/drain-backlog/` (mirrors
   the orchestrator plugin's `scripts/bin/` idiom) or beside prose. Recommend
   `.claude-plugin/scripts/drain-backlog/`, referenced from prose by a
   plugin-root token. Whatever is chosen, `test_drain_backlog_plan_completion.py`
   points its `sys.path` there.
2. **Harness-neutral script pathing in prose.** The prose is read by three
   harnesses, so `<skill-dir>/scripts/...` no longer resolves. The Claude
   binding has `${CLAUDE_PLUGIN_ROOT}`; Codex/pi resolve `$PLUGIN_ROOT`. The
   prose should reference scripts via a single resolved-root variable the
   binding sets before reading prose (the pattern `overseer.md` uses for
   `$OVERSEER_START`), OR instruct the reader to resolve the plugin root once.
   Note the scripts internally already self-resolve the ORCHESTRATOR plugin
   cache (`engine-on-green.sh` globs `~/.claude/plugins/cache/livespec-orchestrator-beads-fabro/...`)
   — that is independent of this plugin's root and is unaffected.
3. **Invocation rename.** Every `/drain-backlog` self-reference in the body →
   `/livespec-overseer:drain-backlog`. The "point a session at this SKILL.md
   directly" affordance changes to "read the prose contract."
4. **`--repo <path>` generality is preserved.** drain-backlog is a fleet-wide
   tool ("run against another checkout"); as a plugin skill it is globally
   available, which is strictly better than a repo-local skill. Home in
   `livespec-overseer` (not `livespec-orchestrator-beads-fabro`) is the
   maintainer's explicit choice.

## Dispatch-safety assessment

Dispatch-safe (repo change only): no `SPECIFICATION/` edit, no `{{...}}` tokens
in the work-item text, deliverable is a repository change (not a ledger
mutation), single atomic unit. Route `hp` (the only target for this repo).
Bound the in-sandbox deliverable at a green merged PR.

**Post-merge host-side obligation (separate, NOT in-sandbox):** reinstall /
reload the plugin so `/livespec-overseer:drain-backlog` resolves and the dead
local skill clone is gone. Name this on the item as a post-merge step so it does
not deadlock a sandboxed run.

## Acceptance criteria (for the implementation child)

- `/livespec-overseer:drain-backlog` resolves in Claude Code and reads
  `prose/drain-backlog.md`; Codex and pi bindings present and resolve their root.
- `tests/test_shipped_skill_surface.py` passes with the three-skill set across
  all four trees + three manifests.
- `tests/test_bindings_reference_their_prose.py`,
  `tests/test_plugin_manifest_lockstep.py`, `tests/test_drain_backlog_plan_completion.py`
  all pass against the new locations.
- `.claude/skills/drain-backlog/` no longer exists; no dangling path reference
  remains (grep the tree).
- `CLAUDE.md` reflects three surfaces and records the D5 reversal.
- `just check` green; PR merged under rebase-merge discipline.
