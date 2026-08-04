# Enforcement inventory — where the permanent ban gets teeth

**Owning repo:** `livespec-overseer`. Companion to
`plan/kill-tombstones/handoff.md` and `plan/kill-tombstones/research/mechanism.md`.

Measured 2026-08-04. Re-measure before quoting any of it.

## The headline: the gate already exists and is DARK in the repo that had the tombstones

`livespec-dev-tooling` already ships **two** plan-lifecycle checks, and
`livespec-overseer` already wires **both** into `just check`
(`justfile:230-231` in the `check` aggregate; recipes at `justfile:969-973`).
Neither has ever fired on a tombstone, for two independent reasons.

### Check 1 — `plan_thread_anchor_declared` (static, credential-free)

`livespec-dev-tooling/livespec_dev_tooling/checks/plan_thread_anchor_declared.py`.
Scans active `plan/*/handoff.md` (excluding `plan/archive/`) and FAILS when a
handoff does not declare a concrete `**Ledger anchor:**` naming a real epic id.

**A tombstone has no `**Ledger anchor:**` line** — verified for
`plan/foreman/handoff.md` — so this check would fail it outright. It does not,
because the check **self-skips unless the consumer repo opts in** with
`plan_lifecycle_anchor = true` under `[tool.livespec_dev_tooling]` in its
`pyproject.toml` (`livespec_dev_tooling/config.py:1035`,
`load_plan_lifecycle_anchor`).

Run in `livespec-overseer` 2026-08-04, exit 0:

```json
{"check_id": "plan_thread_anchor_declared", "key": "plan_lifecycle_anchor",
 "value": null, "event": "plan-lifecycle anchor convention not declared by this
 consumer; check self-skips", "level": "info"}
```

**Opt-in state across all twelve governed repos:**

| repo | `plan_lifecycle_anchor` |
|---|---|
| `livespec-dev-tooling` | **`true`** |
| `livespec` | not declared |
| `livespec-overseer` | not declared |
| `livespec-orchestrator-beads-fabro` | not declared |
| `livespec-orchestrator-git-jsonl` | not declared |
| `livespec-console-beads-fabro` | not declared |
| `livespec-runtime` | not declared |
| `livespec-driver-claude` | not declared |
| `livespec-driver-codex` | not declared |
| `homelab` (adopter) | not declared |
| `openbrain` (adopter) | not declared |
| `resume` (adopter) | not declared |

**One of twelve.** The check is wired, green, and dark in the eleven others —
including the only repo that has ever grown a tombstone.

Caveat to check before flipping the opt-in anywhere: the flag turns on a
CONVENTION (every active handoff declares an anchor), not just the tombstone
case. `livespec-overseer`'s own active handoffs already comply
(`charter-gate-ratchet` cites `overseer-x1q`, `supervisor-scratch-discipline`
cites its epic), so the opt-in should land green here after the `foreman` stub
is deleted — but re-measure per repo before flipping, and expect other repos to
need handoff repairs first. Do not flip a repo's flag and leave its CI red.

### Check 2 — `plan_thread_epic_parity` (ledger-state, credentialed)

`livespec-dev-tooling/livespec_dev_tooling/checks/plan_thread_epic_parity.py`.
For each active handoff, reads the ledger status of its `**Ledger anchor:**`
epic and FAILS when an active thread points at a `done`/`closed` epic — "the
exact drift that leaves a completed plan thread un-archived", which is exactly
what a tombstone is.

Two things stop it firing:

1. **Its tenant regex is hard-coded to one repo.**
   `_TENANT_ID_RE = re.compile(r"^livespec-dev-tooling-[a-z0-9]+$")` — only
   same-tenant `livespec-dev-tooling-*` ids are parity-checked; everything else
   is ignored as a cross-tenant prose reference. An `overseer-*` anchor is
   invisible to it. The tenant prefix must be DERIVED per repo (the store config
   already knows it — `resolve_store_config(...).prefix`) rather than hard-coded.
2. **It is ARMED-ONLY**, self-skipping unless BOTH `LIVESPEC_RUN_PLAN_EPIC_PARITY`
   is truthy AND `BEADS_DOLT_PASSWORD` is present. That design is correct and
   should be kept (it mirrors `check_mutation` / `fleet_conformance` /
   `master_ci_green`, and keeps the check out of credential-less CI) — but it
   means parity can never be the PRIMARY tombstone guard. The primary guard must
   be static and credential-free.

Note it would ALSO have been blind to a tombstone even with the right tenant
regex, because a tombstone declares no anchor at all — `_same_tenant_anchor`
finds nothing and the file is skipped. The two checks are complementary and
neither alone is sufficient.

## The missing check — the both-present detector

Neither existing check names the tombstone condition directly. The cheapest,
static, credential-free, unambiguous signature is:

> A topic that exists at BOTH `plan/<topic>/` and `plan/archive/<topic>/`
> simultaneously.

That pair had never existed before the tombstone convention — it is
representable ONLY because archiving started leaving a stub behind. It needs no
ledger, no credentials, no content parsing, and it cannot false-positive on a
legitimately reopened thread, because reopening is a move BACK (the prose's
"Reopening the epic unarchives it (move back)"), which leaves nothing in the
archive.

A content-sniffing variant (grep the live handoff for "COMPLETE AND ARCHIVED" /
"TERMINAL") is strictly worse: it is evadable by rewording and it would flag a
legitimate handoff that merely QUOTES the banned phrase — this very research
note would trip it. Detect the STRUCTURE, not the wording.

This check belongs in `livespec-dev-tooling` beside its two siblings, wired into
`just check` for every governed repo, fail-closed, with no opt-in lever — the
ban is universal, so there is nothing legitimate to exempt. Per the fleet's
carve-out discipline, if it ever needs a severity lever it stays wired and
always invoked; it is never silently skipped.

## The dependent that must be re-derived, not deleted

`livespec-overseer/tests/test_plan_thread_records_agree.py` and
`livespec-overseer/tests/test_charter_correction_counts_are_current.py` each
carry a `_prefer_archived(*, matches)` helper that picks the ARCHIVED copy when a
thread exists at both locations, plus a test named
`test_the_live_archived_tiebreak_is_a_rule_not_an_alphabetical_accident`.

Their docstrings state the dependency outright: "Archiving now leaves a TOMBSTONE
charter at the LIVE path … so both locations can hold the same file at once.
Before this, that pair had never existed."

**Once the both-present detector lands, that pair becomes unrepresentable and the
tiebreak is dead code.** Do not delete it reflexively and do not keep it
reflexively — re-derive it:

- If the new check makes the pair impossible, the tiebreak's justification is
  gone and it should be removed IN THE SAME CHANGE that lands the check, so the
  repo never carries a helper whose stated reason no longer exists.
- If any legitimate transient both-present window survives (e.g. mid-archive
  inside a single commit), the tiebreak stays and its docstring must be rewritten
  to cite THAT reason rather than tombstones.

Decide it by reading the check that ships, not by reading this note.

## Where the prohibition is written down

Four spec surfaces, in dependency order. The wording must forbid the stub AND
state the two sanctioned alternatives, or a future session re-derives the
workaround from the same pressure that produced it the first time.

1. **`livespec` core** — `SPECIFICATION/non-functional-requirements.md`
   §"Planning Lane guidance" → "Archive on epic close". The invariant already
   implies the ban; make it explicit. Route via `/livespec:propose-change`.
   This is the clause adopters inherit.
2. **`livespec-orchestrator-beads-fabro`** — its `SPECIFICATION/` §"Planning Lane
   realization", plus the driving prose `.claude-plugin/prose/plan.md` §"Step 5 —
   Archive on epic close", which is what an agent actually reads at archive time.
   The prose already prescribes the clean `git mv`; it must also say that leaving
   anything behind is forbidden, because "do X" did not stop sessions doing Y.
3. **`livespec-overseer`** — `SPECIFICATION/spec.md` §"Track discovery and the
   mapping store". It already says archived plans are excluded and rows are
   garbage-collected; it must also say that an archived plan is never kept alive
   by a stub at the live path, and why (the GC is directory-level).
4. **`overseer-y26` itself** — strike remedy 1 from the item's description. The
   correction is recorded in the item's NOTES, but the DESCRIPTION still reads
   "Leaving a stub is the precedent already set and is the cheapest", and a
   dispatched agent reads the description. Remedy 2 (a store-side check that
   every mapping row's `handoff` and `resume` path resolves) stays — it is still
   right, and it covers the window between an archive merging and the next GC
   tick.
