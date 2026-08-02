# Research — problem 1: the overseer plugin is invisible to Codex

> **ANNOTATED 2026-07-28 after the groom. The cause below still holds and was
> not re-derived. Three things it says were later corrected BY MEASUREMENT, and
> are marked inline as `[SUPERSEDED]`.** This note is kept as the reasoning
> record — what was believed and why — so it is annotated, not rewritten.
> `handoff.md` carries the current state and always wins on a conflict.
>
> 1. **Recipe ownership is SPLIT**, not wholly `livespec-dev-tooling`'s (§The
>    cause).
> 2. **"Amend `.livespec.jsonc` as the first act" was re-cut** into A1 + A3
>    (§THE SCOPE SUPERSESSION). The supersession DECISION is untouched.
> 3. **A prerequisite this note never named:** the repo ships no Codex surface
>    at all, and the fleet convention for one is NESTED.

**Provenance: maintainer supervisor brief 17, root-caused with evidence before
this thread existed. Do NOT re-derive it.** This note records the cause so the
thread is self-sufficient, and adds only the two confirmations the PLAN itself
must act on.

## The cause

- `ensure-codex-plugins` — the recipe in the **fleet justfile, owned by
  `livespec-dev-tooling`** — hard-codes exactly three marketplaces: `livespec`,
  `livespec-driver-codex`, `livespec-orchestrator-beads-fabro`.
  **`livespec-overseer` is not among them.**

  > **[SUPERSEDED — ownership is SPLIT.]** Measured 2026-07-28:
  > `livespec_dev_tooling/fleet/_rows_local.py:22` and `justfile:76-78` both
  > state *"the plugin set is repo-specific, so each governed repo's recipe
  > stays the single source; a member lacking either recipe SKIPs that row."*
  > This repo's own hard-coded body is at **`justfile:127-142`**, and
  > `livespec-dev-tooling` **cannot edit it for us**. So the fix is two-part:
  > `livespec-dev-tooling` owns the shared derive-from-settings module
  > (**B1 → `livespec-dev-tooling-3nt9`**, filed), and each repo owns replacing
  > its own recipe body (**B2 → `overseer-vfz5v5`**). The Claude twin,
  > `ensure-plugins`, is ALREADY collapsed one line above it; `fleet/` has
  > `ensure_plugins.py` and no codex counterpart.
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

> **[SUPERSEDED — the ACT was re-cut in two; the DECISION was not touched.]**
> "Amend and record as the first act" collapses two different things. Only two
> statuses exist (`plugin_resolution.py`: `supported` / `exempt`), so amending
> "off exempt" means claiming `supported` — a claim that a command surface
> RESOLVES. This repo ships no Codex surface at all, so that claim would have
> been false, and `just check` would have certified it GREEN anyway: codex
> routes to a `DelegatedResolutionRunner` → SKIP, and the default
> `LIVESPEC_E2E_HARNESS=mock` never runs the live layer. Any non-empty
> `canonical_command` string passes.
>
> So the groom split it: **A1** (`overseer-4km4mj`) records the supersession
> NOW and keeps `exempt`, replacing the false `reason` string — which preserves
> exactly the archive-prune survival property this note demanded — and **A3**
> (`overseer-kju6wh`) flips to `supported` once a surface exists, and must add
> the repo-local `check-codex-skill-picker` in the same change so the green is
> load-bearing. **The maintainer's supersession decision stands unaltered; only
> the sequencing changed.**

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

> **[ADDED 2026-07-28 — the prerequisite this note never named.]** This
> acceptance is **unreachable** until a Codex surface exists to resolve. This
> repo has `.claude-plugin/` and **no `.codex-plugin/` anywhere**. Registering
> the marketplace would point Codex at a repo with nothing to load.
>
> That is slice **A2** (`overseer-vyie5q`). Its remedy was ALSO corrected: an
> early draft specified a repo-root `.codex-plugin/`, **a structure that exists
> in no fleet repo**. The measured convention is a **NESTED** `.codex-plugin/`
> INSIDE the existing `.claude-plugin/`, which hosts it —
> `livespec/.claude-plugin/.codex-plugin/plugin.json` and
> `livespec-orchestrator-beads-fabro/.claude-plugin/.codex-plugin/{plugin.json,skills/<op>/SKILL.md}`.
> The nested manifest mirrors its Claude sibling and adds
> `"skills": "./.codex-plugin/skills/"`; bindings carry `name` + `description`
> frontmatter only and must resolve `$PLUGIN_ROOT` explicitly; both harnesses
> read the same `prose/`; `marketplace.json` needs no change.
> `livespec-driver-codex` is a DIFFERENT repo shape and is not a model to copy.
> The full convention is recorded durably in this repo's `AGENTS.md`.
>
> **A correct diagnosis does not make the prescription correct.** This note's
> cause was right and was never re-derived; its remedy still had to be measured
> against the fleet before it could be trusted.
