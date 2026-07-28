---
topic: background-shell-liveness-attention
author: claude-opus-5[1m]
created_at: 2026-07-28T03:11:07Z
---

## Proposal: Bound busy-suppression of attention: a prolonged background command on a low-context track MUST be surfaced

### Target specification files

- spec.md
- contracts.md

### Summary

spec.md §"Fail-soft posture" currently states that over-firing busy detection is harmless because "a false 'busy' merely suppresses action". That is true for action and false for attention: a busy signal can remain true indefinitely, and while it does no supervision round can open, so the track is never warned, never reported, and never enters the attention surface. This proposal keeps the existing suppression of ACTION unbounded and makes the suppression of ATTENTION bounded. When a track's ONLY busy evidence is a background command running at its prompt, that evidence has been observed continuously past a bounded floor, and the track's remaining context is at or below its wind-down threshold, the daemon MUST surface the track to the operator — and surfacing is the entire response, authorizing no injection, no keystroke, no process termination, no declaration write, and no restart. contracts.md §"Attention surface" gains the corresponding, report-only membership entry. The change SCOPES the existing clause rather than punching a hole in it: the property the clause protects — an ambiguous reading never triggers an act — survives verbatim, because the new obligation produces a report and nothing else.

### Motivation

Measured incident, 2026-07-28 (plan/background-shell-supervision-liveness/research/root-cause.md). The supervised tmux session 04-convergence-loop in /data/projects/homelab sat at an empty Claude input prompt with 29% remaining context while a Bash(run_in_background) poller had been alive for roughly 39 hours. The poller invoked `gh pr checks 61 --json ...`; the installed gh does not support `--json`, its stderr was discarded, and the until-loop could therefore never observe `0`. Its pull request had already merged and its worktree cwd had been deleted. Claude correctly published registry status `shell`, so the daemon took the top-precedence busy branch: it wrote no injection stamp, opened no round, sent no wrap-up, and rendered the row green as `working (background shell)`, outside the NEEDS YOU block, through every remaining escalation band.

The restart interlock behaved exactly as specified and is NOT being weakened here. Restarting without a fresh session-written `ready` would violate the cardinal rule, and the missing restart is not the defect. The defect is indefinite SILENT shielding: one stale background command can hold a track green and unreported forever, and no clause in the current tree obliges the daemon to say anything about it.

The selected policy (plan/background-shell-supervision-liveness/research/policy-options.md, recommendation ratified with the maintainer this session; ledger epic overseer-4xfmez, implementation bug overseer-vyjkzw) introduces NO new evidence source. It times a signal the daemon already derives and already trusts — for a Claude track the runtime's own authoritative registry self-report that it is at its prompt with a live background command, for a Codex track the runtime-agnostic descendant-shell walk — conjoined with the pane not visibly generating, which is precisely the state that already renders the row's `background shell` note. The episode clock is in-memory, mirroring the keep-going nudge's continuous-idle clock that spec.md already ratifies: an unsustainable observation, including a restart of the daemon itself, resets the floor and therefore only ever DELAYS the report, which is why the obligation cannot fabricate an alarm about genuine work.

The wording below is deliberately implementation-neutral. spec.md's scope statement places the pane's track table, its columns, and its status vocabulary outside the governed contract, so no status token, constant, or identifier is named in governed prose; the ratified values (a two-hour floor and a dedicated non-destructive row status) belong to the implementing slice. No `## ` heading is added, removed, or renamed in either file, so no tests/heading-coverage.json co-edit is owed by this proposal. The paired Gherkin scenario in scenarios.md, its integration test under tests/integration/, and that scenario's tests/heading-coverage.json row are obligations of the implementing slice (overseer-vyjkzw) and MUST land atomically with the product change — every scenario heading in this tree is mechanically required to name a real integration test, which cannot exist before the behavior does.

### Proposed Changes

Two edits. Anchors verified verbatim against the working tree at proposal time.

EDIT 1 (spec.md, §"Fail-soft posture", the busy-detection bullet). Replace:

"- Busy detection deliberately over-fires: a false \"busy\" merely suppresses\n  action, while a missed \"busy\" could inject into a working session — so\n  ambiguity always resolves toward doing nothing."

with:

"- Busy detection deliberately over-fires: a false \"busy\" merely suppresses\n  action, while a missed \"busy\" could inject into a working session — so\n  ambiguity always resolves toward doing nothing. That suppression is\n  unbounded for ACTION and bounded for ATTENTION (see below)."

EDIT 2 (spec.md, §"Fail-soft posture", a new paragraph appended after that bullet list, at the end of the section). Add:

"Suppressing action without limit is correct; suppressing ATTENTION without\nlimit is not. A busy signal can stay true indefinitely — a background command\nthat never exits keeps a track classified busy through every escalation band —\nand while it holds, no round can open, so the track is never warned and never\nreported. A low-context track shielded silently is therefore its own failure,\ndistinct from the restart the cardinal rule correctly withholds. When a track's\nONLY busy evidence is a background command running at its prompt, that evidence\nhas been observed CONTINUOUSLY past a bounded floor, and the track's remaining\ncontext is at or below its wind-down threshold, the daemon MUST surface the\ntrack to the operator. Surfacing is the ENTIRE response: on that evidence the\ndaemon MUST NOT inject a wrap-up, send a keystroke, terminate the command,\nwrite a declaration, or restart the session, and a fresh session-written\n`ready` remains the SOLE restart authorization. The floor MUST be long enough\nthat ordinary long-running background work completes inside it, so a genuine\nbuild is never reported as a problem. The condition MUST be re-derived from\nlive state every cycle, so it clears on its own when the command ends or the\ncontext recovers, and it re-arms for a later episode. An episode the daemon\ncannot observe continuously — including across a restart of the daemon itself —\nMUST restart the floor rather than shorten it, so an unprovable episode DELAYS\nthe report and can never fabricate one. Every other busy reading, every episode\nbelow the floor, and every track above its threshold resolve toward silence,\nexactly as before."

EDIT 3 (contracts.md, §"Attention surface", the membership sentence). Replace:

"The daemon owns \"what needs attention now\". Membership: a blocked track, a\nnon-responding track at the danger line, a track whose mapped session is\ngone, a malformed state value, and a restart whose resume has not yet\nsubmitted."

with:

"The daemon owns \"what needs attention now\". Membership: a blocked track, a\nnon-responding track at the danger line, a track whose mapped session is\ngone, a malformed state value, a restart whose resume has not yet submitted,\nand a track at or below its wind-down threshold whose only busy evidence is a\nbackground command observed continuously past a bounded floor (per spec.md\n§\"Fail-soft posture\"). That last member is REPORT-ONLY: it MUST carry the\nsame coordinates and edge-triggering as every other member, and it MUST NOT\nauthorize any act."

No other clause changes. The cardinal rule, the supervision round, the
escalating wrap-up, the restart interlock, and §"Notify, never block" are
unchanged — the new report conforms to the last of these as already written,
and the first four are untouched because this obligation produces no act. No
`## ` heading is added, removed, or renamed, so no tests/heading-coverage.json
co-edit is required by this proposal.
