---
topic: shipped-launchers-run-their-own-plugin-package
author: claude-herdr-overseer
created_at: 2026-10-20T02:37:15Z
---

## Proposal: Shipped launchers run their own plugin's package

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Generalize contracts.md §"Daemon invocation" from overseerd's options to every shipped launcher, adding a BCP14 clause that each launcher imports the overseer package from the plugin root it ships in and starts the daemon from that plugin version's runtime, never from a package the caller's working directory, PYTHONPATH or another checkout would shadow, and add a governing scenario.

### Motivation

Work item overseer-uzvcbn.2 (bug, plan herdr-overseer) fixes a measured defect: run from inside this repository, overseer-start and overseerd imported the checkout's overseer package from the current directory and launched a stale runtime instead of the installed plugin's. The R265(2) pre-dispatch dod_gate judgement refuses the item because no SPECIFICATION heading states which package or runtime version a shipped launcher runs: §"Bootstrap preconditions" and the nearest-terminal scenario govern pane ownership only. The behaviour is load-bearing (a stale daemon silently runs old supervision code against the live fleet), so it needs a clause and a scenario before the fix can be graded. This generalizes an existing contract heading to cover a bug fix; it adds no feature scope.

### Proposed Changes

In SPECIFICATION/contracts.md §"Daemon invocation", append after the startup-gates bullet list:

> Every shipped launcher (`overseer-start`, `overseerd`, and each other executable under the plugin's `bin/`) MUST import the `overseer` package from the plugin root it ships in, and `overseer-start` MUST start the daemon from the runtime of THAT plugin root's own recorded version. A launcher MUST NOT import an `overseer` package that the caller's current working directory, `PYTHONPATH`, or another checkout would otherwise place ahead of its own plugin root, so a launcher run with its current directory inside a livespec-overseer checkout whose `overseer/version.json` differs from the plugin's still runs the plugin's own package and version. A launcher whose own plugin root cannot be resolved MUST refuse before starting anything, naming the missing root, rather than fall back to an importable package found elsewhere.

In SPECIFICATION/scenarios.md, add:

```
## Scenario: A shipped launcher runs its own plugin's package, not the caller's checkout

Given a livespec-overseer checkout whose overseer/version.json differs from the installed plugin's version

When a shipped launcher runs with its current directory inside that checkout

Then it imports the overseer package from its own plugin root and starts the daemon from that plugin version's runtime

And the checkout's overseer package is never imported

And a launcher whose own plugin root cannot be resolved refuses before starting anything, naming the missing root
```

In tests/heading-coverage.json, the new scenario heading MUST be registered in the same revision, linked to the test that exercises it (or carried in the debt register until overseer-uzvcbn.2 lands its test), per the project's heading-coverage convention.
