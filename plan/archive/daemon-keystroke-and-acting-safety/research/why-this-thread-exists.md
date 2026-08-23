> **ARCHIVED 2026-08-23. THE TEXT BELOW IS THE OPENING NOTE, UNALTERED, AND ITS
> PRESENT TENSE IS NOW HISTORY.** All three carriers are CLOSED and merged to
> master: `overseer-cuxv` (A2, PR 1874), `overseer-0ll0` (A1, PR 1923),
> `overseer-9w40` (A3, PR 1927). The table below calls them `ready`; that was
> true when written and is not true now.
>
> The ordering argument was ANSWERED rather than left open: the receiving
> session agreed with A2-first and dispatched in that order. Merge order on
> master ended up A1, A2, A3, because A1's landing was delayed by a rescue —
> nothing rests on it, since all three are predicate-independent.
>
> The inherited dead-pointer maintenance this note demands was discharged on all
> three rows and confirmed present in an exported dispatch brief.
>
> Full thread state, gate evidence and the completeness review live on the
> ledger anchor `overseer-nk3anw`, which is this plan's only durable record.

# What the daemon does to a pane, as distinct from what it publishes

Opening research note for `plan/daemon-keystroke-and-acting-safety`, written by the
`livespec-overseer-grooming` drain pass on 2026-08-23T08:4xZ.

## Why this is a separate thread from the reporting half

These three items and `overseer-hwxe` are the four slices of one regroom of `overseer-ulyv`. The
regroom drew the line, and slice R states it in its own text: it "changes what the daemon PUBLISHES,
not what it does to panes". This thread is the other side of that line.

The line is worth keeping. A reporting defect misleads a reader, who can re-check. An acting defect
sends real keystrokes into a real agent's pane, and there is no re-check: the input has landed. The
two halves have different blast radii, different acceptance bars, and different urgency, and folding
them into one thread would let the cheaper half set the pace for the more dangerous one.

## The population

| item | status | the unsafe act |
|---|---|---|
| `overseer-0ll0` | ready | A1 -- the keystroke budget is per-belief and never resets per episode, so an unsubmitted resume can be retried without an episode bound |
| `overseer-cuxv` | ready | A2 -- no identity gate, so a resume keystroke can land in a DIFFERENT session after a pane is restarted |
| `overseer-9w40` | ready | A3 -- an Enter keystroke is sent into a pane whose session is PROGRESSING, which is unwanted input into a live working agent |

All three are `ready`, all three declare autonomy tier factory, and all three carry a READ FIRST
pointer to `plan/archive/supervision-safety-and-attention-truth/research/ulyv-record-composition.md`
rather than restating the evidence. That pointer is now under `plan/archive/`; the path in the item
text predates the archive. **Re-resolve it before dispatching any of the three** -- a dispatch brief
that cites a path that no longer resolves hands the implementing agent a dead reference, and this is
the one piece of maintenance the archive of the predecessor thread imposed on these rows.

## Ordering, which is a real constraint here and not a preference

A2 is the identity gate. A1 is the budget. A3 is the progressing-pane suppression. A1 and A3 both
decide whether to send; A2 decides where a send is allowed to land. A budget that bounds the number of
keystrokes does nothing about a keystroke landing in the wrong pane, and suppression on a progressing
pane does not help a pane that was restarted into a different occupant.

So A2 is the one whose absence is unbounded in consequence, and the natural first action. That is a
reading of the three rows, not a ruling from the regroom -- the regroom numbered them A1, A2, A3
without stating a required order, so if the receiving session disagrees it should say why on the
thread rather than treat this note as authority.

## What is deliberately NOT here

Slice R (`overseer-hwxe`) and the rest of the reporting family, which live in
`plan/daemon-row-truth-and-attention-coverage`. Anything about the foreman's actuator, which is
`overseer-tdfe`. The cardinal ready-file restart rule in `overseer/marker-protocol.md` is untouched by
all three and must stay untouched.

## Read first

- `plan/archive/supervision-safety-and-attention-truth/research/ulyv-record-composition.md`
- `overseer/marker-protocol.md` -- the restart interlock these keystrokes operate near.
- `overseer/AGENTS.md` -- load-bearing tmux mechanics.
