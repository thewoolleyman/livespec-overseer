# Operational lessons from a live foreman session (2026-08-17)

Captured from a maintainer-directed foreman session (`livespec-foreman` tmux)
that ran for an extended period across multiple tracks (planning-lane-redesign,
fleet-ci-runner-pool, an ad-hoc revise-select-proposal plan), and was asked to
restart with clean context. These are gaps in the SKILL's own instructions, not
one-off mistakes worth forgetting — a fresh foreman session hit several of them
more than once before self-correcting, meaning the skill/prose did not carry
the lesson forward. Filed as research input for prose/foreman.md (and, where
noted, prose/supervise-plan.md) additions, not as a change itself.

## 1. Verification discipline: never trust inference as evidence

Twice in one session, the foreman reported a picker "resolved" or a claim
"landed" based on an activity spinner or an empty prompt line, and was wrong
both times — a NEW picker had appeared, or a message never actually submitted
(stuck as unsent pasted text in the composer). The correct check is always
content-based, not proxy-based:

- A picker is genuinely resolved only when the pane content no longer contains
  its markers (the `☐` checkbox glyph, "Enter to select" footer) — check this
  explicitly after every injection, not "it looks idle now."
- A ledger claim ("filed", "dispatched", "closed", "merged") is only real once
  independently re-queried at the source (`bd show <id> --json`, `gh pr view`,
  `gh run view`) — never accepted from a peer session's or subagent's report
  alone, however detailed and well-formatted that report is.
- Fabro/Dispatcher outcomes specifically: wait on the JOURNAL's `outcome`
  event, never the drive command's own summary or exit code (see the existing
  `.ai/dispatcher-drain-operations.md` in the livespec repo for the fleet-wide
  version of this rule — it is not foreman-specific, but foreman needs to know
  it applies here too).

## 2. Beads/bd JSON field-name traps

Two false negatives happened from guessing field names instead of dumping the
raw JSON structure first:

- A work-item's dependency is under `dependencies[]` with a `dependency_type`
  field (e.g. `"blocks"`, `"parent-child"`), NOT a top-level `depends_on` key.
  Checking `depends_on` on a real dependent item returns `None` even when the
  dependency is correctly recorded.
- A ledger comment's text is under the `text` field, not `body` or `content`.
  A query using the wrong key returns an empty match, which reads as "the
  evidence isn't there" when it actually is — the single most dangerous shape
  of this trap, since it produces a false "not found" that could block a
  legitimate action (e.g. an archive-gate check) on a false premise.
- `bd comment list` / `bd comments list` return an empty result even when
  comments exist (a known, separately-tracked CLI defect — see
  `.ai/beads-gaps-workarounds.md` in the livespec repo). The working form is
  `bd comments <id> --json`.

General rule for foreman: when a `bd`-sourced query returns empty and emptiness
would be surprising, dump the raw JSON and inspect actual key names before
concluding absence.

## 3. tmux messaging: quoting breaks, and picker keypresses are a distinct mechanism

`tmux send-keys -l '<message with an apostrophe>'` reliably breaks Bash's own
shell-quoting (the literal-flag string still gets shell-parsed by the Bash tool
invoking `tmux`), producing garbled or partially-executed commands. Apostrophes
are common in ordinary English prose ("don't", "it's", "session's"), so this is
not an edge case — it hit repeatedly.

Working pattern: write the message to a scratch file, then
`tmux load-buffer -b <name> <file>` followed by `tmux paste-buffer -b <name> -t
<session>`, then a separate `tmux send-keys -t <session> Enter` to submit. This
sidesteps shell quoting entirely since the message content never passes through
a shell command line.

Separately: a numbered structured picker (`☐ ...` with `1.`/`2.`/... options) is
answered by a bare keypress send (`tmux send-keys -t <session> 1` then a
separate `Enter`), not by typed prose — prose sent to an open picker queues as
free text behind it rather than selecting an option.

## 4. Plan-authoring writes are tracked-file writes: worktree discipline applies

`livespec_orchestrator_beads_fabro.commands.plan.create_thread` (and any
Write-tool call adding a research note to an existing thread) writes directly
into whatever `project_root` you pass it, with no built-in check for whether
that path is a primary checkout or a worktree. It is easy to invoke this
against `/data/projects/<repo>` directly and only notice the mistake via
`git status` afterward. This session did exactly that once (recovered cleanly:
moved the untracked content out, verified primary was clean, redid the write in
a proper worktree, committed/pushed/PR'd from there). Foreman should treat
every plan-authoring filesystem write as a tracked-file write requiring the
same worktree -> PR -> merge discipline as any other repo change, and check
`git rev-parse --git-dir --git-common-dir` on the target project root BEFORE
calling `create_thread` or writing a research note, not after.

## 5. `create_thread` does not create the `epic.md` write-once anchor

Per the ratified spec (this repo's own `SPECIFICATION/spec.md` clause on the
Planning Lane, mirrored in the livespec repo's spec.md:375) and per the
daemon's own supervisor-restart certification logic
(`_migrated_supervisor_epic_certifies` reading `plan/<topic>/epic.md`), each
plan thread's directory needs exactly one write-once filesystem anchor naming
the ledger epic id. `create_thread` in
`livespec_orchestrator_beads_fabro/commands/plan.py` creates the research note
and the ledger epic record, but does NOT write `plan/<slug>/epic.md`. A thread
created purely via `create_thread` has no filesystem anchor at all until
someone notices and writes it by hand (this session did, for a
freshly-created thread, using the same minimal template the daemon's
certification heuristic expects: an `# Ledger epic anchor` heading, the epic
id, and one sentence naming the ledger-comment handoff medium).

This is a real gap in `create_thread`'s own contract, not merely a foreman
process note — filing a proper fix is the child work-item below, on the
`livespec-orchestrator-beads-fabro` tenant (the repo that owns `plan.py`), not
on `livespec-overseer`.

## 6. Manually killing a session leaves THREE separate durable-state surfaces stale

When a supervisor or worker's tmux session is killed directly (rather than
wound down through the daemon's own certify/respawn cycle — done once this
session as an emergency unstick), at least three independent state surfaces
can be left describing a session that no longer exists, and each needs its own
correction:

1. `tmp/overseer/<topic>/.overseer-state` (or the `-supervisor`-suffixed
   sibling) — the session's own ready/blocked/winding-down declaration file.
2. `tmp/overseer/<topic>/.supervisor-state` — the richer YAML obligations/
   objective file, which can still show `supervision_active: true` with an
   open obligation and a `wake_producer` pointing at a background task pid
   that died with the killed session.
3. `~/.livespec-overseer-stamps.json`'s round record for that topic — can
   retain a stale `session_identity` or an open `voided_at`/wind-down flag
   that produces a daemon status note like "vanished during an open
   wind-down" even after the other two surfaces are corrected, since it is a
   distinct signal the daemon reads separately.

Fixing only one of the three leaves the daemon's live status view partially
stale and can read as a fresh anomaly on the next tick.

## 7. A freshly-launched `claude` session is not automatically SendMessage-addressable

Launching `claude` fresh in a new tmux pane registers it under a generic
auto-assigned peer name (observed pattern: `livespec-NN`), not the tmux
session's own name. If foreman needs to reach that session later via
SendMessage by a predictable name, it must send `/rename <desired-name>` as
part of (or immediately after) the session's first prompt — the tmux session
name and the SendMessage-addressable name are two independent things.

## 8. Loop-resume after `hard-tick-budget` needs a manual counter reset

The foreman wrapper's own hard tick budget (12 ticks, per
`foreman_runtime.DEFAULT_HARD_TICK_BUDGET`) is a durable counter in
`tmp/overseer/foreman/runtime.json` (`tick_generation`, `stable_ticks`) with no
exposed reset action in the shipped skill surface. Resuming the hourly loop
after hitting `hard-tick-budget` requires editing that file directly
(`tick_generation: 0`, `stable_ticks: 0`) before the next `foreman-runtime`
invocation will report a fresh, non-exhausted tick. This is legitimate use of
the sanctioned `tmp/overseer/foreman/` durable-state exception, but it is not
documented anywhere the operator would find it without reading the wrapper's
own source.

## 9. Cross-reference, not a new finding: `github_rate_limit_guard` bare-word false positives

The rate-limit guard hook in `livespec-driver-claude`
(`.claude-plugin/hooks/github_rate_limit_guard.py`, `_LOOP_OR_SLEEP` pattern)
denies any command containing the standalone word "for" (or "while"/"until"/
"sleep") ANYWHERE in the command string — including inside ordinary English
prose passed to `tmux send-keys` or a `gh pr create --body` argument, not only
inside actual shell loop syntax. This hit the foreman session's own tmux
messaging multiple times. This is NOT a new finding: it is already tracked as
`livespec-driver-claude-mu5` ("github_rate_limit_guard denies on substrings,
not behavior") on the `livespec-driver-claude` tenant. No new item filed here;
today's concrete repro (denied `tmux send-keys` calls containing ordinary
prose, not loop syntax) is worth appending as corroborating evidence on that
existing item.
