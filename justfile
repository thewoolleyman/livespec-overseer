# justfile — livespec-overseer dev-tooling task runner.
#
# Authority: livespec/SPECIFICATION/non-functional-requirements.md
#   §"Enforcement-suite invocation" — `just` is the canonical entry
#   point for every dev-tooling invocation. Lefthook and CI MUST
#   delegate to `just <target>`; direct tool invocations are banned
#   (enforced by the no-direct-tool-invocation check).
#
# Authority: livespec/SPECIFICATION/contracts.md
#   §"Pre-commit step ordering" — gates wired in lefthook.yml mirror
#   the spec-required ordering.
#   §"Shared code sync — livespec-overseer" / §"Shared code sync —
#   livespec-dev-tooling" — the `check:` aggregate below wires EVERY
#   canonical check slug emitted by
#   `python -m livespec_dev_tooling.canonical_checks --json`, in
#   alphabetical order, per the wiring-completeness invariant
#   enforced by `check-aggregate-completeness` (epic li-univck Phase
#   1.3). livespec-overseer self-hosts the full canonical aggregate
#   from livespec-dev-tooling v0.4.0 onwards (epic li-univck Phase
#   3.3, work-item li-runwir).

# `skip` — space-separated list of `check:` aggregate targets to omit
# from a single run (epic li-cvaudit, cvredmd + cvnoarg). Default empty:
# the full aggregate runs. The Red-mode pre-commit overrides it on the
# command line — `just skip="check-coverage check-per-file-coverage" check`
# — so the coverage gates are not run at the Red commit (coverage is
# verified at the Green amend). The Green-amend pre-commit overrides it
# with `just skip="check-red-green-replay" check` so the no-arg replay
# variant does not reject the in-progress Red HEAD. This is a
# self-contained just variable; it replaces the prior ambient
# `LIVESPEC_PRECOMMIT_RED_MODE` env var with no env var and no spec change.
skip := ""

# pytest-xdist worker count, lane-aware (plan/fabro-ci-image-factoring cont.5).
# GitHub-hosted CI (LIVESPEC_CI_LANE=hosted, set from CI_RUNNER_LABELS in
# ci.yml) uses all cores (-n auto — GH runners are small + dedicated). The
# self-hosted/local lane throttles to LIVESPEC_TEST_PARALLELISM, defaulting to
# 25% of cores (min 1) so a shared host is never oversubscribed. Tune per host
# by exporting LIVESPEC_TEST_PARALLELISM (a dedicated box can set it to `auto`
# or a high N); local dev may export it to speed a laptop run.
test_nprocs := if env_var_or_default("LIVESPEC_CI_LANE", "local") == "hosted" { "auto" } else { env_var_or_default("LIVESPEC_TEST_PARALLELISM", `c=$(nproc 2>/dev/null || echo 4); n=$(( c / 4 )); [ "$n" -ge 1 ] || n=1; echo "$n"`) }

# Default to listing targets when no recipe is invoked.
default:
    @just --list

# ---------------------------------------------------------------
# First-time setup.
# ---------------------------------------------------------------

# Worktree-discipline pack recipe fragments — OPTIONAL imports (`import?`, NOT
# plain `import`): the fragments are gitignored-and-installed by
# `just install-worktree-pack` (run from the `worktree-pack` LOCAL obligation
# row that `bootstrap` walks), so they are ABSENT in a fresh clone until then. A
# plain `import` of a missing file makes `just` fail to parse the ENTIRE
# justfile, which would brick `just bootstrap` on a fresh clone; the optional
# `import?` silently no-ops while the file is absent — the `worktree-*` and
# `branch-protection-*` recipes simply are not available until the fragments are
# materialized — and resolves once installed. Without these two lines a
# byte-perfect installed pack is INVISIBLE to `just --list`, which is the
# discoverability hole that let a session fall back to a raw `git worktree add`.
import? 'dev-tooling/worktree.just'
import? 'dev-tooling/branch-protection.just'

# First-touch setup — a THIN delegator to the shipped LOCAL first-touch
# reconcile verb (`livespec_dev_tooling.fleet.local_reconcile`), the
# generalized successor to this recipe's former inline steps (livespec-zs22.8
# M5). Reuse-first: NO copied logic — the verb walks the LOCAL obligation
# partition (`contract.LOCAL_OBLIGATION_ROWS`): mise trust/install, uv sync,
# the canonical worktree-discipline pack, the structural commit-refuse hooks
# (subsuming `lefthook install` — the
# canonical hook overwrites the lefthook stubs and delegates to `lefthook
# run`), the advisory `refs/notes/*` refspec, the worktree-root mise-trust
# entry, the beads tenant-dir hardening, the beads-runtime detect-and-guide
# probes, and project-scoped Claude/Codex plugin registration. The two plugin
# rows delegate back to THIS repo's own `ensure-plugins` / `ensure-codex-plugins`
# recipes below (the plugin set is repo-specific, so each governed repo's recipe
# stays the single source; a member lacking either recipe SKIPs that row). The
# verb resolves shared-state rows worktree-safely via `git rev-parse
# --git-common-dir`, so invoking from a linked worktree still provisions the
# primary checkout's shared state. The `worktree-pack` row is the ONE exception:
# the pack lives in each checkout's own `dev-tooling/` and the `import?` lines
# above resolve relative to the worktree you stand in, so that row targets the
# INVOKED worktree — otherwise every linked worktree would show no
# `worktree-create` in `just --list`. Mirrors the `install-commit-refuse-hooks`
# recipe's `uv run python -m ...` from-package invocation.
bootstrap:
    uv run python -m livespec_dev_tooling.fleet.local_reconcile

# Install the canonical livespec commit-refuse hook by REUSING the shared
# livespec-dev-tooling installer module (the SINGLE source of the structural
# hook body; pinned in pyproject.toml). Idempotent; worktree-safe.
install-commit-refuse-hooks:
    uv run python -m livespec_dev_tooling.install_commit_refuse_hooks

# Install (or idempotently re-install) the canonical worktree-discipline pack —
# FOUR files: `worktree-lib.sh` + `branch-protection.sh` (executable) and
# `worktree.just` + `branch-protection.just` (imported above, not executable) —
# into the current checkout's `dev-tooling/` directory. The livespec-dev-tooling
# installer module is the single canonical-body carrier. The pack files are
# GITIGNORED-AND-MATERIALIZED, never tracked: nothing is committed, and each
# checkout re-materializes them. `bootstrap` covers this automatically via the
# `worktree-pack` LOCAL obligation row, so this recipe is the standalone repair
# path rather than a step `bootstrap` must duplicate. The
# `check-primary-checkout-commit-refuse-hook-installed` verifier guards the
# installed bytes against drift.
install-worktree-pack:
    uv run python -m livespec_dev_tooling.install_worktree_pack

# The standard shared derive-from-settings wrapper: reads the committed
# `.claude/settings.json` (`extraKnownMarketplaces` incl. `ref`, `enabledPlugins`)
# at runtime and issues the marketplace add / install / update commands for
# exactly what it finds — one source of truth, so recipe-content drift is
# structurally impossible. The `update` after each `install` is required because
# `install` is a no-op when any version is already present locally — without
# `update`, a bumped upstream release never reaches a previously-bootstrapped
# working copy. The SessionStart hook in `.claude/settings.json` runs this recipe
# so each new session's project-scope plugins are current.
ensure-plugins:
    mise exec -- uv run --no-sync python -m livespec_dev_tooling.fleet.ensure_plugins

# Idempotent host-wide Codex plugin provisioning. Codex does not support
# project-scoped plugin enablement, so these registrations intentionally land in
# the user's default CODEX_HOME and are visible to every repo on the host. Codex
# is an optional dogfooding runtime; bootstrap skips this target when the CLI is
# absent but fails on real install errors when Codex is present.
ensure-codex-plugins:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! command -v codex >/dev/null 2>&1; then
        echo "codex CLI not found; skipping host-wide Codex plugin install." >&2
        exit 0
    fi
    codex plugin marketplace add thewoolleyman/livespec --ref release
    codex plugin marketplace add thewoolleyman/livespec-driver-codex --ref release
    codex plugin marketplace add thewoolleyman/livespec-orchestrator-beads-fabro --ref release
    codex plugin marketplace upgrade livespec
    codex plugin marketplace upgrade livespec-driver-codex
    codex plugin marketplace upgrade livespec-orchestrator-beads-fabro
    codex plugin add livespec@livespec
    codex plugin add livespec@livespec-driver-codex
    codex plugin add livespec-orchestrator-beads-fabro@livespec-orchestrator-beads-fabro

# ---------------------------------------------------------------
# Aggregate check — wires EVERY canonical check slug emitted by
# `python -m livespec_dev_tooling.canonical_checks --json`, in
# alphabetical order. Enforced by `check-aggregate-completeness`
# (epic li-univck Phase 1.3). Repo-private extras (none today) would
# appear AFTER the canonical block per the same invariant.
#
# Continues on failure (matches CI fail-fast: false); exits non-zero
# with the failure list if any target failed.
# ---------------------------------------------------------------

check:
    #!/usr/bin/env bash
    set -uo pipefail
    # `skip` is a just VARIABLE (declared at the top of this justfile,
    # default empty): a space-separated list of target names to omit from
    # this run (epic li-cvaudit, cvredmd + cvnoarg). The Red-mode pre-commit
    # invokes `just skip="check-coverage check-per-file-coverage" check` so
    # coverage is not gated at the Red commit (it is verified at the Green
    # amend); the Green-amend pre-commit invokes
    # `just skip="check-red-green-replay" check` so the no-arg replay variant
    # does not reject the in-progress Red HEAD — both self-contained just
    # variables that replace the prior ambient `LIVESPEC_PRECOMMIT_RED_MODE`
    # env var. The recipe header stays the bare `check:` the
    # wiring-completeness checks parse for. Pre-push and CI invoke
    # `just check` with no `skip`, so the full aggregate stays the safety net.
    read -ra skip_targets <<< "{{skip}}"
    # Sync the environment ONCE per aggregate pass, then run every
    # target with UV_NO_SYNC=1 so the ~44 per-target `uv run`
    # invocations skip their redundant per-invocation re-sync
    # (work-item livespec-overseer-90k). The single up-front sync
    # keeps the freshness guarantee — a stale lockfile/venv still
    # fails here, loudly, before any target runs. This also caps the
    # cost of a corrupted-venv re-sync loop (e.g. an orphaned
    # dist-info missing its RECORD file, which a sync can never
    # uninstall and therefore retries on EVERY invocation) at one
    # sync attempt per pass instead of one per target, and shrinks
    # the concurrent-sync race window that produces that corruption
    # in the first place. Standalone `just check-<x>` invocations
    # keep uv's default sync-on-run behavior; CI's per-target matrix
    # jobs each sync their own fresh runner and are unaffected.
    if ! uv sync --all-groups; then
        echo "ERROR: up-front 'uv sync --all-groups' failed; aborting the check aggregate" >&2
        exit 1
    fi
    export UV_NO_SYNC=1
    targets=(
        check-agents-ai-references-resolve
        check-aggregate-completeness
        check-all-declared
        check-assert-never-exhaustiveness
        check-branch-protection-alignment
        check-canonical-recipe-fidelity
        check-check-coverage-incremental
        check-check-mutation
        check-check-tools
        check-ci-matrix-completeness
        check-claude-md-coverage
        check-comment-line-anchors
        check-commit-pairs-source-and-test
        check-file-lloc
        check-fleet-marketplace-relative-sources
        check-global-writes
        check-handoff-dispatch-routing
        check-heading-coverage
        check-hook-trees-not-io-exempt
        check-keyword-only-args
        check-local-memory-drift-audit
        check-main-guard
        check-master-ci-green
        check-match-keyword-only
        check-newtype-domain-primitives
        check-no-direct-destructive-cli
        check-no-direct-tool-invocation
        check-no-except-outside-io
        check-no-fmt-directives
        check-no-inheritance
        check-no-lloc-soft-warnings
        check-no-raise-outside-io
        check-no-shadow-ledger-body-identical
        check-no-shadow-ledger-body-typechecks
        check-no-todo-registry
        check-no-write-direct
        check-partition-completeness
        check-pbt-coverage-pure-modules
        check-per-file-coverage
        check-plan-thread-anchor-declared
        check-plan-thread-epic-parity
        check-plugin-resolution
        check-primary-checkout-commit-refuse-hook-installed
        check-private-calls
        check-public-api-result-typed
        check-red-green-replay
        check-required-role-keys-declared
        check-rop-pipeline-shape
        check-self-hosted-routing
        check-skill-invocation-paths
        check-source-trees-scoped-to-consumer
        check-supervisor-discipline
        check-tests-mirror-pairing
        check-tests-no-subprocess-spawn
        check-tool-backed-check-completeness
        check-vendor-manifest
        check-wrapper-shape
        # ---- Repo-private block (extends after canonical) ----
        # Tool-backed checks that are NOT canonical slugs (absent from
        # `livespec_dev_tooling.canonical_checks`) but still gate the
        # aggregate. They appear AFTER the canonical block per the
        # wiring-completeness invariant (which only constrains the
        # canonical block to be exact + alphabetical). `check-lint`,
        # `check-format`, `check-types`, and `check-coverage` are the
        # four tool-backed slugs the canonical `check-tool-backed-check-
        # completeness` meta-check (v0.9.0) requires as literal members
        # of BOTH this targets array AND the CI matrix. Mirrors how
        # livespec-core and livespec-orchestrator-git-jsonl wire them.
        check-lint
        check-format
        check-types
        check-coverage
        check-doctor-static
        check-plugin-manifest-lockstep
        # Repo-local Codex plugin runnable-artifact gate (overseer-g6z):
        # the materialized plugin root must contain executable launchers
        # plus the importable runtime package they need.
        check-codex-plugin-runnable-launcher
        # Repo-local live delegate for the codex `supported` declaration
        # (overseer-kju6wh). The fleet Verifier SKIPs codex and accepts any
        # non-empty canonical_command, so without this member the declaration
        # is green-by-skip in both modes. Self-skips in CI and when codex is
        # absent — see the recipe for why those deviations are declared there.
        check-codex-skill-picker
        # Repo-local release-hygiene gate (overseer-d4t): generator
        # prose may not change without a release-triggering commit,
        # or the fix never reaches the plugin cache that generates
        # charters. Not a canonical slug, so it belongs here rather
        # than interleaved into the canonical block above.
        check-prose-release-hygiene
    )
    failed=()
    ran=0
    for t in "${targets[@]}"; do
        skip_this=0
        for s in "${skip_targets[@]:-}"; do
            if [[ "$t" == "$s" ]]; then
                skip_this=1
                break
            fi
        done
        if [[ "$skip_this" -eq 1 ]]; then
            printf '\n::: just %s (skipped)\n' "$t"
            continue
        fi
        ran=$((ran + 1))
        printf '\n::: just %s\n' "$t"
        if ! just "$t"; then
            failed+=("$t")
        fi
    done
    if [[ ${#failed[@]} -gt 0 ]]; then
        printf '\nFailed targets (%d):\n' "${#failed[@]}"
        printf '  - %s\n' "${failed[@]}"
        exit 1
    fi
    printf '\nAll %d targets passed.\n' "$ran"
    if [[ -z "{{skip}}" ]]; then uv run python -m livespec_dev_tooling.green_token write || true; fi

# ---------------------------------------------------------------
# Tool-backed checks. The slugs `check-lint` / `check-format` /
# `check-coverage` / `check-types` are NOT canonical (not in
# canonical_checks.py's discovery set). `check-types` IS wired into
# the `check:` aggregate's `targets=(...)` repo-private block (after
# the canonical block) and into the CI `check-python` matrix, so
# pyright gates the runtime package everywhere `just check` runs
# (local, pre-push, CI). `check-lint` / `check-format` are invoked
# transitively via the canonical recipes (e.g. `check-file-lloc`
# pairs with ruff) and remain available as standalone helpers;
# `check-coverage` overlaps the canonical `check-per-file-coverage`.
# ---------------------------------------------------------------

check-lint:
    uv run ruff check .

check-format:
    uv run ruff format --check .

check-types:
    uv run pyright

# In Red-mode pre-commit this target is omitted by `check-pre-commit`
# via the `check skip=...` argument (coverage is verified at the Green
# amend), so no ambient env-var read is needed here (epic li-cvaudit,
# cvredmd).
check-coverage:
    #!/usr/bin/env bash
    set -uo pipefail
    if [[ -f .coverage ]]; then
        echo ":: check-coverage: reading existing .coverage (produced by check-per-file-coverage); no duplicate suite run"
        uv run coverage report --fail-under=100
    else
        echo ":: check-coverage: no .coverage data file (CI standalone job); running the suite"
        uv run pytest -n {{test_nprocs}} --cov --cov-branch --cov-config=pyproject.toml --cov-report=term-missing
    fi

# livespec core's doctor STATIC phase (reference-discipline + out-of-band
# invariants) against THIS repo's SPECIFICATION/ tree, wired fleet-wide per
# livespec epic livespec-6jfq. core ships the checker: doctor_static.py is
# self-contained (vendored deps + bare python3), so it runs under plain
# python3 and NEVER `uv run`. Resolve core's plugin root via
# LIVESPEC_CORE_PLUGIN_ROOT (CI sets it to a livespec checkout at this repo's
# .livespec.jsonc compat.pinned tag) → else the installed livespec@livespec
# plugin cache (local dev). The two reference-discipline checks
# (no-cross-spec-reference, no-spec-section-citation-in-code) are pure reads;
# doctor-out-of-band-edits is self-healing — on a drifted tree it writes a
# history backfill into the worktree and fails, and committing that backfill
# heals the track; on a clean tree it never fires.
check-doctor-static:
    #!/usr/bin/env bash
    set -euo pipefail
    core_root="${LIVESPEC_CORE_PLUGIN_ROOT:-}"
    if [ -z "$core_root" ]; then
      # Resolve the CURRENT released core build (== marketplace clone HEAD), NOT
      # installed_plugins.json[...]["livespec@livespec"][0] — that per-project list is
      # unordered and its first row can be a different, stale project on a mixed-build
      # host, which the c1k9 currency gate then correctly blocks (livespec-q2me).
      core_root="$(python3 -c 'import subprocess, pathlib; mk = pathlib.Path.home() / ".claude" / "plugins" / "marketplaces" / "livespec"; head = subprocess.run(["git", "-C", str(mk), "rev-parse", "--short=12", "HEAD"], capture_output=True, text=True).stdout.strip().lower(); cache = pathlib.Path.home() / ".claude" / "plugins" / "cache" / "livespec" / "livespec" / head; print(cache if head and (cache / "scripts" / "bin" / "doctor_static.py").is_file() else "")' 2>/dev/null || true)"
    fi
    if [ -z "$core_root" ] || [ ! -f "$core_root/scripts/bin/doctor_static.py" ]; then
      echo "livespec core not found. Set LIVESPEC_CORE_PLUGIN_ROOT to a livespec checkout's .claude-plugin, or install the livespec@livespec plugin (claude plugin install livespec@livespec)." >&2
      exit 1
    fi
    python3 "$core_root/scripts/bin/doctor_static.py" --project-root .

check-plugin-manifest-lockstep:
    uv run pytest tests/test_plugin_manifest_lockstep.py

# `check-static` — fastest-first fail-fast helper for fast agent/dev
# feedback (work-item livespec-dev-tooling-7us.8). Runs ONLY the cheap
# static checks — `ruff format --check .`, `ruff check .`, `pyright`
# (i.e. check-format, check-lint, check-types) — as a fail-fast
# sequence: it STOPS at the first failing check and exits non-zero, so
# a sub-2s ruff/pyright failure surfaces immediately instead of after
# `just check`'s slow pytest+coverage tail. This is a developer/agent
# convenience like the helper recipes above; it is deliberately NOT a
# member of the `check:` aggregate `targets=(...)` array, NOT a
# canonical slug (no livespec_dev_tooling/checks/ module), and NOT in
# the CI matrix. The authoritative full gate remains `just check`
# (still run at pre-push and in CI) — `check-static` is a fast
# pre-flight, never a replacement for it.
check-static:
    #!/usr/bin/env bash
    set -euo pipefail
    uv run ruff format --check .
    uv run ruff check .
    uv run pyright

# `changed-files` — print the changed `.py` set this branch touches,
# repo-root-relative, one path per line, sorted + de-duplicated
# (work-item livespec-dev-tooling-7us.9). The set is the UNION of two
# git views, so an agent gets the live working set whether or not it has
# committed yet:
#   - `git diff --name-only origin/master...HEAD` — every `.py` this
#     branch's commits changed vs the merge-base with origin/master;
#   - `git diff --cached --name-only --diff-filter=AM` — added/modified
#     `.py` currently staged but not yet committed.
# This is the exact set `check-changed` consumes for its scoped gate.
# Helper recipe (like `check-static`): NOT a member of the `check:`
# aggregate `targets=(...)` array, NOT a canonical slug, NOT in the CI
# matrix.
changed-files:
    #!/usr/bin/env bash
    set -uo pipefail
    # `grep` exits 1 on zero matches; an empty changed set is normal (a
    # clean branch), so swallow that into exit 0 via `|| true` — the
    # consuming `check-changed` treats empty as "nothing to gate".
    { git diff --name-only origin/master...HEAD;
      git diff --cached --name-only --diff-filter=AM; } \
        | { grep -E '\.py$' || true; } | sort -u

# `check-changed` — modified-files INNER-LOOP gate for fast scoped
# feedback during iteration (work-item livespec-dev-tooling-7us.9). Feeds
# the `changed-files` set into `check-check-coverage-incremental --paths
# <set>`, which already (a) resolves each changed impl `.py` to its
# mirror-paired test and runs that pytest SUBSET, and (b) applies the
# path-scoped per-file coverage gate — i.e. it composes the existing
# scoping plumbing rather than re-deriving it. An empty changed set is a
# no-op (exit 0): nothing changed, nothing to gate.
#
# SCOPE — INNER-LOOP SPEEDUP ONLY, NOT a replacement for the final gate.
# It runs only the test subset + path-scopable checks for the files this
# branch touched, so an agent gets sub-suite feedback while iterating. The
# AUTHORITATIVE gate remains `just check`, which runs the FULL suite + the
# full AST scans + the aggregate 100% coverage gate at pre-push and in CI.
# Like `check-static`, this is a developer/agent convenience: NOT a member
# of the `check:` aggregate `targets=(...)` array, NOT a canonical slug,
# and NOT in the CI matrix.
check-changed:
    #!/usr/bin/env bash
    set -uo pipefail
    mapfile -t changed < <(just changed-files)
    if [[ "${#changed[@]}" -eq 0 ]]; then
        echo ":: check-changed: no changed .py vs origin/master (and none staged); nothing to gate"
        echo ":: the authoritative full gate remains 'just check' (run at pre-push + CI)"
        exit 0
    fi
    echo ":: check-changed: scoping the test subset + per-file coverage gate to ${#changed[@]} changed .py:"
    printf '   %s\n' "${changed[@]}"
    echo ":: INNER-LOOP ONLY — 'just check' runs the FULL suite/AST scans at pre-push + CI"
    just check-check-coverage-incremental --paths "${changed[@]}"

# ---------------------------------------------------------------
# Canonical aggregate recipes — one per canonical slug emitted by
# `python -m livespec_dev_tooling.canonical_checks --json`. Each
# resolves to `uv run python -m livespec_dev_tooling.checks.<slug>`
# with the snake_case slug.
# ---------------------------------------------------------------

# AGENTS.md `.ai/` reference-resolution gate — every `.ai/<topic>.md`
# referenced from an AGENTS.md must resolve to an existing file.
check-agents-ai-references-resolve:
    uv run python -m livespec_dev_tooling.checks.agents_ai_references_resolve

# Wiring-completeness gate — verifies the targets=(...) array in this
# very justfile carries every canonical slug in alphabetical order
# (epic li-univck Phase 1.3, work-item li-aggchk). Self-bootstrapping:
# wiring this slug forces wiring every other canonical slug.
check-aggregate-completeness:
    uv run python -m livespec_dev_tooling.checks.aggregate_completeness

check-all-declared:
    uv run python -m livespec_dev_tooling.checks.all_declared

check-assert-never-exhaustiveness:
    uv run python -m livespec_dev_tooling.checks.assert_never_exhaustiveness

check-branch-protection-alignment:
    uv run python -m livespec_dev_tooling.checks.branch_protection_alignment

# Path-scoped fast-feedback variant of check-coverage. With explicit
# `--paths <impl_path> [<impl_path>...]` (repo-root-relative) it scopes
# the per-file 100% gate to those paths. With NO args (the canonical
# aggregate / `just check` invocation) the check DERIVES the changed
# impl-`.py` set from `git diff --name-only origin/master...HEAD` and
# gates those — no longer a no-op (epic li-cvaudit, cvnoarg). The
# interactive developer use case still passes `--paths` explicitly:
# `just check-check-coverage-incremental --paths overseer/cross_repo/foo.py`.
check-check-coverage-incremental *args:
    uv run python -m livespec_dev_tooling.checks.check_coverage_incremental {{args}}

# Always invoked plainly; the module self-manages its RUN/SKIP lever
# (epic li-cvaudit, cvtodo). `LIVESPEC_RUN_MUTATION` unset → the check
# logs "skipped" and exits 0; set to a non-empty value (CI sets it to
# `true`) → the mutmut suite runs. No external gate, no silent skip.
check-check-mutation:
    uv run python -m livespec_dev_tooling.checks.check_mutation

check-check-tools:
    uv run python -m livespec_dev_tooling.checks.check_tools

check-claude-md-coverage:
    uv run python -m livespec_dev_tooling.checks.claude_md_coverage

check-comment-line-anchors:
    uv run python -m livespec_dev_tooling.checks.comment_line_anchors

check-commit-pairs-source-and-test:
    uv run python -m livespec_dev_tooling.checks.commit_pairs_source_and_test

check-file-lloc:
    uv run python -m livespec_dev_tooling.checks.file_lloc

# Fleet marketplace ref-pin guard: catalog plugin sources MUST stay
# checkout-relative (`./...` strings, or the Codex catalog's
# `{"source": "local", "path": "./..."}` object form). Github-type or
# other non-relative sources silently ignore the registered
# marketplace ref pin and clone default HEAD instead.
check-fleet-marketplace-relative-sources:
    uv run python -m livespec_dev_tooling.checks.fleet_marketplace_relative_sources

check-global-writes:
    uv run python -m livespec_dev_tooling.checks.global_writes

check-heading-coverage:
    uv run python -m livespec_dev_tooling.checks.heading_coverage

check-keyword-only-args:
    uv run python -m livespec_dev_tooling.checks.keyword_only_args

check-main-guard:
    uv run python -m livespec_dev_tooling.checks.main_guard

check-master-ci-green:
    uv run python -m livespec_dev_tooling.checks.master_ci_green

check-match-keyword-only:
    uv run python -m livespec_dev_tooling.checks.match_keyword_only

check-newtype-domain-primitives:
    uv run python -m livespec_dev_tooling.checks.newtype_domain_primitives

# Destructive-default CLI wrapping gate (livespec/SPECIFICATION/
# non-functional-requirements.md §"Destructive-default CLI wrapping"):
# greps the agent-facing trees (dev-tooling/, .claude-plugin/,
# .claude/plugins/) for direct invocations of known-destructive-default
# CLIs (bd init, git push --force/-f, git reset --hard, gh repo delete)
# outside the explicit `[tool.livespec_dev_tooling].
# destructive_cli_allowlist` path-prefix allowlist.
check-no-direct-destructive-cli:
    uv run python -m livespec_dev_tooling.checks.no_direct_destructive_cli

check-no-direct-tool-invocation:
    uv run python -m livespec_dev_tooling.checks.no_direct_tool_invocation

check-no-except-outside-io:
    uv run python -m livespec_dev_tooling.checks.no_except_outside_io

check-no-inheritance:
    uv run python -m livespec_dev_tooling.checks.no_inheritance

# Always invoked plainly; the module self-manages its severity lever
# (epic li-cvaudit, cvtodo). The 201-250 LLOC soft-band scan ALWAYS
# runs; `LIVESPEC_FAIL_IF_LLOC_SOFT_WARNINGS_EXIST` unset → soft-band
# offenders warn + exit 0; set (CI sets it to `true`) → they fail.
check-no-lloc-soft-warnings:
    uv run python -m livespec_dev_tooling.checks.no_lloc_soft_warnings

check-no-raise-outside-io:
    uv run python -m livespec_dev_tooling.checks.no_raise_outside_io

# Always invoked plainly; the module self-manages its severity lever
# (epic li-cvaudit, cvtodo). The heading-coverage.json TODO scan ALWAYS
# runs; `LIVESPEC_FAIL_IF_HEADING_COVERAGE_TODOS_EXIST` unset → TODO
# offenders warn + exit 0 (authoring placeholders surface without
# blocking per-commit `just check`); set (CI sets it to `true`) → they
# fail. Replaces the prior LIVESPEC_RELEASE_GATE skip carve-out, which
# silently skipped the scan entirely when the gate was unset.
check-no-todo-registry:
    uv run python -m livespec_dev_tooling.checks.no_todo_registry

check-no-write-direct:
    uv run python -m livespec_dev_tooling.checks.no_write_direct

check-pbt-coverage-pure-modules:
    uv run python -m livespec_dev_tooling.checks.pbt_coverage_pure_modules

# Per-file 100% line+branch coverage gate. Reads `.coverage`; we run
# pytest --cov upfront in the recipe so the data file exists when the
# canonical aggregate invokes the slug as a self-contained check.
# In Red-mode pre-commit this target is omitted by `check-pre-commit`
# via the `check skip=...` argument (coverage is verified at the Green
# amend), so no ambient env-var read is needed here (epic li-cvaudit,
# cvredmd).
check-per-file-coverage:
    #!/usr/bin/env bash
    set -uo pipefail
    uv run pytest -n {{test_nprocs}} --cov --cov-branch --cov-config=pyproject.toml --cov-report=term-missing
    uv run python -m livespec_dev_tooling.checks.per_file_coverage

# Baseline harness plugin-resolution Verifier: asserts each declared
# harness in `.livespec.jsonc` `harnesses` resolves its command/skill
# surface (or is explicitly `exempt`). livespec-overseer currently
# declares Claude supported with a canonical command while Codex remains
# exempt until the Codex parity slice lands its skill surface.
check-plugin-resolution:
    uv run python -m livespec_dev_tooling.checks.plugin_resolution

# Universal cross-boundary invariant: every livespec-governed primary
# checkout MUST install the canonical commit-refuse hook body at
# `.git/hooks/pre-commit` AND `.git/hooks/pre-push`. Replaces the
# prior `core.bare = true` invariant as of epic li-unbare Phase 3 +
# livespec-dev-tooling v0.5.0. CI's metadata matrix runs this target
# with its own hook-installation gating step since `actions/checkout`
# produces a non-bare working tree without the hook installed.
check-primary-checkout-commit-refuse-hook-installed:
    uv run python -m livespec_dev_tooling.checks.primary_checkout_commit_refuse_hook_installed

check-private-calls:
    uv run python -m livespec_dev_tooling.checks.private_calls

# Release-hygiene gate for GENERATOR PROSE (work-item overseer-d4t;
# shape (b) of the release-lane valve in
# plan/supervisor-prompt-quality/handoff.md).
#
# WHY THIS EXISTS. Charters are generated from the INSTALLED plugin
# cache, never from this working tree, so a prose fix reaches nobody
# until a release ships AND adopters update. Measured 2026-07-30: all
# nine cached `prose/supervise-plan.md` copies under
# ~/.claude/plugins/cache/livespec-overseer/ were BYTE-IDENTICAL
# (md5 2283862c…) while master carried 6 exact-target mandates and 4
# supervisor-liveness proofs that NONE of them had, and the active
# version still emitted 4 bare `-t "` tmux targets master had removed.
#
# WHAT IS ENFORCED. If the range changes `.claude-plugin/prose/`, the
# range must also carry at least one commit whose conventional-commit
# type release-please acts on. release-please bumps on feat/fix/perf/
# revert and on a `!` breaking marker; `docs`, `test`, `chore`, `ci`,
# `build`, `style` and `refactor` produce NO version bump, so prose
# landed under one of those cannot trigger a release on its own. This
# repo already carries four such commits — 3ed8667 `docs:`, 454c14d
# `chore(prompt):`, 0b98bed `test(prompts):`, 91d83e7
# `docs(supervise-plan):` — so this is a measured hole, not a
# hypothetical one.
#
# WHAT IS *NOT* CLAIMED, stated so nobody reads more into a green.
# This does not merge the pending release PR and does not refresh any
# adopter's plugin cache; both remain open under overseer-d4t. It
# closes exactly one hole: a prose change that can never produce a
# version bump at all.
#
# The two refs are overridable ONLY so the gate's own fixtures can
# drive this real recipe against synthetic repositories instead of a
# second copy of its logic — a duplicated rule is a rule that drifts.
check-prose-release-hygiene:
    #!/usr/bin/env bash
    # `set -e` is DELIBERATELY ABSENT and must stay absent: the
    # releasing-commit count below is `grep -c`, which exits 1 when the
    # count is zero. Under `set -e` that aborts the recipe at exactly
    # the violation it exists to report — red for the wrong reason, with
    # none of the operator guidance below ever printed.
    set -uo pipefail
    base="${PROSE_HYGIENE_BASE:-origin/master}"
    head="${PROSE_HYGIENE_HEAD:-HEAD}"
    prose_dir=".claude-plugin/prose"
    if ! git rev-parse --verify --quiet "$base" >/dev/null; then
        echo "check-prose-release-hygiene: cannot resolve base ref '$base'." >&2
        echo "  This gate reads the commit RANGE, so it needs real history." >&2
        echo "  A shallow clone cannot satisfy it; fetch full depth." >&2
        exit 1
    fi
    changed="$(git diff --name-only "$base...$head" -- "$prose_dir")"
    if [[ -z "$changed" ]]; then
        echo ":: check-prose-release-hygiene — no generator prose changed in $base...$head"
        exit 0
    fi
    # A releasing subject is `feat|fix|perf|revert`, with an optional
    # (scope), or ANY type carrying the `!` breaking marker.
    releasing="$(git log --format='%s' "$base..$head" \
        | grep -cE '^(feat|fix|perf|revert)(\([^)]*\))?!?:|^[a-z]+(\([^)]*\))?!:')"
    if [[ "$releasing" -gt 0 ]]; then
        echo ":: check-prose-release-hygiene — prose changed and $releasing releasing commit(s) present"
        exit 0
    fi
    {
        echo "Generator prose changed with NO release-triggering commit in the range."
        echo
        echo "Changed prose:"
        echo "$changed"
        echo
        echo "Commit subjects in $base..$head:"
        git log --format='  %h %s' "$base..$head"
        echo
        echo "WHY THIS BLOCKS: charters are generated from the installed plugin"
        echo "cache, not from this tree. release-please bumps the version only on"
        echo "feat/fix/perf/revert or a '!' breaking marker, so prose landed under"
        echo "docs/test/chore/ci/build/style/refactor ships to nobody."
        echo
        echo "REMEDY: re-word one commit that carries the prose change to 'fix:' or"
        echo "'feat:' (whichever is honest), so merging it necessarily produces a"
        echo "version bump. If the prose edit genuinely must not release, it does"
        echo "not belong in .claude-plugin/prose/."
    } >&2
    exit 1

check-public-api-result-typed:
    uv run python -m livespec_dev_tooling.checks.public_api_result_typed

# Trailer-based Red→Green replay verification (hard gate). Invoked by
# lefthook commit-msg stage with the commit-message file path as argv[1]
# (the load-bearing per-commit verifier). The canonical aggregate /
# `just check` invokes this with NO msg_path; the module then DERIVES
# the message from `git log -1 --format=%B` (HEAD) and validates it —
# no longer a no-op (epic li-cvaudit, cvnoarg).
check-red-green-replay *args:
    uv run python -m livespec_dev_tooling.checks.red_green_replay {{args}}

check-rop-pipeline-shape:
    uv run python -m livespec_dev_tooling.checks.rop_pipeline_shape

check-skill-invocation-paths:
    uv run python -m livespec_dev_tooling.checks.skill_invocation_paths

check-supervisor-discipline:
    uv run python -m livespec_dev_tooling.checks.supervisor_discipline

check-tests-mirror-pairing:
    uv run python -m livespec_dev_tooling.checks.tests_mirror_pairing

check-tests-no-subprocess-spawn:
    uv run python -m livespec_dev_tooling.checks.tests_no_subprocess_spawn

check-tool-backed-check-completeness:
    uv run python -m livespec_dev_tooling.checks.tool_backed_check_completeness

check-vendor-manifest:
    uv run python -m livespec_dev_tooling.checks.vendor_manifest

check-wrapper-shape:
    uv run python -m livespec_dev_tooling.checks.wrapper_shape

check-codex-plugin-runnable-launcher:
    #!/usr/bin/env bash
    set -euo pipefail
    start=".claude-plugin/bin/overseer-start"
    daemon=".claude-plugin/bin/overseerd"
    plugin_pkg=".claude-plugin/overseer"
    test -x "$start"
    test -x "$daemon"
    test -d "$plugin_pkg"
    while IFS= read -r -d '' src; do
      rel="${src#overseer/}"
      dst="$plugin_pkg/$rel"
      test -f "$dst"
      cmp -s "$src" "$dst"
    done < <(find overseer -maxdepth 1 \( -name '*.py' -o -name 'version.json' \) ! -name 'test_*.py' ! -name 'conftest.py' -print0 | sort -z)
    while IFS= read -r -d '' dst; do
      rel="${dst#$plugin_pkg/}"
      test -f "overseer/$rel"
    done < <(find "$plugin_pkg" -maxdepth 1 -type f -print0 | sort -z)
    unexpected_dir="$(find "$plugin_pkg" -mindepth 1 -maxdepth 1 -type d ! -name __pycache__ -print -quit)"
    test -z "$unexpected_dir"
    tmp="$(mktemp -d)"
    trap 'rm -rf "$tmp"' EXIT
    repo="$(pwd)"
    (cd "$tmp" && "$repo/$start" --help >"$tmp/overseer-start-help.out")
    grep -F "the /overseer skill's two-pane bootstrap" "$tmp/overseer-start-help.out" >/dev/null

# Repo-local live delegate for `harnesses.codex.status = "supported"`
# (overseer-kju6wh). The fleet Verifier's codex arm is a
# DelegatedResolutionRunner that returns available=False -> SKIP, and
# `_parse_supported` accepts ANY non-empty `canonical_command`, so this
# recipe is the only thing that makes that declaration load-bearing. It
# drives a real Codex TUI over a pty into `/skills` and requires the
# picker to render the row named by the DECLARED canonical_command.
#
# TWO DECLARED SKIP LAYERS, and they are deviations recorded on purpose
# rather than inherited from the template in silence:
#
#   1. CI. A hosted runner has no authenticated codex and no host plugin
#      cache, so this cannot run there. `LIVESPEC_REQUIRE_CODEX_TUI_PICKER=1`
#      opts an authenticated runner in. The consequence is stated plainly:
#      THE CI GREEN FOR THIS SLUG IS NOT EVIDENCE. Local `just check` is,
#      and this repo's pre-commit and pre-push both route through it.
#   2. No `codex` on PATH. A contributor without codex installed is not
#      told their tree is broken.
#
# DELIBERATELY NOT ADDED TO THE CI MATRIX in .github/workflows/ci.yml. A
# matrix entry that can only ever skip manufactures a green CI row that
# reads as coverage; leaving it out keeps the skip honest and visible here.
check-codex-skill-picker:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ "${CI:-}" == "true" && "${LIVESPEC_REQUIRE_CODEX_TUI_PICKER:-}" != "1" ]]; then
        echo ":: check-codex-skill-picker: skipped in CI; set LIVESPEC_REQUIRE_CODEX_TUI_PICKER=1 on an authenticated Codex runner to enforce it"
        exit 0
    fi
    if ! command -v codex >/dev/null 2>&1; then
        echo ":: check-codex-skill-picker: codex CLI not found; skipping live TUI picker acceptance"
        exit 0
    fi
    LIVESPEC_CODEX_SKILL_PICKER=1 uv run pytest tests/e2e-cli/test_codex_skill_picker.py -v

# ---------------------------------------------------------------
# Pre-commit aggregate — Red-mode-aware. Classifies the staged
# tree shape; in Red mode it passes `skip="check-coverage
# check-per-file-coverage"` to `just check` so the coverage gates
# are omitted (the commit-msg replay hook is the verifier; coverage
# is checked at the Green amend). This is a self-contained recipe
# argument — there is NO ambient env var (epic li-cvaudit, cvredmd).
# Pre-push and CI keep invoking `just check` directly.
# ---------------------------------------------------------------

check-pre-commit:
    #!/usr/bin/env bash
    set -uo pipefail
    staged=$(git diff --cached --name-only --diff-filter=AM)
    py_staged=$(echo "$staged" | grep -E '\.py$' || true)
    test_staged=$(echo "$staged" | grep -E '^tests/.*\.py$' || true)
    impl_staged=$(echo "$staged" | grep -E '^overseer/.*\.py$' || true)
    test_count=0
    impl_count=0
    [[ -n "$test_staged" ]] && test_count=$(echo "$test_staged" | wc -l)
    [[ -n "$impl_staged" ]] && impl_count=$(echo "$impl_staged" | wc -l)
    if [[ -z "$py_staged" ]]; then
        echo ":: doc-only mode detected (zero .py files staged): running just check-pre-commit-doc-only"
        echo ":: pre-push + CI keep the full aggregate as the load-bearing safety net"
        just check-pre-commit-doc-only
        exit $?
    fi
    if [[ "$test_count" -eq 1 ]] && [[ "$impl_count" -eq 0 ]]; then
        echo ":: Red-mode shape detected: $test_staged"
        echo ":: skipping coverage gates (commit-msg replay hook is the verifier; coverage runs at Green amend)"
        just skip="check-coverage check-per-file-coverage" check
        exit $?
    fi
    # Green-amend shape: impl staged while HEAD still carries Red-only
    # trailers (the Green amend has not yet written its TDD-Green-*
    # trailers — the commit-msg `check-red-green-replay {1}` hook writes
    # AND verifies them immediately after this pre-commit pass). The
    # no-arg `check-red-green-replay` aggregate variant validates HEAD,
    # which during a Green amend is the in-progress Red commit; it would
    # otherwise reject a perfectly valid Green amend. Skip the aggregate
    # variant here (the commit-msg hook is the load-bearing per-commit
    # verifier); pre-push + CI re-run the full no-arg aggregate against
    # the completed Red->Green HEAD as the safety net.
    head_msg=$(git log -1 --format=%B 2>/dev/null || true)
    if [[ "$impl_count" -ge 1 ]] \
        && grep -q 'TDD-Red-Test-File-Checksum:' <<< "$head_msg" \
        && ! grep -q 'TDD-Green-Verified-At:' <<< "$head_msg"; then
        echo ":: Green-amend shape detected (impl staged; HEAD carries Red-only trailers)"
        echo ":: skipping no-arg check-red-green-replay (commit-msg replay hook verifies the Green amend)"
        just skip="check-red-green-replay" check
        exit $?
    fi
    just check

# When zero `.py` files are staged, `check-pre-commit` delegates here.
# Pre-push delegates here via `check-pre-push` for zero-py changesets.
check-pre-commit-doc-only:
    #!/usr/bin/env bash
    set -uo pipefail
    echo ":: doc-only subset (no repo-metadata checks wired yet)"
    exit 0

# Skip the Python-code check subset when the pushed commits contain
# zero `.py` changes. Falls back to `origin/master` when no upstream
# branch is configured locally.
check-pre-push:
    #!/usr/bin/env bash
    set -uo pipefail
    upstream=$(git rev-parse --abbrev-ref --symbolic-full-name @{upstream} 2>/dev/null || echo "origin/master")
    changeset=$(git diff --name-only "${upstream}..HEAD")
    py_changed=$(echo "$changeset" | grep -E '\.py$' || true)
    if [[ -z "$py_changed" ]]; then
        echo ":: doc-only push detected (zero .py changes vs ${upstream}): running check-pre-commit-doc-only"
        just check-pre-commit-doc-only
        exit $?
    fi
    if uv run python -m livespec_dev_tooling.green_token check 2>&1; then
        echo ":: pre-push: green token matched — tree byte-identical to last green check; skipping full aggregate (CI is authoritative)"
        exit 0
    fi
    just check

# ---------------------------------------------------------------
# Pre-commit auxiliary gates.
# ---------------------------------------------------------------

# Ruff fix + format on staged .py files BEFORE the rest of the
# pre-commit gate runs. Non-blocking — unfixable issues fall through
# to check-lint / check-format inside `just check` later. Re-stages
# post-autofix bytes.
lint-autofix-staged:
    #!/usr/bin/env bash
    set -uo pipefail
    staged=$(git diff --cached --name-only --diff-filter=AM | grep -E '\.py$' || true)
    if [[ -z "$staged" ]]; then
        exit 0
    fi
    echo "$staged" | xargs uv run ruff check --fix --exit-zero
    echo "$staged" | xargs uv run ruff format
    echo "$staged" | xargs git add

# ---------------------------------------------------------------
# Mutating targets (opt-in; not run in CI).
# ---------------------------------------------------------------

fmt:
    uv run ruff format .

lint-fix:
    uv run ruff check --fix .

check-partition-completeness:
    uv run python -m livespec_dev_tooling.checks.partition_completeness

check-canonical-recipe-fidelity:
    uv run python -m livespec_dev_tooling.checks.canonical_recipe_fidelity

check-ci-matrix-completeness:
    uv run python -m livespec_dev_tooling.checks.ci_matrix_completeness

check-no-fmt-directives:
    uv run python -m livespec_dev_tooling.checks.no_fmt_directives

check-local-memory-drift-audit:
    uv run python -m livespec_dev_tooling.checks.local_memory_drift_audit

check-no-shadow-ledger-body-identical:
    uv run python -m livespec_dev_tooling.checks.no_shadow_ledger_body_identical

check-handoff-dispatch-routing:
    uv run python -m livespec_dev_tooling.checks.handoff_dispatch_routing

check-self-hosted-routing:
    uv run python -m livespec_dev_tooling.checks.self_hosted_routing

check-source-trees-scoped-to-consumer:
    uv run python -m livespec_dev_tooling.checks.source_trees_scoped_to_consumer

check-plan-thread-anchor-declared:
    uv run python -m livespec_dev_tooling.checks.plan_thread_anchor_declared

check-plan-thread-epic-parity:
    uv run python -m livespec_dev_tooling.checks.plan_thread_epic_parity

check-no-shadow-ledger-body-typechecks:
    uv run python -m livespec_dev_tooling.checks.no_shadow_ledger_body_typechecks

check-no-workflow-edits:
    #!/usr/bin/env bash
    set -euo pipefail
    committed="$(git diff --name-only origin/master...HEAD -- .github/workflows)"
    local_changes="$(git status --short -- .github/workflows)"
    if [[ -n "$committed" || -n "$local_changes" ]]; then
        {
            echo "Factory branches must not modify .github/workflows/."
            if [[ -n "$committed" ]]; then
                echo
                echo "Committed workflow changes:"
                echo "$committed"
            fi
            if [[ -n "$local_changes" ]]; then
                echo
                echo "Local workflow changes:"
                echo "$local_changes"
            fi
        } >&2
        exit 1
    fi

check-required-role-keys-declared:
    uv run python -m livespec_dev_tooling.checks.required_role_keys_declared

check-hook-trees-not-io-exempt:
    uv run python -m livespec_dev_tooling.checks.hook_trees_not_io_exempt
