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
import re
import stat
import subprocess
from pathlib import Path
from types import ModuleType

import pytest
from livespec_dev_tooling.install_worktree_pack import CANONICAL_NO_WORKFLOW_EDITS_BODY

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent
_AGENTS_GUIDANCE = _REPO_ROOT / "AGENTS.md"
_CLAUDE_GUIDANCE = _REPO_ROOT / "CLAUDE.md"
_SPEC_CHECK = _REPO_ROOT / "scripts" / "check-no-factory-spec-edits.sh"
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


def _workflow_check_declaration_name(*, script: str) -> str:
    match = re.search(r'^declaration="([^"]+)"$', script, flags=re.MULTILINE)
    assert match is not None
    return match.group(1)


def _workflow_check_required_keys(*, script: str) -> set[str]:
    return set(re.findall(r'declared_value "([^"]+)"', script))


def _ci_runner_routing_section(*, guidance: str) -> str:
    match = re.search(
        r"^## CI runner routing\n(?P<body>.*?)(?=^## |\Z)", guidance, re.DOTALL | re.MULTILINE
    )
    assert match is not None
    return match.group("body")


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


def test_agents_guidance_derives_workflow_exemption_literals_from_gate() -> None:
    """Agent guidance must name the same exemption contract the pack guard reads.

    The guard body is the worktree pack's single canonical
    ``check-no-workflow-edits.sh`` (livespec-dev-tooling fy02), installed
    untracked at ``dev-tooling/`` and byte-verified against the pinned package.
    The literals are derived from the constant the installer exposes -- the same
    object that byte-identity verifier asserts against -- so this test can never
    read a stale or absent copy.
    """
    script = CANONICAL_NO_WORKFLOW_EDITS_BODY
    declaration = _workflow_check_declaration_name(script=script)
    required_keys = _workflow_check_required_keys(script=script)

    assert required_keys == {"work_item", "reason"}
    for guidance_path in (_AGENTS_GUIDANCE, _CLAUDE_GUIDANCE):
        section = _ci_runner_routing_section(guidance=guidance_path.read_text(encoding="utf-8"))
        documented_declarations = set(re.findall(r"`(\.livespec-[^`]+)`", section))
        documented_keys = set(re.findall(r"`([A-Za-z0-9_]+)=`", section))

        assert documented_declarations == {declaration}
        assert documented_keys == required_keys
        for key in required_keys:
            assert f"`{key}=`" in section
        assert "legitimate engineering option" in section
        assert "GOVERNED here, not forbidden" in section


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
) -> tuple[int, str, str]:
    monkeypatch.setenv("DISPATCH_ACCEPTANCE_GUARD_BD", str(stub))
    module = _guard_module()
    rc = int(module.main([item_id]))
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def _live_exercise_item(
    *, labels: list[str], acceptance_criteria: object = "Evidence is recorded."
) -> dict[str, object]:
    return {
        "id": "overseer-fake1",
        "title": "harden the restart leg",
        "description": "Acceptance: closure requires live-exercise evidence on the item.",
        "acceptance_criteria": acceptance_criteria,
        "labels": labels,
    }


def test_guard_refuses_unlabeled_live_exercise_item(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Live-exercise criterion + no acceptance label -> refuse with the remedy."""
    stub = _stub_bd(root=tmp_path, item=_live_exercise_item(labels=["intake:triaged"]))

    rc, _stdout, stderr = _run_guard(
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

    rc, _stdout, stderr = _run_guard(
        stub=stub, item_id="overseer-fake1", monkeypatch=monkeypatch, capsys=capsys
    )

    assert rc == 0, stderr


def test_guard_refuses_empty_acceptance_bar(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An otherwise dispatchable item still needs a stated acceptance bar."""
    stub = _stub_bd(
        root=tmp_path,
        item={
            "id": "overseer-fake2",
            "title": "refactor a helper",
            "description": "Acceptance: just check green.",
            "acceptance_criteria": "",
            "labels": ["intake:triaged"],
        },
    )

    rc, _stdout, stderr = _run_guard(
        stub=stub, item_id="overseer-fake2", monkeypatch=monkeypatch, capsys=capsys
    )

    assert rc == 1, stderr
    assert "overseer-fake2" in stderr
    assert "missing acceptance bar" in stderr


@pytest.mark.parametrize("acceptance_criteria", [None, "", "   "])
def test_guard_treats_blank_acceptance_bar_as_empty(
    *,
    acceptance_criteria: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Absent, null, empty, and whitespace-only criteria are all empty."""
    item = {
        "id": "overseer-fake2",
        "title": "refactor a helper",
        "description": "Acceptance: just check green.",
        "labels": ["intake:triaged"],
    }
    if acceptance_criteria is not None:
        item["acceptance_criteria"] = acceptance_criteria
    stub = _stub_bd(root=tmp_path, item=item)

    rc, _stdout, stderr = _run_guard(
        stub=stub, item_id="overseer-fake2", monkeypatch=monkeypatch, capsys=capsys
    )

    assert rc == 1, stderr
    assert "missing acceptance bar" in stderr


def test_guard_passes_single_character_acceptance_bar(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A one-character bar is content; the guard must discriminate."""
    stub = _stub_bd(
        root=tmp_path,
        item={
            "id": "overseer-fake2",
            "title": "refactor a helper",
            "description": "Acceptance: just check green.",
            "acceptance_criteria": "x",
            "labels": ["intake:triaged"],
        },
    )

    rc, stdout, stderr = _run_guard(
        stub=stub, item_id="overseer-fake2", monkeypatch=monkeypatch, capsys=capsys
    )

    assert rc == 0, stderr
    assert "dispatch acceptance guard: overseer-fake2 ok" in stdout


def _host_tier_item(
    *,
    labels: list[str],
    description: str = "Move the ledger row and update the plan timeline.",
) -> dict[str, object]:
    return {
        "id": "overseer-host1",
        "title": "ledger-only plan cleanup",
        "description": description,
        "acceptance_criteria": "Ledger row and plan timeline are updated on the host.",
        "labels": labels,
    }


def test_guard_refuses_explicit_host_tier_before_sandbox_launch(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A positive dispatch-tier marker declares work no sandbox can perform."""
    stub = _stub_bd(
        root=tmp_path,
        item=_host_tier_item(labels=["dispatch-tier:host", "acceptance:ai-then-human"]),
    )

    rc, _stdout, stderr = _run_guard(
        stub=stub, item_id="overseer-host1", monkeypatch=monkeypatch, capsys=capsys
    )

    assert rc == 1, stderr
    assert "host-tier" in stderr
    assert "must never reach a sandbox" in stderr
    assert "acceptance:ai-then-human" not in stderr


def test_guard_refuses_malformed_dispatch_tier_label(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A malformed tier declaration fails closed instead of silently dispatching."""
    stub = _stub_bd(
        root=tmp_path,
        item=_host_tier_item(labels=["dispatch-tier:hostish"]),
    )

    rc, _stdout, stderr = _run_guard(
        stub=stub, item_id="overseer-host1", monkeypatch=monkeypatch, capsys=capsys
    )

    assert rc == 1, stderr
    assert "malformed dispatch-tier label" in stderr
    assert "dispatch-tier:hostish" in stderr
    assert "dispatch-tier:host" in stderr


def test_guard_refusal_text_distinguishes_host_tier_from_acceptance_parking(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Host-tier refusal and parking-label refusal answer different questions."""
    host_root = tmp_path / "host"
    parking_root = tmp_path / "parking"
    host_root.mkdir()
    parking_root.mkdir()
    host_stub = _stub_bd(root=host_root, item=_host_tier_item(labels=["dispatch-tier:host"]))
    parking_stub = _stub_bd(root=parking_root, item=_live_exercise_item(labels=["intake:triaged"]))

    host_rc, _host_stdout, host_stderr = _run_guard(
        stub=host_stub, item_id="overseer-host1", monkeypatch=monkeypatch, capsys=capsys
    )
    parking_rc, _parking_stdout, parking_stderr = _run_guard(
        stub=parking_stub, item_id="overseer-fake1", monkeypatch=monkeypatch, capsys=capsys
    )

    assert host_rc == 1, host_stderr
    assert parking_rc == 1, parking_stderr
    assert "must never reach a sandbox" in host_stderr
    assert "Label it first" not in host_stderr
    assert "Label it first" in parking_stderr
    assert host_stderr != parking_stderr


def test_guard_passes_ordinary_unlabelled_dispatchable_work(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """No dispatch-tier label is ordinary dispatchable work, not implicit host-tier."""
    stub = _stub_bd(
        root=tmp_path,
        item={
            "id": "overseer-fake4",
            "title": "tighten a parser branch",
            "description": "Acceptance: unit tests and just check pass.",
            "acceptance_criteria": "Unit tests and just check pass.",
            "labels": ["intake:triaged"],
        },
    )

    rc, stdout, stderr = _run_guard(
        stub=stub, item_id="overseer-fake4", monkeypatch=monkeypatch, capsys=capsys
    )

    assert rc == 0, stderr
    assert "dispatch acceptance guard: overseer-fake4 ok" in stdout


def test_guard_covers_non_live_exercise_host_tier_ledger_edit(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A ledger-edit item has no live-exercise wording and is still host-tier."""
    stub = _stub_bd(
        root=tmp_path,
        item=_host_tier_item(labels=["dispatch-tier:host"]),
    )

    rc, _stdout, stderr = _run_guard(
        stub=stub, item_id="overseer-host1", monkeypatch=monkeypatch, capsys=capsys
    )

    assert rc == 1, stderr
    assert "host-tier" in stderr


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
            "acceptance_criteria": "Observed on the production daemon.",
        },
    )

    rc, _stdout, stderr = _run_guard(
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

    rc, _stdout, stderr = _run_guard(
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

    rc, _stdout, stderr = _run_guard(
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

    rc_unparseable, _stdout_unparseable, stderr_unparseable = _run_guard(
        stub=unparseable, item_id="overseer-fake1", monkeypatch=monkeypatch, capsys=capsys
    )
    rc_empty, _stdout_empty, stderr_empty = _run_guard(
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
