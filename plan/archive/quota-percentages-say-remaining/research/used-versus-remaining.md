# Quota percentages: say "remaining" everywhere, in labels AND in keys

Maintainer ruling, 2026-09-04, verbatim: "The correct fix for that is to make the
label and keys say '... remaining' EVERYWHERE, the printed table headings, as well
as the keys in any config tables or internal variables."

## The defect

The rendered account table and the stored values disagree about direction, and
nothing names which is which.

- `overseer/caam_rendering.py:222` renders `f"{100 - row.usage.fable:.0f}%"` --
  the printed FABLE / 5H / WEEK columns are percent **REMAINING**.
- `UsageRecord.fable`, `.five_hour`, `.seven_day` store percent **USED**. Every
  decision predicate reads them that way: `can_serve_scoped_model` is
  `usage.fable < _FULLY_SPENT (100.0)`, `fable_left` is
  `active_fable < _FABLE_EXHAUSTED (100.0)`, `weekly_left` is
  `100.0 - usage.seven_day - protection_floor`.

So a table row reading `FABLE 100%` means the allowance is FULLY AVAILABLE, while
the field behind it reads `0`. Same number, opposite meaning, no label saying so.

## Why it is worth a thread rather than a comment

Measured on 2026-09-04 while answering "why did this session switch to Opus": an
agent reading the live table concluded "Fable exhausted fleet-wide" from
`FABLE 100%` and was one step from reporting the opposite of the truth. It caught
itself only by reading the renderer. The failure is directional -- every misread
lands on "exhausted" when the truth is "available" -- so it produces confident
wrong diagnoses in exactly the situation the table exists to diagnose: a session
that changed model. That is the same class of error as the CI-congestion and
daemon-staleness misreads earlier that day, and the same remedy applies: make the
instrument state its own units.

## The scope the ruling asks for

Labels AND keys, everywhere:

1. Printed table headings in `caam_rendering` (FABLE / 5H / WEEK -> "... REMAINING").
2. Internal variable and field names carrying these percentages.
3. Keys in any config tables, state files, or JSON that carry them.

## The design question this thread must settle first

A rename alone can make things WORSE. Two options, and they are not equivalent:

- **(a) Rename to match what each thing already holds.** `usage.fable` becomes
  `fable_used`; the rendered column stays `100 - fable_used` and is labelled
  REMAINING. Cheap, no behaviour change, no comparison flips -- but the ruling
  asks for "remaining" everywhere, and this leaves `used` in the field names.
- **(b) Store remaining, so the name is true end to end.** `usage.fable_remaining`
  holds `100 - used`; the renderer prints it directly; and EVERY predicate flips:
  `can_serve_scoped_model` becomes `fable_remaining > 0`, `fable_left` becomes
  `> 0`, `weekly_left` becomes `fable_remaining - protection_floor`, the
  `_FULLY_SPENT` / `_FABLE_EXHAUSTED` sentinels become `0.0`, and the
  `five_hour < _FULLY_SPENT` / threshold comparisons in `candidate_allowed`,
  `scoped_waiver_ceiling` and `triggered` all invert.

(b) is what "say remaining everywhere" literally means, and it is a correctness-
sensitive refactor across the whole selection path -- the same predicates that
decide rotation, eligibility, protection floors and (as of v045) fleet-wide
scoped servability. It must be done with the beside-tests pinning behaviour
BEFORE the flip, or a single missed inversion silently reverses a rotation rule.

Note the upstream boundary: these percentages arrive from the usage API via
`caam_usage`. Whichever option is chosen, the conversion must happen at exactly
one place, named, so the two directions never coexist unlabelled again.

## Tiering

- Whether the ratified spec names these quantities in a direction-bearing way
  (it speaks of an allowance being "spent or absent", and of "weekly remaining")
  needs checking; if any clause must change, that half is spec-tier and routes
  through /livespec:propose-change.
- The rename/inversion itself is an ordinary stdlib-only change in `overseer/`
  with beside-tests, mirrored under `.claude-plugin/overseer/`.

## Carried in from the archived respect-operator-model-pins plan

Two non-blocking items recorded in that plan's closing handoff and deliberately
not filed as children there (an open child would have blocked its archive gate).
They belong to this thread:

- `_respect_operator_set` in `caam_enforcement_orchestrated.py` still documents
  `scoped_servable` as "the pass's reading of the ACTIVE account's scoped
  balance"; since v045 the caller passes the FLEET-WIDE reading, with the
  active-account read only as fallback. Behaviour correct, prose stale.
- The spec's stale contrast phrase at the per-session clause ("keyed on
  servability, not on the global scoped-allowance-exhausted condition"), and
  the "MUST report that the pin cannot currently be satisfied" wording where an
  observed session, not a literal pin, arms the trigger.
