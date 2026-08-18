# Captured: the queued cross-session delivery pane signature

Work-item: `overseer-jcvi4q.2`. Captured 2026-08-19 from a live pane.

This note supplies the one signal the plan's opening research note recorded
as missing. It is written from a real capture, in this repo's house style
for `overseer/signals.py` shape documentation.

## Source of the capture

The capture is from the **original incident session itself**, still parked
at the time of capture: tmux session `delivery-path-speed-and-caching`
(repo `livespec-console-beads-fabro`). Its daemon row at capture time:

```text
topic  delivery-path-speed-and-caching
status picker-stalled      picker_open True    stall_seconds 2795
```

The queued delivery visible in the pane is the very message described in
`overseer-ra6s` — the `livespec-console-beads-fabro-foreman` relay reporting
that the fleet ClusterQueue resize had discharged the escalation leg behind
the picker's option 2, and closing with "this may also moot your picker's
option-2 rationale". It had been parked, unconsumed, for ~47 minutes.

A **negative control** was captured in the same pass: tmux session
`fabro-on-hp`, row `status blocked:human`, `picker_open True`, sitting on a
5-option picker with **no** queued delivery.

## The signature

The queued delivery renders BELOW the picker's footer line
(`Enter to select · ↑/↓ to navigate · Esc to cancel`) as a two-part block:

```text
  @ livespec-console-beads-fabro-foreman❯
    Console foreman, decision-relevant update for your open dispatch picker
    fleet-ci-runner-pool track has EXECUTED the ClusterQueue resize (2026-08
```

Byte-exact, via `cat -A` (`·` = space, the glyph is U+276F):

```text
··@·livespec-console-beads-fabro-foreman❯
····Console·foreman,·decision-relevant·update·for·your·open·dispatch·picker·
```

### Structural versus incidental

**Structural** — safe to key a detector on:

- A header line of the form: two leading spaces, `@`, one space, the sender
  name, then `❯` as the LAST character of the line. Nothing follows the
  glyph on that line.
- The `❯` sits at the END of the header line, after the sender name. This is
  the load-bearing difference from every other `❯` shape in the TUI.
- The body follows as one or more continuation lines indented FOUR spaces,
  i.e. two deeper than the header.
- The block sits below the picker footer, so the picker's own `❯ N.` cursor
  options appear ABOVE it in the same capture.

**Incidental** — must NOT be keyed on:

- The sender name. It is an arbitrary session topic; here it happens to end
  in `-foreman`, which is not general.
- The body text, its length, and its wrap width (the wrap follows pane width).
- The picker's option count and its footer wording.
- The row's `status` string. The positive read `picker-stalled` and the
  negative read `blocked:human`, and BOTH had `picker_open True`. A detector
  must therefore key on `picker_open`, never on a status literal — keying on
  `blocked:human` alone would have missed the actual incident session.

### Why the existing detectors cannot already do this

Measured directly against both captures by importing `overseer/signals.py`:

| | positive (delivery parked) | negative (picker only) |
|---|---|---|
| `is_structured_gate` | `True` | `True` |
| `input_box_text` | `None` | `None` |
| `is_busy` | `False` | `False` |

Every existing detector returns **identical** values for the two panes. The
daemon today cannot distinguish a picker with decision-relevant context
parked behind it from an ordinary picker. That is the defect, reproduced
mechanically rather than merely reported.

`input_box_text` returns `None` for the specific reason the opening research
note predicted: it requires a `❯` at the START of the line, sandwiched
between two border rules. Here the `❯` is at the END of the header line and
there are no border rules around the block. The two shapes do not overlap,
so a new detector is additive and cannot regress `input_box_text`.

## Guidance for the implementer

- Key on the header line alone; treat the indented body as confirmation, not
  as part of the match. The body is the most variable part.
- Anchor the match to end-of-line after `❯`. Without that anchor the pattern
  risks matching prose that merely contains an at-sign.
- The sender name is worth CAPTURING (the condition wants to name who is
  parked, and the spec text calls for alerting the sender where reachable),
  but must not be constrained by pattern.
- Require `picker_open` as the conjunct rather than any status string.
- The negative control above is the minimum negative test case: a picker with
  no queued delivery must not fire.

## Two limits of this capture, stated rather than glossed

**Multiple queued deliveries were not observed.** The plan asked for that
case. Only one delivery was parked on the only qualifying live pane, and
manufacturing a second by sending a real message to a session genuinely
parked on a maintainer's live decision would inject unreviewed input into
another track's pending choice — not a cost worth a test fixture. The
implementer should treat "one or more blocks" as the expected shape and
cover the multi-block case synthetically, flagging it as unverified.

**Codex has no observed analogue.** `is_structured_gate` spans both the
Claude `❯` and Codex `›` glyphs, but this queued-delivery block is a Claude
composer shape and no Codex pane in the live fleet showed anything like it.
The detector should therefore be documented as Claude-only until a Codex
capture proves otherwise, rather than silently assuming parity.
