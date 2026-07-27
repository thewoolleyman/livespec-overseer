# Research — problem 1: the overseer plugin is invisible to Codex

**Provenance: maintainer supervisor brief 17, root-caused with evidence before
this thread existed. Do NOT re-derive it.** This note records the cause so the
thread is self-sufficient, and adds only the two confirmations the PLAN itself
must act on.

## The cause

- `ensure-codex-plugins` — the recipe in the **fleet justfile, owned by
  `livespec-dev-tooling`** — hard-codes exactly three marketplaces: `livespec`,
  `livespec-driver-codex`, `livespec-orchestrator-beads-fabro`.
  **`livespec-overseer` is not among them.**
- Consequently `~/.codex/config.toml` carries no
  `[marketplaces.livespec-overseer]` and no
  `[plugins."livespec-overseer@livespec-overseer"]`.
- **Codex plugin enablement is HOST-WIDE** (`~/.codex/config.toml`), not
  per-repo like Claude's `.claude/settings.json`. That difference is why the
  Claude-side fix (a checked-in `extraKnownMarketplaces` + `enabledPlugins`
  entry per consuming repo, which `overseer-hbr.13` landed in twelve repos) has
  no Codex analogue and does not carry over.

## Confirmed here, because the plan acts on these two

| fact | state 2026-07-28 |
|---|---|
| `~/.codex/config.toml` plugin entries | `livespec@livespec` present; **no `livespec-overseer` entry of any kind** |
| `.livespec.jsonc` › `harnesses.codex.status` | **`"exempt"`** — goal 1 must amend this |

The exemption reason as it currently stands: *"the overseer's interactive pane
is driven from Claude Code; the daemon half is harness-neutral and is invoked
directly as `overseerd`, not through a Codex skill surface"*.

## Prior art for the DURABLE fix — not a fourth hard-coded line

**`livespec-c1k9.11`** (livespec core, CLOSED) — *"Collapse fleet
ensure-plugins recipes to the shared derive-from-settings…"*. The shape to
follow: derive the marketplace list from declared settings rather than extending
a literal list. Adding `livespec-overseer` as a fourth hard-coded entry would
work today and re-break the moment a fifth plugin ships.

This mirrors the Claude-side lesson already paid for on `overseer-hbr.23`: each
adopter's provisioner derives its commands from that repo's own committed
`.claude/settings.json`, *"so enabling another plugin needs no hook edit
anywhere"*. Same principle, different harness.

## THE SCOPE SUPERSESSION — it must be explicit, and it must land first

`.livespec.jsonc` declares codex **exempt**, and
`plan/archive/cutover-and-shipping/research/operator-surface.md` records that
exemption as a **settled ruling**. The archived `ship-overseer-to-fleet` thread
required an explicit maintainer decision to reopen it, and its goal 1 said
outright: *"Goal 1 does NOT silently reopen Codex scope; doing so needs an
explicit superseding maintainer decision."*

**That decision has now been given** (supervisor brief 17).

So the amendment is not paperwork — shipping Codex support while the repo's own
declaration says Codex is exempt would leave the repo self-contradicting, and
`.livespec.jsonc` is a gate input. **Amend `.livespec.jsonc` and record the
supersession as the first act**, citing brief 17 as the superseding decision.

> **Hazard the archived thread flagged and this thread inherits:** the ruling
> lives under `plan/archive/`. If that archive is ever pruned, the Codex
> exemption's provenance goes with it. Recording the supersession in
> `.livespec.jsonc` itself — rather than only in a plan file — is what makes
> this thread's change survive that.

## ACCEPTANCE — live, not config inspection

**`supervise-plan` (and `overseer`) must RESOLVE and RUN in a real Codex session
that is not this repo's.**

A `config.toml` containing the right strings is **NOT** evidence. That is
precisely the class of mistake that already fooled the predecessor thread once:
twelve merged `settings.json` entries while `installed_plugins.json` held zero
keys, recorded there as **"REGISTRATION IS NOT INSTALLATION"**. The maintainer
caught that attempt. Do not repeat its Codex twin.

Expect the Claude-side lesson to have a Codex analogue too: *"first exposure in
a repo takes TWO sessions"* — a plugin installed by session-start provisioning
cannot appear in that same session's list. Budget two sessions before calling a
negative.
