# File-level disjointness is not independence

Third research note for `plan/foreman-table`. Written 2026-08-22, immediately
after two children of this plan merged green and were then found to disagree
with each other. The disagreement is worth recording; the reason they were
allowed to run concurrently is worth recording more.

## What happened

Two children landed within minutes of each other, both green, both satisfying
their own acceptance in full:

- `overseer-2jblyq.3` (PR 1535) — the PROSE contract: six columns, word
  budgets, the emoji legend.
- `overseer-2jblyq.5` (PR 1539) — the HELPER: emits session and work state as
  separate fields and computes the emoji from the pair.

Each was verified against its own acceptance and each passed. Compared against
*each other*, the emoji mappings do not agree:

| session + work | helper emits | legend says |
|---|---|---|
| working, either | 🟢 | 🟢 |
| idle or absent, runs in flight | **🟡** | **⏳** |
| idle or gone, no runs | **🔴** | **⚪** |
| picker-parked, either | 🔴 | 🔴 |

## Why it was allowed to happen — the transferable part

`overseer-2jblyq.2` had already been serialized behind `.5`, correctly, because
both edit `overseer/foreman_plan_roster.py`. That is a **file** overlap and it
was easy to see.

`.3` and `.5` have **zero** file overlap. One writes
`.claude-plugin/prose/foreman.md`; the other writes Python and tests. On a
path-collision check they are perfectly independent, and that is the check that
was run.

They share a **contract** — the emoji mapping — and each implemented it from the
same research note independently. Two agents, one specification, two readings,
no merge conflict to catch it, because there was nothing to conflict.

**FILE-LEVEL DISJOINTNESS IS NOT INDEPENDENCE. Two items that SPECIFY and
IMPLEMENT the same contract must be serialized even when they touch no common
path.** The question to ask before dispatching siblings concurrently is not
"do these edit the same files" but "could these two disagree with each other and
still both be green".

The failure is silent by construction. A file collision announces itself as a
rebase conflict or a non-fast-forward push. A contract divergence produces two
passing test suites and a system that contradicts itself, and it is discoverable
only by a comparison nobody's acceptance criteria asked for.

## What the divergence actually costs, which is more than tidiness

**🔴 became overloaded.** The helper maps picker-parked AND idle-with-no-work
AND no-session-with-no-work all to 🔴. The prose deliberately separates them:
🔴 blocked means a human is being asked something; ⚪ stalled means nothing is
happening at all. Those demand **different actions** — answer the question,
versus find out why nobody is on it.

That is the SAME failure this whole plan was opened to fix, one level up. The
original incident was a single row contradicting itself. This is the legend
meaning less than it claims, everywhere, for every row. The plan's own remedy
reproduced the plan's own bug in a different register.

**❗ is never emitted at all** — zero occurrences in the helper. It computes
`name_identity_verdict` correctly and then never feeds it into the emoji, so a
plan whose names disagree, which is exactly what column 1 exists to surface,
renders as unremarkable.

## A fourth defect, and it is this thread's own hazard again

`emoji_for_pair` ends in

    return PAIR_EMOJI.get((session_state, work_state), "🔴")

The default means **every** input returns a symbol. So
`test_pair_emoji_mapping_is_total`, which enumerates the known session and work
states and asserts each resolves, **passes no matter what the table contains** —
including for a pair nobody mapped. It cannot fail.

That is the unfalsifiable-check shape, appearing inside the very item whose
acceptance demanded proof by exhaustive enumeration rather than spot checks.
This plan has now produced it **three** times: the name-identity check that
matched 12 of 12 with no negative control, an acceptance clause requiring prose
to handle a floor category that does not exist, and this. Each was written by
someone who had just finished warning about the previous one.

**The pattern is specific enough to name.** Every instance takes the form of a
check whose passing condition is guaranteed by its own construction rather than
by the property it claims to test. Writing "assert this is total" over a
defaulted lookup, "assert both directions differ" where only one direction is
reachable, "assert the handling exists" for an empty category. The defence is
not vigilance — vigilance failed three times here. It is to require, in the
acceptance itself, **an input that must produce the failing result**, and to run
it before the fix.

The fallback is also wrong in direction: an unmapped pair renders as 🔴 blocked,
the most alarming state on the board, when the prose says an unrepresentable row
is ❗ incoherent. A defaulted lookup does not merely fail to detect the gap; it
disguises the gap as a specific, confident, wrong answer.

## Disposition

Filed as `overseer-2jblyq.6`, P0, with acceptance requiring each leg to fail
before the fix — including passing a deliberately unmapped pair, which is what
makes the totality claim falsifiable at all. `overseer-2jblyq.2` is serialized
behind it.

Neither `.3` nor `.5` is being reverted. Both are correct against their own
scope; what was missing was an item that owns the relationship BETWEEN them.
