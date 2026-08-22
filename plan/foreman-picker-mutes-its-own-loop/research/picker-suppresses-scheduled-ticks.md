# The foreman's own picker mutes its own loop

Measured 2026-08-21T22:00Z-22:30Z from the `debug-foreman-loop` session, against
the live `livespec-foreman` pane (repo `/data/projects/livespec`, tmux session
`livespec-foreman`, pane `%137`, claude pid 2339455, transcript
`~/.claude/projects/-data-projects-livespec/2af4f15f-bc51-49d3-a854-ebce98446307.jsonl`).

**Revised 2026-08-22.** The original note stated the shape-1/shape-2 design
question and deliberately stopped there. That question is now SETTLED — see "The
design question, SETTLED" below — and three things measured while settling it are
folded in: what the muting picker actually asked, a second and stronger mute path
on the `converged` exit, and the spec tier of the unimplementable escape. The
2026-08-21 measurements below are unchanged.

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

## What the muting picker actually asked, and why that is load-bearing

Added 2026-08-22, read out of the incident transcript itself. Everything above
records the picker's TIMING. Its CONTENT changes how the incident should be read,
and it is the single most likely thing for an implementer to get wrong.

The blocking question raised at `07:53:19Z` was neither a routine escalation nor
the converged resume question. It asked whether to delete the registration of a
GitHub self-hosted runner, because that runner's private key had leaked into a
session transcript and was still active. Three labelled options, the first
recommended.

It was answered at `13:56:55Z` — **six hours and three minutes later** — with the
free-text string `don't care, ignore it`, which is none of the three options
offered. The daemon's picker-stall nudge landed at `13:55:51Z`, sixty-four
seconds earlier. That nudge pastes without submitting. **So the human was reached
by the daemon's attention surface, not by the picker**, which had sat untouched
for six hours.

Three consequences:

1. **This is a direct positive control for shape 1's channel.** The attention
   surface is not merely an adequate substitute for the picker — in this incident
   it is the thing that actually reached a human, while the picker contributed
   nothing except the mute.
2. **Blocking bought a worse decision, not a better one.** A live leaked
   credential was dismissed in one free-text line by someone who had just been
   nudged to unstick a pane. A non-blocking escalation persists on the NEEDS YOU
   surface until it is genuinely dispositioned; a picker can be cleared by a
   pane-unsticking reflex, and here it was.
3. **Do NOT carve out a security exception.** The standing orders on
   `overseer-z5fo4y` say the only remaining escalation is a security concern a
   panel cannot resolve, so an implementer could reasonably preserve the blocking
   escape for that class. The measurement says otherwise: the one picker ever
   measured muting this loop IS a security escalation, it froze supervision of
   every other track for roughly fifteen hours, and it still failed to obtain a
   considered answer. A security carve-out would be defeated by the very incident
   that motivates the fix. What "escalation is still permitted" means is that the
   DECISION stays the human's — not that the LOOP must stop while it waits.

Recorded as a lead and not a claim: the runner named in that picker is absent
from the `livespec` and `livespec-overseer` runner listings as of 2026-08-22, so
it appears to have been removed or expired since. Whether the key was ever
deliberately revoked is not established here and is not this thread's scope.

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

## A second mute path: the `converged` exit, and it is stronger

Measured 2026-08-22 in `overseer/foreman_runtime.py`. Everything above concerns a
SUPPRESSED cron — the schedule survives, its fires are simply dropped. There is a
second path that is worse, because it tears the schedule down on purpose and then
blocks.

On `exit_reason: converged`, the Loop Carrier section of
`.claude-plugin/prose/foreman.md` instructs the tick to **cancel the armed cron
schedule** and then raise a resume `AskUserQuestion`. If that question is never
answered there is no schedule left at all, and no clock to bound the wait.

The sibling exit reason was already repaired for exactly this shape. In
`ForemanRuntime.step()`, `auto_resume_interval_seconds` is computed under a guard
admitting only `exit_reason == "hard-tick-budget"` and is `None` otherwise, and
the prose records that a resume picker on that path measured 13 hours with no
foreman on 2026-08-19/20. **`converged` never got that repair.**

**How often it fires is not measured — and cannot be from the record, which is
itself the sharper finding.** `converged_ticks` defaults to `2`, so two
consecutive stable ticks over a non-empty monitored set are enough, and a quiet
fleet plausibly reaches that. Plausibility is all that is available, though,
because the runtime journals **only** the hard-tick-budget auto-resume — that is
the single `append_journal` call site in `foreman_runtime.py`, reached under the
same guard. **A `converged` exit writes no journal record at all.**

Measured 2026-08-22 across every repo's dispatch journal on this host: four
`foreman-auto-resume` records exist, spread over four repos, and **no journal
stage anywhere records a converged exit.** (An earlier revision of this note
asserted a quiet fleet "reaches it routinely". That was inferred from the
constant, not measured, and it is retracted here — the structural point below is
both stronger and actually supportable.)

So the converged path cancels the schedule, raises a blocking question, and
leaves no trace that it happened. That is a better reason to fix it than any
frequency estimate would be, and it bears directly on acceptance criterion 2:
a detector for "a tick that ends with a blocking prompt outstanding" has nothing
to key on for this path today.

Two live foreman rows were checked against this and are **not** converged
instances: at `00:45Z` on 2026-08-22 the `livespec-console-beads-fabro` and
`homelab` foremen were heartbeat-stale by 375 and 4079 minutes respectively, and
both carried `stable_ticks: 0` in `tmp/overseer/foreman/runtime.json` — so
neither had converged, and both belong to the died-loop case owned by
`overseer-6tfncs.5`. The console row's `llm_tick_interval_seconds: 7200.0` is a
doubled interval, the hard-tick-budget auto-resume signature, which is a useful
reminder that auto-resume alone did not keep that loop alive.

A criterion-2 detector for "a tick that ends with a blocking prompt outstanding"
will necessarily flag this path, so it is in scope rather than a surprise.
Cancelling the schedule on `converged` remains correct — it is a deliberate stop.
What must change is that the decision to resume travels on the attention surface,
where a human can see it.

## The design question, SETTLED 2026-08-22

Recorded here and, durably, on `overseer-lixhd3.1`, which acceptance criterion 7
requires before implementation lands. **Shape 1: the foreman never ends a tick
with a blocking prompt outstanding.**

Shape 2 — an out-of-process ticker — is rejected, and **not on cost grounds. It is
inoperative against this defect.** The reasoning, which this note previously left
open:

- Any ticker, wherever it runs, must still make the picker-parked session execute
  a turn. The only channel into a tmux pane is keystrokes; while a picker is open
  the picker widget consumes them; and the only key that ends the turn is the one
  that **answers** the picker. That is the deferral ruled out on principle, and
  the daemon already encodes the ruling in code — its picker-stall nudge pastes
  without submitting, deliberately. So shape 2 could un-mute this loop only by
  doing the one thing the hard constraint forbids.
- What shape 2 would genuinely fix is a loop that died while its session stayed
  idle and responsive. That is already owned by `overseer-6tfncs.5` (its
  acceptance criterion 8). Adopting shape 2 here would duplicate that scope and
  still leave this defect open.
- Shape 2 also contradicts the loop's own scoping argument. The Loop Carrier
  section already argues, in refusing the generic loop skill's cloud-schedule
  question, that the loop is scoped to one tmux pane, one repo checkout, and that
  session's runtime lock. An out-of-process ticker is that same incoherence under
  another name: it would have to re-acquire the runtime lock and pane claim from
  outside the pane holding them.

Shape 1's channel meanwhile **already ships**:
`overseer/_supervisor_foreman_escalation.py` reads a per-topic escalation file
under `tmp/overseer/foreman/escalations/` and raises the `foreman-escalated`
condition through the same alert, NEEDS YOU, and window-badge machinery every
other attention member uses. Nothing new is needed to CARRY a foreman decision to
a human. What is missing is only that nothing enforces the foreman uses it
instead of a picker, and that the spec sentence below still licenses the picker.

### The route for the unimplementable escape is `propose-change`

The escape is **spec-tier, not prose-tier**. `SPECIFICATION/spec.md` carries the
sentence permitting a blocking question as a last resort for a bounded wait with
a defined timeout; it arrived in v017 from `overseer-dz2skw` and is unchanged
through **v029**. The `.claude-plugin/prose/foreman.md` sentence is its
restatement, and the two must not be left disagreeing.

So the route is `propose-change`, authoring a file under
`SPECIFICATION/proposed_changes/` — never a direct edit of `spec.md`, whose
accept-or-reject is the maintainer's own `revise` pass. Authoring the proposal
file is itself an ordinary repository change and is dispatch-safe.

**Grep for that sentence; do not navigate to a line number.** An earlier record of
this finding cited it as `spec.md:172-174`; the v029 ratification moved it to
line 234 within a day while the sentence itself did not change. A line number is
a measurement, and it ages faster than the claim it points at.

## The hard constraint

**Inherited verbatim from `overseer-dz2skw` and non-negotiable:** this must leave
the cardinal rule in `overseer/marker-protocol.md` completely untouched. It
changes only how a human decision is surfaced and how the operator loop keeps its
cadence, never who may authorize a restart. No implementation may add a timer- or
heuristic-driven restart path of any kind, and nothing here authorizes the daemon
to answer a picker on a human's behalf.

## Read first

- `.claude-plugin/prose/foreman.md` — "Loop Carrier", "Arming the loop is not
  optional, and is not a question", and the non-blocking-escalation paragraph.
- `overseer/_supervisor_nudge.py` and `overseer/_supervisor_prompts_nudges.py` —
  the paste-without-submit picker-stall nudge.
- `overseer/_supervisor_foreman.py` — the heartbeat staleness surface.
- `overseer/_supervisor_foreman_escalation.py` — the shipped non-blocking
  escalation channel this thread's decision builds on.
- `overseer/foreman_runtime.py` — `_exit_reason` and the auto-resume guard, for
  the `converged` path above.
- `SPECIFICATION/spec.md` — the foreman non-blocking-escalation paragraph. Grep
  for it; the line number moves.
- Ledger: this thread's epic `overseer-lixhd3` and its implementation child
  `overseer-lixhd3.1`, whose comments carry the settled decision and the
  security-escalation finding. Then `overseer-dz2skw`, `overseer-au3pt3.1`,
  `overseer-ra6s`, `overseer-6tfncs.5`, `overseer-w2nwx5`, `overseer-enc7oe`,
  and `overseer-z5fo4y` for the standing orders.
