---
topic: model-profile-admits-statusline-model
author: claude-opus-4-8
created_at: 2026-08-30T05:23:21Z
---

## Proposal: model_profile admits an optional statusline_model key

### Target specification files

- SPECIFICATION/contracts.md

### Summary

Widen the model_profile object contract so it admits an optional fourth key, statusline_model, carrying the rendered model-name verification baseline that the statusline mismatch-veto reads. The no-secret half of the clause is preserved verbatim. This makes the shipped model_profile shape and contracts.md agree, in the only direction v041 leaves coherent.

### Motivation

The shipped launch-profile code writes a fourth key, statusline_model, on every profile adoption and wrap-up refresh (overseer/_supervisor_statusline_model.py, overseer/_supervisor_restart_model_snapshot.py); contracts.md's model_profile clause enumerates exactly harness/model/wrapper and forbids any other key. Before v041 the key served only clause (ii)'s permissive MAY, so deleting it was a viable conformance fix. v041 (launch-profile-records-the-launch-model, ratified 2026-08-30 under overseer-0y69) added a MUST: surfacing must distinguish having READ the verification signal and found agreement from NOT having read it at all, for a track whose profile carries a recorded verification baseline. The only shipped implementation of that MUST reads model_profile[statusline_model], so deleting the key would now breach a spec MUST. The independent ratification reviewer of v041 recorded that widening the contract to admit the key is therefore the only coherent direction; overseer-5a4q's own re-tiering records the same. This is Route A (legalize the key): a pure contracts.md change, spec-tier and host-only.

### Proposed Changes

Amend the model_profile clause in contracts.md (the paragraph beginning "A row MAY additionally carry an optional `model_profile` object"). Two edits, and nothing else:

1. Extend the object shape to admit the optional key: change
     `{harness: string, model: string, wrapper: string|null}`
   to
     `{harness: string, model: string, wrapper: string|null, statusline_model?: string}`
   (the trailing `?` marks it OPTIONAL: a row MAY carry it and MAY omit it; a row without model_profile behaves exactly as today, unchanged).

2. Change the exhaustive-key prohibition from forbidding statusline_model to admitting it, WITHOUT touching the no-secret half. The sentence currently reads: "`model_profile` MUST NOT carry any key other than `harness`, `model`, and `wrapper`; it MUST NOT carry an environment-variable blob or any secret/token value -- the wrapper named by `wrapper` owns its own secrets." Amend only the first clause so the permitted key set is `harness`, `model`, `wrapper`, and the optional `statusline_model`, and add one sentence stating the key's purpose: statusline_model records the RENDERED MODEL NAME captured as the track's verification baseline -- the signal the statusline mismatch-veto reads to distinguish "verification read and in agreement" from "no baseline read at all," per spec.md's launch-profile surfacing obligation. The second clause -- "it MUST NOT carry an environment-variable blob or any secret/token value -- the wrapper named by `wrapper` owns its own secrets" -- MUST be preserved VERBATIM, and the added sentence MUST note that statusline_model holds a rendered model name and never credential material, so admitting it does not weaken the no-secret guarantee.

Everything else in the clause -- the without-model_profile equivalence, the stale-wrapper/harness read-side rule, and the surface-and-skip veto -- is unchanged. No behavior is added: the statusline mismatch-veto behavior is already ratified (v041) and already tested; this change only makes the stored shape the code already writes conformant with the contract.
