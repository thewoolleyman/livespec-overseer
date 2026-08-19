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

**Row count is 25, not the roughly 67 the work item estimates** — 26 later the
same day, once this thread's own track was registered.

**The provenance of the 67 is now known, and it is a category error worth
naming.** That figure came from the daemon STATUS SNAPSHOT,
`~/.livespec-overseer-status.json`, which is a JOINED VIEW and holds 68
entries. It is not the mapping store. The two are easy to conflate because
both are JSON sidecars in `$HOME` describing the same tracks, but only the
mapping store is what `read_mapping` parses. Confirmed by direct read of both
files: snapshot 68, store 26.

**The blast-radius argument does not depend on the count**, and this
correction must not be read as weakening it. 26 rows spanning every repo the
daemon watches is still a fleet-wide loader on the tick path; a read side that
could fail wholesale would still turn one malformed row into a fleet-wide
supervision outage. The count was never the load-bearing part of the
argument.

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

**The headline finding: ALL SIX foreman seats carry `epic: null`.**

That reading was taken at approximately 08:45Z and was accurate at its
timestamp. By 09:09Z it read five of six — `livespec-overseer-foreman` had
been hand-backfilled with `overseer-z5fo4y`. **The exception strengthens the
finding rather than blunting it**, because that value exists only by an
unsupported hand-edit of the JSONL store: exactly the write channel this
thread exists to replace, and one with a measured half-life. The foreman
seat's recorded timeline —

| time | state |
|---|---|
| 08:20Z | backfilled by hand |
| by 08:59Z | null again — clobbered within about 40 minutes |
| 08:59:45Z | re-backfilled by hand |
| 09:09Z | still present, 9 minutes old |

— means **the count of un-respawnable seats is not a stable quantity.** It
oscillates with each hand-edit and each clobber. This is the third independent
sighting of the erasure recorded on `overseer-25fnu2` ("at least the second
time it has been applied and lost"), and an oscillating count is a stronger
argument for a supported writer than any fixed number would have been.

The
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

## 6. What landed, and what the tree looks like now

Recorded 2026-08-19 after slices 1 and 2 merged, so a later reader is not
misled by the file map in sections 1 and 2 above, which describe the
PRE-MERGE tree.

`overseer-y3xhlh.1` — PR #1196, commit `493d9a4`. `supervisor.py add --epic`
can now set a reserved `-foreman` seat's epic. `_signals_topics.py` gained
`reserved_worker_suffix` (returns *which* reserved suffix matched, or None)
and `foreman_seat_accepts_explicit_epic`. The refusal names the suffix it
actually matched instead of always citing `-supervisor`.

`overseer-y3xhlh.2` — PR #1198, commit `ece43b5`. Two new modules:

- `_registry_rows_io.py` — raw JSONL I/O (`RawMappingRow`, `read_row_records`,
  `read_rows`, `write_rows`). The old `_read_rows` / `_write_rows` in
  `_registry_store.py` are gone.
- `_registry_mapping_read.py` — the parse boundary. `MappingValid`,
  `MappingInvalid`, the `MappingEntry` union, `read_mapping` (returns
  entries), and `read_valid_mapping` (the adapter ~15 existing call sites
  use). The old `_track_from_row` is gone.

**The fleet-outage control test now exists** at
`tests/test_mapping_store_invalid_rows.py`: one malformed row is reported
through the Invalid arm and both well-formed neighbours still load. That is
the regression guard for this whole design and must pass unchanged through
every later slice.

### The Invalid arm's boundary, which is narrower than it sounds

The Invalid arm covers exactly one failure: a well-formed JSON *object* row
missing a string `topic` or `repo` (`reason="missing_topic_or_repo"`). Three
other failures stay in an outer fail-soft layer and are only warned to
stderr — a line that is not valid JSON, a JSON line that is not an object,
and an unreadable or non-UTF-8 store (which returns an empty list).

**This is deliberate and documented** in the `read_row_records` docstring, and
preserving it is what keeps the loader fail-soft. But it means a store
inventory that counts only Invalid entries would report a clean store even if
it held unparseable lines. The inventory slice is instructed to measure on two
channels: the Valid/Invalid split, *and* the lines present in the file that
produced no entry at all.

It also means **parser-valid is not semantically sound**: every one of the
null-epic foreman seats is a perfectly Valid row by the current parser's
rules. Expressing the ForemanSeat requirement is what slice 3 adds.

### One regression found on review

`read_mapping` now parses the whole store twice per call in the steady state —
`read_rows` for the `normalize_rows` check, then `read_row_records` for the
result. Filed as `overseer-y3xhlh.7` (P3) rather than fixed inline, since it
has its own acceptance and test. Low priority at 26 rows; on the tick path, so
worth not letting grow.
