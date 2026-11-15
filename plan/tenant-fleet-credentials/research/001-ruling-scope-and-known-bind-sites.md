## The maintainer's statement of what done means

Yes, open them, every tenant in the fleet or adopter that is currently active or on the critical path for any priority now should get the fleet credentials and rotated via cred manager.  That's what you were saying, right?

## Definition of Done assertions derived from that statement

- A homelab factory dispatch authenticates to Anthropic with a CLAUDE_CODE_OAUTH_TOKEN read from a central-credential-service fleet setup-token slot in shared account 672283019497, and no homelab dispatch binds /homelab/v1/providers/anthropic/claude-code/oauth-token.
- A hetzner-xubuntu-info factory dispatch authenticates to Anthropic with a CLAUDE_CODE_OAUTH_TOKEN read from the same fleet setup-token slot, and no hetzner-xubuntu-info binding names the homelab tenant parameter.
- The cross-account read that delivers the fleet slot to homelab and hetzner-xubuntu-info resolves the slot inside the credential launcher itself, so no secret value is carried in an outer environment variable forwarded into a child launcher.
- Every fleet or adopter tenant that is active or on a priority critical path binds its LLM provider credentials only from central-credential-service fleet slots, and the published inventory shows each previously repo-owned provider binding as migrated or explicitly dispositioned.
- The credential manager (caam-anthropic-loop or llm-provider-manager) lists every migrated binding as a consumer of the fleet slot it rotates.
- token-spend-analysis monitoring reports spend for every migrated binding's fleet slot.

# tenant-fleet-credentials — ruling, scope and known bind sites (2026-11-15)

## Source

Maintainer ruling 2026-11-15 ~05:2xZ, recorded verbatim as a plan-scope-event on
`livespec-dev-tooling-6tgd2z` (legacy-coordinator-agent, comment 2026-11-15T05:20:51Z).
The statement above is that ruling, verbatim. The coordinator's confirmed reading:

- Scope: every fleet or adopter tenant that is active now, or on the critical path of any
  priority. homelab and hetzner-xubuntu-info FIRST, then a sweep for every other repo-owned
  provider binding.
- Each such tenant's provider credentials come from the fleet slots central-credential-service
  owns (shared-account setup-token slots, AWS account 672283019497), never from a repo-owned
  account.
- Rotation by the credential manager (caam-anthropic-loop / llm-provider-manager); monitoring by
  token-spend-analysis.
- The cross-account read route (an `hl` per-binding cross-account read, or launcher composition)
  is part of this plan, and this seat decides it with a recorded recommendation.
- Serves priority 1 (bootstrap-credentials-and-onboarding `hxi-vxsmdv` / central-credential-service
  `overseer-iyfjbo`) critical path: the homelab/hxi factory route for the writer key. No new
  priority line.

## Trigger

The tenant parameter `/homelab/v1/providers/anthropic/claude-code/oauth-token` (account
888508923089) hit its weekly limit at 2026-11-15 04:49Z; resets 2026-11-19 08:00Z. Blocked:
hl-kda4mx, hl-nl23hk, hxi-hemuly, hxi-hsgno2, hxi-533a6v, hxi-xwhhtn. Coordinator (05:03Z)
withdrew a stop-gap readers[] rebind because hl resolves only caller-account plain paths and
admits outer variables only as non-secret `--keep`, and the hxi root launcher passes through
LANG/LC_ALL/TERM only (measured by homelab-writer-revise). The interim ruling hand-lands
hl-kda4mx and hxi-hemuly; this plan is the durable fix.

## Known bind sites (measured 2026-11-15 on origin default branches)

| Tenant | File | Binding |
|---|---|---|
| homelab | `.livespec.jsonc` `credential_wrapper` (~l.204, main 30733aa) | `with-homelab-aws.sh --role homelab-workload hl param run --bind CLAUDE_CODE_OAUTH_TOKEN=/homelab/v1/providers/anthropic/claude-code/oauth-token` (plus BEADS_DOLT_PASSWORD, GITHUB_APP_ID, GITHUB_PRIVATE_KEY from /homelab/v1/...) |
| dispatcher (vps) | livespec-dev-tooling `ansible/inventory/host_vars/vps.yml` ~l.243 | tenant bind for homelab dispatch |
| hetzner-xubuntu-info | `config/credential-runtime.vps-source-only.json` | consumers `claude-code-oauth` and `hxi-runtime` bind CLAUDE_CODE_OAUTH_TOKEN from `arn:aws:ssm:us-west-2:888508923089:parameter/homelab/v1/providers/anthropic/claude-code/oauth-token` via `role/hxi-vps-source-reader` |
| hetzner-xubuntu-info | `config/shared-credential-authority.vps.json` | consumer `claude-code-oauth`, owner mi-homelab/homelab, readers hxi-vps / hxi-hetzner source-reader roles |
| hetzner-xubuntu-info | `config/credential-requirements.json` | CLAUDE_CODE_OAUTH_TOKEN listed as conditional dispatch variable |

Observation: the hxi launcher's runtime config already carries per-binding `source_account`,
`reader_role_arn` and `kms_key_arn`, and already reads 672283019497 parameters through
`role/hxi-vps-reader`. So for hxi the route is a binding retarget plus a readers[] grant; the
open design question is homelab's `hl` chain. See note 002 (inventory) and 003 (route decision).

## Constraints carried

- Never create or copy a secret value; credential creation stays the maintainer's.
- No secret passthrough through an outer environment variable.
- Every PR is a DRAFT for grade by legacy-coordinator-agent.
- Collaborators: central-credential-service (slot owner; ACCEPTED anthropic-4 as a second consumer),
  homelab-writer-revise, bootstrap-credentials-and-onboarding.
