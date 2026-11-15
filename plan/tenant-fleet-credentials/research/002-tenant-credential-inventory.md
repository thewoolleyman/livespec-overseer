# 002 — tenant provider-credential inventory (measured 2026-11-15, hetzner-xubuntu)

Read-only sweep of every `~/workspace/*` clone (origin default branches), livespec-dev-tooling
`ansible/`, `/etc/livespec/` and the installed wrapper headers on hetzner-xubuntu. No secret value
was resolved. Rows marked UNVERIFIED could not be confirmed from this host (the vps and gmktec
wrappers are not installed here).

## LLM provider bindings

| tenant | active / critical path | bind site | env var | location | REPO-OWNED | rotation / attribution |
|---|---|---|---|---|---|---|
| homelab | priority-1 critical path (writer-key mint items hl-kda4mx, hl-nl23hk) | `homelab/.livespec.jsonc:198-205` (`hl param run --bind`) | bare `CLAUDE_CODE_OAUTH_TOKEN` | 888508923089 `/homelab/v1/providers/anthropic/claude-code/oauth-token` | **YES** | none; the bare name is the selector's sole slot: never rotated, unattributable |
| homelab (mirror) | — | livespec-dev-tooling `ansible/inventory/host_vars/vps.yml:226-243` | copy of the wrapper argv | `reconcile_runs_tenants` entry, `enabled: false` | mirror | consistency only; NOT the dispatcher's credential source |
| hetzner-xubuntu-info, vps profile | priority 1 (hxi-vxsmdv, hxi-7ituzy) | `config/credential-runtime.vps-source-only.json:23-27` (consumer `claude-code-oauth`), `:62-63` (`hxi-runtime`); `config/shared-credential-authority.vps.json:23-41`; `config/credential-requirements.json:102-108` | bare `CLAUDE_CODE_OAUTH_TOKEN` | the same homelab tenant parameter via `role/hxi-vps-source-reader` | **YES** | none |
| hetzner-xubuntu-info, hetzner profile | same | `config/credential-runtime.hetzner.json:60-66` (commit 7f98570) | bare `CLAUDE_CODE_OAUTH_TOKEN` | 672283019497 `/gitops/v1/shared/providers/anthropic/claude-code/setup-token/anthropic-4` via `hxi-hetzner-reader` | no (fleet slot) | pinned to anthropic-4 under the bare name: the selector cannot move it, and spend attributes to no slot name |
| dolt-server | UNVERIFIED activity | `.livespec.jsonc:113,118`; `runbooks/credentials.md:205-222` | bare `CLAUDE_CODE_OAUTH_TOKEN` | frozen one-time copy in the systemd-creds store `/var/lib/dolt-server/credentials` (vps) | **YES** (a copy outside every rotation) | none |
| openbrain | UNVERIFIED activity | `.livespec.jsonc:87` (`with-openbrain-env.sh`) | `CLAUDE_CODE_OAUTH_TOKEN` | openbrain's own 1Password Environment (presence UNVERIFIED) | **YES** | none |
| livespec family (livespec, -dev-tooling, -overseer, -orchestrator-beads-fabro, -orchestrator-git-jsonl, -driver-*, -console, -runtime, -website) | yes (priorities 1-3 live in dev-tooling and overseer; the orchestrator is the dispatcher) | `/usr/local/bin/with-livespec-env.sh` (1Password environment `fufpvkvatwkmqjzvilvfnemsue`) | `CLAUDE_CODE_OAUTH_TOKEN__ANTHROPIC_0..6` (+ stray bare copies) | the livespec 1Password Environment — a NON-central-credential-service copy of the slots | no, but a copy that can go stale | the dispatcher selects among the numbered slots; central-credential-service research 005 already plans to retire this copy |
| every dispatching host (Codex) | yes (Codex first in factory routing) | orchestrator `_dispatcher_codex_auth.py:84-94` | `$CODEX_HOME/auth.json` | host-local ChatGPT login | **YES** (host-local) | none |

GitHub App and beads bindings were inventoried too. homelab's org App (4688510) and its beads
password are tenant-owned BY DESIGN and are out of scope: they are not provider (LLM) credentials.

## The dispatcher contract that decides rotation and attribution

- `_dispatcher_factory_account_selector.py:89-100`: the injected pool is every non-empty
  `CLAUDE_CODE_OAUTH_TOKEN__*` variable; the bare `CLAUDE_CODE_OAUTH_TOKEN` counts only when no
  numbered slot is present. caam's `selected-account.json` profile `anthropic-N` maps to
  `CLAUDE_CODE_OAUTH_TOKEN__ANTHROPIC_N`.
- `_dispatcher_secret_channel.py` (`native_secrets`, petri): the dispatch still resolves the value
  from ITS OWN environment and stores it under the stable vault key `LIVESPEC_DISPATCH_<ENV>`
  before each launch. Petri holds no credential of its own.
- Therefore a tenant's dispatch gets exactly what its `credential_wrapper` injects. A tenant is
  rotated (caam) and attributed (token-spend-analysis, through the journal's chosen slot name) ONLY
  if its wrapper injects NUMBERED slot names.

## Registration surfaces a migrated binding must reach

1. homelab `infra/shared-credentials/consumer-manifest.json`: the slot `readers[]`, which is the source
   of the rendered `hetzner-xubuntu-info/config/shared-credential-authority.vps.json`. homelab's
   owner-deploy workflow applies it (`infra/shared-credentials/main.tf`).
2. The per-host launcher manifests (`credential-runtime.<host>.json`), installed to
   `/etc/hetzner-xubuntu-credentials/` and cross-checked by `scripts/credential_manifest_crosscheck.py`.
3. `config/credential-requirements.json`.
4. Each tenant's `.livespec.jsonc` `credential_wrapper`, plus the vps.yml mirror.
5. The dispatcher's slot-name contract above (numbered names).
6. caam: `~/.local/state/caam-usage-rotate/selected-account.json`; delivery hosts in
   `~/.config/caam-delivery/config.json`.
7. llm-provider-manager: `~/.config/livespec-overseer/llm-provider-manager.json`. Its only
   secret-store backend today is `onepassword` (`overseer/_lpm_registry.py:48-49`), so it cannot
   yet publish to the SSM slots (open on `overseer-3evlnu`).
8. Monitoring: no per-tenant registration exists. token-spend-analysis attributes spend by the
   dispatch journal's chosen slot name in the Honeycomb `llm-spend` dataset, so a bare-token tenant
   appears as an unattributed billing owner.

## Finding to route (not this plan's to fix)

The petri vault key is `LIVESPEC_DISPATCH_CLAUDE_CODE_OAUTH_TOKEN` for EVERY tenant that projects
that variable, and it is written fresh before each launch. If petri's vault is shared across tenants
(UNVERIFIED), concurrent tenant dispatches overwrite one another's value. Sent to
legacy-dispatcher-agent.
