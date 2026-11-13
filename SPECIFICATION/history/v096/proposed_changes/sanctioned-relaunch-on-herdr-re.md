---
topic: sanctioned-relaunch-on-herdr-re
author: claude-opus-5-5:herdr-overseer
created_at: 2026-11-13T02:51:29Z
---

## Proposal: Paste the relaunch resume at most once and only into a ready composer

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

The sanctioned out-of-band relaunch pastes the resume at most once per relaunch, only once the launched composer accepts input, retries Enter-only, and on an unconfirmed submission ends resume_or_rebind_failed with the row unchanged and at most one copy in the composer.

### Motivation

overseer-f2t7cg: on released 5.54.1 (2026-11-11 19:34Z, sacrificial herdr seat w3A) the relaunch's bounded retry re-pasted the resume four times into a just-launched Claude composer that read empty after each paste and then drew the buffered pastes at once; nothing was submitted. The dispatch-stage tier judge held the fix as spec-change: the visible text says the relaunch delivers the resume but not that it pastes at most once or waits for a ready composer.

### Proposed Changes

In spec.md, under "### The sanctioned out-of-band relaunch", immediately after the paragraph beginning "After a successful launch, the entrypoint MUST deliver the resume prompt", add this paragraph:

On a terminal backend that pastes input, the entrypoint MUST paste the resume text at most ONCE per relaunch, and only after the launched session's composer is observed at its input prompt with no structured gate and no busy evidence. Every later attempt within the same relaunch, after a paste that may have landed, MUST be an Enter-only submission: a just-launched session can show an empty composer for a while and then draw buffered input all at once, so an empty reading after a paste does not prove the paste failed and MUST NOT authorize a second paste. The entrypoint MUST bound its submission attempts and state that bound in its output. When the resume's submission or the mapping row's re-binding is not confirmed within the bound, it MUST end with the failure outcome `resume_or_rebind_failed` amended onto its start-intent, MUST leave the track's mapping row unchanged, and MUST leave at most one copy of the resume text in the composer.

In scenarios.md, add:

## Scenario: A sanctioned relaunch pastes the resume once when the fresh composer reads empty after the paste

Given the sanctioned relaunch entrypoint has launched a non-Codex runtime in a herdr target pane

And the launched session's composer reads empty for a while after the resume is pasted and then shows the buffered paste

When the entrypoint completes its resume delivery

Then the resume text was pasted exactly once and the composer holds at most one copy of it

And every later submission attempt within the relaunch was Enter-only

And either the session runs a turn on the resume prompt and the mapping row is re-bound, or the relaunch ends with the resume_or_rebind_failed outcome and the mapping row is unchanged

tests/heading-coverage.json gains a TODO entry for each new scenario heading, owed by the linked implementation item.
