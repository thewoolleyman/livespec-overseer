---
topic: factory-routing-retire-legacy
author: claude-opus-5-5
created_at: 2026-10-24T06:08:25Z
---

## Proposal: Retire the legacy factory entry from the committed factory table

### Target specification files

- SPECIFICATION/constraints.md

### Summary

Remove the requirement that the committed `dispatcher.factories` table keep declaring `legacy`, the registry name of the hp-xubuntu factory instance being retired. `dispatcher.default_factory` still MUST name `petri`.

### Motivation

Fleet capacity coordinator ruling (gitops-fleet-capacity-monitoring, 2026-10-24) carrying the fabro-currency plan's Definition-of-Done assertion that hp carries no factory role in the committed fabro-hosts inventory: hp's legacy Fabro unit is being stopped and its factory role removed, which first requires every repository to stop declaring `legacy`. The requirement existed so that an open work item whose recorded `dispatch_factory` pin names `legacy` keeps resolving. A fresh dispatch never reads that pin (the orchestrator reads it only for a resume of the same run lineage), and the petri-factory-on-gmktec seat triaged every open legacy-pinned item across the fleet on 2026-10-24: none needs a run read from hp, because each closes through forge-held records.

### Proposed Changes

Apply exactly this edit; no heading changes, so tests/heading-coverage.json is unchanged. The same pull request removes the `legacy` entry from `.livespec.jsonc` and updates every test that asserts the committed table declares it.

```diff
--- a/SPECIFICATION/constraints.md
+++ b/SPECIFICATION/constraints.md
@@ -192,4 +192,2 @@
 renders as `/etc/livespec/fabro-factories.json`; a dispatch resolves a registry-backed entry
-from that file by name. `dispatcher.default_factory` MUST name `petri`. The committed table
-MUST continue to declare `legacy` as a registry-backed entry, so a recorded per-item
-`dispatch_factory` pin naming `legacy` still resolves.
+from that file by name. `dispatcher.default_factory` MUST name `petri`.
```

