# The foreman's own picker mutes its own loop

Measured 2026-08-21T22:00Z-22:30Z from the `debug-foreman-loop` session, against
the live `livespec-foreman` pane (repo `/data/projects/livespec`, tmux session
`livespec-foreman`, pane `%137`, claude pid 2339455, transcript
`~/.claude/projects/-data-projects-livespec/2af4f15f-bc51-49d3-a854-ebce98446307.jsonl`).

## The finding, in one sentence

A Claude Code session parked on an open `AskUserQuestion` receives **no**
scheduled-task fires, and the missed occurrences are **dropped, not backfilled** —
so the foreman's own escalation mechanism silently disables its own re-entry
mechanism, and the condition that most needs a watcher is the one that removes it.

## What was measured

The session armed cron `b24caf76` (`"7 * * * *"`) at `2026-08-20T23:45:42Z`,
exactly as `.claude-plugin/prose/foreman.md` "Loop Carrier" requires. It fired
**eight times, hourly**, from `00:27:54Z` through `07:27:54Z`.

At `07:53:19Z` that eighth tick ended by raising a blocking `AskUserQuestion`.
**There has not been a single fire since** — 14 consecutive hourly occurrences
missed at the time of writing. The first picker was answered at `13:56:55Z`, but
the session raised its next picker roughly 100 seconds later at about `13:59Z` and
has sat on it since, so the mute has been continuous.

Nothing is defective in any component. The cron job was never deleted (no
`CronDelete` anywhere in the transcript, and its 7-day auto-expiry has not
elapsed), the process is alive, and the daemon is healthy at 1.21.0.

## Evidence for the load-bearing claim

Not inferred from one session. Across every session transcript on this host,
**every long picker window pairs with a fire gap of matching duration, and fires
resume immediately once the picker is answered** — 20+ sessions across 6 repos.
Representative rows:

| session | repo | picker window | fire gap | resumed |
|---|---|---|---|---|
| `607d17cd` | livespec-overseer | 16:42:17 - 20:56:44 | 16:41:42 - 21:42:30 | yes |
| `77f6de7a` | livespec-overseer | 18:27:43 - 23:56:21 | 18:27:03 - 00:29:16 | yes |
| `4ee76686` | livespec-dev-tooling | 12:19:10 - 01:27:54 | 12:18:02 - 02:34:41 | yes |
| `b63ed22f` | livespec-console-beads-fabro | 23:06:00 - 20:08:47 | 23:04:00 - 20:34:00 | yes |
| `2af4f15f` | livespec (**this incident**) | 07:53:19 - still open | 07:27:54 - none | **no** |

Live positive control at the time of measurement: six other sessions fired their
crons normally that day, the most recent at `21:45:30Z`, while this one sat
silent. So the harness scheduler was healthy fleet-wide; the discriminator is
session-local and it is the open picker.

## Independent corroboration from the daemon

`~/.livespec-overseer-status.json` written `2026-08-21T22:17:47Z` carried two rows
for the same pane:

    picker_open: true,  status: "blocked:human",           session: claude:2339455:...:livespec-foreman
    picker_open: false, status: "foreman-heartbeat-stale", note: "foreman heartbeat stale 889m; pid 309170; tic..."

889 minutes before `22:17:47Z` is `07:28:5x` — the last cron fire, to the minute.
Detection was correct and had been firing continuously for roughly 14.8 hours.
Nothing acted on it.

## Why the contract's own remedy cannot be implemented

`.claude-plugin/prose/foreman.md` already carries the right rule (the paragraph
beginning "When you need a human decision that you cannot make yourself"):

> A blocking picker is a last resort: use it only with a bounded timeout, and
> return to the non-blocking escalation if the timeout expires.

**No mechanism can implement that bound.** The picker suppresses the only clock
the session has. Enforcing the timeout would require the very fire the picker is
suppressing. The clause is unimplementable in this harness as written, so the
prose currently instructs sessions to do something impossible and reads as
satisfied when they raise a picker "as a last resort" with no bound at all.

## How this incident actually ended, and what it says about the daemon half

The daemon does have a picker-stall response, and it is deliberately not an
answer. `tmp/overseer/daemon.log`:

    13:55:51Z overseer[SURFACE]: livespec-foreman (livespec) - picker stalled (30m):
              structured picker has not changed - unblock it IN THAT PANE [pane %137]
    13:55:51Z overseer: nudged charter-authorized picker stall /data/projects/livespec::livespec-foreman (1812s)

That is `_supervisor_nudge.nudge_charter_authorized_picker_stall`, whose docstring
reads "Paste a charter reminder into a stalled supervisor picker **without
submitting it**". It calls `bracketed_paste` and never sends Enter, and the pasted
constant says so explicitly: "The overseer is not choosing from this picker and
will not answer it for you."

64 seconds later the picker resolved with the free-text answer
`don't care, ignore it` — the type-something path, not one of the four labelled
options. That string appears as an INPUT in no transcript on this host, and no
session issued a `send-keys` or paste at `%137` or `livespec-foreman` in that
window (the only injection in the window targeted `caam-anthropic-loop`). So a
human typed it, prompted by the daemon's surface. The daemon's design is correct
here and must not be changed into an answering mechanism: the fix belongs on the
side that stops the loop from being muted in the first place, not on the side that
would have the daemon choose for a human.

**Secondary defect observed in the same log line and NOT in scope for this thread:**
the picker-stall clock read `30m` at `13:55:51Z` for a picker that had been open
6h2m, having correctly read `4h` at `12:27:58Z`. The stall clock resets.

## Secondary observation: the cron minute field is not honoured

`CronCreate` reports the spec back as e.g. "Every hour at :07", but the fire phase
is not the spec's minute. Same `"7 * * * *"` spec, three sessions:

| session | armed | actual fire minute |
|---|---|---|
| `2af4f15f` (livespec) | 23:45:42Z | `:27:54` |
| `268ee923` (livespec-driver-pi) | 00:10:06Z | `:19:47` |
| `4ee76686` (livespec-dev-tooling) | 11:17:57Z | `:18:02`, then `:34:41` after its picker gap |

And `"13 */2 * * *"` fired at `:17:15`; `"17 */2 * * *"` fired at `:27:08`. The
cadence is honoured and the phase is arbitrary, re-anchored at arm/resume time —
it behaves as an interval timer, not as cron. Cosmetic for a single foreman, but
it defeats any attempt to stagger fleet foremen by minute, and it is why
`4ee76686`'s fire minute moved after its own picker gap.

## Prior art in the ledger, and what is actually missing

`overseer-dz2skw` (CLOSED, P2, epic `overseer-au3pt3`) diagnosed this exact
mechanism on 2026-08-18 off a roughly 12-hour instance, and its description names
it correctly: "the foreman's cron-driven tick only fires while its own REPL is
idle -- one unanswered picker stalled supervision of EVERY OTHER track under that
foreman". It delivered **specification text only** (v017, PR 1105). Its own
closing comment states: "Implementation (the actual daemon/foreman code) is a
follow-up, **not yet filed**."

That follow-up was never filed. What did land from the thread is all detection:

- `overseer-au3pt3.1` (closed) — daemon NEEDS YOU membership when the foreman escalates.
- `overseer-au3pt3.2`, `overseer-ra6s` (closed) — prose routing discipline plus
  delivery-side detection of context parked behind a picker.

None of it restores tick cadence while a picker is open.

Adjacent open items, none of which covers this:

- `overseer-6tfncs.5` (ready) — make `foreman-heartbeat-stale` distinguish
  died / held / completed. Its acceptance criterion 8 explicitly excludes
  self-restart, and it never names picker suppression as a cause. Its own second
  comment records a different cause: a loop that died while its session stayed
  productive.
- `overseer-w2nwx5` (ready) — the inverse problem, the ladder firing against
  healthy foremen.
- `overseer-enc7oe` (pending-approval) — the foreman cannot deliver a maintainer's
  own answer to a blocked session. Would shorten picker windows; would not un-mute
  the loop.

## The design question the implementer must settle

State it rather than let it be decided silently. There are two shapes, and they
are not equivalent:

1. **The foreman never ends a tick with an open picker.** Escalate onto the
   daemon's existing mechanical attention surface (which `overseer-au3pt3.1`
   already built) and return, so the session goes idle and its cron survives. This
   needs no new process and no new clock, and it is what the ratified v017 text
   already asks for; what is missing is that nothing enforces it and the
   "bounded timeout" escape is unimplementable.
2. **An out-of-process ticker** that does not share the session's suppressed
   clock — the daemon, or a detached timer, drives the tick instead of an
   in-session cron.

Shape 1 is cheaper and is already half-built. Shape 2 is more robust but overlaps
the daemon's restart-authorization boundary and must be designed with care.

**HARD CONSTRAINT, inherited verbatim from `overseer-dz2skw` and non-negotiable:**
this must leave the cardinal rule in `overseer/marker-protocol.md` completely
untouched. It changes only how a human decision is surfaced and how the operator
loop keeps its cadence, never who may authorize a restart. No implementation may
add a timer- or heuristic-driven restart path of any kind, and nothing here
authorizes the daemon to answer a picker on a human's behalf.

## Read first

- `.claude-plugin/prose/foreman.md` — "Loop Carrier", "Arming the loop is not
  optional, and is not a question", and the non-blocking-escalation paragraph.
- `overseer/_supervisor_nudge.py` and `overseer/_supervisor_prompts_nudges.py` —
  the paste-without-submit picker-stall nudge.
- `overseer/_supervisor_foreman.py` — the heartbeat staleness surface.
- Ledger: `overseer-dz2skw`, `overseer-au3pt3.1`, `overseer-ra6s`,
  `overseer-6tfncs.5`.
