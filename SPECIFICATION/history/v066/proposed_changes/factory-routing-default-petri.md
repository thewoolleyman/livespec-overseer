---
topic: factory-routing-default-petri
author: claude-opus-5-5
created_at: 2026-10-22T22:12:57Z
---

## Proposal: Default factory names petri

### Target specification files

- SPECIFICATION/constraints.md

### Summary

Change the final sentence of constraints.md §"Factory routing" so `dispatcher.default_factory` MUST name `petri` instead of `legacy`, while `legacy` stays a declared registry-backed entry.

### Motivation

Maintainer direction R668 (relayed by the coordinator 2026-10-22) makes getting the Petri-era Fabro upgrade running on gmktec the priority and approves the blocking cutover steps; the cutover work-item is bd-ib-iud52v. The fleet registry rendered at /etc/livespec/fabro-factories.json already maps `petri` to the gmktec-xubuntu :32276 instance, and the orchestrator repository has already moved its own default to `petri`. This repository's clause pins `legacy`, so the config cutover cannot land without amending it. Keeping `legacy` declared lets an item whose recorded `dispatch_factory` pin names `legacy` keep resolving to its original server.

### Proposed Changes

In SPECIFICATION/constraints.md §"Factory routing", replace the final sentence

> `dispatcher.default_factory` MUST name `legacy`.

with

> `dispatcher.default_factory` MUST name `petri`. The committed table MUST continue to declare `legacy` as a registry-backed entry, so a recorded per-item `dispatch_factory` pin naming `legacy` still resolves.

The rest of the section is unchanged: every committed entry, `petri` included, MUST declare `"registry": true` and MUST NOT carry a `server` or `docker_host` value. A registry-backed entry MAY carry non-addressing keys such as `bin`, `secret_channel` and `environment`. The heading-coverage entry for `## Factory routing` MUST continue to point at the integration test that reads the committed `.livespec.jsonc`, renamed to assert the `legacy`+`petri` table and the `petri` default.
