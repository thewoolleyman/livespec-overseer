---
topic: live-exercise-one-install-root
author: claude-opus-5-5
created_at: 2026-10-22T22:05:56Z
---

## Proposal: The agent client gets exactly one read-only operator-home bind: its resolved install root

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Add a one-install-root invariant to `## The isolated live exercise`. The runner resolves the agent client's launcher to what it actually executes, binds that executable's install root read-only, and binds no other operator-home path on the client's behalf, whatever other home paths the launcher names. The governing scenario gains a matching `And` clause. No heading changes.

### Motivation

Work item overseer-fr8f (the live-exercise harness cannot run a script-launcher Codex) was re-pointed under coordinator ruling R655. Its first factory run, 01M5JDPG8CM5, failed in a non-converging review loop: PR #2573 bound every home path the launcher NAMES, minus a growing denylist (`.claude`, `.codex`, then `.config`), and every further named path became another review finding. The re-pointed fix binds only the install root of what the launcher EXECUTES, so the bound set is one path by construction. The launch-time DoD preflight (codex leg, 2026-10-22T21:46Z) refused the matching DoD bullet as ungoverned: today's section lets every other operator-home path be either hidden or bound read-only, so it does not say the client gets exactly one root. Without this invariant, a reviewer's 'also bind X' finding has nothing in the spec to answer it, which reopens the loop. Coordinator ruling R663 approved this amendment. The invariant is scoped to the binds made FOR the agent client, so the runner's read-only binds for the terminal backend and its own tooling stay governed by the existing writable-path rule.

### Proposed Changes

In `SPECIFICATION/spec.md` §"The isolated live exercise", insert after the paragraph beginning "An agent client installed under the operator home MUST be made runnable":

> To make the agent client runnable, the runner MUST resolve its launcher to what it actually executes, following a script launcher's exec target to that executable's real path, and MUST bind read-only exactly ONE operator-home path on the client's behalf: the install root of that resolved executable. It MUST NOT bind a parent of that install root in its place. It MUST NOT bind any other operator-home path for the agent client, whatever other home paths the launcher names (configuration, cache or state directories, other installs); those paths stay hidden by the scratch home. This one-root rule governs only the binds the runner makes for the agent client. Read-only binds the runner makes for the terminal backend or its own tooling remain governed by the writable-path rule above.

In `SPECIFICATION/scenarios.md` §"Scenario: The isolated live exercise runs the installed agent client or refuses before starting", insert after the line `And the only writable host paths inside the namespace are the runner's scratch root and the evidence directory`:

> And the only operator-home path the runner binds for the agent client is the install root of what its launcher executes, bound read-only, even when the launcher names other home paths

The scenario's behavior MUST stay exercised by the existing `tests/heading-coverage.json` entries; no H2 heading is added, renamed or removed.

## Proposal: The runner refuses before the backend when the resolved install root is unsafe to bind

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Extend the refusal rule of `## The isolated live exercise`. When the resolved install root is the operator home itself, or one of the home directories the exercise writes inside the namespace (`~/.claude`, `~/.codex`, `~/.config`), the runner refuses before it starts any terminal backend and names that root. The governing scenario gains a matching `And` clause. No heading changes.

### Motivation

Under the one-root invariant, binding the resolved install root read-only can still defeat the isolation. If that root is the operator home, the bind masks the scratch home and exposes every operator-home path. If it is `~/.claude`, `~/.codex` or `~/.config`, the bind makes read-only a directory the exercise must write: the credential copy, client state, or the herdr socket that `scripts/overseer-live-exercise-inside.sh` needs under `~/.config`. The client then cannot be made runnable, and failing late as a `bootstrap` stage is exactly what the existing refusal rule forbids. The refusal set is the runner's own FIXED list of roots it writes, so unlike PR #2573's denylist it does not grow with what a launcher names. The launch-time DoD preflight for overseer-fr8f (codex leg, 2026-10-22T21:46Z) refused the matching bullet because neither referenced section specifies this refusal or its diagnostic. Coordinator ruling R663 approved this amendment.

### Proposed Changes

In `SPECIFICATION/spec.md` §"The isolated live exercise", append to the final paragraph (the one beginning "When the runner cannot make the selected agent client runnable inside the namespace"), before its sentence on `bootstrap`:

> The runner MUST likewise refuse BEFORE it starts any terminal backend when the resolved install root is the operator home directory itself, or is one of the home directories the exercise writes inside the namespace (`~/.claude`, `~/.codex` or `~/.config`), because binding that root read-only would defeat the scratch home or make read-only a directory the exercise must write. That refusal MUST name the offending root. This refusal set is the runner's fixed list of the roots it writes; it MUST NOT grow with the home paths a launcher names.

In `SPECIFICATION/scenarios.md` §"Scenario: The isolated live exercise runs the installed agent client or refuses before starting", append as the final line:

> And when the install root of what the launcher executes is the operator home itself, `~/.claude`, `~/.codex` or `~/.config`, the runner refuses before any terminal backend starts, naming that root

No H2 heading is added, renamed or removed, so `tests/heading-coverage.json` MUST NOT change.
