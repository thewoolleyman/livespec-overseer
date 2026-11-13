---
topic: a-codex-replacement-or-relaunch
author: claude-opus-5-5:herdr-overseer
created_at: 2026-11-13T11:59:16Z
---

## Proposal: Launch Codex with its startup update check disabled

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Every Codex launch the daemon or the sanctioned relaunch composes disables Codex's startup update check, so a launched successor never opens at Codex's update picker; the override is part of the launch command, never of the recorded launch profile.

### Motivation

overseer-dd5qus: in the isolated Codex herdr live exercise on released v5.55.6 (2026-11-13, three runs plus an independent replay), the replacement stage failed every time. The fresh successor `codex -m gpt-6.1-sol --dangerously-bypass-approvals-and-sandbox` opened at Codex's own "Update available 0.167.1 -> 0.169.0" picker, and the daemon (correctly, under §"The restart") never keystrokes a structured gate, so it waited until the stage timed out. The same thing gates every Codex replacement on the fleet whenever upstream Codex is newer than the installed one. The dispatch-stage tier judge held the fix as spec-change, because the visible text does not say a Codex launch disables the update check.

### Proposed Changes

In spec.md, under "### The launch profile", immediately after the paragraph beginning "A track's mapping row that carries no launch profile MUST continue to relaunch", add this paragraph:

Every Codex launch command that the daemon or the sanctioned out-of-band relaunch composes MUST run Codex with its startup update check disabled, by passing the Codex configuration `check_for_update_on_startup=false` on that invocation. This covers a fresh successor, a resume, and a relaunch of a Codex row that carries no recorded launch profile. Codex caches a newer upstream release on one launch and opens the NEXT launch at an update picker. A launched successor waiting there shows a structured gate, which §"The restart" forbids keystroking, so the replacement or relaunch would wait forever. The override is a fixed part of the Codex launch command, not a launch-profile field. It MUST NOT be recorded in a captured launch profile, and re-capturing a profile from a running successor that carries it MUST NOT make the next launch carry it twice. For a Codex row that carries no launch profile, this is the one sanctioned difference from the rule above that such a row relaunches with exactly the command it uses today.

In scenarios.md, add:

## Scenario: A Codex successor launch disables Codex's startup update check

Given a tracked Codex session on herdr has declared `ready`
And the installed Codex has cached a newer upstream release, so a plain `codex` launch opens at its update picker
When the daemon launches the fresh Codex successor in the retained shell
Then the launch command carries `check_for_update_on_startup=false`
And the successor opens at its input composer, not at the update picker
And the daemon names and resumes the successor without sending a key to any picker
And the track's recorded launch profile does not record the override
