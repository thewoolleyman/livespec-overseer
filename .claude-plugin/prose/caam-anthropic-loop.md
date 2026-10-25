---
name: caam-anthropic-loop
description: Watch caam-managed Claude Max account usage and rotate safely.
---

# caam-anthropic-loop - Claude Max account rotation

You are running the account-rotation operation for this host. The operation
watches caam-managed Claude accounts, reports their quota table, and rotates the
active Claude credential only when the rebuilt account-rotation program decides
that doing so preserves or improves usable headroom.

This contract owns the operator-facing behavior. The harness bindings expose the
operation to Claude Code, Codex, and pi; they must only resolve the plugin root,
read this file completely, and execute it. Do not move schedule, mode, or
reporting rules into a binding.

## Schedule Self-Installation

At the start of every invocation, inspect the runtime's recurring jobs before
doing anything else.

1. Call `CronList` first.
2. If a recurring job already exists whose prompt starts with
   `/caam-anthropic-loop` and whose prompt contains `--scheduled`, keep it. Note
   its job id and continue the pass.
3. If a recurring job already exists whose prompt starts with
   `/caam-anthropic-loop` but lacks `--scheduled`, delete that job with
   `CronDelete`, then create the replacement below.
4. If no current scheduled-marker job remains, call `CronCreate` with this exact
   schedule:

       cron: "7,37 * * * *"
       prompt: "/caam-anthropic-loop --scheduled"
       recurring: true

5. After creating the job, tell the operator the job id, that it fires every 30
   minutes, and these two limits: the job lives only while this Claude session is
   open, and recurring jobs auto-expire after 7 days. Tell the operator to cancel
   early with `CronDelete <id>`.

Never wrap this operation in `/loop`. It schedules itself, and wrapping it creates
overlapping jobs. The `7,37` minute marks are deliberate: they avoid the `:00` and
`:30` fleet schedule marks. The marker belongs on the scheduled side, not the
manual side, so a lost marker degrades to an observable forced pass rather than a
silent never-force pass.

The recurring `7,37` job is a BACKSTOP, not the only refresh trigger. Because an
idle account's access token is refreshed the instant it expires and the delegated
agent will not renew a still-valid one, waiting up to a full 30-minute tick past
an expiry leaves the account dark for that whole window. So each pass also prints
a `next-warm-wake:` line naming the soonest idle-account expiry; schedule a
per-expiry one-off wake from it as described under Reporting. Keep the recurring
job regardless, so a missed one-off wake still degrades to a bounded delay.

If this runtime has no Cron tools, report that the recurring self-installation
could not be performed in this harness, then continue the current pass. Do not
invent an alternate scheduler.

## Cutover Recovery Notes

The legacy `vps-info` watcher used the same session-only schedule shape. Its
last known job id before the livespec-overseer cutover was `9117bfe3`, firing at
`7,37 * * * *` with prompt `/caam-anthropic-loop --scheduled`. That job lived
only in the Claude session that owned the `caam-anthropic-loop-legacy` pane. It
left no host cron entry, no user systemd timer, and no system systemd timer; a
recurring job of that kind also auto-expires after seven days even if the pane
stays open.

If the legacy watcher must be restored before the cutover completes, open a
Claude session in the `vps-info` checkout and invoke `/caam-anthropic-loop`
there. The legacy project skill self-installs by listing recurring jobs and
creating the same `7,37 * * * *` schedule with prompt
`/caam-anthropic-loop --scheduled`. Confirm the new job id, leave that pane open,
and cancel any replacement livespec-overseer schedule so exactly one
implementation is scheduled. The first unmarked invocation is a manual forced
pass; after an outage, that is expected because it immediately re-evaluates the
active account. Do not wrap the recovery invocation in `/loop`, and do not keep a
second watcher pane alive, because recurring jobs are per-session.

Host schedule evidence was measured by the plan owner on 2026-08-23T06:5xZ and
recorded on work-item `overseer-54k2za.31`: the user crontab had only two
unrelated entries, no `/etc/cron*` file mentioned `caam`, the two user timers
were unrelated, and no system unit name mentioned `caam` or account rotation.
When re-checking that evidence, search for `caam` or the operation name, not for
`rotate`; `sysstat-rotate.timer` and `logrotate.timer` are log rotation and are
not account rotation.

During the cutover, a `session-gone` row for topic `caam-anthropic-loop` may
describe this repository's plan thread rather than the legacy watcher. The
daemon resolves a topic by tmux name plus repository cwd; a pane named for this
operation whose cwd is the `vps-info` checkout does not satisfy the
livespec-overseer plan-thread identity. Do not repair that row by restarting the
legacy watcher seat into this repository. The legacy slash command is a project
skill under `vps-info`, so moving the seat here can silence the row while
breaking the running watcher.

A resumed session whose model reads as `unknown` is also expected in this
operation. The model is read from the transcript, not the tmux status line, and a
resumed session writes to a differently named transcript. Treat `unknown` as
may-need-setting, bounded by the one-hour per-session memo, rather than as a
fault to chase. The cutover record observed this with `homelab-foreman`: it read
as unknown while genuinely running Fable.

## Invocation Mode

Resolve the mode from the invocation text after the schedule check.

- Invoked with `--scheduled`: run the rebuilt account-rotation program with
  `--scheduled`, so normal rotation triggers apply. Pass the marker to the
  program itself; it is not implied by how this operation was invoked. The
  projected short-window drain and the expiring-weekly drain run only when the
  program is passed `--scheduled`. A program run without it is a rotate-now pass
  and prints an `unscheduled:` line saying so.
- Invoked without `--scheduled`: run it with `--force`. A manual run is an
  explicit request to move now, but force still refuses an account with less
  headroom than the current account and still refuses any account with zero
  weekly quota.
- Forward only these operator flags when present: `--force`, `--dry-run`,
  `--no-models`, `--session-model=<session>=<fable|opus|auto>`,
  `--protected-account=<account>[=<percent>]`, and `--no-warm`.
  The operation does not derive any session's model from its name: it enforces
  only an operator-set per-session model, plus the servability reset that moves a
  session off a scoped model no selectable account can serve.
  `--session-model=<session>=fable` and `--session-model=<session>=opus` pin one
  named session above the Fable-balance rule and persist in the operation state
  across later scheduled ticks;
  `--session-model=<session>=auto` clears that session's exception.
  Session exceptions persist even when passed with `--no-models`, are
  reported in the table line as `exceptions:`, and are absolute: a session pinned
  to spent Fable is left there with a warning rather than silently moved.
  `--protected-account=<account>=<percent>` marks one account as protected and
  keeps a weekly floor beneath it; a bare `--protected-account=<account>` takes
  the configurable default floor, and `=auto`, `=none` or `=off` clears that
  account's protection. The flag is repeatable, so several accounts may be
  protected at different floors. Protection persists in the operation state
  across later scheduled ticks and is reported on the summary line as
  `protected-accounts:`. A protected account is never selected while any
  unprotected account is eligible, and its floor is not released by the
  fleet-wide weekly reserve's release. Idle-profile keep-warm maintenance is ON
  BY DESIGN so idle accounts stay selectable: it refreshes an idle snapshot the
  instant that snapshot's token expires, and never before, because the delegated
  agent renews only an already-expired credential and a pre-expiry attempt merely
  burns an inference request. `--no-warm` explicitly disables keep-warm for this
  pass; the retired `--warm` / `CAAM_ROTATE_WARM=1` opt-in no longer governs it.

Do not add retry, recovery, alternate thresholds, or a manual fallback. The
program owns the account decision.

## Rotation Threshold Configuration

The short-window rotation knob is `CAAM_ROTATE_FIVE_HOUR_REMAINING`, default `15`.
It names percent REMAINING, like every quota figure this operation stores, prints
and compares: a pass rotates once the active account's 5-hour window has that
percent or less LEFT.

MIGRATION FOR OPERATORS. It replaces `CAAM_ROTATE_FIVE_HOUR_THRESHOLD`, which named
percent SPENT, and there is no backward-compatible alias -- an environment still
exporting the retired name is ignored outright and the default applies, silently.
Transform a customised value by subtracting it from 100: the old default `85`
spent becomes `15` remaining, and `CAAM_ROTATE_FIVE_HOUR_THRESHOLD=90` becomes
`CAAM_ROTATE_FIVE_HOUR_REMAINING=10`. `CAAM_ROTATE_WEEKLY_RESERVE` (default `10`)
already named a remaining balance and is unchanged.

The scoped-model (Fable) rotation knob is `CAAM_ROTATE_FABLE_REMAINING`, default
`15`, also percent REMAINING. While a Fable-dependent session is active -- one
pinned to Fable or simply observed running it -- a pass rotates once the active
account's Fable has that percent or less LEFT, moving the session onto an account
that still holds Fable ABOVE the reserve BEFORE the active account's Fable is fully
drained, rather than only at exhaustion. It never fires when no session depends on
Fable, so it strands no weekly balance for accounts that have no Fable sessions, and
it never selects a protected account below its floor. `CAAM_ROTATE_FABLE_REMAINING=0`
restores the earlier behaviour exactly: rotate only when the active account's Fable
is fully spent.

### Usage-Limit Refusals

A refusal for a usage limit is ground truth about an account's allowance; a usage
percentage is a report about it. On 2026-10-13 an account read 45 percent of its
five-hour window remaining nine minutes before it refused every session on the
host, and the loop held every pass. So every pass also reads the refusal records
that tracked sessions' transcripts already carry -- it sends no request of its own
-- and a refusal attributed to the active account rotates the fleet off it
whatever the usage figures report.

This trigger has no configuration of its own. It governs wherever it fires:
candidates are compared on the window the refusal NAMES and the departing
account's headroom on that window is taken as zero, so the eligibility margin,
the weekly reserve, every per-account protection floor, the zero-weekly and
cannot-serve disqualifiers and live verification all apply beneath it unchanged.

Its trigger line names `usage-limit refusal`, the account, the window it refused
on and the instant the refusal was recorded. Its switch line names the same
refusal and instant beside the destination's weekly percent remaining and time to
weekly reset. Read that instant against the table printed above the decision:
those figures will disagree with the move, and the time the refusal was recorded
is what reconciles them. Where no candidate survives the other rules the pass
holds and says both things -- that the active account is refusing requests, and
that no account could be selected.

An account a refusal holds is never selected, whatever its readings report, until
that refusal lapses: when the reset the provider reported passes, or -- where it
reported none -- when a later reading of the named window shows it fully
replenished or shows a reset more than a minute later than the one that window
carried when the refusal was attributed. That hold is what keeps the trigger from
oscillating, since the lagging reading on an account that has refused is exactly
the one that would otherwise attract a return to it.

A lapse is final. The transcript the refusal was read from still carries the
record, so the loop also remembers, per account and window, the latest instant at
which a refusal on that window lapsed, and attributes no refusal recorded at or
before it. Without that memory a hold would end for one pass and re-arm on the
next -- and a refusal that reported no reset would re-arm against the very
reading that ended it, so the pass would go on reporting that the account is
refusing requests long after its window had rolled. A refusal recorded AFTER that
instant is a fresh refusal of the window and holds the account on its own terms.

Refusals are only ever attributed to the account that was actually spending. A
session's own agent configuration directory decides whether it authenticates with
the host-wide live credential, so the refresh-maintenance sandbox and any
separately provisioned credential contribute nothing; a refusal recorded before
the operation observed this account become active belongs to whatever was active
then; and a refusal whose reported reset matches, within a minute, the same
window's reset last read on an account just departed belongs to that account,
because concurrent sessions keep spending a departed credential for a while after
a switch.

### Projected Short-Window Drain

A percentage threshold cannot protect an account that falls faster than the gap
between two passes. Measured 2026-10-13 on host hp: an account on the $20 plan
fell about 70 short-window points per 30-minute pass where it had fallen about
10 on the $200 plan, and on 2026-10-15 the Anthropic session limit ended five
factory runs under an account the loop rotated off 20 minutes too late. A pass
that reads 32 percent remaining and holds because 32 is above 15 has not
measured anything about where 32 is going.

So a scheduled pass also projects. It measures the active account's short-window
BURN RATE across two readings and rotates when the projected remaining -- the
current reading less the rate multiplied by the projection horizon -- is at or
below `CAAM_ROTATE_FIVE_HOUR_REMAINING`, even while every reading is still above
it. An account whose projection stays above the floor across the horizon holds.

`CAAM_ROTATE_PROJECTION_HORIZON_S` sets the horizon, default `1800` -- the
documented 30-minute interval of this operation's own schedule, because the
question the trigger asks is whether the account survives until the next pass.
It is the only knob this trigger adds, and the operation never shortens or
otherwise changes its schedule in response to a burn rate: the horizon is what
the projection measures ACROSS, not a request for more passes.

The rate is UNKNOWN, and this trigger cannot fire, whenever the two readings
cannot be compared: less than half a horizon apart, reporting short-window
resets more than a minute apart (two different windows, so the fall between them
is a replenishment), or straddling a switch, where the account became active
after its own baseline was taken. The baseline reading is kept until a reading at
least half a horizon after it, so closely spaced passes measure across the older
baseline rather than amplifying one percentage step into a large rate. The
trigger never fires on an invocation without the scheduled marker, which has no
interval to project across.

Its trigger line names `projected short-window drain` with the current
percentage, the fall per horizon and the projected remaining at the end of it.
Its switch line names the same projection -- the burn rate and the projected
remaining -- beside the destination's short-window figures. Read both against the
table printed above: those figures are above the floor, which is the whole point,
and the projection is what reconciles them with the move.

### Carrying The Current Load

An account the fleet drains within one horizon is not a destination, it is the
next pass's problem. So every selection this operation makes -- under every
trigger, the expiring-quota drain included, and on an invocation without the
scheduled marker -- also projects each CANDIDATE forward and excludes anyone the
projection leaves at or below `CAAM_ROTATE_FIVE_HOUR_REMAINING`.

The FLEET LOAD is the active account's burn rate multiplied by its own capacity
weight, recorded with the instant it was measured. A candidate's share of it is
that load divided by the candidate's weight. Where the rate is unknown the last
recorded load is used for as long as it is no older than twice the horizon, so
the test still applies on the pass after a switch; where no load is available at
all the test excludes nobody, because failing closed would strand the fleet on an
exhausted account on exactly the pass that knows least about demand.

The weights are per provider and capacity class:
`CAAM_ROTATE_CAPACITY_WEIGHT_ANTHROPIC_SMALL`, `..._MEDIUM` and `..._LARGE`,
defaulting to `1`, `2` and `7`. The large default is the measured ratio rather
than the nominal plan multiplier -- about seven to one against a nominal twenty
-- which is why every one of them is a knob: a ratio measured once, on two
accounts, on one day, is evidence rather than a constant. A candidate whose class
is `unknown` is weighted as the smallest class configured for its provider, which
is the strict direction. An active account whose own class is unknown has no
weight to measure a load with, so such a pass records none and the candidate
under test contributes its own weight instead.

Nothing here changes RANKING, which stays soonest weekly reset first with no
capacity term in it. The test is an eligibility rule that happens to read a
weight: it only ever removes candidates from the ranked set, and it never
reorders what survives.

Where a trigger other than the drain has fired and the test excludes every
candidate that survived the other rules, the pass HOLDS and reports that no
candidate can carry the current load until the next pass. Report that line as
printed: the table beside it shows every one of those candidates healthy and
above its floor, so nothing else in the output explains either the hold or the
move that did not happen. Where the DRAIN finds no candidate for this reason the
pass simply holds as for any absent drain candidate, with no line of its own.

The one case the test stands aside for is a REFUSING active account. An account
that is refusing serves nothing at all, while an account the load drains before
the next pass still serves until then -- so where a refusal holds the active
account and nothing passes the test, the test is RELEASED and the pass selects
among the failing candidates by the unchanged ranking. It is released, not
relaxed: the release is conditioned on the refusal rather than on the emptiness,
and every other rule still applies beneath it. A refusal-held pass also records
no fleet load, because an account serving a fraction of what the fleet asks of it
falls more slowly than the demand, and that figure would stand in for up to twice
the horizon.

### Expiring Weekly Quota Drain

A scheduled pass that has no forced or threshold-triggered rotation drains quota
whose weekly window expires sooner. The active account must have a readable weekly
reset, and a destination is eligible only when its stored credential was exercised
successfully on this pass, it has weekly allowance remaining, and its readable
weekly reset is at least one minute sooner than the active account's. The destination
must also clear `CAAM_ROTATE_WEEKLY_RESERVE`, its own protection floor, and the
observed `CAAM_ROTATE_FIVE_HOUR_REMAINING` balance by at least
`CAAM_ROTATE_MIN_HEADROOM_GAIN`, and must pass the capacity test above, exactly as
under any other trigger. This comparison uses the observed short-window
balance; it does not project a future five-hour balance. While a Fable pin applies,
the destination must clear `CAAM_ROTATE_FABLE_REMAINING` by that same margin.

An unprotected active account never drains onto a protected destination. From a
protected active account, unprotected destinations rank before protected ones; each
group ranks by soonest weekly reset, without plan-capacity weighting. A successful
move caused by a short-window trigger records the reset reported for the account it
left, even when another trigger fired too. Scheduled drains cannot return to that
account until the recorded reset passes. If no reset was reported, its observed
short-window balance must reach 100 percent before it can receive a drain.

This is the lowest-precedence rotation path: a usage-limit refusal, any force or
ordinary quota trigger, and the projected short-window drain each govern instead,
and an invocation without the scheduled marker does not drain. Its
trigger and successful switch lines name `expiring weekly quota`; the switch line
also reports the destination's weekly percent remaining and time to weekly reset.
The drain adds no configuration knobs.

## Running The Program

Run the shipped account-rotation program from the resolved plugin root for this
installation. Bindings provide `$PLUGIN_ROOT`; in Claude Code the equivalent
root is `${CLAUDE_PLUGIN_ROOT}`.

Use the mode rules above to choose the flags. Preserve the program's stdout and
exit code. If the program is not exposed by the installed plugin version, report
that as a failure of this operation surface and stop rather than reconstructing
the implementation inside the binding.

## Published Account Selection

Every pass that fully determines the active account -- both the account
manager's profile name and that account's own stable identifier -- publishes
that identity as a small record beside the operation's own state. It exists for
a CREDENTIAL CONSUMER: a party outside this host's interactive agent that bills
against the same accounts under its own separately-provisioned credential, which
this operation neither stores, installs, nor refreshes. Such a consumer cannot
follow a rotation unless the operation states which account it selected.

The record carries IDENTITY ONLY, never credential material, and the program
owns its location and shape. Do not hand-write it, hand-repair it, delete it, or
quote it back to the program as evidence of which account is active. It is an
OUTPUT of a pass, never an input to one: its presence, absence, age or contents
change nothing about eligibility, ranking, or the decision to hold.

A pass publishes on a hold exactly as on a switch, because the record must name
the account active when the pass ends, and an account activated by hand outside
this operation must be followed rather than reported as a rotation of its own.
Three conditions suppress the write instead, and in every one the previously
published record is left standing because a stale but complete record is safer
than a fabricated or half-resolved one:

- The pass could not take the lock that serializes the decision-and-switch
  sequence. Another caller holds it and is deciding the very fact the record
  states, so that caller owns the write. The pass reports a hold and exits zero.
- The pass could not determine the active account at all. It reports that
  failure as usual.
- The pass determined the account but could not resolve its stable identifier.
  It prints a `note:` line saying so, above the table, and CONTINUES: this is a
  reported condition, not a failure, and on its own it never makes a pass exit
  non-zero. Report the note alongside the table and the decision.

If publication itself fails, the program prints a `FAIL` line naming it and
exits non-zero. Report that failure per the `FAIL` rule under Reporting -- and
report the table and the decision too, because a completed switch STANDS. Never
re-run the pass to try to undo a rotation whose only failure was publishing it,
and never `caam activate` back by hand.

## Capacity Class

Every account row of the table carries a `CAPACITY` cell: one of `small`,
`medium`, `large` or `unknown`, with the provider's own plan name in parentheses
as detail, as in `large (default_claude_max_20x)`. Two accounts at the same
percentage can hold very different absolute headroom, so the class is what says
how much an account can actually carry, and the plan name is what says which
plan produced that class.

The class is read LIVE on every pass, with the same credential that account's
usage was polled with -- the host's live credential for the active account, each
other account's own stored snapshot for the rest. It is never derived from the
plan fields a credential recorded at login. Those are written once, at login,
and an account downgraded afterwards goes on reporting its old plan there
indefinitely, which is exactly what happened on 2026-10-13: a snapshot still
read `max` / `default_claude_max_20x` for an account already on the $20 plan.

`unknown` means this pass could not say. A failed or unparseable read, a plan
name the operation has no mapping for, and a locally-expired token that was
skipped rather than sent all read `unknown`. None of them is a failure: an
unknown class never makes a pass exit non-zero and never changes the rotation.
Report the cell exactly as printed, and never substitute a class from an earlier
pass, from the vault, or from what you know the plan to be.

## Reporting

Show the account table verbatim on EVERY pass -- scheduled, held, dry-run,
forced or switched, and whether or not anything changed since the previous pass.
It is the point of the turn, not a detail to summarize, and an unchanged held pass
is NOT an exception: paste the program's full table output, never a one-line
digest such as "Held on <account> (5h=.., weekly=.., Fable=..)". After the table,
add the decision line from the program and quote its percentages rather than
paraphrasing them.

If the program prints a line beginning with `FAIL`, say plainly that the pass
failed and stop. Do not retry with a lower threshold. Do not attempt `caam
activate` by hand. Do not use a cached or dark account as a destination.

If the program prints any line beginning with `ALERT:`, relay every one of them
VERBATIM and say plainly that a managed account is spending pay-as-you-go
dollars or has reached its monthly spend cap. Do not fold them into the table
summary and do not omit them from an otherwise unremarkable held pass -- they
are the whole point of that pass. An `ALERT:` is not a failure and does not stop
the pass: rotation already treats a spend-capped account as unable to serve and
routes around it, so report the alert alongside the decision and continue. The
alert fires on the first dollar spent, well before the cap, so an early one is
the signal working rather than an emergency.

If the program prints a `next-warm-wake: <timestamp>` line and Cron tools are
available, schedule a one-off wake for it: delete any prior one-off wake you
created for this operation, then `CronCreate` with `recurring: false`, a `cron`
expression for that timestamp's minute, and prompt `/caam-anthropic-loop
--scheduled`. This refreshes the soonest-expiring idle account within seconds of
its token expiring rather than at the next 30-minute mark. If no `next-warm-wake:`
line is printed, no idle account has a pending expiry to wake for; rely on the
recurring backstop.

For a successful scheduled, held, dry-run, forced, or switched pass, report the
table and the decision exactly as printed -- both, every time, per Reporting's
first rule above -- and then stop. "Report the decision" never licenses dropping
the table: a held or unchanged pass shows the same full table as a switching one.
To stop watching entirely, delete the recurring job id with `CronDelete`.

"And then stop" bounds the report's CONTENT, not just the pass. The report holds
only what THIS pass's program run printed (the table, the decision, and its
`FAIL`, `ALERT:`, `note:`, `warm:` and `next-warm-wake:` lines) plus the schedule
action taken this turn. Append nothing else: no status of another system (a plan
thread, a herdr pane, a file on disk, a ledger item), no standing reminder, and
no sentence carried forward from an earlier report or a context summary. A
reminder copied from tick to tick has no source in the pass that prints it, so
nothing ever refreshes it and it goes stale silently while reading as current --
measured 2026-10-13, when three consecutive reports told the operator a plan
thread was waiting on a question it had long since left. If something outside
the program's output genuinely matters this turn, measure it with a command in
this same turn and say what you ran; if you did not measure it this turn, leave
it out.
