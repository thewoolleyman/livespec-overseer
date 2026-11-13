---
topic: enrolled-host-refresh-push
author: claude-opus-5-5
created_at: 2026-11-13T17:16:21Z
---

## Proposal: Refresh push keeps a reachable host current between deliveries

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

The push service MUST re-send the current delivery to a host that already holds it once that host's last successful push is older than half of `delivery.stale_after`, so a reachable host that holds the current delivery is never shown as `stale` merely because no new delivery was issued. The meaning of `stale` is unchanged: no successful push within `delivery.stale_after`, which remains the silent-host signal.

### Motivation

Work item overseer-r7pymu (plan epic overseer-iyfjbo, central-credential-service). Measured 2026-11-13: the push service never re-pushes an unchanged delivery (caam_delivery_push_state.due() returns False once a host's applied sequence reaches the current one), so nothing contacts a healthy host between deliveries and the status command shows it `stale` 900 s after each delivery. At 13:47Z gmktec, poweredge and hp read `stale` while holding the current sequence 7, applied at 13:03Z. That makes `stale` useless as the silent-host signal Scenario "A silent enrolled host is reported as stale" defines. The host-side apply step already answers a same-sequence push with `stale-sequence N host-applied N` without writing anything, and the push record already folds that answer as a successful push; what is missing is the obligation to send it.

### Proposed Changes

In SPECIFICATION/contracts.md, section "Enrolled-host delivery", paragraph **Retry and timeouts**, append after its second sentence:

> The service MUST also push the current delivery again to a listed host that already holds it whenever that host's last successful push is older than half of `delivery.stale_after`, so that a reachable host is never shown as `stale` between deliveries; a host's answer that it already holds that delivery MUST count as a successful push and MUST NOT change anything on the host.

In SPECIFICATION/scenarios.md, immediately after `## Scenario: A silent enrolled host is reported as stale`, add:

```
## Scenario: A reachable host holding the current delivery stays current between deliveries

Given a converted listed host that applied the current delivery and stays reachable

And no new delivery is issued for longer than `delivery.stale_after`

When the operator runs the status command

Then that host is shown as `current`, not `stale`

And its last successful push is more recent than half of `delivery.stale_after` ago
```

The new scenario's coverage row MUST be a spec-first TODO row in tests/heading-coverage.json owned by overseer-r7pymu, with a matching tests/heading-coverage-debt.json entry, until the code change lands.
