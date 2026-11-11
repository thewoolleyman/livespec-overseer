# 005 — Factory credential remedy (P2 draft, 2026-11-11)

Requested by the coordinator (legacy-coordinator-agent, session ec00b770) on 2026-11-11, after anthropic-burn-mitigation's
read-only investigation of anthropic-0's unattributed weekly-quota drain. This note is a DRAFT for P2. Any token swap,
rotation or retirement goes to the maintainer through the coordinator. This seat changes no credential.

## What was measured (fingerprints only: sha256, first 12 hex; no value printed)

- **The factory is on anthropic-0, by design.** Factory runs do NOT use the bare `CLAUDE_CODE_OAUTH_TOKEN`. The dispatcher
  picks a pool slot for each dispatch with `select_factory_credential` and projects that choice into the run config. The
  dispatch journals, read by anthropic-burn-mitigation, show that admission chose `CLAUDE_CODE_OAUTH_TOKEN__ANTHROPIC_0` for
  every Claude-projecting dispatch since 2026-11-11T00:18Z. anthropic-1 was floor-skipped, and every other slot ranked lower
  on a later reset. That accounts for anthropic-0's weekly quota falling from 100% at 00:12Z to 88% at 08:42Z while
  telemetry attributed none of it: the ranker spends the soonest-expiring quota, as designed, with no paid credits.
- The bare `CLAUDE_CODE_OAUTH_TOKEN` that `with-livespec-env.sh` injects is `9223c8ccc926`, which equals
  `CLAUDE_CODE_OAUTH_TOKEN__ANTHROPIC_1` (anthropic-1's setup token). caam reads anthropic-1 as at 0% weekly until
  2026-11-12T17:00Z. The bare token is only `select_factory_credential`'s last-resort fallback, so nothing is swapped.
  The earlier inference that factory spend is anthropic-4, taken from caam's interactive selection history, was wrong.
- The seven per-account copies `CLAUDE_CODE_OAUTH_TOKEN__ANTHROPIC_0..6` are byte-identical in the homelab and livespec
  1Password Environments.
- The homelab Environment's `CLAUDE_CODE_OAUTH_TOKEN_1` is `6fd1f6914a0c`, which matches NONE of the seven. About 30 honeycomb
  mcp-remote processes on the vps hold it. Its account is unknown.
- Every process launched under `with-livespec-env.sh` on the vps carries `CLAUDE_CODE_OAUTH_TOKEN_0` (anthropic-0) in its
  environment. No code reads that name, so this is presence, not use.
- The shared SSM token `/homelab/v1/providers/anthropic/claude-code/oauth-token` could not be read from the vps under any
  profile. Its fingerprint, and so its account, is still unmeasured.

`6fd1f6914a0c` cannot be identified from this seat. The wrapper reads a 1Password Environment through a service account
(`op run --environment`), and that path exposes values, not per-variable creation or edit history. The service account's
daily quota is also shared across every tenant. The coordinator is asking the maintainer to read that variable's history in
the 1Password UI.

## The factory selection that exists today

The dispatcher already holds a factory selection mechanism. P2 builds on it rather than adding a second one. Read from
`livespec-orchestrator-beads-fabro` on the fleet launch build `5be0e21eac36` (v0.316.1): `_dispatcher_factory_account_selector.py`
and `_dispatcher_session_headroom_pool.py`, governed by that repository's `SPECIFICATION/scenarios.md` Scenario 278. Both modules
and their `_acp_session_headroom*` imports are byte-identical to `8348582ab96a` (v0.315.1).

1. **Admission slot.** Session-headroom admission assesses every injected `CLAUDE_CODE_OAUTH_TOKEN__*` slot. A slot qualifies
   when `headroom_skip_kind` finds no shortfall (floor, seven-day or projection; an unobservable reading counts as a floor
   skip). Qualifying slots rank by: a measured projection over an unavailable one; then the SOONER provider-reported window
   reset, "so quota does not expire unused", with a missing reset claim ranking last; then the larger remaining headroom; then
   the slot name. The chosen slot wins whenever it is still injected.
2. **Fallback.** With no admission choice, the selector reads caam's published interactive selection record and uses the slot
   `CLAUDE_CODE_OAUTH_TOKEN__<PROFILE>`. Failing that, it uses the bare unnumbered token and prints one warning line.

## Against the ratified Definition of Done

Plan assertion 5 is the maintainer's own wording, taken verbatim from the request in note 001: long-lived credentials injected
into factory runs are rotated centrally across every factory, **under a strategy independent of the interactive rotation**.
The coordinator first asked for the factory to "follow caam's selection". On reading assertion 5 it withdrew that, because
following it would put the factory and the interactive sessions on one account at once. That couples their failures, as the
2026-11-10 lifetime-cap outage did, and doubles the drain. The existing mechanism falls short of assertion 5 in two places:

- **(a) It does not exclude the interactive-active account.** Admission ignores caam's interactive pick rather than excluding
  it, and the fallback in step 2 follows that pick outright. So nothing stops factory and interactive spend landing on the
  same account. A future caam rotation onto anthropic-0 would do exactly that today.
- **(b) It is per dispatching host, not central.** Each dispatcher ranks the pool its own host injects. No one decision
  covers every factory in `/etc/livespec/fabro-factories.json` and the homelab workers.

## Proposed remedy (P2 end state, assertions 5 and 11)

No interim action is proposed. The factory is drawing quota as designed, so there is nothing to repoint.

1. **Close gap (a) in the existing ranker.** Make the interactive-active account a disqualification in admission, not a
   ranking input. Remove the step-2 fallback to caam's interactive pick, so a run with no admission choice refuses loudly
   instead of joining the interactive account. This is a change in `livespec-orchestrator-beads-fabro` and its Scenario 278,
   so it is a cross-repo slice in that tenant.
2. **Close gap (b) by moving the decision to the role holder.** The central instance publishes one factory selection, made
   by the same rule from the same observations the interactive decision reads. Every factory's dispatcher reads it at run
   start, through the credential_wrapper or the `llm-provider-manager-consumer` hook, in place of its local ranking. Runs keep
   their token for the run, so the selection changes only between runs.
3. **Probes and alerts are already specified.** P1-J (`overseer-hydiph`) implements **Factory credential probes** and
   **Push alerts** (spec.md §"Account rotation and quota supervision"). A factory credential at zero weekly becomes an alerted
   UNUSABLE verdict instead of a silent drain. Those probes stay observation only.
4. **One stored copy (assertion 11).** Each setup token is stored in exactly one place, and the factory and every consumer
   read that store. Retire `CLAUDE_CODE_OAUTH_TOKEN__ANTHROPIC_0..6` from the per-repo Environments, the stray homelab
   `CLAUDE_CODE_OAUTH_TOKEN_1` (`6fd1f6914a0c`) once identified, and the unread `CLAUDE_CODE_OAUTH_TOKEN_0` exposure on the vps.

## Routing

- Items 1 and 2 are new behaviour for this repository's spec, which states factory probes but no factory selection. They
  also amend the orchestrator's Scenario 278. When P2 is planned, file a proposal here through `/livespec:propose-change`,
  route the orchestrator half to that repository's spec, then file factory children under a carrier-map event for
  assertions 5 and 11.
- Every retirement in item 4 is a maintainer action, routed through the coordinator.
