---
topic: account-table-quota-resets-column
author: herdr-overseer
created_at: 2026-11-13T20:23:24Z
---

## Proposal: The account table summarises each account's resets in one QUOTA RESETS column, and its columns align

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Replace the v057 requirement that the account table show every reset's cleared windows, uses and lapse with one compact QUOTA RESETS column, placed immediately to the left of EXTRA. It reads `<uses>, next expires in <d>d <h>h`: the reset uses the account holds, and the time until the soonest of those resets lapses. Also require every cell of the table to align under its header on every kind of row.

### Motivation

Maintainer direction, 2026-11-13, given to the herdr-overseer plan for the reset-handling track: "I want a new column (to the left of extra) named QUOTA RESETS, that lists number of resets available, and the days until the next one expires. E.g. '3, next expires in xd yh'", and "The column layout is bad, the alignment is broken starting at the \"EXTRA\" column". The current text (spec.md §"Account rotation and quota supervision", the reset-display paragraph) instead requires per-reset detail (windows cleared, uses remaining, time to lapse) for every reset, which the maintainer's one-column summary replaces. The misalignment is measured: a readable row prints its FABLE LEFT cell 9 characters wide (overseer/caam_rendering.py:300, `{fable:>9}`) under a header printed 10 wide (:109, `{'FABLE LEFT':>10}`), so the shift starts AT FABLE LEFT: that cell and every column after it, EXTRA included, sit one character left of their headers and of the unreadable and stale rows (master 2026-11-13). The EXTRA column is where the maintainer saw it.

Two interpretation choices, recorded with their reasons: (1) "number of resets available" is the number of reset USES the account holds, summed over its resets, because a single reset can carry several uses, every use is separately claimable, and the uses are what the operator can still spend; (2) the hours in `<d>d <h>h` are whole hours rounded DOWN, so the cell never promises more time than remains before a reset lapses.

### Proposed Changes

In SPECIFICATION/spec.md §"Account rotation and quota supervision", replace the paragraph that begins "The operator-facing account table MUST show each account's resets in provider-agnostic terms beside its windows" with:

> The operator-facing account table MUST show each account's resets in one column headed QUOTA RESETS, placed immediately to the left of the EXTRA column. For an account whose resets were read, the cell MUST state the number of reset uses the account holds, the uses remaining summed over all its resets, and, where at least one reset with a use remaining reports when it lapses, MUST follow that number with `, next expires in <d>d <h>h`, the whole days and remaining whole hours until the soonest such reset lapses; for example `3, next expires in 5d 4h`. An account holding no reset uses MUST show `0`. An account whose resets could not be read MUST show `unreadable`, and MUST NOT be shown as holding none. Reset observation MUST NOT influence selection or ranking except through the reset-claim clauses below, and a failure to read resets MUST NOT disturb the quota report or the rotation.
>
> Every cell of the account table MUST be aligned under its column's header on every kind of row, whether readable, unreadable, stale, without a short-window limit, or with the unrecognised-limits column shown: a right-aligned column's cells MUST end where its header ends, and a left-aligned column's cells MUST start where its header starts, measured in the width the cell occupies on a terminal (a wide character such as the CURRENT column's ✅ occupies two). So that this can always be met, each column's width MUST be the larger of its header's width and the widest cell that column holds in that rendering: no cell is truncated, and a cell wider than its header widens its whole column rather than overflowing into the next one.

In SPECIFICATION/scenarios.md, replace the body of "## Scenario: The account table shows each account's resets" with:

> Given an account holds two resets with one use remaining each, one lapsing in five days and four hours and the other in eight days
>
> When a pass renders the account table
>
> Then that account's QUOTA RESETS cell, immediately to the left of its EXTRA cell, reads `2, next expires in 5d 4h`

and add after it:

> ## Scenario: The account table's columns align on every kind of row
>
> Given the account table renders the active account, whose CURRENT cell holds the two-column-wide ✅, a readable inactive account, an account whose current reading has no short-window limit, an account with no usage reading, and an account whose reading is stale
>
> And one account reports an unrecognised limit, so the OTHER LIMITS column is shown
>
> And one cell is wider than its column's header
>
> When a pass renders the account table
>
> Then in every row, each cell of each column ends where that column's right-aligned header ends, or starts where its left-aligned header starts

This conflicts with "## Scenario: The capacity cell shows the plan display name without wrapping", which asserts that no row wraps for seven accounts in a 120-column terminal: the table's header is already about 150 columns wide on master and becomes about 178 with this column, so no 120-column rendering can hold an unwrapped row. That scenario's test is still a TODO (owned by overseer-zmkkef), which is why the clash is not visible yet. Amend that scenario's body to:

> Given the provider reports the display name `Ultra` and the tier `default_claude_max_20x` for an account
>
> When the operation renders the account table for seven accounts in a terminal at least as wide as the table's header
>
> Then the account's capacity cell shows the class with `Ultra` as detail
>
> And the class is still `large`
>
> And no row wraps

The unreadable scenario ("A reset reading declined for the requesting client is unreadable, not empty") stands unchanged: the cell reads `unreadable`. The ratified change owes one implementation follow-up, a factory child of plan caam-quota-resets (overseer-pv53ri) that follows overseer-zelcaq, which is building the v057 per-reset display.
