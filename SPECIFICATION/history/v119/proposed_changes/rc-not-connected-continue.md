---
topic: rc-not-connected-continue
author: central-credential-service
created_at: 2026-11-18T12:26:41Z
---

## Proposal: The keep-alive sweep answers the Remote Control not-connected panel by choosing Continue, then reconnects, instead of dismissing it with Escape

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Change how the keep-alive sweep answers the NOT-CONNECTED panel (the Remote Control status panel shown by a session whose record shows it is not on Remote Control, which Claude Code opens in place of reconnecting when /remote-control is typed shortly after the signed-in account changes). Today the sweep presses Escape, which dismisses the panel without reconnecting, and sends nothing to a busy seat. Instead it MUST press Enter on the panel's Continue option, wait for Remote Control to turn off, then send the reconnect command; and for a busy seat it MUST press Enter on Continue only, with no text.

### Motivation

Measured twice. On 2026-11-16 (16:47:30Z rotation) the sweep pressed Escape on 9 hetzner, 4 role-holder and 1 gamingpc pane (panel:Escape, 16:49:18Z-16:51:19Z), none reconnected, every pane then sat in the ten-minute re-issue limit, and ntfy off-RC alerts fired at 16:54Z; ten hetzner panes were not recovered in the first twenty minutes (overseer-fdwat6 B3 table). On 2026-11-18 (12:17:31Z rotation, anthropic-3 to anthropic-2) every seat's Remote Control was signed out and 15 seats across the vps and hetzner sat blocked on the dialog until legacy-coordinator-agent cleared them by hand with Enter (the picker defaults to Continue), a wait of about 12 s, then /remote-control <session name>. Seats with a WORKING turn showed the dialog too, and the same keypresses cleared them. A session launched after the switch also started disconnected. The panel text itself says: 'To try again, choose Continue, wait about 10 seconds for Remote Control to turn off, then run /remote-control.' DoD 4 of plan central-credential-service (Remote Control comes back on every listed-host session that lost it, with no operator action) did not hold on either rotation. Ledger: overseer-fdwat6.

### Proposed Changes

contracts.md, paragraph 'Remote Control keep-alive sweep'. Replace the sentence that begins 'a status panel shown by a session whose record shows it is not on Remote Control is the NOT-CONNECTED panel' with: a status panel shown by a session whose record shows it is not on Remote Control is the NOT-CONNECTED panel, which Claude Code opens in place of reconnecting when /remote-control is typed shortly after the signed-in account changed, and which it also opens by itself on a session that was not typed into. The sweep answers the NOT-CONNECTED panel by pressing Enter only after a re-read shows its Continue option selected, whatever the session record's status, because Continue closes the panel and cannot select Disconnect or interrupt a running turn; it names the pane as continued while not connected. When the record's status is idle and the input box holds no unsubmitted text, the sweep then waits at least 12 seconds, re-reads the pane and the record, and sends the reconnect command followed by Enter exactly as for an idle seat; when the status is busy it sends nothing more, and the pane is reconnected by a later sweep once it is idle. The ordinary connected status panel keeps Escape under the existing busy condition. The release of a pane from the ten-minute limit applies to a pane just continued at the NOT-CONNECTED panel, and the journal line names under offline the panes it continued. In the same paragraph, the clause that accepts 'a seat left on the panel through a long busy turn' applies only to the ordinary connected status panel. The sweep's test evidence MUST also include a real capture of the NOT-CONNECTED panel with its Continue option selected, read the way the sweep reads a herdr pane and naming the Claude Code version. scenarios.md: change the scenario 'A seat that meets the not-connected panel after an account switch is retried at the next sweep' so its Then reads: the sweep presses Enter on Continue, waits, sends the reconnect command, and names the pane as continued while not connected; change 'A mid-turn seat at the not-connected panel gets no key' so a busy seat at the NOT-CONNECTED panel gets Enter on Continue and no text, and is named as continued; add 'A fresh session that starts disconnected after an account switch is reconnected by the next sweep' (Given a herdr pane whose Claude Code started after the push and whose record has no bridgeSessionId and shows the NOT-CONNECTED panel, When the sweep reads it, Then it presses Enter on Continue and, once idle, reconnects it).
