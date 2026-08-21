"""Gate fixtures for `just check-prose-release-hygiene` (work-items overseer-d4t/zg0m).

These drive the REAL justfile recipe against synthetic repositories rather
than re-implementing its rule in Python. A gate whose fixtures test a COPY
of the rule goes green while the shipped rule rots — the same
verifier-that-cannot-fail shape the supervisor-prompt-quality epic exists to
remove.

WHAT THE RULE IS. If the commit range changes any shipped surface under
`.claude-plugin/`, the range must carry at least one commit release-please will
act on (`feat`/`fix`/`perf`/`revert`, or any type with a `!` breaking marker).
Otherwise no version bump is cut, no release ships, and the plugin fix never
reaches the cache that harnesses actually run.

BOTH LEGS ARE INDEPENDENTLY DEMONSTRATED, which is what makes a green here
mean something. Each leg is pinned by an ASYMMETRIC PAIR differing in
exactly one variable:
  - prose-detection leg: `docs:` + prose changed is RED, `docs:` with prose
    UNTOUCHED is GREEN. Only the prose changed, so the prose test is
    load-bearing.
  - non-prose shipped-surface leg: a real historical `docs:` commit that changed
    skill bindings and manifests is RED, while an ordinary unshipped docs commit
    stays GREEN.
  - releasing-type leg: prose changed + `docs:` is RED, prose changed +
    `fix:` is GREEN. Only the subject changed, so the type test is
    load-bearing.
Neither leg can be deleted without one of those pairs collapsing.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_JUSTFILE = _REPO_ROOT / "justfile"
_PROSE_FILE = ".claude-plugin/prose/supervise-plan.md"
_SKILL_FILE = ".claude-plugin/skills/supervise-plan/SKILL.md"
_PLUGIN_MANIFEST = ".claude-plugin/plugin.json"
_PLUGIN_VERSION = ".claude-plugin/overseer/version.json"
_STRANDED_BINDING_COMMIT = "6833264"

# The subjects below are REAL commits from this repo's history that changed
# shipped plugin surfaces under a type release-please will not release. They
# are the empirical case for this gate: the hole is measured, not hypothetical.
# Kept as data so the gate is pinned against the shapes that actually got
# through.
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


def _make_repo(
    root: Path, name: str, *, subject: str, touch_prose: bool, touch_plugin_binding: bool = False
) -> Path:
    """A repo with a `basepoint` ref and one commit on top of it."""
    repo = root / name
    (repo / ".claude-plugin" / "prose").mkdir(parents=True)
    (repo / ".claude-plugin" / "skills" / "supervise-plan").mkdir(parents=True)
    (repo / _PROSE_FILE).write_text("base prose\n")
    (repo / _SKILL_FILE).write_text("base binding\n")
    (repo / "README.md").write_text("base readme\n")
    _git(repo, "init", "-q", ".")
    _git(repo, "config", "user.email", "gate@example.invalid")
    _git(repo, "config", "user.name", "gate")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "chore: base")
    _git(repo, "branch", "-f", "basepoint")
    if touch_prose:
        target = _PROSE_FILE
    elif touch_plugin_binding:
        target = _SKILL_FILE
    else:
        target = "README.md"
    (repo / target).write_text("changed\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", subject)
    return repo


def _make_release_manifest_repo(root: Path, name: str, *, subject: str) -> Path:
    """A release-please-shaped repo with one manifest-only release commit."""
    repo = root / name
    (repo / ".claude-plugin" / "overseer").mkdir(parents=True)
    (repo / _PLUGIN_MANIFEST).write_text('{"name": "overseer", "version": "1.7.9"}\n')
    (repo / _PLUGIN_VERSION).write_text('{"version": "1.7.9"}\n')
    (repo / "README.md").write_text("base readme\n")
    _git(repo, "init", "-q", ".")
    _git(repo, "config", "user.email", "gate@example.invalid")
    _git(repo, "config", "user.name", "gate")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "chore: base")
    _git(repo, "branch", "-f", "basepoint")
    (repo / _PLUGIN_MANIFEST).write_text('{"name": "overseer", "version": "1.8.0"}\n')
    (repo / _PLUGIN_VERSION).write_text('{"version": "1.8.0"}\n')
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", subject)
    return repo


def _make_repo_without_prose_at_base(root: Path, name: str) -> Path:
    """A repo whose base ref cannot resolve the configured plugin root."""
    repo = root / name
    repo.mkdir()
    (repo / "README.md").write_text("base readme\n")
    _git(repo, "init", "-q", ".")
    _git(repo, "config", "user.email", "gate@example.invalid")
    _git(repo, "config", "user.name", "gate")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "chore: base")
    _git(repo, "branch", "-f", "basepoint")
    (repo / "README.md").write_text("changed\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "docs: ordinary readme edit")
    return repo


def _make_repo_without_prose_at_head(root: Path, name: str) -> Path:
    """A repo whose head ref cannot resolve the configured plugin root."""
    repo = root / name
    (repo / ".claude-plugin" / "prose").mkdir(parents=True)
    (repo / _PROSE_FILE).write_text("base prose\n")
    _git(repo, "init", "-q", ".")
    _git(repo, "config", "user.email", "gate@example.invalid")
    _git(repo, "config", "user.name", "gate")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "chore: base")
    _git(repo, "branch", "-f", "basepoint")
    (repo / _PROSE_FILE).unlink()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "fix: remove shipped plugin directory")
    return repo


def _run_gate(
    repo: Path, *, base: str = "basepoint", head: str = "HEAD"
) -> subprocess.CompletedProcess[str]:
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
        env={**os.environ, "PROSE_HYGIENE_BASE": base, "PROSE_HYGIENE_HEAD": head},
    )


def _run_gate_under_pty_with_blocking_pager(
    repo: Path, *, pager: Path, timeout_seconds: float = 2.0
) -> tuple[int | None, str]:
    """Run the real recipe under a TTY with a pager that would hang if invoked."""
    env = {**os.environ, "PROSE_HYGIENE_BASE": "basepoint", "PAGER": str(pager)}
    env.pop("GIT_PAGER", None)
    command = " ".join(
        (
            "just",
            "--justfile",
            shlex.quote(str(_JUSTFILE)),
            "--working-directory",
            shlex.quote(str(repo)),
            "check-prose-release-hygiene",
        )
    )
    try:
        result = subprocess.run(  # noqa: S603
            ["script", "-q", "-e", "-c", command, "/dev/null"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
            env=env,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return None, _timeout_output(exc)
    return result.returncode, result.stdout + result.stderr


def _timeout_output(exc: subprocess.TimeoutExpired[str]) -> str:
    output = ""
    for stream in (exc.stdout, exc.stderr):
        if isinstance(stream, bytes):
            output += stream.decode(errors="replace")
        elif stream is not None:
            output += stream
    return output


def test_prose_changed_under_a_docs_subject_is_rejected(tmp_path):
    repo = _make_repo(tmp_path, "docs", subject=_HISTORICAL_NON_RELEASING[0], touch_prose=True)
    result = _run_gate(repo)
    assert result.returncode == 1
    assert "NO release-triggering commit" in result.stderr
    # The message must name the offending file and offer a remedy: a HALT
    # with no remedy is a guaranteed stall (this epic's family-3 defect).
    assert _PROSE_FILE in result.stderr
    assert "Repository: docs" in result.stderr
    assert "REMEDY:" in result.stderr


def test_plugin_binding_changed_under_a_docs_subject_is_rejected(tmp_path):
    repo = _make_repo(
        tmp_path,
        "binding",
        subject="docs(skill): clarify the supervise-plan binding",
        touch_prose=False,
        touch_plugin_binding=True,
    )
    result = _run_gate(repo)
    assert result.returncode == 1
    assert "NO release-triggering commit" in result.stderr
    assert _SKILL_FILE in result.stderr
    assert "Repository: binding" in result.stderr
    assert "docs(skill): clarify the supervise-plan binding" in result.stderr


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


def test_release_please_manifest_only_release_commit_is_accepted(tmp_path):
    repo = _make_release_manifest_repo(
        tmp_path,
        "release-please",
        subject="chore(master): release 1.8.0",
    )
    result = _run_gate(repo)
    assert result.returncode == 0, result.stderr
    assert "release-please manifest bump" in result.stdout
    assert "NO release-triggering commit" not in result.stderr


def test_plugin_manifest_changed_under_an_ordinary_chore_subject_is_rejected(tmp_path):
    repo = _make_release_manifest_repo(
        tmp_path,
        "manifest-chore",
        subject="chore: adjust plugin manifest",
    )
    result = _run_gate(repo)
    assert result.returncode == 1
    assert "NO release-triggering commit" in result.stderr
    assert _PLUGIN_MANIFEST in result.stderr
    assert _PLUGIN_VERSION in result.stderr
    assert "chore: adjust plugin manifest" in result.stderr


def test_a_non_releasing_subject_is_fine_when_no_prose_changed(tmp_path):
    """The shipped-surface-detection half of the asymmetric pair.

    Same non-releasing subject as the rejected case; only the shipped plugin
    surface is untouched. If this went red the gate would be firing on every
    docs commit in the repo and would be turned off within a day.
    """
    repo = _make_repo(tmp_path, "noprose", subject=_HISTORICAL_NON_RELEASING[0], touch_prose=False)
    result = _run_gate(repo)
    assert result.returncode == 0, result.stderr
    assert "no shipped plugin surface changed" in result.stdout


def _stranded_commit_is_reachable() -> bool:
    """Report whether the real RED fixture commit exists in this checkout.

    CI clones shallow, so a commit pinned by hash is absent there while it is
    present in any full clone. The gate itself refuses a range it cannot
    resolve — correctly — so without this guard the assertions below compare
    against that refusal instead of against a real verdict.
    """
    probe = subprocess.run(  # noqa: S603
        ["git", "cat-file", "-e", f"{_STRANDED_BINDING_COMMIT}^{{commit}}"],  # noqa: S607
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
    )
    return probe.returncode == 0


@pytest.mark.skipif(
    not _stranded_commit_is_reachable(),
    reason=(
        "real RED fixture commit is unreachable in a shallow clone; "
        "the hermetic _make_repo fixtures above cover the same verdict"
    ),
)
def test_historical_docs_typed_plugin_binding_commit_is_rejected():
    """Real RED fixture for overseer-zg0m: 6833264 stranded until later release."""
    result = _run_gate(
        _REPO_ROOT,
        base=f"{_STRANDED_BINDING_COMMIT}^",
        head=_STRANDED_BINDING_COMMIT,
    )
    assert result.returncode == 1
    assert "Repository: livespec-overseer" in result.stderr
    assert _STRANDED_BINDING_COMMIT in result.stderr
    assert "docs(grooming): bind the grooming operation into all three harnesses" in result.stderr
    assert ".claude-plugin/skills/grooming/SKILL.md" in result.stderr
    assert ".claude-plugin/plugin.json" in result.stderr
    assert "SCOPE: this detects the stranded case only" in result.stderr


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


def test_an_unresolvable_base_prose_path_fails_loudly_rather_than_skipping(tmp_path):
    repo = _make_repo_without_prose_at_base(tmp_path, "missing-base-prose")
    result = _run_gate(repo)
    assert result.returncode == 1
    assert "cannot resolve shipped plugin path" in result.stderr
    assert ".claude-plugin" in result.stderr
    assert "basepoint" in result.stderr
    assert "no shipped plugin surface changed" not in result.stdout


def test_an_unresolvable_head_prose_path_fails_loudly_even_with_a_releasing_commit(tmp_path):
    repo = _make_repo_without_prose_at_head(tmp_path, "missing-head-prose")
    result = _run_gate(repo)
    assert result.returncode == 1
    assert "cannot resolve shipped plugin path" in result.stderr
    assert ".claude-plugin" in result.stderr
    assert "HEAD" in result.stderr
    assert "releasing commit(s) present" not in result.stdout


def test_rejection_under_a_tty_cannot_block_on_the_git_pager(tmp_path):
    """RED: plain `git log` in the failure block invokes the pager and hangs."""
    repo = _make_repo(tmp_path, "pager", subject=_HISTORICAL_NON_RELEASING[0], touch_prose=True)
    pager = tmp_path / "blocking-pager.sh"
    pager.write_text("#!/usr/bin/env bash\necho PAGER-INVOKED >&2\nsleep 60\n")
    pager.chmod(0o755)

    returncode, output = _run_gate_under_pty_with_blocking_pager(repo, pager=pager)

    assert returncode == 1, output
    assert "PAGER-INVOKED" not in output
    assert "NO release-triggering commit" in output
    assert "Stranded shipped-surface commits in basepoint..HEAD:" in output
    assert "REMEDY:" in output
