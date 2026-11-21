---
topic: lpm-parameter-store-reference-records
author: claude-opus-5-5
created_at: 2026-11-15T07:51:04Z
spec_commitments:
  impl_followups:
    - id_hint: lpm-parameter-store-reference-backend
      description: |
        Implement the `parameter-store-reference` secret_store_backend in overseer/_lpm_*: register the backend name in _lpm_registry.REGISTERED_SECRET_STORE_BACKENDS; validate the new `parameter_store_references` configuration key in _lpm_config.py; reconcile one reference record per entry in a local owner-only metadata store under <manager-state>; resolve the slot value at final provisioning ONLY through the declared reader route (the installed shared-credentials launcher with the entry's consumer id); compare the value's sha256-12 with the record's recorded fingerprint; and refuse acquire, reacquire and replacement with the named `writer-owned-value` refusal. Red-green-replay; tests cover every new scenario.
---

## Proposal: A Parameter Store reference backend holds records that reference canonical SSM slots instead of a second value

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Register a second secret_store_backend, `parameter-store-reference`. Under it, each provisionable record's value lives in a canonical AWS Systems Manager Parameter Store SecureString slot written only by the fleet's dedicated write-only writer. The manager's record carries a reference to that slot (account, region, parameter name, reader consumer) and the slot value's sha256-12 fingerprint, never a value. Records are declared by configuration, not acquired by browser. Final provisioning reads the slot through the host's declared reader route at provision time, verifies the fingerprint, and writes to the isolated target with the existing atomic write. The manager never writes a value under this backend.

### Motivation

livespec v248/v249 make Parameter Store the single canonical source for fleet secrets, with no dual-backend fallback. The fleet's managed Claude Max setup tokens already live in seven canonical slots, `/gitops/v1/shared/providers/anthropic/claude-code/setup-token/anthropic-<n>` in homelab-gitops 672283019497, written only through homelab's `write-secret-as-writer.sh`. Under the only registered backend today (`onepassword`), llm-provider-manager can obtain a provisionable value solely by browser acquisition into its own 1Password values vault. That mints a new token per account, a maintainer credential act, and creates a second writable copy of a value whose canonical home is Parameter Store. The coordinator ruled (2026-11-15, plan central-credential-service, overseer-3evlnu) that the manager must REFERENCE the canonical slot read-only. Measured on hetzner-xubuntu 2026-11-15: the manager has never been initialized there (no configuration file, no state directory), so its factory-purpose provisioning cannot run at all today without either a browser mint or this backend. The host reader route already exists: homelab's committed consumer manifest declares consumers `anthropic-setup-token-0..6`, each readable by `hxi-hetzner-reader` through the installed shared-credentials launcher.

### Proposed Changes

spec.md §"LLM provider credential management": add one paragraph after the browser-acquisition paragraph.

**Parameter Store reference records.** When the configured `secret_store_backend` is `parameter-store-reference`, a provisionable record's value MUST NOT be stored by the manager. Each record MUST instead reference one canonical Parameter Store SecureString slot, which is written only by the fleet's canonical writer and never by the manager. Records under this backend MUST be declared by configuration and MUST NOT be created, replaced or reacquired by browser acquisition. A direct `acquire`, and any replacement or reacquisition the lifecycle would otherwise start, MUST be refused with the named `writer-owned-value` refusal, change nothing, and name the canonical writer as the only route that changes the value. Final provisioning MUST read the referenced slot only at provision time, only through the host's declared reader route, and MUST write it to the isolated target with the same single atomic write, receipt and lease rules as every other backend. The manager MUST NOT cache, copy or persist the value anywhere except that target.

contracts.md §"Configuration and state": add `parameter_store_references` to the permitted optional keys, default `[]`, and allow `parameter-store-reference` as a `secret_store_backend` value. Each entry MUST contain exactly `provider`, `account_id`, `kind`, `purpose`, `source_account` (12-digit AWS account id), `region`, `parameter_name` (absolute, beginning `/`), `reader_manifest` (absolute path of the host's installed shared-credentials consumer manifest) and `reader_consumer` (the consumer id that manifest declares for that parameter). The four identity fields MUST name a registered provider-and-kind row, and no two entries may share them. A non-empty `parameter_store_references` with any other backend, an entry naming an unregistered row, a duplicate identity, or an entry whose `reader_consumer` the named manifest does not declare for exactly that `parameter_name`, `source_account` and `region` is an invalid configuration for every command, refused with `invalid-request` and exit 2 before any lock, worker, store or target action.

contracts.md §"Secret-store privileges": add, after the `OnePasswordSecretStore` paragraphs:

The `parameter-store-reference` backend keeps credential METADATA in an owner-only local store under `<manager-state>/parameter-store-reference/`, using the same append-only logical-revision protocol, per-record lock, `effect_id` conditional set, audit-append pairing and mode rules as the 1Password metadata adapter. It has NO values vault and no value writer. A record's `value_ref` MUST be exactly `parameter-store:<source_account>:<region>:<parameter_name>`, and `previous_value_ref` MUST equal it whenever it is non-null. `value_generation` MUST be the RFC 4122 UUIDv5, in the URL namespace, of the string `<value_ref>@<parameter-version>`, where `<parameter-version>` is the slot's Parameter Store version read from the reader route's metadata. A record therefore changes generation exactly when the canonical writer writes a new version. Each record MUST also carry the additional member `value_fingerprint`: lowercase hex, the first 12 characters of the SHA-256 of the slot's value bytes, recorded at the last successful validation. This member is permitted ONLY for records under this backend, and it is not a secret.

Reconciliation: after mandatory recovery and before selection, every command MUST reconcile the configured entries. A missing record is created in `acquiring` with null value fields, and is then validated by one reader-route read and the registered validation adapter. A definitive success records `valid`, `last_validated`, `value_generation` and `value_fingerprint`. A definitive rejection records `dead` with `failure_reason` `provider-rejected`. Inconclusive leaves the record `suspect`. A record whose entry has been removed from configuration MUST become ineligible and MUST be tombstoned by the existing tombstone rules. A record's identity is never changed by reconciliation.

Final provisioning under this backend: the final-provisioning role MUST obtain the value only by running the entry's reader route, `shared-credentials launch --manifest <reader_manifest>` with consumer `<reader_consumer>` delivered as `systemd-credential-child-environment`, whose child is the manager's packaged target-writer companion. That companion is the ONLY manager-owned process permitted to hold the value in its environment, under exactly the one variable the manifest declares, and it MUST remove that variable from its own environment before any other action. This is the third and last permitted environment representation; the two service-account-token representations above are unchanged. Before writing, the companion MUST compute the value's sha256-12. When the slot's current version yields a `value_generation` different from the record's, or the fingerprint differs from the record's `value_fingerprint`, it MUST NOT write. Final provisioning then reports the record `suspect`, leaves the target byte-identical, and provision continues with recovery-candidate handling exactly as a mismatched revalidation does. On a match, it performs the existing single atomic target write. The provisioning receipt MUST additionally carry `value_fingerprint`. A reader-route failure (missing manifest, launcher refusal, AWS denial, timeout) MUST be `store-unavailable` with exit 4 and MUST leave the target byte-identical.

The `writer-owned-value` refusal is a pre-mutation refusal with exit 2 and `error_type` `writer-owned-value`. Its secret-free message names the canonical writer route, `write-secret-as-writer.sh`, as the only way to change the value.

scenarios.md: add

## Scenario: A Parameter Store reference record provisions the canonical slot value without a second copy

Given `secret_store_backend` is `parameter-store-reference`

And one `parameter_store_references` entry names an anthropic `claude-code-oauth` factory account whose canonical slot the host's reader manifest declares

When a factory-purpose provisioning request selects that record

Then the isolated target holds the slot's current value

And the receipt's `value_fingerprint` equals the sha256-12 of that value

And the manager's state directory and audit log contain no value bytes

## Scenario: A slot rewritten by the canonical writer is revalidated before it is provisioned again

Given a `valid` Parameter Store reference record whose `value_generation` was derived from slot version 3

And the canonical writer has since written slot version 4

When a provisioning request selects that record

Then the target is left byte-identical

And the record becomes `suspect` and is handled as a recovery candidate

## Scenario: Acquisition is refused under the Parameter Store reference backend

Given `secret_store_backend` is `parameter-store-reference`

When the operator runs a direct acquire for a configured identity

Then the manager returns the `writer-owned-value` refusal with exit 2

And no record, lock, worker or target changes

## Scenario: A reference entry whose consumer the reader manifest does not declare invalidates the configuration

Given a `parameter_store_references` entry names a `reader_consumer` that the named manifest does not declare for that parameter

When any manager command runs

Then it returns `invalid-request` with exit 2 before any lock, worker, store or target action

Revise MUST add `tests/heading-coverage.json` rows for these four headings in the same change, with `test` set to `"TODO"` and a reason naming the `lpm-parameter-store-reference-backend` implementation follow-up.
