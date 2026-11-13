---
topic: codex-helper-spawned-from-a
author: claude-opus-5-5:herdr-overseer
created_at: 2026-11-13T02:51:28Z
---

## Proposal: Read every thread's children when finding a carrier's session

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Live process evidence covers children spawned by any thread of the carrier, each child once, failing soft when the process or a thread is gone, so a Codex session whose helper a worker thread spawned is discovered and adopted.

### Motivation

overseer-uzvcbn.21: proc_children reads only /proc/<pid>/task/<pid>/children, so a Codex helper spawned from a worker thread is invisible and fresh Codex sessions are never adopted. The dispatch-stage tier judge (spec v095) held the fix as spec-change: the visible text requires exact live process evidence but never says that evidence covers every thread's children.

### Proposed Changes

In spec.md, under "## Supervised runtimes", immediately after the paragraph ending "an index MUST NOT override live evidence.", add this paragraph:

Live process evidence MUST include every process the carrier spawned, whichever of the carrier's threads spawned it. When the daemon reads a process's children to find a carrier's session, it MUST read the children of EVERY thread of that process, MUST return each child process identifier once even when it is listed under more than one thread, and MUST fail soft: a process or thread that has gone contributes no children, and its absence MUST NOT raise an error or discard the children of the remaining threads. A session held by a helper that a non-main thread of the carrier spawned is therefore that carrier's live session for discovery and adoption, exactly as one spawned by the main thread would be.

In scenarios.md, add:

## Scenario: A Codex session held by a helper a worker thread spawned is adopted like any other

Given a mapped track whose recorded pane runs a live Codex carrier

And the process holding that carrier's session was spawned by a non-main thread of the carrier

When the daemon reads the carrier's live process evidence

Then the helper is found among the carrier's children exactly once

And the session is identified and adopted exactly as one spawned by the main thread would be

And a thread that has exited contributes no children, without an error and without hiding the children of the carrier's remaining threads

tests/heading-coverage.json gains a TODO entry for each new scenario heading, owed by the linked implementation item.
