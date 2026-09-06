# What the daemon publishes about a tracked session is not true

Opening research note for `plan/daemon-row-truth-and-attention-coverage`, written by the
`livespec-overseer-grooming` drain pass on 2026-08-23T08:4xZ. It records why this thread exists and
what its population is; it does not design any of the fixes.

## Why this thread exists

Eleven open, measured, unparented work items describe one subject: the daemon's published row about a
tracked session says something that is not true of that session, or fails to say something that is.
Every one of them was filed by a live seat from a live observation. None of them had a plan home.

They were homeless for a structural reason rather than a careless one. Their natural home,
`plan/supervision-safety-and-attention-truth` (ledger anchor `overseer-6tfncs`), **archived on
2026-08-23** with every one of its parent-child children disposed. The archive was correct. What the
archive did not do -- because no gate asks it to -- is find the rows that had been filed against the
thread's SUBJECT without ever becoming its children. Those rows outlived the thread and inherited no
successor.

So this is not a re-opening of that thread and must not be described as one. `overseer-6tfncs` stays
archived and stays disposed. This is a new thread over the residue its archive left behind, plus
later findings in the same family filed after it closed.

## The population, as measured

Composed from the merged `list-work-items --json` projection at 2026-08-23T08:2xZ: 892 rows total,
173 non-done, 41 unparented, of which 27 were neither plan anchors nor seat anchors. Eleven of those
27 are this thread's subject.

| item | status | what the row says is untrue |
|---|---|---|
| `overseer-hwxe` | ready | publishes `blocked:human` for an ANSWERED picker, and a contradictory stall pair |
| `overseer-j2vbcq` | pending-approval | `picker_open` and `human_wait` both read false while a human decision is genuinely pending |
| `overseer-i6eu2k` | pending-approval | `picker_open` true for a session that merely QUOTES picker markers in prose about a peer |
| `overseer-5p6d6g` | pending-approval | `session-gone` for a topic whose tmux name is squatted by a live session in another repo |
| `overseer-zljboi` | pending-approval | the parked-delivery SENDER is extracted and rendered, then elided out of the snapshot at 48 chars |
| `overseer-62mgxr` | pending-approval | an open picker makes context headroom unreadable: 7 of 7 stalled rows report no ctx, 13 of 13 others do |
| `overseer-gx95` | ready | voiding a stale blocked declaration ERASES the operator's stated reason |
| `overseer-nwtw` | ready | one live foreman session is published as TWO rows with contradictory attention states |
| `overseer-2h6u` | ready | no condition fires when the rendered table is not reaching a pane: headless reads as dead |
| `overseer-c7nq` | ready | open question whether the bounce re-key branch is still reachable after PR 1722 |
| `overseer-qq2f` | ready | a pane capture attributes inbound peer messages to the pane's occupant, so provenance is misread |

Four of the eleven were slices of one regroom (`overseer-ulyv`); this thread holds only slice R, the
REPORTING half. The three ACTING slices went to `plan/daemon-keystroke-and-acting-safety`, because the
regroom itself drew that line and it is the right one: what the daemon PUBLISHES and what it DOES to
a pane fail differently and are fixed differently.

## The shape the eleven share, and why it is worth one thread

Each row is a separate defect and none blocks another. What makes them one subject is the failure
mode they produce in an operator, and it is the same failure mode every time: **the row is not merely
wrong, it is wrong in a direction that routes a reader to a destructive or wasteful remedy.**

`overseer-5p6d6g` states this most sharply -- its own filing seat drew the wrong conclusion from the
row, acted on it, and had to retract the accusation to the session it had wrongly accused. The
ambiguous reading pointed at a destructive remedy. `overseer-i6eu2k` makes a healthy pane unreachable
under the foreman's own no-SendMessage-to-a-picker rule, so the untruth removes the operator's ability
to check it. `overseer-62mgxr` blinds the daemon to headroom on exactly the sessions most at risk of
being lost.

That is the argument for treating them together: the individual fixes are independent, but the
acceptance bar they share is not "the field is now correct", it is "a reader of this row is not routed
to the wrong act". A fix that corrects a field while leaving the ambiguity is not a fix.

## What is deliberately NOT here

The acting half (`plan/daemon-keystroke-and-acting-safety`). The foreman's own actuator, gather and
roster surfaces (`overseer-tdfe`). Seat identity and registry derivation (`overseer-ow7c`). The repo's
enforcement machinery (`overseer-4z97`). Observability and log/OTel emission (`overseer-temi26`).

## Read first

- `plan/archive/supervision-safety-and-attention-truth/` -- the archived predecessor thread; its
  research directory carries the evidence records several of these rows point at, including
  `research/ulyv-record-composition.md` and `research/prose-question-detector-inversion.md`.
- `overseer/marker-protocol.md` -- the wrap-up and state-declaration protocol.
- `overseer/AGENTS.md` -- architecture invariants. Enumerate modules from the tree, not from its lists.
