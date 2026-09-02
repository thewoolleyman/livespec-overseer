# Plan: capture the RUNTIME model in the overseer launch profile

**Repo:** `/data/projects/livespec-overseer` (stdlib-only Python `control-plane-tool`)
**Type:** ONE interactive PR — governed spec change + implementation together.
**Authorization:** maintainer-authorized, including ratifying the spec proposal (`/livespec:revise`). Interactive change, so committing `SPECIFICATION/` edits is allowed (the no-factory-spec gate only blocks *factory*-authored commits).

---

## 1. Problem

The overseer daemon captures a track's model from **launch identity only**: `--model` in argv,
else `ANTHROPIC_MODEL` in `/proc/<pid>/environ`. A mid-session `/model` switch (e.g. Opus 4.8 →
Fable 5.1) updates **neither** argv nor the environ, so on the daemon's ready-restart the track
reverts to its **launch** model — silently undoing the runtime switch.

**Verified live 2026-09-02:** `ci-runner-pod-lifecycle-reliability` was switched to Fable 5.1 at
runtime (statusline showed `Fable 5.1`) but its recorded `model_profile.model` was
`claude-opus-4-8[1m]` (from argv), so the daemon restarted it as Opus 4.8.

## 2. Key finding — the fix fits the spec's own escape hatch

`SPECIFICATION/spec.md` §"The launch profile" (~lines 806–850) **deliberately** reverts to the
launch model *"where a session's current model is expressed in no permitted source"*, and
**enumerates the permitted sources** as `/proc/<pid>/environ` and argv/parent-chain — explicitly
barring the statusline as a token source (*"never through a display-name-to-launch-token lookup
table"*). So this is **spec-governed**, not a bug.

The fix uses the spec's own mechanism (*"re-check at wrap-up honors a mid-session change ONLY
where a permitted source expresses it"*): **add a NEW permitted source** — the Claude
**conversation transcript's latest top-level assistant-message `model` token**. Confirmed: the
transcript records `message.model` as a real launch **token** (e.g. `claude-fable-5-1`), not a
display name — so it satisfies the spec's "no display-name lookup" constraint.

## 3. Scope decisions (do NOT widen)

1. **Claude-only.** Do NOT touch Codex. Hard maintenance invariant (`overseer/.claude/CLAUDE.md`):
   the Codex reader (`codex_sessions.py`) **never reads rollout bodies**. Codex keeps launch-model
   behavior; file it as a separate follow-up and note it in the PR body.
2. **"Runtime model" = the latest TOP-LEVEL assistant message's token**, EXCLUDING sidechain /
   sub-agent messages (a session mixes models — e.g. this transcript had 190 `claude-opus-4-8` +
   14 `claude-fable-5-1` sub-agent turns). Confirm the sidechain marker (likely `isSidechain: true`)
   against a real transcript before relying on it.

## 4. Orientation reading (do first)

- `overseer/_supervisor_launch_profile_capture.py` — current capture. Around line 117–119:
  `model = _model_from_argv(argv=argv) or env.get("ANTHROPIC_MODEL")`.
- `SPECIFICATION/spec.md` §"The launch profile" and `SPECIFICATION/contracts.md` (model_profile
  object, ~lines 458–471).
- `overseer/.claude/CLAUDE.md` §"Launch Profile Preservation" and §"The RELAUNCH COMMAND is the one
  thing the beside-tests structurally cannot own" — **this subsystem has a documented P1 history**
  (silent model downgrades; unrunnable relaunch commands that destroyed panes). Tests must reach
  real behavior, not just assert rendered strings.
- `/data/projects/livespec-overseer/CLAUDE.md` — working discipline.
- A real transcript to confirm schema: `~/.claude/projects/-data-projects-livespec/*.jsonl` —
  verify assistant lines carry `message.model` as a token; find the sidechain flag.

## 5. Spec half

1. `/livespec:propose-change` — draft a proposal amending `spec.md` §"The launch profile": add the
   Claude transcript's latest top-level assistant-message model token as a **permitted source** for
   the profile's `model`, **preferred over argv/environ** when present + readable; argv/environ
   remain the **fallback**; statusline stays **verification-only** (unchanged); Codex out of scope.
   Preserve every other guarantee (set-or-scrub env rule, divergence surfacing, wrapper handling).
   Update `contracts.md` model_profile wording only if needed.
2. `/livespec:revise` — **accept** it (authorized) and snapshot a new `history/vNNN/`.
3. `/livespec:doctor` — resolve findings.

## 6. Code half

- `overseer/_supervisor_launch_profile_capture.py`: change model resolution to prefer a transcript
  token —
  `model = _model_from_transcript(...) or _model_from_argv(argv=argv) or env.get("ANTHROPIC_MODEL")`.
- New reader: resolve pid → `sessionId` + `cwd` via `~/.claude/sessions/<pid>.json`, then transcript
  path `~/.claude/projects/<cwd-slug>/<sessionId>.jsonl` (cwd-slug = cwd with every `/` → `-`).
  Read the **tail**, parse JSONL, take the LAST **top-level** (non-sidechain) assistant message's
  `message.model`. **Fail soft to None** on any missing/unreadable/absent case.
- **Inject the transcript reader as a seam** (mirror the existing `/proc` and `sessions_dir` seams)
  so the beside-tests stay hermetic and touch no real host state.
- Keep `statusline_model` capture unchanged. Stdlib-only.

## 7. Tests (red-green-replay)

Hermetic beside-tests:
- (a) capture PREFERS the transcript token over a differing argv/env model;
- (b) a mid-session model change (transcript's latest top-level model ≠ launch argv) is captured;
- (c) fallback to argv/env when the transcript is absent/unreadable;
- (d) sidechain/sub-agent messages are ignored when picking the latest model.

Follow **red-green-replay** (verified-RED commit, GREEN, replay). Never `--no-verify`. Use
`mise exec -- git …` so hooks fire. Iterate with `uv run pytest overseer -q`.

## 8. Landing / discipline

- Create the worktree with `just worktree-create runtime-model-permitted-source` — **NOT**
  `git worktree add` (a raw worktree can't commit `.py` or push here). Work in that worktree.
- `mise exec -- just check` must be **GREEN with nothing skipped** on the final commit (stdlib-only,
  pyright-strict, 100% statement+branch coverage, ruff, LLOC bands).
- Land worktree → PR → rebase-merge. Do not force-merge.
- Commit trailer:
  ```
  Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01Cr8UTpWnyCmCeyuQp9qKb9
  ```
- PR body ends with:
  ```
  🤖 Generated with [Claude Code](https://claude.com/claude-code)
  ```

## 9. Definition of done

PR open and green: new spec `history/vNNN/` version + `spec.md`/`contracts.md` edits, the capture
code preferring the transcript token, the four hermetic tests, `just check` green with nothing
skipped. Report: PR URL, new spec version, files changed, test names.

## 10. Follow-up (separate, not in this PR)

Codex runtime-model capture — deferred because the Codex reader must never read rollout bodies;
needs its own design (and possibly a different permitted source).
