# The event shape, measured before `.2` and `.3` are implemented

ledger anchor `overseer-temi26`, children `overseer-temi26.2` and `.3`

Written 2026-08-22, after the `.1` decision, because `.2`'s acceptance reads
"its fields match the exported span's attributes" and `.3`'s span does not exist
yet. Left as-is, whichever child ran first would have invented the shape and the
other would have had to chase it. This note fixes the shape from what the daemon
already emits, so both children implement against the same record.

## The emission surface is already a choke point — that is the good news

Every daemon event leaves through `overseer/_supervisor_diagnostics.py`, an
86-line module with exactly two exits:

  - `log(message=...)` — plain `<ts> overseer: <message>`, **22 call sites**
    (counted across `overseer/*.py`, tests excluded).
  - `surface(message=...)` — `<ts> overseer[SURFACE]: <message>`, reached in
    practice through `alert(request=...)`, whose `AlertRequest` is raised at
    **39 call sites** carrying a `condition=`.

So the reshape has one module to change, not thirty.

## Half the record already exists and is thrown away at the last moment

`AlertRequest` is *already* a structured record: `repo`, `topic`, `session`,
`pane`, `message`, `condition`. `alert` then flattens it into

    f"{topic} ({repo_slug}) — {message} [{where}]{jump}"

and `surface` writes that string. **Nothing needs deriving — the fields are
there and are discarded.** The 39 `condition=` values are already a closed,
stable vocabulary (`ctx-stale`, `picker-stalled`, `ready-uncertifiable`,
`blocked-human`, `stale-launch-profile`, `winddown-starved`,
`escalation-exhausted`, `shell-prolonged`, `supervisor-gone-mid-round`, …), so
the event NAME needs no invention either.

The `log` half is the weaker one: 22 free-prose f-strings. But they are
strikingly uniform — nearly every one interpolates the same natural key,
`{repo}::{topic}`, plus a verb and one or two extras (`pane`, `ctx`, `bands`,
`{exc}`). The record is latent in them too.

## Three defects the reshape must fix, not merely survive

These were measured in the live `tmp/overseer/daemon.log` (7.3 MB) on
2026-08-22. They matter because a reshape that preserves them ships a
structured version of the same problem.

**1. The edge-trigger dedup is defeated, and it is why the log is 7.3 MB.**
`alert` is documented as edge-triggered: it stores the rendered line under
`(repo, topic, condition)` and returns early when the line is unchanged, so a
stuck track reports once rather than every tick. The docstring records why —
"a track blocked overnight logged ~3,000 of them".

It does not work for the largest emitter. `_supervisor_foreman.py:165` builds
the note as `foreman heartbeat stale {int(age // 60)}m; pid …; tick …;
interval …`. **The age is inside the line.** It increments every minute, so the
line differs every minute, so the equality test never matches. Measured over the
last 4,000 lines: 2,177 are `foreman heartbeat stale`, of which **2,021 are
distinct** — the dedup suppresses 7% of them. One track (`foreman` in `homelab`)
has been stale 4,073 minutes ≈ 68 hours and emits roughly one line per tick for
all of it.

The contrast proves the mechanism rather than merely asserting it: conditions
that BAND the age into the `condition` key instead — `blocked-age-{band}`,
`ready-uncertifiable-age-{band}` — dedup correctly. `picker-stalled` was checked
as a control and is fine: its 34 lines at `(30m)` are 34 *different tracks*, two
or three lines each, which is the intended shape.

**So structuring the event is not sufficient.** If `age_minutes` becomes a field
and the dedup still keys on the whole rendered record, the volume defect
survives untouched in a tidier format. The dedup must key on the event's STABLE
identity — event name plus track plus the non-monotonic fields — with
monotonically-varying fields excluded from that key.

**2. The verb is printed twice.** `_supervisor_foreman.py:200` wraps a note that
already begins with the same phrase, producing `… — foreman heartbeat stale:
foreman heartbeat stale 368m; pid …`. Measured: **14,155 lines** carry the
doubling. A structured event has one `event` field and cannot express this.

**3. Truncation severs a field mid-record.** That note is passed through
`elide(text=…, limit=MAX_REASON_IN_ALERT)`, and live lines end at `pid 3617418;`
— cut between fields, dropping `tick` and `interval` entirely. Eliding a prose
blob is lossy in an unpredictable place; eliding a record means dropping named
fields, which a reader can at least detect.

## The shape

One event, rendered two ways. Common envelope on every event:

| field | source | notes |
|---|---|---|
| `ts` | `iso_now()` | already the line prefix |
| `event` | `condition` for alerts; a new kebab verb per `log` site | the stable name; 39 alert values already exist |
| `severity` | `alert` for the surface path, `info` for the log path | preserves the SURFACE/plain split the bottom pane reads |
| `repo` | `registry.repo_slug(repo=…)` | see the inconsistency below |
| `topic` | the track topic | absent on daemon-level events |
| `daemon_instance_id` | constant for the life of one `overseerd` process | see the correction below |
| `tick_generation` | the loop iteration | see the correction below |
| `message` | the human sentence | retained verbatim so the log stays eye-readable |

Event-specific fields, promoted out of the f-strings — every one of these is
interpolated into prose today: `session`, `pane`, `ctx_percent`, `bands`,
`age_minutes`, `pid`, `tick`, `interval`, `error`.

**One inconsistency to settle while promoting `repo`:** the two halves disagree
today. `alert` renders `registry.repo_slug(repo=…)` (`livespec-overseer`) while
the `log` sites interpolate the raw path (`/data/projects/livespec-overseer`).
The same event stream currently spells the same repo two ways, which is exactly
what makes the log uncorrelatable. Emit the slug in both.

**Daemon-level events carry no track.** `daemon log opened`, `interrupted;
exiting`, `claude build at <phase>` have no `repo`/`topic`. The record must
allow their absence rather than emit an empty string.

## Correction: two envelope fields the existing log does NOT carry

Added after the table above was first written, and it is worth stating why
rather than editing the table silently. **The envelope was derived from what the
daemon already emits, and that was the wrong side to derive it from alone.**
Sibling `.3` names attributes the daemon does not print today, and singles out
two of them as the ones that matter most. Deriving only from the existing prose
lines would have shipped a log the exporter then could not match — the exact
failure this note exists to prevent.

`.3` asks spans to carry what the TOP PANE carries, "so Honeycomb answers the
questions the table answers": `topic`, `tmux`, `repo`, `status`,
`session_identity`, `ctx`, `tick_generation`, `daemon_instance_id`. Of those it
says the last two "make currently-unanswerable questions answerable — was this
the same daemon instance as before the bounce, and how many ticks did a state
persist".

**Both belong in the ENVELOPE, on every event, not only on spans.** The premise
of this plan is one event rendered two ways, identical in shape, so the local log
is a replayable fallback when the exporter is unreachable. A field present on the
span and absent from the log breaks that premise exactly where the fallback
matters most — an operator reading `daemon.log` after an outage is precisely the
reader who needs to know which daemon instance produced a line.

  - **`daemon_instance_id`** answers "is this the same daemon as before the
    bounce". `AGENTS.md` records that as a live operational question here: the
    daemon imports its modules once at startup and never hot-reloads, so a merged
    fix is not in effect until a bounce, and today the log gives a reader no way
    to tell one process's lines from the next one's. Note this is *also* partly
    available from the status file's `daemon_package.version` — but that reports
    the RELEASE, not the INSTANCE, so two consecutive bounces of the same release
    are indistinguishable there and would be distinguishable here.
  - **`tick_generation`** answers "how many ticks did a state persist" directly,
    and it is the natural companion to `.2`'s dedup fix: once an alert is
    edge-triggered and reported ONCE, the tick number is what tells a reader when
    it was first observed, without re-emitting the line every tick to say so.

The remaining `.3` attributes — `tmux`, `status`, `session_identity`, `ctx` — are
TRACK-scoped, so they join the promoted per-event fields rather than the
envelope. **One naming collision to settle in `.2`:** `ctx` and `ctx_percent` are
the same quantity under two names, and `.3`'s acceptance turns on the two
renderings using identical keys, so pick one.

So the envelope is: `ts`, `event`, `severity`, `repo` (slug on both paths),
`topic`, `daemon_instance_id`, `tick_generation`, `message`. Track-scoped events
add the promoted fields; daemon-level events carry no `repo`/`topic` but DO carry
the instance and tick.

## What `.3` inherits from this

  - `event` becomes the span name; every other field becomes a span attribute
    with the SAME key. That is what makes `.2`'s acceptance — "its fields match
    the exported span's attributes" — mechanically checkable rather than a
    judgement call.
  - **A daemon event is instantaneous.** Emit a zero-duration span
    (`startTimeUnixNano == endTimeUnixNano`) rather than inventing a duration.
  - `severity` maps to an attribute, NOT to `status.code`. An alert is not an
    error — a stale foreman heartbeat is a correct observation correctly
    reported. Reserve `status.code` 2 for the daemon's own failures (the
    `error`-carrying events).
  - The dedup fix in `.2` is inherited by the exporter for free: edge-triggered
    alerts mean the OTLP stream carries one span per condition ENTRY rather than
    one per tick. Without the `.2` fix, `.3` would export ~2,000 spans a day for
    a single stale track.
