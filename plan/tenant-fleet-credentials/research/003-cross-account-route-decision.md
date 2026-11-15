# 003 — cross-account route: decision (2026-11-15)

Decided by this seat under the AGENTS.md decision-authority rules, and recorded for objection.

## Options weighed

- **D — dispatcher/petri-layer "config flip"** (coordinator reframe, ~05:3xZ): have every tenant's
  petri dispatch take the factory slot the dispatcher already rotates. Measured in the launch build
  (c1f8445f), there is no tenant-independent fleet credential source. The selector reads the
  dispatching process's environment, which for a tenant is its `credential_wrapper` output, and
  `native_secrets` only moves that value into petri's vault. A config-only flip does not exist.
  The code version of D (the dispatcher resolves the Claude slots from a fleet source while tenant
  wrappers keep supplying tenant secrets) is an orchestrator change against the "Worker credential
  projection" contract. It still needs a reader of the slots on the dispatching host, so it adds a
  release and a contract change without removing any IAM work. legacy-dispatcher-agent has been asked
  to confirm this from the code. If it finds a config-only path, this decision flips to D.
- **A — an `hl` per-binding cross-account read.** hl's source was deleted in homelab's purge
  (bd09eed, #958). Its path grammar (`crates/hl-core/src/path.rs`, ROOT `/homelab/v1/`) cannot even
  parse an ARN, it reads with one ambient identity (`plan.rs:214`), and the tool is scheduled for
  retirement. Rebuilding it would take days. Rejected.
- **B — homelab's wrapper runs through hxi's launcher.** This works, but it puts homelab's bindings
  in hxi's manifest and breaks per-tenant ownership. Rejected in favour of C.
- **C — launcher composition, one manifest per tenant (CHOSEN).** homelab's `shared-credentials`
  launcher (the one hxi already runs, `tools/shared_credentials/launch.py`) reads each binding by
  full ARN under its own reader role (`:68-108`), builds the child environment from scratch
  (`:111-117`, with passthrough limited to reviewed non-secret names), and execs any child. That
  satisfies no-passthrough by construction. hxi-hetzner already reads anthropic-4 this way.

## The rider that makes rotation and monitoring work

Whatever the launcher, a migrated binding MUST inject NUMBERED names,
`CLAUDE_CODE_OAUTH_TOKEN__ANTHROPIC_<n>`, one per slot the tenant is granted, and NOT the bare
`CLAUDE_CODE_OAUTH_TOKEN`. Only numbered names enter the dispatcher's selectable pool, follow caam's
published selection, and appear in the journal's chosen-slot attribution that token-spend-analysis
reads. hxi-hetzner's current bare binding of anthropic-4 moves to the numbered form under the same
rule.

## Change set (each a DRAFT PR for grade by legacy-coordinator-agent)

1. **homelab** `infra/shared-credentials/consumer-manifest.json`: add a readers[] entry `hxi-vps →
   role/hxi-vps-reader` on the granted anthropic slot(s) (central-credential-service accepted
   anthropic-4 as a second consumer). Add a homelab vps source reader for homelab's own three
   888508923089 parameters to `hosts.hxi-vps.reader_roles`. The owner-deploy workflow applies it.
2. **hetzner-xubuntu-info**: retarget `hxi-runtime` in `credential-runtime.vps-source-only.json` to the
   numbered fleet slot(s) via `hxi-vps-reader`, and drop the `claude-code-oauth` consumer of the
   homelab parameter. Rename the hetzner profile's bare binding to the numbered name. Update
   `credential-requirements.json`, the authority render, and the delivery digest pins.
3. **vps-info**: re-pin the hxi manifest digest, install homelab's manifest and shim, and run
   `install.sh apply` on the vps (no full re-provision).
4. **homelab**: add a committed `config/credential-runtime.vps.json` with consumer `homelab-dispatch`
   (three tenant bindings plus the numbered fleet slot(s)), a shim `with-homelab-credentials.sh`, and
   repoint `.livespec.jsonc` `credential_wrapper` to it. The hl argv stays in the comment block as the
   revert path.
5. **livespec-dev-tooling**: mirror the new wrapper in `vps.yml:226-243`, for consistency.
6. The other tenants (dolt-server, openbrain, the Codex host logins): each gets a disposition, either
   migrated under the same pattern or dispositioned with a reason, once its activity is measured.
7. Registration: caam delivery and selection already follow numbered names. llm-provider-manager
   publishing to SSM is gated on `overseer-3evlnu`. token-spend-analysis attribution follows the
   journal's slot name, and is confirmed per tenant from the `llm-spend` dataset.

Order: 1, then 2 and 3 (which unblock hxi on the vps), then 4 plus a value-free launch proof (the token
variable is present and non-empty, and the child has no AWS variables), then 5, then 6. Rollback:
revert the tenant's wrapper argv; hl and its seal are untouched.

## Ownership

homelab changes go through homelab-writer-revise's lane; it owns the hl/launcher measurement and the
writer-key items. hxi changes go through bootstrap-credentials-and-onboarding. Slot grants need
central-credential-service's quota OK. This seat authors PRs only where an owner hands it the lane,
and never creates or copies a secret value.

## Addendum, ~05:4xZ: the coordinator's code answer and interim rulings

legacy-coordinator-agent relayed legacy-dispatcher-agent's reading of c1f8445f. It CONFIRMS D's
premise as measured above: the factory credential source is the target repo's `credential_wrapper`
environment, and petri's vault is only a sink. Two interim measures were ruled outside this seat:

1. **homelab: `--keep CLAUDE_CODE_OAUTH_TOKEN__ANTHROPIC_4` in the hl argv** (homelab-writer-revise,
   DRAFT). This seat records an OBJECTION and does not count it toward assertion 3. `--keep` forwards
   an OUTER environment variable through hl, and hl's own README admits `--keep` for non-secret names
   only. That is the secret-passthrough shape this plan's brief rules out. It also makes homelab's
   token depend on whatever environment the dispatching process inherited, not on a reader grant
   the slot owner can audit or revoke. Acceptable as a stop-gap only. Option C replaces it.
2. **An anthropic-4 value copied into `/homelab/v1/providers/anthropic/claude-code/oauth-token`**
   (on the maintainer's standing authorization). This is a second stored copy outside the slot
   owner's rotation, and it goes stale the moment anthropic-4 rotates. Plan obligation: once C lands
   for homelab and hxi-vps, the tenant parameter has no reader. It is then reported to
   central-credential-service and homelab for retirement (the value's lifecycle stays theirs).

**hxi on the vps is this seat's first design item.** Of the two routes named (a sudoers `env_keep`
plus a manifest change, or the cross-account readers[] grant through vps-info
`services/hxi-source-credentials`), the decision is the readers[] grant: change-set steps 1 to 3
above. `env_keep` would carry a secret across the root boundary from the caller's environment,
which is the passthrough again. The readers[] route keeps the launcher's from-scratch child
environment intact.
