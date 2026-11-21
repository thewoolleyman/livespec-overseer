---
topic: retire-remote-control-support
author: remote-control-retirement
created_at: 2026-11-21T02:05:24Z
---

## Proposal: retire-remote-control-support

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md
- SPECIFICATION/contracts.md

### Summary

Retire Remote Control support entirely: no launch passes --remote-control, and the caam-delivery-push service types nothing into any seat.

### Motivation

On 2026-11-20 a caam account rotation made the role holder's Remote Control re-issue type /remote-control into every seat. That opened a Continue dialog nobody pressed, and the whole fleet froze from about 09:47Z to 23:48Z; a second freeze followed at about 00:09Z on 2026-11-21. The maintainer, verbatim: "we need to just disable the remote control support completely and open a plan to figure out a different way to do it that doesn't leverage remote control or can guarantee that nothing ever gets deadlocked in this way." Plan remote-control-retirement (livespec-dev-tooling-s63cb5). The implementation halves are livespec-overseer#3191 (service wiring removed) and livespec-overseer#3197 (launches pass -n only).

### Proposed Changes

1. spec.md §"The launch profile" (around line 486): delete the paragraph beginning "For a Claude-harness track, every launch the daemon or the sanctioned relaunch entrypoint performs MUST pass `--remote-control <seat-name>`" and replace it with: a Claude-harness launch MUST NOT pass `--remote-control`; the seat name is passed with `-n` only.
2. spec.md sanctioned relaunch (around line 684): delete the sentence "For a Claude-harness launch the submitted command MUST carry `--remote-control <seat-name>` as §\"The launch profile\" requires." and state that the command carries no `--remote-control`.
3. spec.md enrolled-host delivery (around line 2002): delete the paragraph "Remote Control follows an account switch." and state that the service MUST NOT type any command into an agent session.
4. contracts.md §"Enrolled-host delivery" (around lines 1265-1267): delete the "Remote Control re-issue" and "Remote Control keep-alive sweep" paragraphs and state that the service types nothing into any pane.
5. scenarios.md: delete the scenarios "An account switch re-issues Remote Control only where it stopped", "An idle seat showing only a prompt suggestion is re-issued, and a seat with typed text is not", "An account switch re-issues Remote Control on the role holder's own sessions", "A reconnected seat keeps the name it is addressed by", "A seat with no usable name is reconnected with the bare command", "A session name holding a control character is never typed", "A seat that meets the not-connected panel after an account switch is retried at the next sweep", "The not-connected retry is bounded", "A mid-turn seat at the not-connected panel is continued and typed nothing", "A fresh session that starts disconnected after an account switch is reconnected by the next sweep", "A sweep that runs out of time leaves the remaining seats to the next sweep", "A seat that starts a turn after its reconnect command gets no key", and "A ready-gated restart of a Claude seat keeps its Remote Control name". Add one scenario: after a delivery that names a different account, the service types nothing into any pane of any host.
6. Edit the sanctioned-relaunch scenario around line 6893 so its launch command carries `-n <seat-name>` and no `--remote-control`.
7. The revise commit MUST update tests/heading-coverage.json in the same commit for every removed or added `## ` heading, and regenerate any debt register.
