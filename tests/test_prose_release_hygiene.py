"""Gate fixtures for `just check-prose-release-hygiene` (work-item overseer-d4t).

These drive the REAL justfile recipe against synthetic repositories rather
than re-implementing its rule in Python. A gate whose fixtures test a COPY
of the rule goes green while the shipped rule rots — the same
verifier-that-cannot-fail shape the supervisor-prompt-quality epic exists to
remove.

WHAT THE RULE IS. If the commit range changes `.claude-plugin/prose/`, the
range must carry at least one commit release-please will act on
(`feat`/`fix`/`perf`/`revert`, or any type with a `!` breaking marker).
Otherwise no version bump is cut, no release ships, and the prose fix never
reaches the plugin cache that actually generates charters.

BOTH LEGS ARE INDEPENDENTLY DEMONSTRATED, which is what makes a green here
mean something. Each leg is pinned by an ASYMMETRIC PAIR differing in
exactly one variable:
  - prose-detection leg: `docs:` + prose changed is RED, `docs:` with prose
    UNTOUCHED is GREEN. Only the prose changed, so the prose test is
    load-bearing.
  - releasing-type leg: prose changed + `docs:` is RED, prose changed +
    `fix:` is GREEN. Only the subject changed, so the type test is
    load-bearing.
Neither leg can be deleted without one of those pairs collapsing.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_JUSTFILE = _REPO_ROOT / "justfile"
_PROSE_FILE = ".claude-plugin/prose/supervise-plan.md"

# The four subjects below are REAL commits from this repo's history that
# changed generator prose under a type release-please will not release.
# They are the empirical case for this gate: the hole is measured, not
# hypothetical. Kept as data so the gate is pinned against the shapes that
# actually got through.
_HISTORICAL_NON_RELEASING = (
    "docs: emit verification discipline commands",
    "chore(prompt): ratify supervisor obligation re-entry",
    "test(prompts): prove the SUPERVISOR half of the pair is a live agent",
    "docs(supervise-plan): the generator emits both stall modes and real commands",
)

_HISTORICAL_RELEASING = (
    "feat: enforce supervisor handoff confirmations",
    "fix: harden generated supervisor prompt gates",
    "feat: gate cold-open supervisor prompts",
    "fix(supervise-plan): the generated charter prohibits killing the acting daemon",
)


def _git(repo: Path, *args: str) -> None:
    """Build synthetic history. Every argument is a literal from this module.

    S603/S607 suppressed on the same narrow reasoning as the sibling real-tmux
    fixture: the argv is fixed here and `git` must resolve the way the recipe
    resolves it, so pinning an absolute path would test a different program
    from the one CI runs.
    """
    subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _make_repo(root: Path, name: str, *, subject: str, touch_prose: bool) -> Path:
    """A repo with a `basepoint` ref and one commit on top of it."""
    repo = root / name
    (repo / ".claude-plugin" / "prose").mkdir(parents=True)
    (repo / _PROSE_FILE).write_text("base prose\n")
    (repo / "README.md").write_text("base readme\n")
    _git(repo, "init", "-q", ".")
    _git(repo, "config", "user.email", "gate@example.invalid")
    _git(repo, "config", "user.name", "gate")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "chore: base")
    _git(repo, "branch", "-f", "basepoint")
    target = _PROSE_FILE if touch_prose else "README.md"
    (repo / target).write_text("changed\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", subject)
    return repo


def _run_gate(repo: Path, *, base: str = "basepoint") -> subprocess.CompletedProcess[str]:
    """Invoke the real recipe with its refs pointed at the synthetic repo."""
    return subprocess.run(  # noqa: S603
        [  # noqa: S607
            "just",
            "--justfile",
            str(_JUSTFILE),
            "--working-directory",
            str(repo),
            "check-prose-release-hygiene",
        ],
        capture_output=True,
        text=True,
        # Explicit: a non-zero exit IS the observation under test.
        check=False,
        # Inherit the caller's environment rather than fabricating a PATH:
        # `just` is provided by mise here and by the runner image in CI, so a
        # hand-built PATH would pass locally and vanish in one of them.
        env={**os.environ, "PROSE_HYGIENE_BASE": base},
    )


def test_prose_changed_under_a_docs_subject_is_rejected(tmp_path):
    repo = _make_repo(tmp_path, "docs", subject=_HISTORICAL_NON_RELEASING[0], touch_prose=True)
    result = _run_gate(repo)
    assert result.returncode == 1
    assert "NO release-triggering commit" in result.stderr
    # The message must name the offending file and offer a remedy: a HALT
    # with no remedy is a guaranteed stall (this epic's family-3 defect).
    assert _PROSE_FILE in result.stderr
    assert "REMEDY:" in result.stderr


def test_prose_changed_under_a_fix_subject_is_accepted(tmp_path):
    repo = _make_repo(tmp_path, "fix", subject=_HISTORICAL_RELEASING[1], touch_prose=True)
    result = _run_gate(repo)
    assert result.returncode == 0, result.stderr
    assert "releasing commit(s) present" in result.stdout


def test_a_breaking_marker_releases_even_on_a_non_releasing_type(tmp_path):
    """`refactor` never bumps, but `refactor!` does — the marker decides."""
    repo = _make_repo(
        tmp_path, "bang", subject="refactor!: drop the legacy target form", touch_prose=True
    )
    result = _run_gate(repo)
    assert result.returncode == 0, result.stderr


def test_a_non_releasing_subject_is_fine_when_no_prose_changed(tmp_path):
    """The prose-detection half of the asymmetric pair.

    Same non-releasing subject as the rejected case; only the prose is
    untouched. If this went red the gate would be firing on every docs
    commit in the repo and would be turned off within a day.
    """
    repo = _make_repo(tmp_path, "noprose", subject=_HISTORICAL_NON_RELEASING[0], touch_prose=False)
    result = _run_gate(repo)
    assert result.returncode == 0, result.stderr
    assert "no generator prose changed" in result.stdout


def test_every_historical_non_releasing_subject_is_caught(tmp_path):
    for index, subject in enumerate(_HISTORICAL_NON_RELEASING):
        repo = _make_repo(tmp_path, f"hist-red-{index}", subject=subject, touch_prose=True)
        result = _run_gate(repo)
        assert result.returncode == 1, f"{subject!r} should be caught: {result.stdout}"


def test_every_historical_releasing_subject_is_allowed(tmp_path):
    for index, subject in enumerate(_HISTORICAL_RELEASING):
        repo = _make_repo(tmp_path, f"hist-green-{index}", subject=subject, touch_prose=True)
        result = _run_gate(repo)
        assert result.returncode == 0, f"{subject!r} should pass: {result.stderr}"


def test_an_unresolvable_base_ref_fails_loudly_rather_than_skipping(tmp_path):
    """A shallow clone must not read as a clean pass.

    This gate reads a commit range, so a depth-1 checkout cannot satisfy
    it. Exiting 0 there would make the gate silently absent in exactly
    the environment where nobody is watching.
    """
    repo = _make_repo(tmp_path, "shallow", subject=_HISTORICAL_NON_RELEASING[0], touch_prose=True)
    result = _run_gate(repo, base="no-such-ref")
    assert result.returncode == 1
    assert "cannot resolve base ref" in result.stderr
    assert "shallow" in result.stderr
