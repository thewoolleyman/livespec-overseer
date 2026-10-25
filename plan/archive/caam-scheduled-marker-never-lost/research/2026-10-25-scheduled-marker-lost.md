## The maintainer's statement of what done means

A scheduled pass of caam-anthropic-loop always carries the scheduled marker, so the projected-drain trigger and the expiring-weekly drain are live, and a pass that lost the marker is visible instead of silently weaker.

## Definition of Done assertions derived from that statement

- A scheduled pass on an active account that is projected to reach the short-window floor within the projection horizon rotates off that account before it reaches the floor.
- Running the caam-anthropic-loop executable with no mode flag performs a rotate-now pass as the specification's Mode resolution requires, and its output says it ran unscheduled.
- The caam-anthropic-loop prose tells a scheduled invocation to pass the scheduled marker to the executable.

# caam-anthropic-loop runs without the scheduled marker, silently

Recorded 2026-10-25 from a live incident. Everything below was measured in the
session that was running the loop, not inferred.

## What happened

- 2026-10-24 02:13Z: the active account (anthropic-1) read 5h 17% and burned
  roughly 26-32 points/hour. The pass HELD, because 17% is above the 15% trigger.
  The next read was 03:21Z; the account had run down in between, and the factory
  fleet was held.
- 2026-10-25 ~02:05Z: the active account (anthropic-3) was exhausted ("You've hit
  your session limit"), five factory launch pre-screens failed, and the fleet was
  held from 02:14Z to 02:21Z. The maintainer switched the account by hand.

## Root cause found

Every pass in the session was run as `python3 overseer/caam_anthropic_loop.py`
with NO flags. In the code, the projected short-window drain is computed only
when the pass is scheduled (`caam_decide_rotation.py`:
`fast_drain_projection(...) if request.scheduled else None`), and `scheduled` is
True only when `--scheduled` is passed (`caam_anthropic_loop.py`, flag parse).
So the early-rotation trigger, the expiring-weekly drain and the lapse claims
were all OFF, and only the plain 15% trigger was live. At 25-40 points/hour with
a 30-minute gap between passes, a plain 15% trigger cannot beat the drain.

Two defects made that possible:

1. The prose, `.claude-plugin/prose/caam-anthropic-loop.md` ("Invocation Mode"),
   says an invocation carrying `--scheduled` runs the program "without extra
   flags". The code needs the marker passed to the executable, so a literal
   reading disables every scheduled-only behaviour.
2. The executable's bare mode (no `--scheduled`, no `--force`) is a third state
   the specification does not define: it applies the plain triggers and says
   nothing. `caam_anthropic_flags.scheduled_pass` documents absence as "the
   explicitly unscheduled form".

## What the specification says

`SPECIFICATION/contracts.md`, "Mode resolution": an invocation carrying the
scheduled marker MUST respect the rotation triggers; an invocation WITHOUT it
MUST be treated as an explicit request to rotate now and MUST bypass the
triggers (still refusing a move that loses headroom, an exhausted destination,
or a destination that fails the capacity test). "Marking the scheduled side
rather than the manual side is deliberate: a lost marker MUST degrade to
forcing a rotation, which is observable, rather than to never forcing one,
which is silent."

The projected-drain trigger, the expiring-weekly drain and the reset claims each
state that they MUST NOT fire on an invocation without the scheduled marker,
"which already rotates under Mode resolution".

So making the bare executable default to scheduled would CONTRADICT Mode
resolution (it would make a lost marker silent), and would be a spec-change-tier
change. The conforming fix is the opposite: an unmarked executable run is a
rotate-now pass.

## Scope of this plan

- Code: an executable invocation with no mode flag resolves per Mode resolution
  (rotate now, bypass triggers, keep the headroom / exhausted / capacity-test
  refusals) and prints a visible line saying the pass ran unscheduled.
- Prose: the scheduled invocation explicitly passes `--scheduled` to the
  executable.

## Explicit deferrals

- No change to `SPECIFICATION/`. The user asked first for "default to scheduled";
  that option is NOT taken because it contradicts Mode resolution. If it is ever
  wanted, it is a `propose-change` item, not part of this plan.
- Not in scope: the cron-scheduler's behaviour across a DST fall-back (the
  2026-10-25 01:00Z gap in cron fires is consistent with wall-clock next-run
  times, but is unproven and is not an overseer component), and the structural
  fact that the loop's session runs on the account being rotated. Both are
  recorded here so they are not lost; neither is carried by a child of this plan.
