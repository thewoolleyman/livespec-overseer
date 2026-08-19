# Track record type safety — measured baseline

Opened 2026-08-19 by the `track-record-type-safety` worker session under a
direct maintainer order. Root-cause carrier: `overseer-hj7zp2`. Symptom
siblings: `overseer-25fnu2`, `overseer-axql66`. Adjacent: `overseer-a2txsq`.

This note records what was MEASURED against the tree and the live store
before any design work, so the plan rests on observation rather than on the
work-item's prose alone.

## 1. The defect, confirmed in the tree

`overseer/_registry_core.py` defines `Track` as one frozen keyword-only
dataclass with eight nullable fields plus a boolean `assigned` tag. Its own
docstring states the variant structure in prose because the type cannot
carry it. Two further variants are never in the record at all — they are
recomputed from the topic STRING at every call site by
`signals.topic_reserved_for_supervisor` and `signals.is_foreman_topic`
(`overseer/_signals_topics.py`), both lowercase `endswith` suffix tests.

The `allow_reserved` parameter on `registry.tmux_id` is documented as
existing solely for the supervisor-epic-inheritance path, justified by "the
caller has already validated a supervised counterpart exists" — a
precondition discharged by the caller and recorded only in a docstring.

## 2. The failure path, traced end to end

- `_supervisor_restart_binder._handle_uncertified_foreman_binder` refuses a
  restart when `is_foreman_topic(topic=track.topic)` and `track.epic is None`,
  emitting `missing_foreman_epic_message()`.
- `_supervisor_prompts.resume_for_track` returns `None` for a foreman track
  whose `epic` is `None`, which is what makes the track unusable.
- `_supervisor_restart.rederive_epic_if_stale` is the only healing path. It
  calls `sup.epic_lookup`, which resolves to
  `_registry_epic.epic_from_plan_anchor`.
- `epic_from_plan_anchor` can resolve exactly three things: `plan/<topic>/epic.md`,
  `plan/<topic>/handoff.md`, or a ledger epic tagged `spec_id plan:<topic>` /
  `metadata.plan_slug == <topic>`. A foreman seat has none of the three by
  construction — it has no plan directory of its own.

So the derivation is not merely failing; it is the wrong question for the
variant, and the `None` it returns is read by the gate as "not configured
yet" rather than "inapplicable".

## 3. Live store inventory (acceptance criterion 7, first pass)

Measured 2026-08-19 against the real `~/.livespec-overseer.jsonl`.

**Row count is 25, not the roughly 67 the work item estimates.** Recorded so
the migration slice sizes against the real store.

Keys present: `topic`, `repo`, `tmux`, `resume`, `epic`,
`pinned_session_id`, `observed_session_identity` on all 25 rows;
`added_at` on 21 of 25. No `ctx_threshold` and no `model_profile` on any
live row.

Variant distribution by topic suffix:

| variant | rows | rows with a non-null epic |
|---|---|---|
| plan track | 19 | 12 |
| foreman seat | 6 | **0** |
| supervisor seat | 0 | n/a |

**The headline finding: ALL SIX foreman seats carry `epic: null`.** The
outage recorded on `overseer-25fnu2` is not specific to
`livespec-overseer-foreman` — it is the current state of every foreman seat
in the fleet:

- `livespec-dev-tooling-foreman`
- `livespec-console-beads-fabro-foreman`
- `livespec-orchestrator-beads-fabro-foreman`
- `livespec-foreman`
- `livespec-driver-pi-foreman`
- `livespec-overseer-foreman`

Every one of them would refuse a durable respawn today. This raises the
value of the fix from one seat to the whole operator layer, and it is direct
evidence for `overseer-axql66`'s claim that the condition is detectable at
any tick while the sessions are still healthy — six seats are in the
un-respawnable state right now, none of them idle.

Seven plan tracks also carry a null epic, but for those the derivation is at
least well-defined and `rederive_epic_if_stale` can heal them; they are a
different condition and must not be conflated with the foreman rows.

No `-supervisor` rows exist live, so the SupervisorSeat variant has zero
production instances to migrate. Its rules must still be modelled — the
inheritance path and `allow_reserved` exist for it — but the migration slice
carries no risk from it.

## 4. Blast radius

- `Track` is referenced across 69 modules under `overseer/`.
- `.epic` is read at 23 sites.
- `topic_reserved_for_supervisor` has 12 call sites, `is_foreman_topic` 10.
- `registry.read_mapping` is on the daemon tick path and is LIVE for every
  tracked session in the fleet, including the session authoring this plan.

That last point is why the read side is non-negotiable: the loader must
never refuse wholesale. The `Invalid` arm replaces today's silent
warn-and-drop with a typed, surfaced failure while preserving the fail-soft
posture exactly.

## 5. Sequencing that must not be inverted

The supported WRITER lands before the schema tightens. Today the only way to
set a reserved seat's epic is an unsupported hand-edit of the JSONL store,
because `supervisor.py` `_refuse_reserved_topic` (line 225) rejects reserved
topics outright — and its refusal text names the `-supervisor` suffix while
rejecting a `-foreman` topic. Tighten first and the sole existing write path
becomes illegal with no replacement, across all six seats above.
