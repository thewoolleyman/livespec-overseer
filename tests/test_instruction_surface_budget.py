"""Tests for the always-loaded instruction surface budget gate."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO_ROOT / "scripts" / "check-instruction-surface-budget.py"
# The budget and the harness limit are asserted as LITERALS rather than read
# back off the module under test: a gate whose threshold is whatever its own
# source says cannot fail by changing the threshold, which is the "not
# satisfied by raising the threshold when the gate fires" clause of this
# work-item's acceptance.
_BUDGET = 145_000
_HARNESS_LIMIT = 150_000
_RETIRED_ENFORCE_ENV = "LIVESPEC_FAIL_IF_INSTRUCTION_SURFACE_OVER_BUDGET"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("instruction_surface_budget", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_surface(*, root: Path, chars: int, symlink: bool) -> None:
    """Build a fixture checkout whose root instruction surface holds `chars` characters.

    `symlink` mirrors this repo's own layout, where `CLAUDE.md` is a symlink
    to `AGENTS.md` and the two names are therefore ONE file. Both shapes are
    exercised so neither the symlinked nor the bare tree is left unmeasured.
    """
    root.mkdir(parents=True, exist_ok=True)
    agents = root / "AGENTS.md"
    _ = agents.write_text("x" * chars, encoding="utf-8")
    if symlink:
        (root / "CLAUDE.md").symlink_to(agents)


def test_instruction_surface_budget_counts_utf8_characters_not_bytes(tmp_path: Path) -> None:
    module = _load_module()
    agents = tmp_path / "AGENTS.md"
    _ = agents.write_text("abcé\n", encoding="utf-8")
    claude = tmp_path / "CLAUDE.md"
    claude.symlink_to(agents)

    report = module.measure_instruction_surface(root=tmp_path, budget=10)

    assert report.current_chars == 5
    assert agents.read_bytes().__len__() == 6
    assert report.headroom == 5


def test_instruction_surface_budget_deduplicates_symlinked_surface(tmp_path: Path) -> None:
    module = _load_module()
    agents = tmp_path / "AGENTS.md"
    _ = agents.write_text("abcd", encoding="utf-8")
    claude = tmp_path / "CLAUDE.md"
    claude.symlink_to(agents)

    report = module.measure_instruction_surface(root=tmp_path, budget=5)

    assert report.current_chars == 4
    assert report.paths == (agents,)


def test_instruction_surface_budget_fails_over_and_passes_under_in_one_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """THE DISCRIMINATING CONTROL: both fixture trees, one pytest run, no env and no flag.

    A size gate that cannot fail would report a clean instruction surface
    forever, so the over-budget tree and the under-budget tree are measured
    in the SAME run and the two verdicts must differ. Neither invocation
    sets an enforcement environment variable or an enforcement flag — the
    gate is armed by construction.
    """
    module = _load_module()
    monkeypatch.delenv(_RETIRED_ENFORCE_ENV, raising=False)
    under = tmp_path / "under"
    over = tmp_path / "over"
    _write_surface(root=under, chars=_BUDGET - 1, symlink=True)
    _write_surface(root=over, chars=_BUDGET + 1, symlink=False)

    under_code = module.main(argv=["--root", str(under)])
    under_report = capsys.readouterr()
    over_code = module.main(argv=["--root", str(over)])
    over_report = capsys.readouterr()

    assert under_code == 0
    assert "OK: instruction surface within budget" in under_report.out
    assert f"current={_BUDGET - 1} chars" in under_report.out
    assert f"budget={_BUDGET} chars" in under_report.out
    assert "headroom=1 chars" in under_report.out
    assert over_code != 0
    assert "ERROR: instruction surface over budget" in over_report.err
    assert f"current={_BUDGET + 1} chars" in over_report.err
    assert f"budget={_BUDGET} chars" in over_report.err
    assert f"harness_limit={_HARNESS_LIMIT} chars" in over_report.err
    assert "overflow=1 chars" in over_report.err


def test_instruction_surface_report_names_the_user_global_file_and_its_reserve(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Both branches must name what the measured population CANNOT see.

    The harness limit covers every instruction file it loads, including the
    user-global `~/.claude/CLAUDE.md`, which lies outside any repository and
    whose size is not fixed. A figure summing less than the limit it is
    compared against is misleading unless it says so, so the OK branch and
    the ERROR branch both carry the note.
    """
    module = _load_module()
    under = tmp_path / "under"
    over = tmp_path / "over"
    _write_surface(root=under, chars=4, symlink=True)
    _write_surface(root=over, chars=_BUDGET + 1, symlink=True)

    _ = module.main(argv=["--root", str(under)])
    under_report = capsys.readouterr()
    _ = module.main(argv=["--root", str(over)])
    over_report = capsys.readouterr()

    for text in (under_report.out, over_report.err):
        assert "~/.claude/CLAUDE.md" in text
        assert "OUTSIDE" in text
        assert f"{_HARNESS_LIMIT - _BUDGET}-char reserve" in text
        assert f"{_HARNESS_LIMIT}-char harness limit" in text


def test_instruction_surface_budget_cannot_be_disarmed_by_the_retired_env_lever(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The gate shipped WARN-only behind an env lever nothing ever set; the lever is retired.

    Asserted behaviourally rather than by grepping the source, because the
    lever also carried an INVERSION worth closing for good: enforcement was
    tested with `bool(os.environ.get(...))`, and `bool("0")` is True, so the
    conventional spelling of OFF switched it ON. No value of the retired
    name may change the verdict in either direction.
    """
    module = _load_module()
    over = tmp_path / "over"
    _write_surface(root=over, chars=_BUDGET + 1, symlink=True)

    for value in ("", "0", "false", "1"):
        monkeypatch.setenv(_RETIRED_ENFORCE_ENV, value)

        assert module.main(argv=["--root", str(over)]) == 1
        _ = capsys.readouterr()


def test_instruction_surface_budget_passes_on_this_checkout(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The armed gate is green on THIS tree, which is what makes arming landable."""
    module = _load_module()
    monkeypatch.delenv(_RETIRED_ENFORCE_ENV, raising=False)
    current = len((_REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8"))

    return_code = module.main(argv=["--root", str(_REPO_ROOT)])
    captured = capsys.readouterr()

    assert current < _BUDGET
    assert return_code == 0
    assert f"current={current} chars" in captured.out
    assert f"budget={_BUDGET} chars" in captured.out
    assert f"headroom={_BUDGET - current} chars" in captured.out


def test_instruction_surface_budget_is_a_member_of_the_check_aggregate() -> None:
    """Membership in `targets=(...)` is what puts the gate in the aggregate's failing list.

    The aggregate runs every target, appends each non-zero one to `failed`,
    and prints that list before exiting non-zero — so an over-budget
    checkout fails `just check` WITH this target named, and the only thing
    a test can usefully pin is the wiring. Parsed out of the array rather
    than matched as a substring of the whole justfile: the recipe
    DEFINITION also contains the name, so a substring match passed a
    justfile that defined the target and never ran it.
    """
    justfile = (_REPO_ROOT / "justfile").read_text(encoding="utf-8")
    targets_block = re.search(r"\n    targets=\(\n(.*?)\n    \)\n", justfile, re.DOTALL)
    assert targets_block is not None
    members = {
        line.strip()
        for line in targets_block.group(1).splitlines()
        if line.strip() and not line.strip().startswith("#")
    }

    assert "check-instruction-surface-budget" in members
    assert 'failed+=("$t")' in justfile
    assert _RETIRED_ENFORCE_ENV not in justfile


def test_root_agents_md_names_every_ai_guidance_document() -> None:
    """Relocated guidance must be REACHABLE from the always-loaded file, not merely filed.

    `check-agents-ai-references-resolve` verifies that references RESOLVE,
    which a repo making no references at all passes with its guidance
    orphaned. This asserts the other direction: every `.ai/<topic>.md` the
    prune produced is named by its path in the file that is always loaded.
    """
    agents = (_REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    topics = sorted(path.name for path in (_REPO_ROOT / ".ai").glob("*.md"))

    assert topics
    assert [name for name in topics if f".ai/{name}" not in agents] == []
