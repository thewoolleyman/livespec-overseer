---
topic: relaunch-keeps-remote-control-name
author: claude-opus-5-5
created_at: 2026-11-15T02:10:52Z
---

## Proposal: Relaunch and ready-restart launch a non-Codex seat with Remote Control under its seat name

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Require both the sanctioned out-of-band relaunch and the daemon's ready-gated restart to launch a Claude-harness seat with `--remote-control <seat-name>`, where `<seat-name>` is the same name passed to `-n` (the track's derived session name), so a relaunched seat stays reachable across machines without a manual `/remote-control` step. Extend the sanctioned-relaunch scenario and add a restart scenario.

### Motivation

`overseer relaunch` (5.58.2) types `claude --model <m> --dangerously-skip-permissions -n <topic>` and the daemon's restart builds the same shape; neither passes `--remote-control`. Seats in this fleet are launched with `--remote-control <topic>` so other machines (the coordinator runs on another host) can reach them by SendMessage over Remote Control. Relaunching bootstrap-credentials-and-onboarding and central-credential-service on hetzner-xubuntu on 2026-11-15 dropped their Remote Control names; the fleet coordinator accepted an interim of typing `/remote-control <seat-name>` into each new pane by hand. The launch profile (spec.md §"The launch profile", `{harness, model, wrapper|null}`) and the sanctioned-relaunch scenario (scenarios.md, "A sanctioned relaunch of a non-Codex seat submits no rename") say nothing about Remote Control. Work item overseer-m3p2ei is held at spec-change tier pending this rule.

### Proposed Changes

In SPECIFICATION/spec.md §"The launch profile" (under §"The restart"), add:

> For a Claude-harness track, every launch the daemon or the sanctioned relaunch entrypoint performs MUST pass `--remote-control <seat-name>` to the runtime, where `<seat-name>` is EXACTLY the name the same launch passes to `-n`, the track's derived session name under §"Session-name derivation". This is part of re-asserting the launch: a restart or relaunch MUST NOT leave a seat without the Remote Control name its successor needs to be reached from another machine. The flag is not a fourth launch-profile field and MUST NOT be read from or written to the recorded profile; it is derived from the session name on every launch. A Codex launch is unaffected.

In SPECIFICATION/spec.md §"The sanctioned out-of-band relaunch", in the paragraph beginning "Otherwise it MUST launch that profile's runtime", add after its first sentence: "For a Claude-harness launch the submitted command MUST carry `--remote-control <seat-name>` as §"The launch profile" requires."

In SPECIFICATION/scenarios.md, in "## Scenario: A sanctioned relaunch of a non-Codex seat submits no rename", add after its Then line:

And for a Claude-harness profile the launch command carries `--remote-control` with the same name it passes to `-n`

and add:

## Scenario: A ready-gated restart of a Claude seat keeps its Remote Control name

Given a mapped Claude-harness track that has declared a certifiable `ready`
When the daemon restarts the track
Then the launch command carries `-n <seat-name>` and `--remote-control <seat-name>` with the same `<seat-name>`
And the recorded launch profile is unchanged by the flag

The revise that accepts this MUST co-edit tests/heading-coverage.json to link the new scenario heading, per spec.md §"Self-application".
