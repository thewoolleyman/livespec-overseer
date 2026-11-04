---
topic: rebind-a-row-whose-stored
author: claude-opus-5-5:herdr-overseer
created_at: 2026-11-04T08:02:16Z
---

## Proposal: The vanished-pane rebind is a supervising-loop act and the read-only list path never performs it

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

State that the rebind of a row whose stored pane has vanished, together with the session-identity re-record it performs, is an act of the supervising loop only. The read-only list path MUST report the same classification the loop would report, and MUST leave the row's stored coordinate and recorded session identity unchanged. The existing rebind scenario gains one step that pins this.

### Motivation

overseer-m2hwyd implements the vanished-pane rebind. Its fourth Definition-of-Done bullet ("the read-only list path leaves the row's stored coordinate and recorded identity unchanged", folded in from overseer-iffpgw) was held as spec-change tier by the dispatch-stage tier judge on 2026-11-04 at 04:02Z, because no ratified clause states it. The bullet was removed from m2hwyd and routed to this proposal. The spec already treats the list path as read-only elsewhere: §"The terminal declaration" says every observation of a done track is read-only "exactly as the `list` path is", and the blocked-onboarding clause requires the read-only list path to report without sending. The rebind clause is silent on which surface may perform the rewrite. A listing that rewrote the mapping store would turn an operator's read into a durable coordinate and identity change, with no supervising round, no logged old/new pane pair, and no edge-triggered alert.

### Proposed Changes

In spec.md §"Supervised runtimes", append one sentence to the paragraph that begins "A row whose stored pane no longer exists on its recorded backend instance MUST be rebound", after "A done track and a discovered-but-unassigned plan never read unidentified-session.":

```diff
 stored coordinate is unchanged and the track reads unidentified-session with
 the refusing condition ambiguous panes, naming every candidate pane. A done
 track and a discovered-but-unassigned plan never read unidentified-session.
+The rebind, and the session-identity re-record it performs, is an act of the
+supervising loop: the read-only list path MUST report the classification the
+loop would report for such a row, and MUST leave the row's stored coordinate
+and recorded session identity unchanged.
```

In scenarios.md, under "## Scenario: A row whose stored pane is gone is rebound only to a single qualifying pane", append one final step:

```diff
 And when none exists, the stored coordinate is unchanged and the track reads session-gone
+
+And when the read-only list path observes that row instead, it reports the same classification and the stored coordinate and recorded identity are unchanged
```

The scenario keeps its heading, so its existing `tests/heading-coverage.json` link is unchanged. The implementation half, a list-path test proving the mapping store is not written, MUST be carried by a follow-up implementation child under plan epic overseer-uzvcbn once this proposal is revised in.
