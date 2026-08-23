# The event shape, measured before `.2` and `.3` are implemented

ledger anchor `overseer-temi26`, children `overseer-temi26.2` and `.3`

Written 2026-08-22, after the `.1` decision, because `.2`'s acceptance reads
"its fields match the exported span's attributes" and `.3`'s span does not exist
yet. Left as-is, whichever child ran first would have invented the shape and the
other would have had to chase it. This note fixes the shape from what the daemon
already emits, so both children implement against the same record.

## The emission surface is already a choke point — that is the good news

Every daemon event leaves through `overseer/_supervisor_diagnostics.py`, an
80-line module with exactly two exits:

  - `log(message=...)` — plain `<ts> overseer: <message>`, **31 call sites**
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
there and are discarded.** **A `condition=` grep returns 39 hits — but see the
correction below: that is a count of SITES, the vocabulary is not closed, and
fifteen alerts name no condition at all.**

The `log` half is the weaker one: 31 sites, mostly free-prose f-strings. But they are
strikingly uniform — nearly every one interpolates the same natural key,
`{repo}::{topic}`, plus a verb and one or two extras (`pane`, `ctx`, `bands`,
`{exc}`). The record is latent in them too.

## Correction: the condition vocabulary is NOT closed, and naming it is real work

This note first said "the 39 `condition=` values are already a closed, stable
vocabulary … so the event NAME needs no invention either." **That was wrong**,
derived from a grep for `condition=` that returned 39 hits. Re-measured, the
vocabulary is neither closed nor 39, and the error concealed scope `.2` did not
know it had.

**39 counted SITES, not values:**

  - **23** distinct literal strings (two used at two sites each);
  - **9** named module constants — stable names, just indirected, and invisible
    to a grep for a quoted string;
  - **2** PARAMETERIZED families — the blocked and ready-uncertifiable age bands
    are f-strings interpolating the band;
  - **3** forwarded variables whose real values live in their callers.

**And the forwarding hides names the grep cannot see.** `_supervisor_offer.py`
assigns its condition to a LOCAL on three branches — `supervisor-missing`,
`supervision-capture-offer`, `supervision-offer` — none of which appear among the
39. The enumeration was incomplete as well as miscounted.

**The serious part: 15 of 51 `alert()` call sites name no condition at all.**
`Supervisor.alert` declares `condition: str = "default"`, so every caller that
omits it lands on the literal condition `default`. They are not trivia — restart
respawn FAILED, the idle-with-context-left nudge FAILED, five codex-restart
paths, claude-restart and resume-retry, and wrap-up injection
(`_supervisor_restart.py:122,145,181`;
`_supervisor_codex_restart.py:114,123,133,155,166`;
`_supervisor_nudge.py:127,159,209`; `_supervisor_resume_retry.py:89,135`;
`_supervisor_claude_restart.py:34`; `_supervisor_wrapup_injection.py:122`).

Two consequences, both new scope for `.2`:

  1. **These 15 must be NAMED.** `condition` becomes the event name, so as things
     stand fifteen distinct failure kinds would export as the single event
     `default`. The signal-choice note endorses the curated-closed-catalog
     principle and states the failure mode as "exporting a line because it
     happens to be written". An event called `default` is exactly that — arriving
     BY DEFAULT rather than by neglect, which is worse, because nothing in the
     code looks wrong.
  2. **Their dedup is entangled.** The key is `(repo, topic, condition)`, so all
     fifteen share ONE key per track: re-arming is shared and "this track entered
     condition X" is not expressible for any of them. Naming them fixes the
     export and the dedup in one edit.

**Method note, because the first attempt at "15" was also wrong.** A non-greedy
regex over multi-line `.alert(` blocks reported 33 without a condition;
balanced-paren parsing reports 15, and spot-checks confirm the parser — the regex
truncated call bodies before reaching a `condition=` on a later line. 33 versus
15 is the difference between "most alerts are unnamed" and "a specific,
enumerable set is": different findings with different remedies. **Parse, do not
pattern-match, when the answer depends on what is INSIDE a call.**

**Two further counts corrected the same way, and together they change the SIZE of
this work by about a third.** The original `22` for the `log` half came from a
grep for `log(message=` — which matches only calls whose keyword sits on the SAME
LINE. Parsed: **31** `.log()` sites, of which 23 pass a single-line literal or
f-string and 8 pass a parenthesized multi-line f-string or a variable. Two of
those 8 are forwarders rather than emission points and one passes a message built
elsewhere, so roughly **29 real emission points**. And the module is **80** lines,
not the 86 stated twice above before this correction.

So the emission surface to convert is **31 log sites plus 51 alert sites — 82
call sites**, not the 61 the original figures implied. **None of this changes the
DESIGN** — the envelope, the promoted fields, the dedup rule, the repo-slug
inconsistency and the banded-reporting decision all stand exactly as written. It
changes the size, which matters for how the work is finished: this repo's
guidance records an item that was "not too big to implement, it was too big to
FINISH UNATTENDED", and the remedy there was not splitting but ensuring work is
pushed before any blocking question. If a single pass lands only part of the
surface, the right disposition is a follow-up child for the remainder.

**There is no consistent bias to correct for, only the wrong instrument.** Of the
three miscounts in this note, the first over-counted (39 sites read as 39
values), the second under-counted (22 for 31), and the third mis-classified sites
as values. A grep over source answers questions about LINES; any question about
what a CALL contains needs a parser.

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

**The control, run afterwards against this very claim — it holds, and it was
UNDERSTATED.** A high distinct count could have been track VARIETY rather than
dedup failure, since different tracks are legitimately different dedup keys.
That is exactly what `picker-stalled` turned out to be, and the same test had not
been applied here when the paragraph above was first written. Applied since: only
**three** tracks produce all 2,177 lines, and isolating the largest — one repo,
one topic, one condition, hence ONE dedup key — gives **1,189 lines with 1,189
distinct bodies**. One hundred percent. For that key the dedup suppresses nothing
at all; the 7% above is an aggregate softened by two smaller tracks. The
transferable method: counting distinct lines answers nothing on its own —
partitioning by the dedup's OWN key is what discriminates, and it is what made
one control come out innocent and this one guilty.

**That raises the bar for `.2`'s acceptance.** "Fewer lines than before" is too
weak when the current state is one line per tick per stale track forever. The
control must assert the strong form: a track held in one condition across N ticks
produces EXACTLY ONE event for that condition, plus one per crossed escalation
band.

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
