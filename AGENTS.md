# livespec-overseer — repo orientation

livespec-overseer is the Control-Plane operator tool for livespec: a
two-pane tmux supervisor that watches every tracked agent session's
remaining context headroom, injects an escalating wrap-up at threshold, and
atomically restarts a session ONLY once that session has declared itself
`ready` on the filesystem. Repo class: `control-plane-tool` — a peer of the
operator console, never a component of it, and an ordinary pin-consuming
fleet member (its enforcement gates come from the pinned
`livespec-dev-tooling` release).

## Layout

| Path | Purpose |
|---|---|
| `SPECIFICATION/` | The live livespec specification governing the supervision contract (maintained via the `/livespec:*` lifecycle) |
| `overseer/` | The supervision package: eight stdlib-only modules, the `overseerd` daemon and `overseer-start` bootstrap executables, their beside-tests, and the deep maintenance docs |
| `tests/` | Repo-level test fixtures (`heading-coverage.json`) |
| `justfile`, `pyproject.toml`, `lefthook.yml`, `.mise.toml`, `.livespec.jsonc`, `.beads/` | Fleet-standard toolchain, livespec, and work-items configuration |

## The three module documents

Read these beside the code before changing anything in `overseer/`:

- `overseer/marker-protocol.md` — the wrap-up + state-declaration protocol
  between the daemon and a supervised session (the cardinal rule, the one
  state file, the restart interlock).
- `overseer/SKILL.md` — the interactive bottom-pane operator contract.
- `overseer/AGENTS.md` — the maintenance guide: architecture invariants
  that must not regress, load-bearing tmux mechanics, and live-exercise
  guidance.

Those three documents are CURRENT — read them as authoritative. They
predate the relocation of this package out of livespec core, but that
staleness was swept out (work-item `overseer-zvo`, closed). Re-measured
2026-07-26: **zero** `.claude/skills/overseer/` path references across all
three, and no "local-only to this repo" framing — the single `local-only`
string in `AGENTS.md` describes the externally-sandboxed HOST, justifying a
codex flag, and is not about the package's scope.

As always `SPECIFICATION/` governs and the code is the final word on
behavior — that is normal precedence, not a warning about these files.

## Daily commands

- `just bootstrap` — first-touch setup on a fresh clone.
- `just check` — the full enforcement aggregate (the single local,
  pre-push, and CI gate).
- `just check-static` — fastest-first fail-fast lint/format/types subset.

## Working discipline

Fleet-standard rules apply: every tracked-file change goes worktree → PR →
rebase-merge (never commit on the primary checkout; hooks refuse it);
product `.py` changes follow the red-green-replay commit ritual; never pass
`--no-verify`; use `mise exec -- git …` so hooks fire. Work-items live in
the `livespec-overseer` beads tenant (`bd` via the fleet credential
wrapper). Durable agent guidance belongs in this file — never in any
harness-private memory store.

**Create worktrees with `just worktree-create <branch> [base_ref]`, NOT with
`git worktree add`.** The recipe provisions the worktree-discipline pack into
`dev-tooling/` and hydrates; raw `git worktree add` does neither, and a
worktree without that pack **can neither commit a `.py` change nor push at
all** — `check-primary-checkout-commit-refuse-hook-installed` fails with
`worktree_pack_absent` in both the pre-commit and pre-push aggregates. Observed
both ways on 2026-07-27: a `.py` commit rejected, and a DOCS-ONLY branch
rejected at push, so do not assume the doc-only fast path exempts you.

Two things make it expensive to learn the hard way. The check is only reachable
through a full `just check`, so it fires at COMMIT or PUSH time — after the work
is done — rather than at worktree-creation time. And the rejected `git commit`
leaves the change STAGED, so a following `git log` shows some other track's
commit at HEAD and reads as success. **Check `git status`, not `git log`, after
a hook-gated commit.** To rescue an
already-created worktree, run `just install-worktree-pack` inside it — but note
it also writes a `worktree_discipline` key into `.livespec.jsonc`, a tracked
file; that key only makes the existing default explicit, so discard it unless
you mean to land it.

The lifecycle has recipes for the rest too: `just worktree-hydrate`,
`just worktree-land [base_ref]`, and `just worktree-reap [--execute]` for
orphans. `dev-tooling/*` is gitignored and byte-verified against the package
source — never hand-edit the installed copy.
