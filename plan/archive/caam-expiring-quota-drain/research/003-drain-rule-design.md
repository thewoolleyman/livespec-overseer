# caam-expiring-quota-drain — the drain rule as settled with the maintainer (2026-10-13)

The first proposal (PR #2456) carried a 12h horizon, a 30% minimum weekly quota and a
10-minute near-reset projection. Those numbers were carried forward from the suggestions
in `001-root-cause-and-decision.md` without analysis. The maintainer questioned them, and
the rule below replaced them. The pending proposal was amended to match before revise.

## What the maintainer asked for

- Spend expiring quota as fully as possible, and give it time to be used up.
- No extra configuration that isn't needed.
- No flapping back and forth between accounts. Switching has a real cost: with Claude, a
  switch to another organization forfeits every live session's prompt cache, so each
  switch re-reads all context. Two switches per short-window cycle while a balance drains
  is acceptable; constant switching is not.
- Nothing hardcoded to Anthropic's five-hour window. The rule will apply to other
  providers, whose short windows may differ in length or replenish gradually.

## The rule

On a scheduled pass where no other trigger fired, rotate to a candidate whose weekly window
resets strictly sooner than the active account's, provided it passes every existing check
and is at least the existing eligibility margin (`CAAM_ROTATE_MIN_HEADROOM_GAIN`, default
10 points) clear of:

- the weekly reserve (weekly remaining ≥ reserve + margin; 20% at today's defaults), and
- the short-window rotation threshold (≥ 25% short-window remaining at today's defaults).

It adds no setting. It has the lowest precedence of any trigger, and ranking stays
soonest-weekly-reset with no plan-capacity weight.

## Why each alternative was rejected

- **Fixed horizon.** At the incident's burn of about 2.3 weekly points per hour, 79%
  needed about 34 hours, so a 12h horizon would have caught the account and still let
  most of it lapse. Spending a sooner-resetting balance first is never worse, because the
  later-resetting balance keeps.
- **Separate minimum-quota setting.** The weekly reserve plus the margin does the same job
  with existing settings. The maintainer chose the reserve as the floor; the margin on top
  stops the reserve trigger from undoing a drain one pass later.
- **A 10-point gap between the candidate's and the active account's balances** (discussed
  as an anti-flap gate). It blocks valuable drains: a 75% active account against an 80%
  candidate resetting in three hours would hold and let the 80% lapse. Two accounts can't
  swap back and forth under the drain anyway, because it only moves to a strictly sooner
  reset.
- **A no-return cooldown measured in hours.** It would hardcode a provider's window length.
- **Projecting a near-reset short window as replenished.** Projecting over the 30-minute
  schedule interval could move the fleet onto a nearly-spent window up to half an hour
  early and stall sessions on a rate limit; a shorter interval needs its own setting. The
  drain already covers that incident case: once the window resets, the next pass drains
  onto the account. The cost is at most one pass on the second-best account. The
  maintainer had agreed to a schedule-interval projection; this session dropped it on
  finding the rate-limit hazard and reports it as a deviation.

## What the independent ratification reviews added

Four review rounds (all opus, read-only, none involved in authoring) found blockers that
reshaped the rule without adding any setting:

- **Reset-time jitter.** The operation's own state file shows one nominal weekly reset
  read with sub-second jitter, sometimes on either side of a minute boundary
  (`23:59:59.874` vs `00:00:00.146`). "Sooner" now means **at least one minute sooner**,
  and readings under a minute apart are the same reset. A reverse move would then need the
  departed account to reset a minute sooner than the destination, which can't happen
  until a weekly window actually resets. A drain-memory condition tried in between was
  removed: it was stated inconsistently and could block a legitimate drain.
- **Gradually replenishing short windows.** A margin-clear test alone would let the loop
  return after every margin's worth of ageing-out — several times per window. Condition
  (f): after a short-window trigger moves off an account, the drain may not return until
  the short-window reset time the provider reported at that move has passed, or, if none
  was reported, until the window is fully replenished. That's at most one return per
  window for any provider shape. The operation remembers those moves in its durable store,
  and the contract's Durable store clause now allows one premature return if a concurrent
  overwrite loses that memory.
- **Protection ordering.** A drain never moves from an unprotected account onto a
  protected one; a protected active account prefers unprotected drain candidates; a
  protected destination needs the margin above its own floor.
- **Scoped pins.** Under a pin, a drain candidate needs the scoped allowance a margin
  above the scoped-model reserve, so the scoped trigger can't immediately undo it.
- **Existing sentences.** "The one exception" to the margin and "exactly the three ways"
  the scoped allowance influences selection were amended to include the drain.

## Why it can't flap

- **Strict reset order with a one-minute tolerance:** a drain can't move back until a
  weekly window resets, and jittered readings of one reset can't order two accounts.
- **Threshold buffers:** a drain can't land on an account the weekly reserve, its own
  protection floor, the short-window threshold or the scoped-model reserve would move it
  off at the next pass.
- **Short-window return wait (f):** after a short-window trigger moves the operation off
  a drained account, the drain can't return until that window has reset (reported reset
  time, or full replenishment). So it makes at most one return per short-window cycle,
  whatever that cycle's length or shape.
- **The loop ends** when the account falls under the weekly buffer or its reset passes.
