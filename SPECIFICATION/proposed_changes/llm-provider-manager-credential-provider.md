---
topic: llm-provider-manager-credential-provider
author: gpt-5.6-sol
created_at: 2026-09-10T16:01:28Z
spec_commitments:
  impl_followups:
    - id_hint: llm-provider-manager-operator-surface
      description: |
        After ratification, file and complete the implementation children under plan epic overseer-tm2qtw for the new llm-provider-manager surface in this repository, including the Anthropic factory-purpose slice, coexistence proof, and later browser-acquisition slice; update the maintainer-ruled shipped-surface count and its test from three to four only when the new operation ships; and link the separately filed livespec-orchestrator-beads-fabro consumer child rather than mixing repositories or spec and implementation tiers.
---

## Proposal: A distinct credential-provider operator surface

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Add llm-provider-manager as a distinct operator surface that owns the lifecycle of real LLM credentials and provisions one directly into each consumer's own execution environment, while leaving the existing caam-anthropic-loop account-rotation operation intact until the replacement has passed an explicit production proof gate.

### Motivation

The factory currently concentrates concurrent work on manually maintained Anthropic setup-token environment values even when other accounts have headroom. The existing account-rotation operation publishes identity only by design and cannot supply the separately-scoped inference credential the factory needs. The approved plan therefore requires a separate provider- and purpose-aware credential provider, forbids a request-path proxy, keeps the working caam loop running during the transition, and removes manual token-pool maintenance only after the new path is proven.

### Proposed Changes

Add a new `## LLM provider credential management` section to spec.md with these normative requirements.

1. `llm-provider-manager` MUST be a distinct operator operation, not a renamed mode of `caam-anthropic-loop`. It MUST acquire, validate, store, select, provision, revalidate, and replace LLM provider credentials for a requested provider, credential capability, and purpose. Its domain model MUST keep provider, credential kind, purpose, health signal, selection strategy, secret store, and provisioning target as independent axes; the first shipped adapter MAY support Anthropic alone, but the core contract MUST NOT encode Anthropic-only assumptions.
2. Provisioning MUST be direct and in place. The operation MUST write one real selected credential into the requesting consumer's isolated environment or credential file so the consumer authenticates directly to the provider as that account. The operation MUST NOT proxy, relay, rewrite, or otherwise enter the inference request path, and MUST NOT pool subscription credentials behind one network endpoint.
3. Purpose MUST be a policy partition over credentials and shared provider-account usage, not an assertion that two credential kinds on the same account have independent quota. Selection for one purpose MUST consult any shared-usage state needed to avoid exhausting capacity reserved for another purpose. The factory default MUST be consume-first across non-overlapping runs; a spread strategy MAY be selected explicitly.
4. Every credential MUST move through `acquiring`, `valid`, `suspect`, `revalidating`, `dead`, and `reacquiring` states. A provider-specific API validation probe MAY establish validity even though hard-coded provider UI flows are forbidden. A consumer MUST be able to report an authentication failure, rate limit, or provider outage against the provisioned credential; such a report MUST make the credential suspect before it can be selected again. Acquisition and re-acquisition for one provider account MUST be serialized so concurrent agents cannot replace the same credential. When no valid credential satisfies a request, the operation MUST fail closed with a retryable exhaustion result and MUST NOT provision a stale, suspect, or dead credential.
5. Browser acquisition MUST remain agent-discovered rather than provider-scripted. A research role MAY use web search but MUST have no secret access. An execution role MAY control the acquisition browser but MUST have no web-search capability and MUST NOT receive password or minted-token values in its context; local tools MUST type stored login material into the browser and persist newly minted tokens without echoing either value. The browser MUST be a headed, installed Google Chrome reached over CDP with an account-specific persistent profile, not bundled Chromium and not a cloud-account browser extension. CAPTCHA and 2FA walls MUST surface through operator attention with a bounded wait and give-up path.
6. `caam-anthropic-loop` MUST remain installed, runnable, and responsible for interactive Anthropic account rotation throughout the initial factory-purpose rollout. It MAY be deprecated only after `llm-provider-manager` has completed at least seven consecutive days of real factory use, has successfully provisioned two simultaneous test runs with distinct accounts under the explicit spread strategy, has completed at least one production selection or rotation without a manager-attributable authentication failure, and has demonstrated that every legacy `CLAUDE_CODE_OAUTH_TOKEN*` pool entry can be deleted without breaking factory authentication. A failed proof resets the consecutive-day soak.
7. Amend the existing `## Account rotation and quota supervision` section to name its operation as `caam-anthropic-loop` and state that its publication and no-credential clauses govern that identity-only operation. Its published selection record MUST remain credential-free and MUST NOT become a credential source. `llm-provider-manager` is the separate credential-provider boundary and MUST NOT read the published identity record as credential material or as authority to bypass its own validation and selection.

Add Gherkin scenarios to scenarios.md, with atomic `tests/heading-coverage.json` links when revised: (a) a factory consumer receives a real credential in its own isolated target and calls the provider directly while no manager process is in the request path; (b) the explicit spread strategy provisions two simultaneous runs with distinct valid accounts; (c) a reported 401 makes a credential suspect and prevents reselection until successful revalidation; (d) an exhausted pool produces a retryable refusal and writes no credential; (e) acquisition web research cannot access secrets and acquisition execution cannot read raw password or token values; and (f) the caam loop remains available until every production-proof condition has held.

## Proposal: Credential-provider records, privilege boundaries, and consumer protocol

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Define the stable records and privilege boundaries joining acquisition, storage, selection, and in-place consumers, and correct the existing account-rotation surface contract so it names the surviving operation rather than retired seats.

### Motivation

A provider-independent selection brain and separately implemented consumers cannot interoperate safely without a stable credential-record shape, an explicit local-provisioning result, and a failure-report boundary. The most sensitive values must not enter agent context, logs, audit records, or durable orchestration envelopes. The current account-rotation contract also describes itself as a peer of retired foreman and grooming seats, so the new operation must be introduced without propagating that stale surface map.

### Proposed Changes

Add `## The LLM credential-provider operation` to contracts.md and amend `## The account-rotation operation` as follows.

1. The new operation MUST ship one harness-neutral `llm-provider-manager` prose contract and one thin binding per supported harness; bindings MUST resolve and delegate to shared code, and every manifest that declares the operation MUST move in lockstep. The existing account-rotation surface paragraph MUST identify `caam-anthropic-loop` as the identity-only rotation operation and its current peers as `overseer` and `drain-backlog`; it MUST NOT name the retired foreman or grooming seats.
2. The manager MUST depend on a SecretStore port supporting get, set, list, and delete plus metadata. The initial backend MUST be replaceable without changing selection behavior. Two least-privilege stores MUST be distinct: an acquisition-secrets store containing provider login material and Gmail read-only authorization, readable only by local acquisition tools; and a provisionable-token store writable by acquisition and readable by the selection/provisioning brain. The brain's provisionable-token access MUST be read-only, it MUST NOT hold authority to read provider passwords or Gmail, and backend credentials MUST remain outside either agent context.
3. Each provisionable credential record MUST carry `provider`, `account_id`, `kind`, `purpose`, an opaque `value_ref`, `acquired_at`, optional `expires_at`, `last_validated`, `status`, and optional `previous_value_ref`. Raw credential bytes MUST live behind `value_ref`; they MUST NOT appear in the record, operation output, selection receipt, audit entry, log, trace, screenshot, or handoff. Store writes MUST produce an append-only local audit entry naming the record, actor, operation, and time but no secret value.
4. A provisioning request MUST name `provider`, required credential capability, `purpose`, a unique consumer-run identity, an isolated provisioning target, and an optional strategy override. Success MUST atomically write the selected secret to that target and return a credential-record identity, account identity, validation time, and purpose but no secret bytes. Failure MUST leave the target unchanged and return a typed retryable-exhaustion, invalid-request, store-unavailable, or provisioning-failed result. Selection MUST hold a non-blocking per-account lease while assigning concurrent runs, and a caller that cannot acquire the needed lease MUST retry selection rather than share a half-assigned credential silently.
5. A consumer-failure report MUST name the consumer run, credential-record identity, occurrence time, and one classification from authentication, rate-limit, provider-outage, or unknown, with an optional redacted diagnostic. Reporting MUST be idempotent for the same run, credential, time, and classification. Authentication MUST transition the record to suspect immediately; other classifications MAY feed the configured signal strategy but MUST NOT expose the credential.
6. Reads from a rate-limited secret backend MUST be cached for a bounded configured interval, defaulting to five minutes. A cache entry MUST be invalidated after a write, delete, failed validation, or consumer authentication report. Cache failure MUST degrade to a store read and MUST NOT make an unvalidated credential eligible.
7. The existing account-rotation published selection record MUST retain exactly its profile name, stable account identifier, and write time and MUST remain credential-free. No credential-provider request or response MAY reinterpret it as a credential reference.

Add contract-covering scenarios to scenarios.md, with atomic `tests/heading-coverage.json` links when revised: (a) a success writes the secret only to the isolated target and returns a secret-free receipt; (b) a failed provision leaves the target byte-identical; (c) the selection brain can read tokens but cannot read login or Gmail material; (d) a store write invalidates the cache and appends a secret-free audit entry; and (e) the account-rotation publication remains identity-only while the separate credential-provider operation provisions independently validated material.
