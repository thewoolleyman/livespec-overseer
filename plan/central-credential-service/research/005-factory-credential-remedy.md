# 005 — Factory credential remedy (P2 draft, 2026-11-11)

Requested by the coordinator (legacy-coordinator-agent, session ec00b770) on 2026-11-11, after anthropic-burn-mitigation's
read-only fingerprinting. This note is a DRAFT for P2. Any token swap, rotation or retirement goes to the maintainer through the
coordinator. This seat changes no credential.

## What was measured (fingerprints only: sha256, first 12 hex; no value printed)

- `with-livespec-env.sh`'s bare `CLAUDE_CODE_OAUTH_TOKEN`, which every factory run carries, is `9223c8ccc926`. That equals
  `CLAUDE_CODE_OAUTH_TOKEN__ANTHROPIC_1`, so it is anthropic-1's long-lived setup token. Factory Claude spend bills
  anthropic-1. The earlier inference that factory spend is anthropic-4, taken from caam's selection history, was wrong.
- caam reads anthropic-1 as rate-limited, with 0% weekly left until 2026-11-12T17:00Z. Every factory run is therefore drawing
  on an account that is already exhausted.
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
daily quota is also shared across every tenant. Identifying it needs the 1Password account owner (the maintainer) to read
that variable's history in the 1Password UI, or a fingerprint of a candidate source: a revoked or re-minted setup token, or
an account outside the seven.

## The coordinator's framing against the ratified Definition of Done

The coordinator asked how the factory token should "follow caam's selection rather than a fixed setup token". Plan assertion 5
is the maintainer's own wording, taken verbatim from the request in note 001: long-lived credentials injected into factory runs
are rotated centrally across every factory, **under a strategy independent of the interactive rotation**. So the remedy is
central and dynamic, but it does NOT follow caam's interactive selection. Following it would put the factory and the
interactive sessions on the same account at the same moment. That couples their failures, as the 2026-11-10 lifetime-cap
outage did, and doubles the drain on whichever account is active. Changing that rule would need a maintainer ruling. This
draft keeps it.

## Proposed remedy

**Interim (maintainer decision, before P2 lands).** Repoint the bare `CLAUDE_CODE_OAUTH_TOKEN` away from anthropic-1 while that
account sits at 0% weekly. Use this criterion, not a fixed name: the per-account setup token with the most weekly headroom that
is NOT caam's current interactive account. Re-check it at each weekly reset. This is a one-line Environment change, and only the
maintainer makes it.

**P2 end state (assertions 5 and 11).**

1. **One factory selection, owned by the central instance.** On the role holder, the operation keeps a FACTORY SELECTION. It is
   chosen from the per-account setup-token pool with the same usage observations the interactive decision reads, under its own
   rule. The rule excludes the account that is interactive-active, ranks the rest by weekly headroom, and holds a selection
   until it nears exhaustion. Factory runs keep their token for the whole run, so the selection changes only between runs.
2. **Factories read the selection, not a fixed variable.** The credential_wrapper, or the dispatcher's per-run credential hook
   (`llm-provider-manager-consumer`), resolves the token the factory selection names at run start. This replaces the bare
   variable, and nothing in a factory pins an account.
3. **Probes and alerts are already specified.** P1-J (`overseer-hydiph`) implements **Factory credential probes** and
   **Push alerts** (spec.md §"Account rotation and quota supervision"). A factory credential at zero weekly becomes an alerted
   UNUSABLE verdict instead of a silent drain. Those probes stay observation only.
4. **One stored copy (assertion 11).** Each setup token is stored in exactly one place, and the factory and every consumer
   read that store. Retire `CLAUDE_CODE_OAUTH_TOKEN__ANTHROPIC_0..6` from the per-repo Environments, the stray homelab
   `CLAUDE_CODE_OAUTH_TOKEN_1` (`6fd1f6914a0c`) once identified, and the unread `CLAUDE_CODE_OAUTH_TOKEN_0` exposure on the vps.

## Routing

- Item 1 is new behaviour. The spec states factory probes but not a factory selection strategy. So it goes spec-first: file a
  proposal through `/livespec:propose-change` when P2 is planned, then factory children under a carrier-map event for
  assertions 5 and 11.
- Item 2 may cross into `livespec-orchestrator-beads-fabro` (the per-run credential hook). If it does, that half is a
  cross-repo slice in that tenant.
- The interim repoint and every retirement in item 4 are maintainer actions, routed through the coordinator.
