---
topic: remote-control-reissue-herdr-panes
author: claude-opus-5-5
created_at: 2026-11-13T17:19:21Z
---

## Proposal: Remote Control re-issue reaches herdr panes as well as tmux panes

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

contracts.md §"Remote Control re-issue" confines the re-issue to tmux panes: it reads `every tmux pane`, guards on `a tmux mode such as copy mode`, requires a fixture that is a real `tmux capture-pane -p -J` capture, and declares any session not in tmux unreachable. This proposal widens only the pane backend to the host's terminal multiplexer, herdr or tmux. That covers pane enumeration across every running herdr session, visible-text capture with wrapped lines joined, foreground-executable identification, a not-in-a-mode guard (tmux copy mode, or a herdr pane scrolled back from its bottom), and sending `/remote-control` plus Enter through the pane's own multiplexer. The fixture requirement is restated as a real capture read the way the service reads that pane's multiplexer. Every other rule of the clause stays exactly as it is.

### Motivation

Measured 2026-11-13: the role holder and every listed host (hetzner-xubuntu, gmktec-xubuntu, poweredge-xubuntu, hp-xubuntu, gamingpc-xubuntu) run a `herdr server`, and `pgrep tmux` finds nothing on any of them. As ratified, the clause reaches only tmux panes and declares every other session "outside what the service can reach, which is accepted and unfixed", so on today's fleet the re-issue reaches no session anywhere. The tmux-only implementation (work item overseer-fdwat6, draft PR #2992) cannot be fixed in code without contradicting the clause, which names tmux in its enumeration, its mode guard, its fixture requirement and its reach exclusion. The maintainer asked for a minimal widening with no other rule changed. Plan epic overseer-iyfjbo (central-credential-service).

### Proposed Changes

The `**Remote Control re-issue.**` paragraph of `contracts.md` (§"Enrolled-host delivery") MUST be replaced, in full, by:

**Remote Control re-issue.** After a push whose result is `applied` and whose account differs from the one that host last applied, the service MUST, over the same ssh destination, read the visible text, with wrapped lines joined, of every pane of the host's terminal multiplexer whose foreground process is Claude Code and which is not in a mode that takes over the pane, such as tmux's copy mode or a herdr pane scrolled back from its bottom. The multiplexers the service reaches are herdr, in every herdr session running on the host, and tmux. A pane MUST be identified as Claude Code by the executable its foreground process runs, never by the multiplexer's current-command or process name alone: Claude Code 2.1.323 reports its version number, such as `2.1.323`, as that name. A pane's foreground process is Claude Code when its command line's executable either has the basename `claude` or lies under Claude Code's per-version install directory, `~/.local/share/claude/versions/<version>`, of the host's user. The trigger is the ACCOUNT-CHANGED NOTICE: what Claude Code renders when the signed-in account changes under a running session on a pushed credential. In Claude Code 2.1.323, the version a real account switch was captured from on 2026-11-13, it takes either of two forms. In the transcript, a line carries `Remote Control disconnected — ` followed by the notice text `signed-in claude.ai account or organization changed on this machine — run /remote-control`, behind the transcript's leading status mark. In the footer below the input box, the Remote Control status reads `/rc failed`, without the notice text. The service MUST match the transcript notice text as part of a line, never as a whole line, and MUST accept the footer status in place of the transcript line, because the transcript line can scroll out of the visible text. Neither form may be matched by its leading mark or glyph. In each such pane where the notice appears, no submitted `/remote-control` prompt line follows it, and the input box holds no unsubmitted text, it MUST send `/remote-control` followed by Enter, through that pane's multiplexer, once for that delivery. A pane whose input box holds unsubmitted text MUST be skipped, never typed into. It MUST send nothing to any other pane, including a pane that merely displays the notice text in a shell, a pager or another program. A Claude Code release that changes either form is a recorded drift from the version named here, corrected by revising this clause, never a silent miss: the re-issue's test evidence MUST include at least one fixture that is a real capture of a pane taken after a real account switch, read the way the service reads that pane's multiplexer, naming the Claude Code version it was captured from. When the account that the role holder's live credential holds changes to a different account, the service MUST apply the same re-issue, locally, to the role holder's own herdr and tmux panes, once for that change. It MUST do so whether it first observes the change in the live credential or in a delivery it issues, and whether or not the change produces a delivery. The first account the service observes after it starts MUST only be recorded, never treated as a change, because the account that preceded it is unknown. A session that does not run in a herdr or tmux pane is outside what the service can reach, which is accepted and unfixed.

Every other rule of the paragraph is unchanged: the two notice forms and how each is matched, the footer `/rc failed` acceptance, never typing into unsubmitted input, once per delivery, the role-holder local re-issue and its two observation paths, and recording only the first account observed. The changes are exactly these. (1) Panes are those of the host's terminal multiplexer, herdr or tmux, and every running herdr session on the host is reached, not only tmux's. (2) The not-in-a-mode guard names tmux's copy mode and a herdr pane scrolled back from its bottom. (3) Claude Code MUST NOT be identified by the multiplexer's current-command or process name alone, whichever multiplexer reports it. (4) `/remote-control` and Enter MUST be sent through that pane's multiplexer. (5) The required real fixture is a real capture read the way the service reads that pane's multiplexer, no longer specifically `tmux capture-pane -p -J`. (6) The role holder's own panes are its herdr and tmux panes, and the reach exclusion becomes a session that does not run in a herdr or tmux pane.

In `scenarios.md`, the Given steps of the two re-issue scenarios MUST become multiplexer-neutral, with headings unchanged so `tests/heading-coverage.json` still resolves:

- `## Scenario: An account switch re-issues Remote Control only where it stopped`: replace

```
Given a following host runs two agent sessions in tmux panes, one using Remote Control and one not

And tmux reports each pane's current command as the Claude Code version number `2.1.323`, not `claude`
```

with

```
Given a following host runs two agent sessions in panes of its terminal multiplexer, herdr or tmux, one using Remote Control and one not

And the multiplexer reports each pane's current command as the Claude Code version number `2.1.323`, not `claude`
```

- `## Scenario: An account switch re-issues Remote Control on the role holder's own sessions`: replace `Given the role holder runs an agent session in a tmux pane that was using Remote Control` with `Given the role holder runs an agent session in a herdr or tmux pane that was using Remote Control`.

`spec.md` §"Remote Control follows an account switch" already speaks of "every agent session it can reach" and names no multiplexer, so it MUST NOT change.
