---
topic: claude-seat-under-a-launch-shell
author: claude-opus-5-5
created_at: 2026-11-15T02:10:51Z
---

## Proposal: A Claude carrier under a launch shell in the recorded pane is the track's live seat

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

State in §"Supervised runtimes" that, for a Claude-harness track, the pane's identity gate MUST look at every process in the recorded pane's foreground process group, not only the group leader. A launch shell (`bash <script>`) leading a group whose member is the topic's live `claude` process in the track's repository is the track's live supervised seat, read with a live status and context. A foreground group holding no such `claude` process keeps the existing fail-closed outcome. Two scenarios pin both directions.

### Motivation

Observed 2026-11-14 on hetzner-xubuntu, overseerd 5.58.2 under herdr: three live, correctly-mapped Claude seats (bootstrap-credentials-and-onboarding, central-credential-service, expedited-incident-response-flag) read session-gone with no context because each had been started by typing `bash <scratchpad>/<x>-launch.sh`, a script that runs `claude -n <topic> ...` as a child. The terminal backend reports the foreground group LEADER as that bash, the daemon reads `bash` as the pane's command, and the Claude identity gate refuses the pane. The seats were therefore silently unsupervised (no wrap-up, no restart) and misreported as dead. The current text (spec.md §"Supervised runtimes", the live-carrier and `unidentified-session` paragraphs) does not say which process in the recorded pane the gate reads. Work item overseer-aw336m is held at spec-change tier pending this rule.

### Proposed Changes

In SPECIFICATION/spec.md §"Supervised runtimes", after the paragraph that begins "A LIVE carrier of a supported runtime running in a mapped track's recorded pane", add:

> For a Claude-harness track, the daemon MUST evaluate the recorded pane's identity against EVERY process in that pane's foreground process group, not only the group's leader. When the leader is an interactive or script-running shell (a launch shell) and the group contains a live `claude` process whose session name is the track's derived session name under §"Session-name derivation" and whose working directory is inside the track's repository, that `claude` process MUST be treated as the track's live supervised session: the track MUST be read with a live status and its context percentage, and it receives adoption, wrap-up, nudge and restart exactly as a session that leads its own group. The existing name, repository and per-carrier evidence requirements MUST still hold for that member; being in the group grants nothing on its own. When the foreground group contains no `claude` process for the track's topic, the outcome MUST be exactly what it is today (session-gone, `unidentified-session`, or misnamed under this section), so the gate stays fail-closed. A restart of such a seat MUST launch the runtime as the pane's foreground group leader, so a seat leaves the launch-shell shape at its next restart.

In SPECIFICATION/scenarios.md add, beside the existing `unidentified-session` scenarios:

## Scenario: A Claude seat started under a launch shell is read as the track's live seat

Given a mapped Claude-harness track whose recorded pane's foreground process group is led by a shell running a launch script
And that group contains a live `claude` process named for the track's topic with its working directory inside the track's repository
When the daemon evaluates the track
Then the track reads a live status with its context percentage, not session-gone
And the track is eligible for wrap-up, nudge and ready-gated restart

## Scenario: A launch shell with no Claude process for the topic stays session-gone

Given a mapped Claude-harness track whose recorded pane's foreground process group is led by a shell
And that group contains no `claude` process named for the track's topic
When the daemon evaluates the track
Then the track reads exactly as it would without this rule, and no act is taken on the pane

The revise that accepts this MUST co-edit tests/heading-coverage.json to link both new scenario headings, per spec.md §"Self-application".
