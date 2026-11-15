---
topic: remote-control-keep-alive-sweep-record-pid
author: distributed-send-message
created_at: 2026-11-15T00:21:22Z
---

## Proposal: Name the session record by the Claude Code process, and allow three Down presses

### Target specification files

- contracts.md

### Summary

Correct two details of the keep-alive sweep paragraph measured while implementing it.

### Motivation

Measured on hetzner-xubuntu 2026-11-15: a seat launched through a wrapper script (central-credential-service) has a foreground process group led by bash (pid 1502316) while its Claude Code process is 1502318 and its record is 1502318.json, so the group id named in v111 finds no record and leaves the seat unknown. The implementation reads the pid of the foreground process whose executable is Claude Code. The trust prompt loop re-reads the pane before each Down and presses at most three, never pressing Enter unless a re-read shows Yes selected; the bound and the order of re-read and key are restated to match.

### Proposed Changes

In SPECIFICATION/contracts.md, in the "Remote Control keep-alive sweep" paragraph, replace:

where `<pid>` is herdr's foreground process group id for the pane, the Claude Code process that leads it, and the record's own `pid` equals it:

with:

where `<pid>` is the process id herdr reports for the pane's foreground process whose executable is Claude Code, which need not lead the foreground process group, and the record's own `pid` equals it:

and replace:

To trust, it presses Down only while that option is not selected, at most twice, re-reading after each,

with:

To trust, it presses Down at most three times, each only after a re-read shows that option not selected,
