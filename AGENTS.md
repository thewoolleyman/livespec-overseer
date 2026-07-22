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

CAUTION: those three documents predate the relocation of this package out
of livespec core and still carry `.claude/skills/overseer/` path references
and "local-only to this repo" framing from that era. The CODE is
location-independent (fixed `$HOME` config paths); the `overseer-start`
bootstrap and the doc paths are known relocation residue tracked in this
repo's work-items ledger. Trust the code and `SPECIFICATION/` over a stale
path in prose.

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
