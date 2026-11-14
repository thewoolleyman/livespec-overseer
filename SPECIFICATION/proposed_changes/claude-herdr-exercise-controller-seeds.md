---
topic: claude-herdr-exercise-controller-seeds
author: claude-opus-5-5
created_at: 2026-11-14T17:06:01Z
---

## Proposal: A Claude exercise seeds its scratch profile before the client starts

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Under "## The isolated live exercise", state as a MUST that when the selected agent client is Claude Code, the exercise seeds the scratch home before it starts that client, so that no first-run screen can consume the client's first input: `hasCompletedOnboarding: true`, and `hasTrustDialogAccepted: true` in the `projects` entry for the repository directory the exercise starts the client in, in the scratch Claude profile file; and `skipDangerousModePermissionPrompt: true` in the scratch Claude settings file. Each write MUST keep every other key the file already holds. This holds for every Claude exercise controller, on the herdr backend and on the tmux backend. A new scenario states the observable result: against a client that shows a first-run theme picker and a Bypass Permissions warning unless those keys are seeded, the run still records a passed `bootstrap` stage.

### Motivation

Both Claude exercise controllers failed to bootstrap a REAL Claude Code client in the exercise's fresh scratch home, measured by herdr-overseer on the operator host on 2026-11-14 against the released controllers (overseer-uzvcbn.19 on v5.57.0, overseer-uzvcbn.20 on v5.58.0). The herdr controller left real Claude Code v2.1.325 on its first-run theme picker, because it never seeds onboarding; the tmux controller, which does seed onboarding and folder trust, left the client on the "Claude Code running in Bypass Permissions mode" warning, because the scratch settings lack `skipDangerousModePermissionPrompt` (the operator's real client skips that dialog only because the operator's own settings set it, and the scratch home deliberately hides those). The fix is filed as overseer-5vtwxy (plan herdr-overseer, epic overseer-uzvcbn). Its dispatch tier pre-read at 2026-11-14T17:02:12Z held it as spec-change: the ratified section states the outcome (the client reaches its idle input prompt, so `bootstrap` passes) but not the seeding that makes it reachable. legacy-coordinator-agent ruled that this is new behaviour, declined a clause release, and directed this proposal so the item places FRESH once the topic ratifies. The seeding is not operator content: it is written by the exercise into the scratch home, so it does not widen the existing rule that the credential is the only operator content copied there.

### Proposed Changes

In `SPECIFICATION/spec.md`, section "## The isolated live exercise", insert this paragraph immediately after the paragraph ending "the agent client's credential is the only operator content copied into the scratch home.":

> When the selected agent client is Claude Code, the exercise MUST seed the scratch home before it starts that client, so that no first-run screen can consume the client's first input. It MUST write `hasCompletedOnboarding: true`, and `hasTrustDialogAccepted: true` in the `projects` entry for the repository directory the exercise starts the client in, into the scratch Claude profile file (`.claude.json` in the Claude configuration directory, or directly in the scratch home when none is set). It MUST write `skipDangerousModePermissionPrompt: true` into the scratch Claude settings file (`settings.json` in the Claude configuration directory, or in `.claude` under the scratch home when none is set). Each write MUST keep every other key the file already holds, including other `projects` entries and the other keys of the exercise repository's entry. These values are written by the exercise, not copied from the operator home, so they do not count as operator content under the rule above. This holds for every Claude exercise controller, on the herdr backend and on the tmux backend.

In `SPECIFICATION/scenarios.md`, add this scenario immediately after "## Scenario: The isolated live exercise runs the installed agent client or refuses before starting":

```
## Scenario: A Claude exercise seeds its scratch profile so no first-run screen takes the first input

Given a Claude Code client that shows a first-run theme picker unless its profile records `hasCompletedOnboarding: true`, and a Bypass Permissions warning unless its settings record `skipDangerousModePermissionPrompt: true`

And a scratch profile and settings file that already hold other keys

When the released live-exercise runner starts a lifecycle run for that client on the herdr backend and on the tmux backend

Then the client reaches its idle input prompt, so the run records a passed `bootstrap` stage

And the scratch profile records `hasCompletedOnboarding: true`, and `hasTrustDialogAccepted: true` in the `projects` entry for the repository directory the exercise starts the client in, and the scratch settings record `skipDangerousModePermissionPrompt: true`

And every other key those files held before the run is still present with its value
```

The revise that accepts this proposal MUST add a `tests/heading-coverage.json` row for the new scenario heading as a TODO row with `work_item: overseer-5vtwxy` and a reason naming the integration tier, with its debt row, until that item's tests bind it. The section's existing sentences are unchanged.

Implementation note for overseer-5vtwxy (not spec text): both Claude controllers today read the settings directory from `CLAUDE_HOME` and the profile location from `CLAUDE_CONFIG_DIR`. The implementation MUST make the two agree with the paths above, so the settings file and the profile file resolve from the same Claude configuration directory.
