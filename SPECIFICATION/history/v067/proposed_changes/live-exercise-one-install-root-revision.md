---
proposal: live-exercise-one-install-root.md
decision: modify
revised_at: 2026-10-23T01:11:00Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

Accepted with one modification, under delegated mode (coordinator ruling R663). The specification already required the agent client to be made runnable by binding what it executes, but it permitted every other operator-home path to be hidden or bound read-only. So it neither limited the client's binds to one root nor specified a refusal for an install root that cannot be bound safely. overseer-fr8f's launch-time DoD preflight refused both corresponding bullets as ungoverned (codex leg, 2026-10-22T21:46Z). Its prior factory run, 01M5JDPG8CM5, failed in a non-converging review loop because a denylist of named home paths has no fixed point. One root by construction, plus a fixed refusal set of the roots the runner writes, gives a reviewer's 'also bind X' finding a governed answer. The one-root rule is scoped to binds made for the agent client, so the backend and tooling binds remain under the existing writable-path rule. No design record is contradicted: v065 introduced this section and is extended, not reversed.

## Modifications

MODIFIED ON INDEPENDENT RATIFICATION REVIEW (two blockers). (1) The one-root rule as proposed forbade binding the launcher at its own PATH location, which keeps the client callable by name. The client binds are now at most two: the launcher at its own path, plus the install root of what a script launcher runs, with nothing else. (2) The install root is now defined: the first directory below the operator home on the real path of the program the launcher exec line runs, or of the script file it passes when that program lies outside the home; the operator home itself when the program sits directly in it. A self-contained launcher needs only the launcher bind. A program and script in different first-level home directories is a refusal. The scenario line is reworded to match. (3) The section.s closing sentence, 'It MUST NOT report the condition later as a failed bootstrap lifecycle stage', is reworded to 'The runner MUST NOT report either refusal condition later as a failed bootstrap lifecycle stage', placed after the new unsafe-root refusal. This keeps the late-bootstrap prohibition applying to both refusals instead of only the first. The rest is as proposed.

## Resulting Changes

- spec.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-10-22T22:11:08Z
verdict: NO BLOCKERS
proposal_stem: live-exercise-one-install-root
content_digest: e51ad757c8ff0c8bf8d7cf68907320afa6aa98f2ddab542d44cbd82b1a88a768
