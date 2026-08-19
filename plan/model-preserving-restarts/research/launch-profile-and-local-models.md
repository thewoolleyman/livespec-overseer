# Why a restart must re-assert the track's model — and why "model" means launch profile

Reasoning note for the `model-preserving-restarts` plan thread (repo:
`livespec-overseer`). Maintainer-directed 2026-08-13: record the model
per track, READ it from the live session, and make it survive restarts —
including local-model sessions.

## The defect today (verified 2026-08-13 on current master)

Neither restart command carries a model, and the mapping registry has no
model field:

- Claude: `claude --dangerously-skip-permissions -n <topic>`
  (`overseer/_supervisor_launch.py`) — a restarted session takes the
  `~/.claude/settings.json` default, which is currently **`sonnet`**
  (changed from `opus[1m]` between 2026-08-02 and 2026-08-13). Most
  fleet sessions are hand-launched with explicit
  `--model claude-opus-5[1m]` (argv-verified), so every daemon restart
  is now a SILENT DOWNGRADE to Sonnet.
- Codex: `codex resume --dangerously-bypass-approvals-and-sandbox
  <uuid> "<kick>"` — the resumed thread takes the `~/.codex/config.toml`
  default (`gpt-5.6-luna` today); an explicitly non-default `-m` or
  `model_provider` choice is not re-asserted.

## The local-model case makes "record the model string" insufficient

Local-model sessions (repo `local-llm`, read 2026-08-13:
`/data/projects/local-llm/AGENTS.md`, `bin/claude-local-llm`,
`bin/codex-local-llm`) are launched through ENV WRAPPERS, not a model
flag:

- `bin/claude-local-llm` exports `ANTHROPIC_BASE_URL` (the Tailscale
  fleet router), `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_MODEL` (e.g.
  `macmini/qwen3-coder-next`), `ANTHROPIC_SMALL_FAST_MODEL`, gateway
  discovery + context-limit vars (`CLAUDE_CODE_DISABLE_1M_CONTEXT`,
  `CLAUDE_CODE_MAX_CONTEXT_TOKENS`, …), UNSETS the cloud credentials
  (`ANTHROPIC_API_KEY`, Bedrock/Vertex vars), and launches `claude`
  with `--bare --mcp-config …`.
- `bin/codex-local-llm` / the Codex `local-llm` profile select
  `model_provider` at process start.

Consequence: for a local-model track, a bare `claude -n <topic>`
restart does not merely change the model string — it **silently
converts the track from the local router to the cloud API** (different
base URL, different credentials, different context limits). The
converse also holds: the restart of a local track must NOT inherit the
daemon's own environment beyond the recipe (the daemon must not leak
its cloud credentials into a deliberately-local session).

So the per-track record is a **launch profile**, of which the model is
one field:

```
model_profile:
  harness: claude | codex | pi | …   # RECORDED string, extensible
  model: <string>            # e.g. claude-opus-5[1m], macmini/qwen3-coder-next
  wrapper: <path | null>     # e.g. /data/projects/local-llm/bin/claude-local-llm
```

**The harness is first-class and preserved** (maintainer-directed
2026-08-13): today the daemon infers claude-vs-codex from the live
pane at act time; under this change the RECORDED harness is the
dispatch key at every relaunch. The field is an open string in
STORAGE (so `pi` — whose wrapper `bin/pi-local-llm` already ships in
repo `local-llm` — and future harnesses need no schema migration), but
DISPATCH enumerates known harnesses and an unknown or unadoptable
harness is REPORT-ONLY: the daemon never guess-launches (aiming
`claude -n` at a codex/pi pane destroys the session — the existing
never-cross-runtimes invariant). Pi has no overseer adoption reader
yet; recording its harness+wrapper is the forward-compatible half.

Re-launch = wrapper + `--dangerously-skip-permissions` + `-n <topic>`
when a wrapper is recorded for a Claude-harness track (autonomy flags
are REQUIRED on every restart — the wrapper passes `"$@"` through;
omitting them stalls the fresh session on its first permission
prompt); Codex-harness: wrapper (or bare) `codex resume
--dangerously-bypass-approvals-and-sandbox <uuid> "<kick>"`;
`--model <model>` / `-m <model>` (or the Codex provider profile)
otherwise. **Model re-assertion on a wrapper track**: the claude
wrapper defers to inherited env (`ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-default}"`),
so the daemon re-asserts a recorded non-default model by PREFIXING
`ANTHROPIC_MODEL=<recorded>` onto the wrapper invocation — the
deference IS the mechanism.

## READING the profile from the live session (the "read it" directive)

Ranked sources, all same-user readable:

1. **`/proc/<pid>/environ`** — `ANTHROPIC_MODEL`, `ANTHROPIC_BASE_URL`
   (presence of a non-Anthropic base URL ⇒ local profile),
   `CLAUDE_CODE_*` overrides. For Codex, the profile/provider from its
   env/argv.
2. **argv** (`/proc/<pid>/cmdline`) — explicit `--model X` / `-m X`,
   and the wrapper is recoverable from the parent chain
   (`bash <wrapper-path>` ancestor) or from `ANTHROPIC_BASE_URL`
   matching the local-llm router.
3. **The statusline** (both TUIs render the model name) — verification
   only, never the primary source: display names ("Opus 5
   (1M context)", "Local LLM (…)") are not launch tokens.

Capture points: at ADOPTION (first join) and re-checked at WRAP-UP
time (the human may have `/model`-switched mid-session; the statusline
at wrap-up is the freshest truth — reconcile display name → launch
token via a small explicit mapping, fail-open to "record what argv/env
said" when the display name is unrecognized).

## Storage

A `model_profile` object on the mapping row (`~/.livespec-overseer.jsonl`)
— the store that already holds the only other facts that cannot be
rederived from the filesystem (custom resume line, threshold override).
Readers fail soft: a row without the field behaves exactly as today
(default-model relaunch), so the change is backward-compatible with
every existing row.

## What does NOT change

- THE CARDINAL RULE and the whole authorization/certification machinery
  — this thread touches only WHAT is launched, never WHEN.
- Codex resume-by-UUID (adoptability) — the profile adds provider/model
  re-assertion, it never replaces the UUID resume.
- No daemon-side model OPINIONS: the daemon records and re-asserts; it
  never chooses. A track with no recorded profile launches exactly as
  today.
- Secrets discipline: the profile must never store token VALUES
  (`ANTHROPIC_AUTH_TOKEN` is the wrapper's job; recording the wrapper
  path, never its secrets).

## Design points — ALL RESOLVED AND RATIFIED (kept as the reasoning trail)

> **These are no longer open.** Every point below was carried into the
> proposed change and ratified as `SPECIFICATION/history/v018` on
> 2026-08-18, each landing on the shape marked RECOMMENDED here. The
> section is kept because the *reasoning* is still the best record of why
> each shape was chosen — but do not read it as a decision still to make,
> and do not re-litigate a bullet without reopening the ratified clause.
>
> One point EVOLVED past what it says below, and the difference matters.
> The statusline bullet describes a mismatch as flagged "for report". As
> shipped it is stronger: a resolved disagreement between the pane's
> rendered model and the recorded baseline **surfaces and SKIPS the
> restart**, keeping the ready declaration, rather than merely reporting.
> The bullet's substance — no display-name-to-launch-token table, primary
> sources stay argv and environ — is unchanged and remains binding.
>
> What the statusline can and cannot actually do was measured after this
> note was written; see
> [`statusline-signal-characterization.md`](./statusline-signal-characterization.md).

- Whether `extra_env` is allowed at all, or wrapper-or-flag are the
  only two shapes (RECOMMENDED and now the drafted shape:
  wrapper-or-flag only; an env blob in JSONL rots and can leak
  secret-shaped values — the local-llm repo already maintains the
  canonical wrappers).
- Statusline display-name → launch-token mapping (RECOMMENDED: no
  display-name table at all — the wrap-up re-check re-reads
  argv/environ, the primary sources; the statusline is used only to
  flag a MISMATCH for report. A name table silently records stale
  values exactly when a mid-session `/model` switch lands on an
  unrecognized display name — the one case the re-check exists for).
- Env inheritance is NOT "verify later" — it is a named SET-OR-SCRUB
  rule: at every launch the daemon explicitly sets or unsets
  `ANTHROPIC_MODEL`, `ANTHROPIC_SMALL_FAST_MODEL`, and the
  `CLAUDE_CODE_*` overrides — set to the recorded values for a
  wrapper/local track, scrubbed for a cloud track. The wrappers'
  `:-` defaults mean a LEAKED value silently WINS over the wrapper's
  own default, so passive inheritance is the failure mode in both
  directions; the credential direction is already self-defending (the
  wrapper unsets cloud credentials itself).
- A STALE or CORRUPT profile (wrapper path missing/non-executable,
  model token the runtime rejects, harness/wrapper mismatch) is
  SURFACE + SKIP — the recovery module's existing idiom — never a
  silent fall-back to the default launch, which would reproduce the
  exact downgrade this thread exists to kill.

## Relations

- The day-one finding (2026-08-02: restart reverts hand-picked models;
  no ledger record was filed then) and the 2026-08-13 severity change
  (`settings.json` default now `sonnet` → active downgrade path).
- `plan/archive/resume-submit-integrity/` + `overseer-mgg` /
  `overseer-idxe` (read their live status from the ledger): the
  restart DELIVERY defects — orthogonal; this thread rides the same
  launch commands they harden.
- Repo `local-llm` (`/data/projects/local-llm`): owns the wrappers and
  the router; this thread must not duplicate its env recipe, only
  invoke it. Cross-repo read is one-directional (overseer reads
  local-llm's public wrapper paths; nothing in local-llm reads the
  overseer).
- Sweep surfaces at proposed-change time: `SPECIFICATION/spec.md`
  §"The restart" (and any clause stating the launch commands),
  `overseer/marker-protocol.md`, `.claude-plugin/prose/overseer.md`
  (the `start`/restart wording), `overseer/_supervisor_launch.py`,
  `overseer/_supervisor_recovery.py`, `overseer/registry.py`.
