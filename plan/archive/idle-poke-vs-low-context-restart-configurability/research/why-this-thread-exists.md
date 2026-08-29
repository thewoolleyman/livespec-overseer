# Why this thread exists

Maintainer directive (2026-08-29, relayed through the bottom-pane overseer
session): overseerd currently conflates two behaviorally distinct daemon
actions under the umbrella of "the daemon pokes a track." They need to be
independently configurable.

## The two mechanisms, as they exist in code today

Both are private collaborators of `overseer/supervisor.py` (package
`livespec-overseer`, installed plugin cache checked at build `5bab46610bde`
/ package version 1.62.6 at time of writing):

1. **Idle-with-context nudge** (`overseer/_supervisor_nudge.py`,
   `overseer/_supervisor_idle.py`). Fires when a track is idle at an empty
   prompt, above the wind-down (`ctx_threshold`) band, and has declared
   nothing in its `.overseer-state` file. Single-shot per idle episode (the
   daemon writes its own `idle-with-context-left` marker to prevent
   re-nudging until the session goes non-idle and back), gated by
   `IDLE_NUDGE_AFTER = 3600.0` (one hour) in `_supervisor_config.py`. This is
   a "keep going" prompt — the daemon's opinion that an idle session with
   context to spare should probably be doing something. It is NOT part of
   the cardinal-rule restart path; it never restarts anything.

2. **Low-context wrap-up + cardinal-rule restart**
   (`overseer/_supervisor_wrapup_injection.py`,
   `overseer/_supervisor_ready.py`, `overseer/_supervisor_restart.py`, and
   the escalation-band logic overseer-wide). Fires as remaining context
   crosses the warn/40/30/20/10 bands, injecting an escalating wrap-up
   message; the daemon restarts the session ONLY after it writes `ready` to
   its own state file (THE CARDINAL RULE — see `marker-protocol.md`). This
   is the mechanism that prevents a track from silently burning out its
   context window with no wrap-up and no restart path.

These are independent code paths today (different modules, different
trigger conditions, no shared config surface) but there is currently NO
config knob for either — both are daemon-wide, unconditional, with only
`ctx_threshold` (the wind-down band itself) already overridable per-track.

## The maintainer's concrete problem

Idle pokes may be unwanted noise on a per-track basis: not every open/
tracked plan is actively being driven at a given moment. An idle plan
waiting for the maintainer's attention is not a bug, and the daemon nudging
it to "keep going" every hour is unhelpful noise on those tracks.

The low-context wrap-up + restart, by contrast, must ALWAYS fire for every
ACTIVELY DRIVEN plan, regardless of whatever idle-nudge setting is in
effect — losing it would mean a track a maintainer IS actively steering can
run its context window to zero with no wrap-up and no restart path. This
mechanism must stay unconditional (or at most daemon-wide-configurable,
never silently coupled to the idle-nudge setting).

## Existing per-track override precedent

`ctx_threshold` is ALREADY a per-track override field on every `Track`
variant (`overseer/_registry_track_variants.py`: `PlanTrack`,
`SupervisorSeat`, `ForemanSeat`, `GroomingSeat` all carry
`ctx_threshold: int | None = None`), settable via
`add --ctx-threshold N` (or `inherit` to clear), read by
`registry.py`/`_supervisor_evaluate_threshold.py` with the daemon-wide
`--warn-percent` as the fallback when the per-track field is `None`.
That precedent is exactly TWO tiers (daemon-wide default, per-track
override) — no per-repo tier exists anywhere in the codebase today.

## Maintainer refinement (2026-08-29, same session): THREE tiers, not two

The idle-nudge knob must be configurable at three levels, most specific
wins:

1. **Daemon-wide default** — mirrors `--warn-percent`'s role for
   `ctx_threshold`. Proposed: `overseerd --idle-nudge {on,off}`
   (default `on`, preserving current behavior when unset).
2. **Per-repo override** — NEW tier; no existing precedent to follow
   verbatim. The natural home is `~/.livespec-overseer-repos.json`, the
   existing hand-edited, JSONC, per-repo declaration file
   (`registry.watch_set_from_config`, `_registry_discovery.py`). Today
   each `repos[]` entry is a bare path string; the minimal extension is
   to accept EITHER a bare string (path, all defaults) OR an object
   (`{"path": "...", "idle_nudge": true|false}`) per entry — additive,
   backward-compatible with every existing repos.json on the fleet
   (including the ones this very session has been editing all day).
   Alternative considered: a second config file
   (`~/.livespec-overseer-repo-settings.json`) keyed by repo path,
   keeping `repos.json` a pure watch-set declaration with no per-repo
   settings mixed in — cleaner separation of "what to watch" from "how
   to behave," at the cost of a second file to keep in sync. Needs a
   maintainer decision before implementation (see open questions).
3. **Per-track override** — the `idle_nudge: bool | None = None` sibling
   field on `Track` variants, as already sketched above; settable via
   `add --idle-nudge {on,off,inherit}`.

Resolution order for a given track: per-track field (if not `None`) →
per-repo override (if the repo entry sets one) → daemon-wide default
(`--idle-nudge`, itself defaulting to `on`). This is a straightforward
extension of the existing two-tier `ctx_threshold` precedent, not a new
pattern invented from scratch — it just adds the one missing tier.

The low-context wrap-up/restart mechanism gets NO analogous per-repo or
daemon-wide "off" switch in this thread's scope — per the maintainer's
original framing, it "should happen for all active plans," full stop.
`--warn-percent` and `ctx_threshold` already control WHEN it fires, not
WHETHER; nothing here proposes changing that.

## Open questions for scoping (to resolve via a scope event before any
child work is filed)

- Per-repo config location: extend `repos.json` entries to accept an
  object shape (leaning toward this — one file, one place an operator
  looks), or a separate per-repo settings file? Needs a maintainer call.
- Daemon-wide CLI surface: `overseerd --idle-nudge {on,off}` (mirrors
  `--warn-percent` exactly), defaulting to `on` so existing behavior is
  unchanged for anyone who never touches the new flag.
- Per-track CLI surface: extend `add` with `--idle-nudge {on,off,inherit}`
  (mirrors `--ctx-threshold N|inherit`), keeping the CLI vocabulary at
  list/add/remove/unassign/start rather than growing a new verb.
- Table/status-vocabulary impact: does an idle track with nudging
  suppressed need a distinct status label (e.g. still `idle`, vs a new
  `idle-nudge-suppressed`), or is silence (no nudge, same `idle` status)
  sufficient? Silence is simpler and matches "this is opt-out noise
  suppression," not a new lifecycle state.
- Does the per-track field want a corresponding `remove`/`unassign`-time
  reset, or does it simply live and die with the mapping row like
  `ctx_threshold` already does?
- Does a repo-level `idle_nudge: false` need to be visible anywhere in
  the live table (e.g. a `Repo` column annotation), or is it purely a
  config-file fact an operator confirms by reading `repos.json`?

No implementation children are filed yet — this thread opens with research
only, per the plan operation's contract. A scope event should record the
requirement carriers and any deferrals before `capture-work-item` is used
to file the first child.
