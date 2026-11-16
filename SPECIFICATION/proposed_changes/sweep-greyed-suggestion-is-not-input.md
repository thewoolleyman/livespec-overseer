---
topic: sweep-greyed-suggestion-is-not-input
author: central-credential-service
created_at: 2026-11-16T18:42:47Z
---

## Proposal: A greyed prompt suggestion is not unsubmitted text in a Remote Control input box

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Define the empty-input-box judgement used by the Remote Control re-issue and the keep-alive sweep so that Claude Code's greyed prompt suggestion does not count as unsubmitted text, read from the pane with colour attributes, while typed text still blocks.

### Motivation

Measured 2026-11-16 on hetzner-xubuntu: panes w5:p13 (master-green-external-outage) and wB:p5 (ccs-completeness-reviewer) were idle with no bridgeSessionId and showed only a greyed suggestion after the prompt mark for 40+ minutes, and the sweep reported them off_rc with actions=[] on every pass because _empty_box treats any text after the prompt as typed input. The same predicate exists in remote_control_reissue.py. A seat that shows a suggestion is never reconnected, which defeats the plan's DoD 4 on every herdr host. herdr pane read --format ansi renders the suggestion in the dim foreground (38;2;136;136;136 on the observed pane).

### Proposed Changes

### contracts.md, under `## Enrolled-host delivery`, in the paragraph `**Remote Control re-issue.**`

Insert the following sentences immediately after the sentence that ends "A pane whose input box holds unsubmitted text MUST be skipped, never typed into." and before the sentence that begins "It MUST send nothing to any other pane, including a pane that merely displays the notice text":

"A pane's input box holds unsubmitted text only when it holds text a person typed. Claude Code shows a greyed PROMPT SUGGESTION after the prompt mark of an input box that holds no typed text, and that suggestion is NOT unsubmitted text: the judgement MUST tell the two apart by reading the pane's text WITH its colour attributes, in a herdr pane read as `--format ansi`, where the suggestion is rendered in the dim foreground and typed text is not, and MUST treat dim text after the prompt mark as an empty input box. Text after the prompt mark that is not dim is unsubmitted text. A read that cannot show the colour attributes MUST be treated as holding unsubmitted text, so a pane is never typed into on a guess. This judgement is the one every clause that names an input box holding no unsubmitted text uses, including 'Remote Control keep-alive sweep'."

### contracts.md, the paragraph `**Remote Control keep-alive sweep.**`

The sweep paragraph already says the input box is judged as 'Remote Control re-issue' judges it, so it takes the sentence inserted above. Make the consequence explicit: after "whose input box holds no unsubmitted text, judged as 'Remote Control re-issue' judges it," add the words "so that a greyed prompt suggestion is not unsubmitted text,".

### scenarios.md, immediately after the scenario `## Scenario: An account switch re-issues Remote Control only where it stopped`

Add `## Scenario: An idle seat showing only a prompt suggestion is re-issued, and a seat with typed text is not`:

Given a herdr pane runs Claude Code whose session record has no `bridgeSessionId` and status `idle`, and whose input box shows only a greyed prompt suggestion, rendered in the dim foreground, after the prompt mark

And a second such pane whose input box holds text a person typed, rendered in the normal foreground

When the keep-alive sweep runs

Then the sweep sends the reconnect command followed by Enter to the first pane and names it in the journal

And it sends nothing to the second pane

And a pane read that carries no colour attributes is treated as holding unsubmitted text and is sent nothing

FLEET SCOPE: every herdr host the keep-alive sweep and the account-switch re-issue run on, local and over ssh. Both read the input box through the same judgement.

Implementation note (not spec text): `_empty_box` in overseer/remote_control_sweep.py and in overseer/remote_control_reissue.py both treat any text after the prompt mark as typed; both must read `--format ansi` and ignore dim text. Work item overseer-klzawj.

The revise commit must add the heading-coverage row for the new scenario heading, owned by overseer-klzawj, and stage the regenerated debt register, if this repo carries those gates.
