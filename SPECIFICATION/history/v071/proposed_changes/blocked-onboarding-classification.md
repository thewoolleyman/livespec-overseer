---
topic: blocked-onboarding-classification
author: claude-opus-5-5
created_at: 2026-10-26T04:07:20Z
---

## Proposal: Classify and safely resolve Claude Code first-run onboarding screens

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Adds a governed rule that the daemon classifies a tracked pane on the Claude Code theme picker, security-notes screen or workspace-trust prompt as `blocked-onboarding`, logs it, and on the acting path resolves it (Dark mode, submit, and accept trust only for the track's own repository, never a bare Enter on the trust prompt's exit option), as the one bounded exception to the never-keystroke-a-structured-gate rule. Adds three scenarios.

### Motivation

Measured 2026-10-25T20:30Z to 2026-10-26T03:25Z on Claude Code v2.1.310: restarted seats (w2H:p4, w2J:pB, w2H:p2V, w5:p5 and the coordinator's own) came up on first-run onboarding because the caam account switch restored an un-onboarded ~/.claude.json (root cause filed as overseer-hc7j). The daemon log held zero lines about these screens, so the seats stalled silently, and the trust prompt's default `No, exit` kills a seat on a bare Enter. The maintainer directed, through coordinator gitops-fleet-capacity-monitoring, that the daemon resolve them with Dark mode and the defaults, accepting trust safely. Work item overseer-q156 failed its Codex-first screen because no spec heading governs onboarding classification; this proposal supplies that heading.

### Proposed Changes

Add a new H2 section to `SPECIFICATION/spec.md`, placed immediately after `## Supervised runtimes` and before `## Non-interference with tracked work`, reading exactly:

```markdown
## First-run onboarding screens

A tracked Claude Code session can come up on a first-run onboarding screen
instead of its input prompt: the THEME PICKER, the SECURITY-NOTES screen
("Press Enter to continue"), or the WORKSPACE-TRUST prompt, whose default
selection is its exit option. These screens are harness setup, not a human
decision about the tracked work, and a session parked on one makes no progress
and declares nothing.

The daemon MUST classify a tracked pane showing any of these screens as
`blocked-onboarding`, a status distinct from session-gone, idle, busy, and
blocked on a human. Classification MUST rest on an exact match of the screen's
pane text; unrecognized, partial, or conflicting text MUST NOT be classified
`blocked-onboarding` and suppresses action as ambiguous evidence does. On the
first observation of each onboarding episode the daemon MUST log one event
naming the pane, the screen, and, for the workspace-trust prompt, the prompted
folder.

These three screens are the ONE bounded exception to the rule that a fresh
session showing a structured gate is never keystroked. On the acting path only,
the daemon MAY resolve them:

- the theme picker, by selecting Dark mode and submitting it;
- the security-notes screen, by submitting it;
- the workspace-trust prompt, by moving the selection to its accept option and
  submitting it, ONLY when the prompted folder equals the track's recorded
  repository path.

Before every keystroke the daemon MUST re-read the pane and confirm that the
same screen is still shown, and it MUST log each keystroke it sends. The daemon
MUST NOT send a bare Enter while the workspace-trust prompt's selection is on its
exit option. When the trust prompt names a folder other than the track's
recorded repository, or a screen cannot be matched exactly, the daemon MUST send
nothing and MUST surface the track as an attention row naming the pane and the
screen. The read-only list path MUST report `blocked-onboarding` without sending
any keystroke. A pane that is not a tracked session MUST NOT be keystroked by
this rule.
```

Add three scenarios to `SPECIFICATION/scenarios.md`, appended at the end of the file, reading exactly:

```markdown
## Scenario: A tracked session on a first-run onboarding screen is resolved to its input prompt

Given a tracked Claude Code pane whose recorded repository is `/data/projects/example`

And the pane shows the theme picker

When the daemon evaluates the track on the acting path

Then the daemon reports the track as `blocked-onboarding` and logs one event naming the pane and the theme picker

And the daemon selects Dark mode and submits it only after re-reading the pane and confirming the theme picker is still shown

And when the pane next shows the security-notes screen the daemon submits it after the same re-read

And when the pane next shows the workspace-trust prompt for `/data/projects/example` the daemon moves the selection to the accept option and submits it, never sending a bare Enter while the selection is on the exit option

And the daemon logs every keystroke it sent

## Scenario: A workspace-trust prompt for a folder other than the track's repository is never accepted

Given a tracked Claude Code pane whose recorded repository is `/data/projects/example`

And the pane shows the workspace-trust prompt for `/data/projects/other`

When the daemon evaluates the track on the acting path

Then the daemon sends no keystroke to the pane

And the daemon reports the track as `blocked-onboarding` on an attention row naming the pane, the workspace-trust prompt, and `/data/projects/other`

## Scenario: The read-only list path reports an onboarding screen without keystroking it

Given a tracked Claude Code pane showing the security-notes screen

When the read-only list path reports the track

Then the track is reported as `blocked-onboarding`

And no keystroke is sent to the pane
```

At revise time, `tests/heading-coverage.json` MUST gain one entry per new heading (the H2 above and the three scenarios), each with `test: "TODO"`, `work_item: "overseer-q156"`, and a reason naming the owed integration-tier test, co-edited atomically with the spec files.
