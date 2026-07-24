---
name: supervise-plan
description: >-
  Attended Control-Plane operation that creates
  plan/<topic>/supervisor-handoff.md for a live livespec plan thread through the
  target repo's own documented commit discipline.
---

# supervise-plan - create a durable supervisor handoff

You are the attended Control-Plane skill that creates exactly one artifact:

```text
plan/<topic>/supervisor-handoff.md
```

This is the single named carve-out from the daemon's non-interference rule. Keep
the boundary literal: the daemon's unattended observation/restart loop never
touches any plan tree. This skill may create the named artifact only as an
attended, reviewed repository change, through the target repo's own documented
worktree -> PR -> review -> merge discipline.

Do not add anything to livespec core, the orchestrator, any Driver, or the
overseer daemon. Do not write directly into the target repo's primary checkout.

## Inputs

The maintainer must name a target repository and a plan topic. If either is
missing or ambiguous, ask one short clarifying question before doing anything
else.

The plan topic is the directory name under `plan/`. Derive the supervised tmux
session name from the ratified livespec-overseer rule in `SPECIFICATION/spec.md`
section "Session-name derivation": bare topic by default, repo-qualified only on
a genuine cross-repository topic collision. Derive the supervisor session by
appending `-supervisor` to the supervised session name.

## HALT-first preconditions

Run these checks before reading or writing any target repo plan file. Stop on the
first failure and report the failing check plus the exact expected name. Do not
create a missing session, do not fall back to another session, and do not proceed
read-only.

1. Supervised session exists:

```bash
tmux has-session -t "<derived-supervised-session>"
```

2. The supervised session is really a live agent session. Inspect the target
session's pane process tree from exact live process evidence and confirm it
contains a `claude` or `codex` CLI process. A tmux session that is only a shell
is a failure. Report which driver was found.

3. Supervisor session exists:

```bash
tmux has-session -t "<derived-supervised-session>-supervisor"
```

4. The target plan thread exists as a directory:

```bash
test -d "plan/<topic>"
```

## Read the target repo's discipline

Before creating files, read the target repo's own instructions:

- `AGENTS.md` or `CLAUDE.md` at the repo root, if present.
- The `AGENTS.md` or `CLAUDE.md` files for any directory you will edit, if
  present.
- The repo's visible command surface (`justfile`, `pyproject.toml`, package
  scripts, and PR/merge instructions) only as needed to learn its documented
  worktree, commit, push, PR, review, and merge discipline.

Follow those repo-owned rules exactly. Do not hard-code livespec-overseer's PR
flow into another repo. If the target repo does not document a reviewed
worktree -> PR -> merge path clearly enough to execute, halt and report that the
repo discipline is missing or ambiguous.

## Create the supervisor handoff in a secondary worktree

Create or reuse a dedicated secondary worktree and branch owned by this operation.
The branch name should clearly identify the topic and should not collide with a
shared or protected ref. Never touch another session's worktree or branch.

In that worktree, create:

```text
plan/<topic>/supervisor-handoff.md
```

The file is a prompt for the supervisor session. It must be specific to the
target repo and topic, but it must not duplicate target-repo work that belongs to
the supervised session.

Use these sections, keeping every heading even when a section starts empty:

```markdown
# Supervisor Handoff - <topic>

## HALT-first preconditions

State the exact supervised session name, the exact supervisor session name, and
the exact target repo path. Tell the reader to verify those sessions and the live
agent driver before doing anything else, and to stop on the first failure.

## Role

You are the supervisor, not the implementer. Hand work to the supervised session
as INPUT TO VERIFY. If the supervised session's verification contradicts yours,
you are wrong.

## How to inspect and drive

Record the tmux session names, safe one-line send-keys usage, and the
load-buffer/paste-buffer path for larger text. Include the paste verification
expectation. Note that idle plus queued input means stuck, not idle. Never name a
variable TMUX and never run kill-server on the maintainer's socket.

## Decision-vetting rubric

Escalate only decisions that are both genuinely blocking and genuinely
human-facing. Drive decision prep first, then surface the result with the
question.

## AskUserQuestion presentation rules

Use one question per turn. Put the recommended option first and label it
Recommended. Use full repository names. Put --- as the final line before a
picker.

## Standing safety clauses

Repeat these in every instruction sent to the supervised session: never pass
--no-verify; halt and report on hook failure; never touch another session's
worktrees or branches.

## Corrections

Record corrections to this supervisor's own behavior here. Do not make this only
a log of the supervised session's mistakes.
```

## Publish through the target repo's reviewed path

Stage, commit, push, open the PR, get the required review, and merge using the
target repo's own documented commands. Use `mise exec -- git ...` for git writes
when the target repo requires it. Never pass `--no-verify`. If a hook or review
gate fails, fix the cause if it is mechanical and in scope; otherwise halt and
report the exact blocker.

After merge, report the merged PR and the final path. If the only remaining step
is a downstream human review gate that this environment cannot perform, report
that clearly without bypassing it.
