# How a failed export must report — `.4` collides with `.2` unless it uses bands

ledger anchor `overseer-temi26`, child `overseer-temi26.4` (with `.2`)

Written 2026-08-22, before `.3` or `.4` is implemented. `.4` is the child this
plan's opening handoff called "the control that matters", and it has a design
collision with `.2`'s dedup fix that neither item records. Both of the obvious
implementations are wrong, in opposite directions, and the item's own framing —
"an exporter that silently drops events is worse than none, because it
manufactures confidence" — is what makes getting it wrong expensive.

## The collision

`.4` requires that "export failures (network, auth, HTTP non-2xx, partial
rejection) surface in `daemon.log` and on the operator attention surface, with
the rejected count".

`.2` requires that the alert dedup key on an event's STABLE identity, so a
condition that persists reports ONCE rather than once per tick — the fix for the
measured 7.3 MB log where a single stale track emitted ~2,000 near-identical
lines.

Put together naively, they contradict:

  - **Report every tick** and a Honeycomb outage reproduces the exact volume
    defect `.2` exists to remove — worse than the foreman case, because an
    unreachable endpoint fails on every event rather than every track.
  - **Report once, edge-triggered** and a persistent outage goes quiet after its
    first line. An operator who was not watching in that minute never learns the
    fleet stopped being observable. That is the "manufactures confidence" failure
    `.4` was written to prevent, arriving through the door `.2` opened.

A third temptation — exempt export failures from the dedup — is the worst of the
three, because it puts a permanent exception in the one mechanism that keeps the
log readable, and it will be copied.

## The repo already has the answer, and it is not a compromise

The established pattern for "a persistent condition must keep re-alerting without
flooding" is escalating AGE BANDS, each alerted exactly once under its own
condition key:

  - `_supervisor_config.py:173` — `BLOCKED_AGE_ALERT_BANDS = (4 * 3600.0, 24 *
    3600.0)`, with the comment recording that further daily bands derive from the
    same 24h cadence in the evaluator.
  - `_supervisor_liveness.py:55-89` — `surface_blocked_alerts` computes the
    crossed bands, tracks which have already been alerted in per-track state, and
    emits one alert per NEWLY crossed band under `condition=f"blocked-age-{band}"`.
  - The same shape appears for `ready-uncertifiable-age-{band}`.

That is why those conditions dedup correctly while `foreman heartbeat stale`
does not: the age is in the CONDITION KEY, at coarse granularity, instead of in
the message at per-minute granularity. Entry reports once; each escalation
reports once; the ticks in between are silent.

**So `.4` needs no new mechanism.** Report export failure as a banded condition —
entry on the first failure, then one alert per crossed band as the outage
persists. Bands for a telemetry outage should be tighter than the 4h/24h used for
a blocked human, since an unobservable fleet is a faster-moving problem than a
parked track; that value is `.4`'s to choose and should be a named constant beside
the existing bands, not a literal.

## The rejected count is a FIELD, not part of the identity

`.4` asks for "the rejected count". Under `.2`'s rule that monotonic values stay
out of the dedup key, the count must be a promoted field on the event, never part
of the condition string. A count in the key would defeat the dedup exactly the way
the per-minute age does today — and it would do so silently, because the resulting
flood would look like diligent reporting.

## Both directions, and what "both" has to mean here

`.4`'s acceptance is explicit that "a control proving only that success works
would pass a fix that swallows every failure". Two refinements the item does not
yet carry, both following from the shape settled elsewhere in this thread:

  - **An injected rejecting emitter proves the REPORTING path, not the
    TRANSPORT.** The seam that makes `.3` testable — the emitter passed as a
    parameter — also makes it possible to satisfy `.4` without ever exercising a
    real rejection. Necessary, not sufficient; hence the
    `acceptance:ai-then-human` label and the live control of a deliberately bad
    key against the real endpoint.
  - **"Unconfigured" must mean the ENDPOINT is absent.** `.3` degrades to
    local-only when unconfigured. If that degradation is keyed on the KEY being
    missing instead, then an endpoint configured with no key silently no-ops —
    which passes a naive reading of `.3` and violates `.4`, since Honeycomb would
    have rejected that request and the rejection is exactly what must be reported.

## Silence is the success signal, and it needs its own control

`.4` says a successful export is silent. That is right, and it is also the reason
the failure path cannot be proven by absence: a broken exporter that reports
nothing is indistinguishable from a working one that reports nothing. The
distinguishing evidence has to come from the OTHER side — spans present in
Honeycomb (`.3`'s acceptance) — or from a deliberately induced failure. A test
asserting "no error was logged" proves nothing about either.
