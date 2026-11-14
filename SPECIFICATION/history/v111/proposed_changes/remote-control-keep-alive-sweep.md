---
topic: remote-control-keep-alive-sweep
author: distributed-send-message
created_at: 2026-11-14T23:08:35Z
---

## Proposal: Keep every dev seat on Remote Control and never leave a Remote Control dialog open

### Target specification files

- contracts.md

### Summary

Add a 30-second keep-alive sweep to caam-delivery-push that answers Remote Control's enable dialog and status panel, accepts folder trust for dev roots, re-issues /remote-control in idle disconnected seats judged by the session record, and alerts after five minutes off Remote Control.

### Motivation

Maintainer direction 2026-11-15: every interactive dev seat on vps, hetzner-xubuntu and gamingpc-xubuntu must always be on Remote Control and never stall, using an existing service rather than a new one. The re-issue sends /remote-control but never answers the dialog it opens, so seats stalled on it (a vps token-spend-analysis seat stalled on the status panel on 2026-11-14). Claude Code has no setting that reconnects Remote Control after an account change or enables it without the dialog (remote-control.md, errors.md). The session record ~/.claude/sessions/<pid>.json carries bridgeSessionId only while Remote Control is connected (measured on hetzner-xubuntu 2026-11-15: null on the seat whose footer read /rc failed).

### Proposed Changes

In SPECIFICATION/contracts.md, insert a new paragraph immediately after the paragraph that begins "**Remote Control re-issue.**":

**Remote Control keep-alive sweep.** Every 30 seconds the service MUST also sweep, locally on the role holder and over each listed host's ssh destination, every pane of every herdr session running on that host whose foreground process is Claude Code, identified as in "Remote Control re-issue", and which is not scrolled back from its bottom. The sweep MUST judge whether a session is on Remote Control from that session's own record, `~/.claude/sessions/<pid>.json` of the host's user for the pane's foreground process group: the session is on Remote Control when the record carries a non-empty `bridgeSessionId`, and never from the pane's visible text, which can keep showing a disconnected notice after the session has reconnected. Re-reading the pane before each key, and using key presses only, the sweep MUST: press Enter in a pane showing Claude Code's Remote Control enable dialog with its first option, `Enable Remote Control`, selected; press Escape, never Enter, in a pane showing the Remote Control status panel, recognised by its `Disconnect this session` option and its `Esc to continue` hint, so that no key it sends can select Disconnect; and, in a pane showing Claude Code's folder-trust prompt whose working directory lies under `~/workspace` or `~/.worktrees` of the host's user, move the selection to `Yes, I trust this folder` and press Enter only after a re-read shows that option selected, leaving a trust prompt in any other directory alone. In a pane whose session record shows it is not on Remote Control, whose record status is `idle`, and whose input box is empty as "Remote Control re-issue" defines it, the sweep MUST send `/remote-control` followed by Enter, then answer the dialog that opens as above, at most once per pane per sweep; it MUST send nothing to any other pane and never type into an input box that holds unsubmitted text. Each sweep MUST write one journal line per host naming every key or command it sent and every Claude Code pane it found not on Remote Control. When a pane is found not on Remote Control by every sweep for more than five minutes, the service MUST send one ntfy push naming the host and the pane to the role holder's Claude ntfy address, `CLAUDE_NTFY_TOPIC` with `CLAUDE_NTFY_SERVER` or else `https://ntfy.sh`, read from the `env` of the role holder's `~/.claude/settings.json`, and at most one push per pane until it is seen on Remote Control again; a missing address MUST be recorded in the journal and never stop the service. The sweep MUST NOT delay a delivery push, and a sweep still running when the next is due MUST be skipped, not overlapped.
