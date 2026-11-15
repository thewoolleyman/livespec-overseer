---
topic: enrolled-host-delivery-host-ahead-state
author: claude-opus-5-5
created_at: 2026-11-15T07:51:47Z
---

## Proposal: A host ahead of the delivery counter gets a named state and pulls the sequence forward

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Adds an `ahead` STATE to contracts.md §"Enrolled-host delivery"'s closed list, for a listed host whose apply step refuses a delivery because the host has already applied a GREATER sequence than the service's counter (for example after the counter was lost or restored from an older copy). The service MUST then raise its counter above the host's applied sequence and issue the current account's delivery with the next sequence, so the host is resolved by moving FORWARD. A host ahead stays under the existing retry rule and is never exempted from it. The `stale-sequence` result line is required to name the host's applied sequence, which is what lets the service detect the case.

### Motivation

Work item overseer-ceehcd (plan overseer-iyfjbo), routed to propose-change by legacy-coordinator-agent's ruling of 2026-11-15 ~07:0xZ: contracts.md's closed STATE list and its retry rule forbid the behaviour as the item first stated it, so no code lands before ratification. Today a host ahead of the counter folds to `failed` in the push record (overseer/caam_delivery_push_state.py record_result) and is re-pushed the same refused sequence every `delivery.retry_interval` with no end, and the status command misreports it as a failure. The item's original remedy, to stop retrying such a host, would breach the retry rule ("MUST retry a host whose last push failed or did not reach it at least once per `delivery.retry_interval`"). This proposal resolves the case without any exemption: the counter, not the host, is wrong, so the service moves its counter forward past the host. That is consistent with spec.md **Deliveries never move backwards**, whose sequence already continues across a move of the role, and it is the one way a counter loss can be repaired without ever moving a host back.

### Proposed Changes

### spec.md §"Enrolled-host credential delivery", **Deliveries never move backwards**

Append one sentence:

> When the service learns that a listed host has applied a delivery sequence greater than every sequence the service itself has issued, the service MUST continue the sequence above that host's applied sequence, so that every later delivery is again greater than every sequence any listed host holds.

### contracts.md §"Enrolled-host delivery", **The apply step**

1. Replace the `stale-sequence` bullet with:

> - It MUST compare the delivery's sequence with the APPLIED SEQUENCE recorded on the host in an owner-only file beside the credential file, and MUST change nothing and report `stale-sequence` when the delivery's sequence is not greater. An applied-sequence file that is absent, empty, or holds anything other than a non-negative integer MUST be read as applied sequence 0.

2. Replace the result-line bullet with:

> - It MUST print exactly one result line, containing no credential material, naming one of `applied`, `stale-sequence`, `not-converted` or `failed`, the sequence it applied or refused, for `stale-sequence` the host's applied sequence in the form `stale-sequence <sequence> host-applied <applied>`, and, for `failed`, the reason.

### contracts.md §"Enrolled-host delivery", **Retry and timeouts**

Append:

> A push whose result is `stale-sequence` naming a host-applied sequence GREATER than the sequence pushed is a HOST AHEAD. A host ahead MUST NOT be recorded as a failed push and MUST NOT count as a successful push. On a host ahead, the service MUST write its delivery-sequence counter to the greatest host-applied sequence it has observed, as **Service stores** requires for any counter write, and MUST then issue the current delivery with the next sequence to every listed host. A host ahead MUST remain subject to the retry rule above: until it reports `applied` or holds the current delivery, the service MUST push it again at least once per `delivery.retry_interval`, and MUST NOT exempt it from retry for being ahead. A host's answer that it already holds the delivery, `stale-sequence` naming a host-applied sequence EQUAL to the sequence pushed, remains a successful push as stated above.

### contracts.md §"Enrolled-host delivery", **Service stores**

In the PUSH STATE bullet, after "the last result its apply step reported", insert "(including the host-applied sequence of a host ahead)".

### contracts.md §"Enrolled-host delivery", **Status command**, STATE list

Insert `ahead` as the SECOND value, so the list and its precedence read:

> - `not-converted`: the host's last result was `not-converted`;
> - `ahead`: the host's last result was `stale-sequence` naming a host-applied sequence greater than the service's current delivery sequence;
> - `expired`: ...;
> - `stale`: ...;
> - `lagging`: ...;
> - `current`: none of the above applies.

For a host whose STATE is `ahead`, the status command MUST also show the host-applied sequence it reported. The STATE list MUST remain closed: a value outside it is a defect.

Rationale for the position: `ahead` means the service's own record of what the host holds is behind the host, so `expired` and `lagging`, which are computed from that record, are not meaningful for it; and a host ahead was reached, so it is not `stale`.

### scenarios.md, new scenarios beside "A stale delivery cannot move a host back"

```gherkin
## Scenario: A host ahead of the delivery counter is shown as ahead, not failed

Given the role holder's delivery-sequence counter is 31
And a listed host has applied delivery sequence 40

When a push carrying delivery sequence 31 reaches that host

Then the apply step reports `stale-sequence 31 host-applied 40` and changes nothing on the host
And the status command shows the host's STATE as `ahead` with host-applied sequence 40
And the push record does not mark the host as a failed push

## Scenario: A host ahead moves the sequence forward, never the host back

Given the role holder's delivery-sequence counter is 31
And a listed host has applied delivery sequence 40

When the delivery service records that host as ahead

Then it writes its delivery-sequence counter as 40 before pushing again
And it issues the current account's delivery with sequence 41 to every listed host
And that host applies sequence 41 and its STATE becomes `current`

## Scenario: A host ahead is never exempted from retry

Given a listed host is recorded as ahead
And the push of the next delivery to that host does not reach it

When `delivery.retry_interval` passes

Then the delivery service pushes that host again

## Scenario: A corrupt applied-sequence file reads as zero

Given a listed host whose applied-sequence file holds non-numeric content

When a push carrying delivery sequence 5 reaches it

Then the apply step applies the delivery
And it prints `applied 5`
```

These scenario headings are new, so revise MUST add `tests/heading-coverage.json` entries for them in the same change, with tier and `work_item` `overseer-ceehcd`; the `test` MAY be `"TODO"` naming the overseer-ceehcd implementation. Revise SHOULD also amend overseer-ceehcd's first Definition of Done bullet to the ratified behaviour (the counter moves forward; the host is not exempted from retry).
