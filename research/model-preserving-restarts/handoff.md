# model-preserving-restarts — handoff

> Cold-open handoff. It assumes you have read nothing and remember nothing,
> and that you may be a different model than the session that wrote it.
> Everything load-bearing is either stated here or cited by a path in §5.
> Do not treat chat history as a source of truth.

## 1. The primary goal

A restart must never change WHAT a track runs. Today neither restart
command carries a model and the mapping has no model field, so a
restarted Claude session takes the `~/.claude/settings.json` default —
**`sonnet`** as of 2026-08-13 — silently downgrading the fleet's
hand-launched `claude-opus-5[1m]` sessions; a restarted Codex thread
takes the config default provider/model. Worse, LOCAL-MODEL sessions
(repo `local-llm`) launch through env wrappers
(`/data/projects/local-llm/bin/claude-local-llm` exports the router
base URL, auth token, `ANTHROPIC_MODEL`, context-limit vars, and UNSETS
cloud credentials), so a bare relaunch silently converts a local track
back to the cloud API. The fix: record a per-track **launch profile** —
`{harness, model, wrapper|null}`, where **harness (claude | codex |
pi | …) is first-class and preserved**: the recorded harness is the
dispatch key at relaunch, stored as an open string (pi's wrapper
already ships in repo `local-llm`; no schema migration for future
harnesses) while dispatch enumerates known harnesses and treats an
unknown one as REPORT-ONLY, never a guessed launch — READ from the
live session
(`/proc/<pid>/environ` + argv/parent-chain as primary, statusline as
verification; captured at adoption, re-checked at wrap-up so a
mid-session `/model` switch is honored), stored on the mapping row, and
re-asserted at every launch: for Claude, wrapper +
`--dangerously-skip-permissions -n <topic>` when a wrapper is recorded
(the autonomy flag is REQUIRED on every restart; the recorded model is
re-asserted by prefixing `ANTHROPIC_MODEL=<recorded>`, which the
wrapper's `:-` deference honors), else
`--model <model>`; for Codex, `resume
--dangerously-bypass-approvals-and-sandbox <uuid>` with the provider
profile / `-m` as recorded.
Rows without the field behave exactly as today. Token VALUES are never
stored — a wrapper owns its secrets.

## 2. Where this thread stands

Created 2026-08-13. The epic anchor is **`overseer-bc55wx`**. Read live
status from the ledger — `list-work-items`, or the credential-wrapped
read `source /data/projects/1password-env-wrapper/with-livespec-env.sh
bd -C /data/projects/livespec-overseer show overseer-bc55wx` (a bare
`bd` fails with Access denied) — never from this file; this handoff
cites ids read-only and carries no work queue.

Done so far: the reasoning note (§5 item 1) carries the verified
defect, the local-llm wrapper analysis, the profile shape, the read
sources, and the open design points. NOT done: everything else.

## 3. The next action (exactly one), then the follow-on sequence

THE next action: author the spec proposed change via the
`/livespec:propose-change` operation against THIS repo's
`SPECIFICATION/` — the launch-profile record and its re-assertion are
contract-bearing (they change what a conforming restart MUST do and add
a mapping-row field) — resolving the reasoning note's open design
points in the draft (recommended dispositions are stated there:
wrapper-or-flag only, no `extra_env` blob; verify tmux env inheritance
for the daemon-launched cloud case), and sweeping every ratified
statement of the launch commands (`SPECIFICATION/spec.md` §"The
restart", `SPECIFICATION/contracts.md`, `SPECIFICATION/scenarios.md`,
`overseer/marker-protocol.md`, `.claude-plugin/prose/overseer.md`).

Follow-on, in order: (1) independent adversarial review by a
separately-spawned Fable-model agent, then `/livespec:revise` with the
maintainer; (2) file implementation slices as CHILDREN of
`overseer-bc55wx` via the `capture-work-item` operation (`depends_on`
the epic + the ratification; autonomy tier T2 — the fleet's
dispatch-after-ratification tier), implemented through the FACTORY
path — the `drive` operation (`impl:<id>`) or the Dispatcher drain —
never the in-session `implement` operation; (3) live-exercise evidence
per fleet discipline: one cloud track restarted preserving
`claude-opus-5[1m]`, one local-llm track restarted arriving back on the
router (verify `ANTHROPIC_BASE_URL` in the fresh process's environ,
not just the statusline), journaled on the accepting items.

Every repo artifact rides worktree → PR → rebase-merge.

## 4. The regression boundary

- The cardinal rule and all authorization/certification machinery are
  untouched: this thread changes WHAT is launched, never WHEN.
- Codex restart stays resume-by-UUID (adoptability); the profile only
  adds provider/model re-assertion.
- A mapping row WITHOUT a profile launches exactly as today (fail-soft;
  no migration required, no reader crash on old rows).
- The daemon never CHOOSES a model: record-and-re-assert only. An
  unrecognized statusline display name falls back to what argv/environ
  said — never to a daemon-side guess.
- No secret values in the mapping (`ANTHROPIC_AUTH_TOKEN` etc. live in
  the wrapper); the profile stores paths and model tokens only.
- Env inheritance is governed by an explicit SET-OR-SCRUB rule, not
  hope: every launch sets or unsets `ANTHROPIC_MODEL`,
  `ANTHROPIC_SMALL_FAST_MODEL`, and the `CLAUDE_CODE_*` overrides —
  set to recorded values for wrapper/local tracks, scrubbed for cloud
  tracks. (The wrappers' `:-` defaults mean a leaked value silently
  WINS; passive inheritance is the failure mode in both directions.)
- A stale/corrupt profile (missing wrapper, rejected model token,
  harness mismatch) is SURFACE + SKIP — never a silent default-launch
  fallback.
- An unknown harness is REPORT-ONLY: the daemon never launches a
  command it cannot certify matches the pane's runtime (aiming
  `claude -n` at a codex or pi pane destroys the session).

## 5. Read-first chain (all committed unless noted)

1. `plan/model-preserving-restarts/launch-profile-and-local-models.md`
   — the verified defect, the wrapper analysis, profile shape, read
   sources, open design points (this repo).
2. `overseer/_supervisor_launch.py` and `overseer/_supervisor_recovery.py`
   — the two launch surfaces the profile threads into (this repo).
3. `overseer/_registry_core.py` (the `Track` value type) and
   `overseer/_registry_store.py` (the JSONL row) — where the profile
   field actually lands; `overseer/registry.py` is only the re-export
   facade (this repo).
4. Repo `local-llm` at `/data/projects/local-llm` (SEPARATE repo, read
   there): `AGENTS.md` §"Client/provider workflow" and
   `bin/claude-local-llm`, `bin/codex-local-llm` — the wrapper recipe
   the profile records by PATH and must never duplicate.

Ledger ids to read live (never stored here): `overseer-bc55wx` (this
thread's epic), `overseer-mgg` and `overseer-idxe` (restart-leg
delivery defects — orthogonal, same launch surfaces).
