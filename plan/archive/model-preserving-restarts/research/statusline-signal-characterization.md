# The statusline as a model signal — what it can and cannot tell the daemon

Measured 2026-08-19 on this host, under the `model-preserving-restarts` plan
thread (ledger anchor `overseer-bc55wx`). This note exists because the thread's
original analysis,
[`launch-profile-and-local-models.md`](./launch-profile-and-local-models.md),
predates every measurement below and left the statusline's usefulness as an open
question. That question is now answered, and the answer shaped both the ratified
design and two subsequent defects.

Handoffs and status live on the ledger epic, not here. This note is research: the
measurements, and the reasoning they forced.

## Why the question mattered

The launch profile is read from argv and the process environment. Neither can see
a mid-session `/model` switch — a switch rewrites neither. So the profile a track
carries can silently become a lie about what the session is actually running, and
a restart then re-asserts the lie.

The ratified spec (`SPECIFICATION/spec.md`, "The launch profile") anticipated
this and named exactly one instrument for it: the statusline's rendered model
name, permitted **only** as a mismatch-detection verification signal — never as
the primary source, and never through a display-name-to-launch-token lookup
table.

Whether that instrument actually works was never measured. This note measures it.

## What the statusline is

It is not a lookup table the overseer maintains. It is produced by the operator's
own statusline command from the harness's `.model.display_name` field on the
status payload the harness pipes to it. That provenance is what makes it able to
express things argv cannot — and it is also why it is **user-configurable
presentation text**, which is the constraint that bars it from ever becoming a
source.

## Measurement 1 — it tracks a mid-session switch, promptly

Sampled every 0.25s from the keypress, in a disposable scratch session:

| transition | first sample showing the new model |
|---|---|
| Fable → Opus (1M context) | t+0.28s |
| Opus (1M context) → Fable | t+0.62s |

Re-measured on a session carrying conversation history, where switching first
raises a "this conversation is cached for the current model" confirmation
dialog: still t+0.28s after confirming.

There is no material lag. The signal is effectively immediate in both
directions.

## Measurement 2 — it expresses the variant that matters

The 1M-context variant renders as a string distinct from the plain model name —
`Opus 5 (1M context)` versus `Opus 5`. This is the discriminator the thread cared
about, and it is the one thing the per-session transcript candidate could not
express.

Across a live capture of all 37 tmux panes on this host the source distinguished
the fleet's real mix: `Opus 5 (1M context)`, `Opus 5`, and `Fable 5`.

## Measurement 3 — truncation, and the counter-intuitive part

**The statusline truncates from the end, and the usual parse anchor dies before
the value it guards.**

The rendered order is model, cwd, git branch, context segment, rate-limit
segment. The model name is *first* and always survives truncation. A parser that
locates the line by looking for the *context* segment is anchoring on one of the
first things truncation removes.

Swept against a live pane:

| cwd | widths where the model resolved | widths where it did not |
|---|---|---|
| short (`/tmp`), plain model | 120, 100, 80, 70, 60, 50, 40 | 30 |
| short (`/tmp`), 1M variant | 120, 80, 60, 50, 40 | 30 |
| long nested path | *none* | 120, 80, 60 |

**The availability threshold is not pane width.** It is the rendered length of
everything *before* the anchor — cwd plus git branch — relative to the width. A
wide pane in a deeply nested path loses the signal while a narrow pane in a short
path keeps it.

The practical consequence for this fleet is the part to carry forward: paths are
longest in **worktrees**, which is where nearly all real work happens here. A
statusline-derived check goes quiet exactly where it would most often be
consulted. Never design one whose silence means "nothing wrong".

## Measurement 4 — the parser accepted prose

Scanning all live panes with the then-shipped helper, one returned
`ActionStaging variant for navigation actions` — a line of ordinary transcript
conversation that merely mentioned context. The helper selected the last
non-blank line containing a context marker and took everything before the first
separator, so any sentence discussing context could impersonate a statusline.

Inert while the helper was verification-only. Wired into a restart veto it
becomes a *false mismatch*, and a false mismatch **suppresses a legitimate
restart**.

Note the inverted failure direction, because it is why this needed an unusual
test: the defect being closed fails toward *silent conversion*; a false mismatch
fails toward a *visible suppressed restart*. Since the measured defect was a
false **accept**, the guarding test must prove a **reject** — a conventional
parser test that only proves it accepts a well-formed statusline would pass
while the defect stood.

## What the design landed on, and why it is the only legal shape

The comparison is **rendered-to-rendered**: a baseline rendering is recorded
alongside the profile, and the current rendering is compared against that
baseline. Not rendered-to-launch-token.

This is not a shortcut. Rendered names and launch tokens are different
vocabularies; relating them *requires* the display-name-to-launch-token table the
spec forbids. Rendered-to-rendered is the only construction available that stays
inside the ratified clause.

## The limitation this creates, which is inherent rather than accidental

If a session's model was switched **before** the daemon adopted it, the baseline
records the switched model while the profile records the launch model. The two
then agree with themselves forever: no mismatch ever fires, and every restart
re-asserts the launch model. A silent conversion the veto cannot see.

It cannot be closed in the implementation without the barred lookup table. It is
currently unreachable — no tracked session on this host carries a capturable
model token at all — and it becomes reachable at exactly the moment tracks start
carrying one.

The spec-legal escape is to capture the baseline at **launch** time rather than
at adoption, for tracks the overseer itself starts: such a track has a known
model from birth and no pre-adoption window in which to diverge. That closes it
for overseer-launched tracks without touching spec text.

## Method notes, if this is ever re-measured

Every trial ran in **disposable scratch tmux sessions**, killed afterwards. No
live tracked pane was ever switched. Before any outbound switch, the `/model`
picker was read to confirm the return model was present as a distinct selectable
row, so the return trip could not strand a session on the wrong model.

Every switch used the **session-only** selection, never the default-setting
confirm — the latter rewrites the fleet-wide default in `settings.json` and would
change the model every future session starts under. Verified after teardown: the
fleet default was unchanged and no scratch session remained.

One trap worth repeating: a detached tmux session created with an explicit size
does not necessarily honour it. Confirm the actual pane width before trusting a
width-sensitive reading, and set it explicitly if it did not take.
