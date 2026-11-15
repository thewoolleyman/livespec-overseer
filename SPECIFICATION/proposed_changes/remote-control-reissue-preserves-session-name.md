---
topic: remote-control-reissue-preserves-session-name
author: claude-opus-5-5
created_at: 2026-11-15T08:37:42Z
---

## Proposal: Remote Control reconnects a session under its own name

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

The Remote Control re-issue and the keep-alive sweep type `/remote-control <name>`, with the name read from the session's own record, instead of a bare `/remote-control`. They fall back to the bare command only when no usable name is available. A name holding a control character is refused and journalled, never typed. The keep-alive sweep also recognises the NOT-CONNECTED panel that `/remote-control` opens right after an account switch, and the service retries such a seat at the next sweep instead of holding it for the ten-minute cap.

### Motivation

NOT-CONNECTED PANEL, measured 2026-11-15 on the role holder's own journal (vps, caam-delivery-push) across the 16:47:30Z account switch (anthropic-1 to anthropic-3, sequence 35). At 16:49:03Z-16:49:06Z the re-issue typed `/remote-control` into 15 hetzner-xubuntu panes, 5 role-holder panes and gamingpc's w1:p2. In each, it opened the Remote Control status panel rather than reconnecting: Claude Code 2.1.325 shows that panel with `Remote Control isn't connected.` while its bridge is down. The sweep then pressed Escape on it as an ordinary status panel (16:49:18Z-16:51:19Z), which dismissed it without reconnecting, and every pane sat out the ten-minute cap. ntfy off-Remote-Control alerts fired at 16:54:21Z. Seats that were busy when it opened sat at the panel, and the coordinator had to answer three of them by hand. When the cap expired, at 16:59:37Z, the sweep's second bare `/remote-control` reconnected the panes: about 12 minutes off Remote Control, against the two minutes overseer-fdwat6 requires, and under auto-generated names.

Measured live on 2026-11-15 after the 07:49:58Z account switch (sequence 32) on the credential-rotation role holder vmi3006760. The re-issue and the sweep reconnected the idle seats with no operator action, as overseer-fdwat6 (DoD 4 of plan central-credential-service) requires. But ccs-completeness-reviewer's agent listing at 08:32Z showed several of them back on Remote Control under AUTO-GENERATED names (vmi3006760-prancy-knuth, -zesty-giraffe, -splendid-quokka, gamingpc-xubuntu-luminous-hanrahan) rather than their session names. Other seats address a seat by that name (SendMessage), so such a seat is on Remote Control yet unreachable, which defeats the point of keeping it there. Claude Code's Remote Control documentation (code.claude.com/docs/en/remote-control.md, sections 'From an existing session' and 'Name') says `/remote-control <name>` sets the remote session title, and gives the precedence as: the name passed to `--name`/`--remote-control`/`/remote-control`, then `/rename`, then the last meaningful message, then an auto-generated name. A reported issue (claudeissues #76206) shows a bare `/remote-control` dropping a session's name. Passing the name explicitly is the documented way to keep it. The ready-gated restart already does this (scenario 'A ready-gated restart of a Claude seat keeps its Remote Control name' carries `--remote-control <seat-name>`); this brings the in-place reconnect into line with it. The name comes from the same session record the sweep already reads for `bridgeSessionId` and `status`, matched by the same pid rule. Because the name is session-authored text that the service would type into a terminal, it is checked first: a control character (newline included) could submit or alter input, so such a name is refused, and so is an over-long one.

### Proposed Changes

1. contracts.md, section "Enrolled-host delivery", paragraph **Remote Control re-issue**. Replace the sentence "In each such pane where the notice appears, no submitted `/remote-control` prompt line follows it, and the input box holds no unsubmitted text, it MUST send `/remote-control` followed by Enter, through that pane's multiplexer, once for that delivery." with: "In each such pane where the notice appears, no submitted `/remote-control` prompt line follows it, and the input box holds no unsubmitted text, it MUST type the RECONNECT COMMAND followed by Enter, through that pane's multiplexer, once for that delivery. The reconnect command is `/remote-control <name>`, where `<name>` is the `name` field of that session's own record, `~/.claude/sessions/<pid>.json` of the host's user, `<pid>` being the process id the multiplexer reports for the pane's foreground process whose executable is Claude Code and the record's own `pid` being equal to it. The service MUST type the bare `/remote-control` instead when no such record is readable, when the record has no `name`, or when the name is not a string, is empty, is longer than 200 characters, or holds a control character (any code point below U+0020, newline and tab included, or U+007F); a refused name MUST be named in the journal, never typed. A tmux pane gets the bare command, because the service does not read a tmux pane's foreground process id. Claude Code titles a Remote Control session with the name passed to `/remote-control` ahead of every other source, so a reconnected session keeps the name other sessions address it by; a bare `/remote-control` can come back under an auto-generated name such as `<host>-<adjective>-<noun>`, which no other session knows." The phrase "no submitted `/remote-control` prompt line" keeps matching a submitted line that starts `/remote-control`, with or without a name after it.

2. contracts.md, same section, paragraph **Remote Control keep-alive sweep**. Replace "the only text it ever types is `/remote-control`" with "the only text it ever types is the reconnect command \"Remote Control re-issue\" defines, read from the same session record the sweep judges the pane by". Replace "the sweep MUST send `/remote-control` followed by Enter and then answer the dialog that opens as above" with "the sweep MUST send the reconnect command followed by Enter and then answer the dialog that opens as above". The rule that "It MUST send that command to a pane at most once in any ten minutes, counting a send by \"Remote Control re-issue\"" is unchanged and covers the reconnect command whatever name it carries. Every other condition (status `idle`, an empty input box, the re-read before each input, never typing into unsubmitted text, the ten-minute cap) is unchanged. Each sweep's journal line names the reconnect command it typed, name included, and any name it refused.

3. spec.md, section "Remote Control follows an account switch" (the paragraph beginning **Remote Control follows an account switch.**). After the sentence ending "…as contracts.md §\"Enrolled-host delivery\" defines." (the second such reference), add: "The re-issue MUST carry the session's own name, as contracts.md §\"Enrolled-host delivery\" defines, so that a reconnected session can be reached under the name other sessions address it by."

4. scenarios.md, scenario "An account switch re-issues Remote Control only where it stopped": replace "Then the service sends `/remote-control` to the first pane once" with "Then the service sends the reconnect command to the first pane once". Scenario "An account switch re-issues Remote Control on the role holder's own sessions": replace "Then the service sends `/remote-control` to that pane once" with "Then the service sends the reconnect command to that pane once".

5. scenarios.md, add these scenarios after "An account switch re-issues Remote Control on the role holder's own sessions":

## Scenario: A reconnected seat keeps the name it is addressed by

Given a herdr pane whose foreground Claude Code process has a session record with `name` `caam-anthropic-loop-runner` and a `pid` equal to that process's id

And the session is not on Remote Control, its record's status is `idle`, and its input box is empty

When the keep-alive sweep or the Remote Control re-issue reconnects it

Then the text typed into the pane is `/remote-control caam-anthropic-loop-runner` followed by Enter

And the journal line names that command

## Scenario: A seat with no usable name is reconnected with the bare command

Given a herdr pane whose Claude Code session record has no `name`, or a tmux pane

When the service reconnects it to Remote Control

Then the text typed into the pane is `/remote-control` followed by Enter

## Scenario: A session name holding a control character is never typed

Given a herdr pane whose Claude Code session record's `name` contains a newline, a tab, or another control character, or is longer than 200 characters

When the service reconnects it to Remote Control

Then the text typed into the pane is the bare `/remote-control` followed by Enter

And the journal line names the refused name's pane

And no part of the name is typed

6. contracts.md, same section, paragraph **Remote Control keep-alive sweep**. After the sentence that ends "…(an operator deliberately using that panel is dismissed, which is accepted);", add: "a status panel shown by a session whose record shows it is not on Remote Control is the NOT-CONNECTED panel, which Claude Code opens in place of reconnecting when `/remote-control` is typed shortly after the signed-in account changed; the sweep answers it exactly as the status panel, under the same `busy` condition, and names the pane as dismissed while not connected;". Judging it by the record, not by the panel's text, keeps the paragraph's rule that whether a session is on Remote Control is never judged from visible text. Replace "It MUST send that command to a pane at most once in any ten minutes, counting a send by \"Remote Control re-issue\", which the service records by pane for this purpose, as one, so a seat that cannot connect is not typed into every sweep." with "It MUST send that command to a pane at most once in any ten minutes, counting a send by \"Remote Control re-issue\", which the service records by pane for this purpose, as one, so a seat that cannot connect is not typed into every sweep, EXCEPT that a pane the sweep has just found at the not-connected panel is released from that limit, so that the next sweep may send the command again; the service MUST release a pane this way at most four times before a sweep reads it on Remote Control again or reads a new session in it, after which the ten-minute limit applies. Each such journal line names the panes released." Every other condition (status `idle`, an empty input box, the re-read before each input, never typing into unsubmitted text, Escape only while not `busy`) is unchanged.

7. scenarios.md, add these scenarios after "A session name holding a control character is never typed":

## Scenario: A seat that meets the not-connected panel after an account switch is retried at the next sweep

Given an account switch has just been pushed to a listed host

And the Remote Control re-issue typed the reconnect command into an idle herdr pane whose session record shows it is not on Remote Control

And the pane then shows the Remote Control status panel

When the keep-alive sweep reads the pane while its record's status is not `busy`

Then the sweep presses Escape and names the pane as dismissed while not connected

And the next sweep may send the reconnect command to that pane again, without waiting ten minutes

## Scenario: The not-connected retry is bounded

Given a herdr pane the sweep has found at the not-connected panel four times since a sweep last read it on Remote Control

When the sweep finds it at the not-connected panel again

Then the service sends that pane the reconnect command at most once in the next ten minutes

## Scenario: A mid-turn seat at the not-connected panel gets no key

Given a herdr pane showing the Remote Control status panel whose session record shows it is not on Remote Control and has status `busy`

When the keep-alive sweep reads the pane

Then the sweep sends the pane no key and no text

And it names the pane as not on Remote Control

8. Revise co-edit owed: `tests/heading-coverage.json` rows for the six new scenario headings, with `work_item: overseer-fdwat6`. The implementation is a separate draft PR held until this proposal is revised in.
