# Plan — foreman-missing-session-commands

**Owning repo:** `livespec-overseer`. **Ledger anchor:** epic `overseer-7jskz4`

**Status is not stored here.** Read it from the ledger. `bd` needs the fleet
credential wrapper in this tenant — a bare `bd` returns `Access denied`:

```bash
/data/projects/1password-env-wrapper/with-livespec-env.sh \
  bd -C /data/projects/livespec-overseer show overseer-7jskz4 --json
```

Pass `--limit 0` to any `bd list`; the default caps at 50 rows.

Everything below is a claim with a timestamp, including this sentence.
Re-measure.

## Why this thread exists

The foreman tick already gathers everything needed to see that an open plan
thread is missing its worker or supervisor tmux session, but it surfaces that
only as prose in the LLM tick's summary, and the maintainer hand-derives the
attach commands. Measured 2026-08-15 on this box: 7 open threads, 8 missing
sessions, all 8 commands composed by hand. The foreman should print them
deterministically on every tick.

The full mechanism — the `<topic>` / `<topic>-supervisor` naming convention,
the maintainer-specified output contract (alphabetical by topic, supervisor
line before worker line, missing sessions only, `ssh -t <host> 'cd
<home-relative repo path> && tmux new -A -D -s <session>'`), where in the
tick pipeline it belongs, and the boundary (print, never auto-start) — is in
`research/mechanism.md` beside this file. Read it first.

## Ledger state (2026-08-15 — re-measure)

- `overseer-7jskz4` — the epic anchor, `backlog` (epic-shaped).
- `overseer-4bbnit` — the one implementation item, filed `ready` with the
  acceptance spelled out in its description. Thread membership is recorded in
  its TEXT, deliberately not as a `depends_on` edge — an anchor-as-dependency
  edge makes an item undispatchable (the ranker requires deps to resolve
  closed and an epic cannot close before its children).

## Next action

Dispatch `overseer-4bbnit` through the factory path:

```bash
python3 <orchestrator-plugin-root>/scripts/bin/drive.py \
  --action impl:overseer-4bbnit --repo /data/projects/livespec-overseer
```

(Resolve `<orchestrator-plugin-root>` to the CURRENT build — `just
ensure-plugins` prints it; a stale session's Skill-resolved path reproduces
the "plugin build is stale" refusal. Confirm the run exists with `fabro ps`
after `drive.py` exits 0; an exit of 0 alone is not evidence a run started.)

Do NOT implement this item inline in a planning or foreman session — it is
factory-eligible and the factory path is the implementation path.

## Closing this thread

`overseer-4bbnit` merged and accepted, its behavior observed in a live foreman
tick (the printed lines appear beside the runtime JSON), then close
`overseer-7jskz4` and `git mv plan/foreman-missing-session-commands
plan/archive/foreman-missing-session-commands` — whole directory, epic closed
in the same motion. Check first whether this thread has acquired a
`supervisor-handoff.md`; if it has, archiving while `overseer-y26`
(archive-safe respawn) is unfixed recreates the stranded-respawn condition
that thread exists to fix.
