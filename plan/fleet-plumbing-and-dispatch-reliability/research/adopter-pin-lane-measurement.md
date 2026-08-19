# The adopter pin lane, measured end to end

Measured 2026-08-19T18:00Z, resuming this thread against its 16:45Z wind-down
entry. That entry's single next action is a wait on another tenant's foreman,
so this session spent its time discharging the two bounded unknowns it had
itself put on the record earlier the same day, rather than idling.

Both unknowns are now closed. One of them **refuted my own lead**, and the
refutation is the more useful half.

Nothing here turns a valve, changes a carrier's status, or edits anything
outside this note.

## Why this note exists

`overseer-mim` gap 1 says the release fan-out skips adopters. That is a claim
about a code path. What it never carried is the **cost**: what actually happens
to an adopter's pins because of it. This note measures that, and the
measurement turns out to have a control built into it.

## The measurement

Four plugins, the same two `pinned`-posture adopter repositories, the same day.
Pins read from each repo's `.claude/settings.json` on its own default branch;
latest releases read from the forge.

| plugin | latest | openbrain | resume | gap |
|---|---|---|---|---|
| `livespec` | v0.36.0 | v0.7.3 | v0.7.3 | ~29 minors |
| `livespec-driver-claude` | v0.5.8 | v0.2.1 | v0.2.1 | ~3 minors |
| `livespec-orchestrator-beads-fabro` | v0.59.2 | v0.13.9 | v0.13.9 | ~46 minors |
| `livespec-overseer` | v0.63.0 | **v0.63.0** | **v0.62.2** | **0 / 1 release** |

**The fourth row is the control.** Same repositories, same cron, same day. One
plugin is current and three are 3 to 46 minors behind. Whatever explains the
difference is not the adopter's own health, its posture, or its credentials —
those are held constant across all four rows.

## What explains it

**The adopters' pull lane is hard-coded to a single source repository.**
`bump-plugin-pin.yml` resolves its source as
`client_payload.source_repo || inputs.source_repo || 'livespec-overseer'`. A
scheduled run carries no payload and no input, so the daily cron resolves the
literal default **every time**. It is a one-source lane by construction.

Confirmed against history rather than read off the workflow alone: of the last
40 pin commits on each adopter's default branch, **80 of 80** bump
`livespec-overseer` and nothing else. Both adopters, identical shape, all
authored by `github-actions[bot]`.

So for the other three plugins there is **no lane at all**:

- no PUSH, because the reusable fan-out reads `.fleet // .members` and never
  `manifest.adopters` — that is `overseer-mim` gap 1, re-measured still open
  on dev-tooling master earlier today;
- no PULL, because the adopter cron's source is not them.

`livespec-overseer` is current only because it is the one repository that
carries its own `adopter-release-dispatch.yml` shim AND is the cron's
hard-coded default.

## The conclusion that should drive the fix, and it is the useful one

**The adopter side is already source-agnostic. The missing half is entirely
producer-side.** `bump-plugin-pin.yml` accepts an arbitrary `source_repo` from
its `client_payload`, and the rewrite step takes `--source-repo` as a
parameter. Nothing about the adopter needs to change.

So fixing gap 1 alone would repair all three stale pins, with **zero
adopter-side edits**. That is a much stronger argument for gap 1's priority
than "a code path reads the wrong array", and it is measured rather than
reasoned.

## Correction: my `overseer-ye5` prior-art lead is REFUTED

Earlier today I offered `livespec-dev-tooling-0j3i`'s ratified never-fired
escalation class as possible prior art for `overseer-ye5`, explicitly labelled
a LEAD and not a control because I had not read the escalation code. I have now
read it, and **the lead is wrong**.

`fleet/_adopter_lane.py` runs exactly one row over `manifest.adopters`, and
**posture gates the iteration itself**: a non-`released` adopter is never read.
Its own docstring calls exclusion "the honored behavior, not a tolerated skip",
and the excluded set is reported at info severity. `openbrain` and `resume` are
`pinned`, so they are never evaluated at all.

An escalation predicate cannot fire for a repository the iteration never
reaches. 0j3i's class is therefore **structurally incapable** of covering ye5's
scenario — not merely a poor fit.

**The correct prior art for `overseer-ye5` is `livespec-dev-tooling-z7wxbd`**,
whose item 1 reads: "Include adopters in the pin-freshness reporting surface so
a pinned adopter's pin age is VISIBLE (a periodic staleness signal — not a bump
PR, and not a red gate in the adopter's own CI)." That is precisely ye5's
remedy: it converts a silent drop into an observed one.

This is method rule 4 applied to my own finding and returning the answer I did
not want. The labelling is what made being wrong cheap — it was handed over as
a lead requiring judgement, so nothing was closed on it.

## `z7wxbd`'s headline measurement has partly gone stale, in both directions

It records openbrain at v0.6.10 and resume at v0.7.1 on 2026-07-20, and states
that adopter staleness is "completely unobserved" with no adopter pin ever
moved by a bot.

A month later both are at `livespec` v0.7.3 — so the pins did move slightly,
and they moved **by bot**. But the item's CONCLUSION is if anything
understated: against a v0.36.0 line, both adopters are now ~29 minors behind on
`livespec`, and ~46 behind on the orchestrator. The gap widened by roughly
eighteen minors while the item sat.

The part of its premise that needs correcting is the mechanism, not the
verdict: bot commits DO reach these repos daily. They just only ever carry one
source.

## The chokepoint, which affects how both carriers should be routed

`livespec-dev-tooling-9j8.6` gates **three** adopter/pin-lane items:
`qrunmn` (the gap 1 dedup candidate), `z7wxbd` (the ye5 prior art), and
`zm5cbp`. It is `backlog`, created 2026-06-30, **last updated 2026-07-03** —
untouched for about seven weeks.

Verified not-done rather than assumed from its status: both named extraction
targets are still inline shell on dev-tooling `origin/master`. The dispatch
matrix `jq` still reads `.fleet // .members`, and the pin-freshness evaluate
step is still an inline `run:` block.

**So deduping both of this thread's carriers onto dev-tooling records would
park both behind one stale extraction task.** That is not an argument against
deduping — the records are the right ones — but it is the thing to say out loud
when handing them over, because a dedup onto a blocked item reads as progress
and produces none.

## Scope of these claims

- **Measured directly here**: the four-plugin pin table; the 80-of-80 commit
  tally; the workflow's hard-coded source default and its `client_payload`
  parameterisation; `_adopter_lane.py`'s posture-gated iteration; 9j8.6's
  status, dates, blocked-set, and the two extraction targets still being inline.
- **Inherited, not re-measured this session**: that this repo's shim delivers
  eight adopter dispatches a day (read from the forge by an earlier session and
  recorded on `overseer-ye5`); and today's 10:30Z re-measurement that gap 1 is
  still open on dev-tooling master.
- **NOT established**: I did not measure whether the `livespec` App's dispatch
  boundary to adopters has changed. `bump-plugin-pin.yml`'s comment records
  `delivered: 0, unauthorized: 3` for the producer fan-out and says the App
  reaches no adopter; this repo's shim evidently does reach them. I did not
  determine what differs, and it matters for gap 1's fix — a producer-side fan-out
  that reads `manifest.adopters` still needs delivery access to act on it.
  **Whoever implements gap 1 must settle that first**, or the fix will read the
  right array and still deliver nothing.
