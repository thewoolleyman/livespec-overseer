"""Production-path tests for caam rendering (work-item overseer-54k2za.38).

Carrier R12's trigger header shipped defined, exported, unit-tested and NEVER
CALLED. The unit test that existed for it asserted the format string by calling
the function directly, which passes forever against a function nothing invokes --
so these tests drive the PROGRAM and assert on what a pass actually emits.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
from types import ModuleType

import caam_rendering
from caam_anthropic_loop import Flags
from caam_anthropic_pass import run_pass
from caam_decision import UsageRecord

__all__: list[str] = []

OVERSEER_DIR = Path(__file__).resolve().parents[1] / "overseer"


def _usage(*, five_hour: float = 20.0, seven_day: float = 30.0) -> UsageRecord:
    return UsageRecord(
        five_hour_remaining=100.0 - five_hour,
        seven_day_remaining=100.0 - seven_day,
        five_hour_resets_at="2026-08-22T12:00:00Z",
        seven_day_resets_at="2026-08-24T00:00:00Z",
        fable_remaining=90.0,
        fable_resets_at="2026-08-24T00:00:00Z",
    )


class _FakeProcess:
    returncode = 0
    stdout = '{"tools": [{"tool": "claude", "active_profile": "active"}]}'
    stderr = ""


def _flags() -> Flags:
    return Flags(
        scheduled=True,
        force=False,
        dry_run=False,
        no_models=True,
        no_warm=True,
        foreman_model=None,
        session_models=(),
        protected_accounts=(),
    )


def _home_with_profiles(*, tmp_path: Path, names: tuple[str, ...]) -> Path:
    for name in names:
        (tmp_path / ".local/share/caam/vault/claude" / name).mkdir(parents=True)
    return tmp_path


def _run(*, home: Path, lines: list[str], fetcher) -> int:
    return run_pass(
        flags=_flags(),
        home=home,
        now=1787395200.0,
        stdout=lines.append,
        caam_runner=lambda *, args: _FakeProcess(),
        fetcher=fetcher,
        save_state=lambda *, state, state_path: None,
    )


def test_production_pass_emits_the_trigger_header(*, tmp_path: Path) -> None:
    """LEG 1. Only process boundaries are seamed: the account manager subprocess,
    the usage endpoint, and the state file. Nothing in the rendering or decision
    path is stubbed, so this fails if the header has no production caller."""
    lines: list[str] = []

    code = _run(
        home=_home_with_profiles(tmp_path=tmp_path, names=("active", "other")),
        lines=lines,
        fetcher=lambda *, creds_path, now=None: (_usage(), None),
    )

    assert code == 0
    headers = [line for line in lines if "  triggers: " in line]
    assert len(headers) == 1, f"expected exactly one trigger header, got {headers}"


def test_trigger_header_text_and_position_match_the_oracle(*, tmp_path: Path) -> None:
    """LEG 2. The oracle emits the header immediately after the active profile is
    resolved and BEFORE resnapshot, so it precedes the table on every pass. Its
    text is compared against the renderer's own contract for the same stamp."""
    lines: list[str] = []

    _ = _run(
        home=_home_with_profiles(tmp_path=tmp_path, names=("active", "other")),
        lines=lines,
        fetcher=lambda *, creds_path, now=None: (_usage(), None),
    )

    header_index = next(i for i, line in enumerate(lines) if "  triggers: " in line)
    table_index = next(i for i, line in enumerate(lines) if "PROFILE" in line and "5H" in line)
    assert header_index < table_index, "the header must precede the table"
    assert lines[header_index] == caam_rendering.trigger_header(stamp="2026-08-22T10:40:00Z")


def test_trigger_header_survives_the_unreadable_active_usage_path(*, tmp_path: Path) -> None:
    """LEG 3. The oracle prints the header before it ever reads usage, so a pass
    that then FAILS to read the active profile's usage still shows it."""
    lines: list[str] = []

    def fetcher(*, creds_path: Path, now: float | None = None):
        del now, creds_path
        return None, "boom"

    code = _run(
        home=_home_with_profiles(tmp_path=tmp_path, names=("active", "other")),
        lines=lines,
        fetcher=fetcher,
    )

    assert code == 2
    header_index = next(i for i, line in enumerate(lines) if "  triggers: " in line)
    fail_index = next(
        i for i, line in enumerate(lines) if line.startswith("FAIL cannot read usage")
    )
    assert header_index < fail_index


def _module_of(*, path: Path) -> ModuleType:
    return importlib.import_module(path.stem)


def _exported_names(*, path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        target = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target = node.target.id
        elif isinstance(node, ast.Assign) and node.targets:
            first = node.targets[0]
            target = first.id if isinstance(first, ast.Name) else None
        if target == "__all__" and isinstance(node.value, ast.List | ast.Tuple):
            return [
                element.value
                for element in node.value.elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            ]
    return []


def _assign_target(*, node: ast.AST) -> str | None:
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    if isinstance(node, ast.Assign) and node.targets:
        first = node.targets[0]
        return first.id if isinstance(first, ast.Name) else None
    return None


def _non_use_node_ids(*, tree: ast.AST) -> set[int]:
    """Node ids that must not count as uses: `import` statements and the
    `__all__` literal. Both mention a name without calling it, and together with
    the `def` that declares it they are the entire footprint of an orphan."""
    skip: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom) or _assign_target(node=node) == "__all__":
            skip.update(id(child) for child in ast.walk(node))
    return skip


def _production_uses() -> set[str]:
    """Every name USED by production code under overseer/ -- a load of a bare
    name, or an attribute access. A `def` statement's own name is not a Name
    node, so declaring a function never counts as calling it."""
    uses: set[str] = set()
    for path in sorted(OVERSEER_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        skip = _non_use_node_ids(tree=tree)
        for node in ast.walk(tree):
            if id(node) in skip:
                continue
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                uses.add(node.id)
            elif isinstance(node, ast.Attribute):
                uses.add(node.attr)
    return uses


def test_the_orphan_detector_discriminates() -> None:
    """The control. A detector that cannot report a known-used name as used is
    not measuring anything, and one that cannot flag a name nothing calls would
    have passed while carrier R12 was dark. Both directions are asserted here so
    the leg-4 test below is trustworthy rather than merely green."""
    uses = _production_uses()
    assert "current_cell" in uses, "a helper called inside its own module IS used"
    assert "render_table" in uses, "a helper called across modules IS used"
    assert "no_such_renderer_exists" not in uses


def test_no_exported_renderer_or_decision_helper_is_orphaned() -> None:
    """LEG 4. Two carriers have now shipped exported-and-uncalled -- model
    enforcement (overseer-54k2za.26) and this one. Finding the third by running
    the program is luck; this is the method."""
    uses = _production_uses()
    orphans: list[str] = []
    for module_name in ("caam_rendering", "caam_decision"):
        path = OVERSEER_DIR / f"{module_name}.py"
        for name in _exported_names(path=path):
            if name not in uses:
                orphans.append(f"{module_name}.{name}")
    assert orphans == [], f"exported but never called from production: {orphans}"
