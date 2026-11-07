## The maintainer's statement of what done means

I want one caam instance running somewhere, on a single machine, to manage all of my account rotations on all hosts. Thgis is the only way there can be a single source of truth and monitoring for my accounts when I start using them in the distributed infra and on multiple machines. This includes managing token rotation when I run claude on other intances, like local laptops other than the hetzner vps. So this is probably a scope change and likely a new plan, but it has to work this way. Probably by making the existing caam a client-server archetecture, or giving it an API, or something. ... And keep in mind that this should still manage factory-independent rotations of injected credentials (because fabro keeps longer lived tokens, we already do this, but this will expand too, e.g. the multiple factories, and homelap factories, etc). And also consider the expansion of caam to manage codex and other provider tokens, we have already discussed this in other plans too. The coordinator should consider all of these and make a dedicated priotitization track for this (priority overall TBD, but with the parts that are blocking you prioritized appropriately based on your prioritization).

## Definition of Done assertions derived from that statement

- Exactly one running instance, on whichever machine holds the credential-rotation role, decides account rotation for every enrolled host, and no other host makes its own rotation decision.
- After the central instance rotates, Claude sessions on each reachable enrolled host authenticate directly to the provider as the selected account without a restart, and no process sits in the request path.
- One central view shows every managed account's limits, the account each enrolled host is using, and when each host last reported, and it reports a silent host as stale.
- A Claude session on an enrolled laptop follows central rotation the same way a session on a server host does.
- Long-lived credentials injected into factory runs are rotated centrally across every factory, under a strategy independent of the interactive rotation.
- Codex accounts rotate through the same central instance, and adding another provider requires no change to the topology.
- A compromised enrolled host's credentials cannot read the central store or another host's credential material.
- caam-anthropic-loop keeps running with its selection rules unchanged until the central instance is proven, and per-host caam is then deprecated with no host left unmanaged.
- Reassigning the credential-rotation role to another machine moves the central instance, and every enrolled host's client follows it with no change on that host.
- Provisioning and client configuration name the credential-rotation role and contain no hostname for it.

# central-credential-service: the requirement, and the prior art it extends

Opened 2026-11-07 by the seat `central-credential-service`, on the maintainer's direction relayed by
`legacy-coordinator-agent` (session 348c3d09). **The maintainer's requirement above is the authority for this plan**, in the
form that coordinator relayed it, including its `...` elision and its typos. When this plan drifts, that text wins over every
summary here. The eight assertions under it were derived by this session and await the maintainer's correction, recorded in
the first handoff entry.

## Maintainer ruling, 2026-11-07: the central host is a role

Verbatim, relayed by seat `bootstrap-credentials-and-onboarding`, which received it directly: "There is a machine ROLE that runs caam. Currently the VPS is this role. It may move in the future. Do NOT hardcode hostnames."

This session reworded the first derived assertion and added the last two to carry it. The statement above is unchanged.

## Hard constraints inherited from `llm-provider-manager`

Source: `plan/llm-provider-manager/research/001-design-intent-and-decisions.md`, `002-verbatim-discussion-transcript.md` and
`003-review-findings-and-revisions.md`.

1. **No request-path proxy.** Swap the real credential in place, so every session authenticates directly as one account.
2. **Least privilege everywhere.**
3. **`caam-anthropic-loop` keeps running, untouched, until the replacement is proven.** Never a window with a broken skill.
4. **No pre-scripted per-provider login flows.** Validation probes per credential kind are allowed; they are APIs.

Added by the coordinator for this plan: do not change caam's rules or its account selection (maintainer limits, rule E, R489).
The topology choice belongs to the maintainer (coordinator-duties section 9).

## Prior art this extends rather than competes with

- `llm-provider-manager` (`overseer-tm2qtw`): the axes (provider, kind, purpose, signal, strategy), the `SecretStore` port, the
  credential lifecycle and the only enabled target adapter, `isolated-run`. 20 of 23 children are closed. `overseer-v3tutb`,
  `overseer-psqcmg` and `overseer-p6pod4` are open, its pointer expired 2026-10-21, and on 2026-11-02 the coordinator held it as
  outside the current priorities.
- `livespec-orchestrator-beads-fabro` plan `llm-provider-manager-consumer`: the per-run factory credential hook.
- `caam-quota-resets` and `caam-generic-limit-windows`: the provider-agnostic limit and reset model the central view reports.
- `livespec-console-beads-fabro` plan `retire-overseer-and-redesign-control-plane-around-console`: decision D5, amended
  2026-09-09, keeps caam in this repo and allows it to generalize multi-provider here. The console does not own this service.
- `vps-info` plan `caam-snapshot-orphaning`: why a copied rotating refresh token dies. See note 002.

Options and the recommendation are in `research/002-topology-options.md`.
