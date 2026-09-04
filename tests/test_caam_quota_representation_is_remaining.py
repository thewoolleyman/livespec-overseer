"""The representation contract itself: quota percentages say REMAINING, once.

`plan/quota-percentages-say-remaining/research/used-versus-remaining.md` records
the maintainer ruling and names option (b) -- STORE remaining -- as what it
literally asks for. Its sibling `test_caam_quota_predicate_outcomes.py` pins that
the flip preserved every DECISION; this file pins the property that made the flip
worth doing at all, and that no outcome test can see:

* the stored record NAMES what it holds, so no reader has to trace a figure back
  to its source to know which way it runs, and
* the complement from the API's spent direction to the stored remaining one
  happens in exactly the places that are NAMED for doing it.

The second is the one that rots quietly. A stray `100 - usage.five_hour_remaining`
added later would read as ordinary arithmetic, would pass every outcome test that
did not happen to cross it, and would put the two directions back in circulation
together -- which is the defect the ruling names. So it is checked structurally
over the caam modules rather than left to review.

Derivation FROM utilization is unchanged and remains what the specification
requires; what this pins is that the derivation happens once and says so.
"""

from __future__ import annotations

import ast
import dataclasses
import importlib
import json
from pathlib import Path
from types import ModuleType

__all__: list[str] = []

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "overseer"
FULL_ALLOWANCE = 100.0

# The two functions allowed to turn a spent-direction percentage into a remaining
# one, each named for exactly that job. Everything else in the quota path reads a
# stored figure that already runs the right way.
COMPLEMENT_SITES = {
    # The parse boundary: the Anthropic usage response reports utilization.
    ("caam_usage.py", "remaining_from_utilization"),
    # The knob bridge: `CAAM_ROTATE_FIVE_HOUR_THRESHOLD` is still exported as
    # percent SPENT, and its clean-break rename is its own change.
    ("caam_decision.py", "five_hour_remaining_floor"),
}


def usage_module() -> ModuleType:
    return importlib.import_module("caam_usage")


def models_module() -> ModuleType:
    return importlib.import_module("caam_decision_models")


def write_creds(*, path: Path) -> None:
    path.write_text(
        json.dumps({"claudeAiOauth": {"accessToken": "tok", "expiresAt": 9_000_000}}),
        encoding="utf-8",
    )


class _Response:
    def __init__(self, *, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        del size
        return self._body


def _fetch(*, tmp_path: Path, body: dict[str, object]) -> object:
    creds = tmp_path / ".credentials.json"
    write_creds(path=creds)

    def transport(*, request: object, timeout: float) -> _Response:
        del request, timeout
        return _Response(body=json.dumps(body).encode())

    record, why = usage_module().fetch_usage(creds_path=creds, now=1000.0, transport=transport)
    assert why is None
    assert record is not None
    return record


def test_a_parsed_record_stores_what_each_allowance_has_left(*, tmp_path: Path):
    """One response with three known utilizations, read back as three balances.

    Asserted through `getattr` with a default rather than attribute access, so a
    record that does not carry these names yet fails as a plain wrong-value
    assertion instead of dying on the attribute -- the difference between a test
    that says "the figures run the wrong way" and one that says nothing at all.
    """
    record = _fetch(
        tmp_path=tmp_path,
        body={
            "five_hour": {"utilization": 30.0, "resets_at": "2026-09-06T12:00:00Z"},
            "seven_day": {"utilization": 70.0, "resets_at": "2026-09-10T12:00:00Z"},
            "limits": [
                {
                    "kind": "weekly_scoped",
                    "percent": 90.0,
                    "resets_at": "2026-09-10T12:00:00Z",
                    "scope": {"model": {"display_name": "Fable"}},
                }
            ],
        },
    )

    assert getattr(record, "five_hour_remaining", None) == 70.0
    assert getattr(record, "seven_day_remaining", None) == 30.0
    assert getattr(record, "fable_remaining", None) == 10.0


def test_an_unreadable_scoped_allowance_stays_distinct_from_nothing_left(*, tmp_path: Path):
    """Absent is not zero, and the flip must not quietly merge the two.

    Zero remaining is an account that spent its scoped allowance; None is one
    whose allowance could not be read. Both are unable to serve a pin, but only
    the first is a fact about the account, and every predicate downstream fails
    closed on the second rather than treating it as a full balance.
    """
    record = _fetch(
        tmp_path=tmp_path,
        body={
            "five_hour": {"utilization": 30.0, "resets_at": None},
            "seven_day": {"utilization": 70.0, "resets_at": None},
            "limits": [],
        },
    )

    assert getattr(record, "fable_remaining", "missing") is None


def test_every_quota_field_on_the_record_is_named_for_what_it_holds():
    """The names ARE the contract -- a field called `five_hour` said nothing."""
    names = {field.name for field in dataclasses.fields(models_module().UsageRecord)}

    assert names == {
        "five_hour_remaining",
        "seven_day_remaining",
        "five_hour_resets_at",
        "seven_day_resets_at",
        "fable_remaining",
        "fable_resets_at",
    }


def _full_allowance_constants(*, tree: ast.Module) -> set[str]:
    """Module-level names bound to the full-allowance figure, so aliases count too.

    Without this the scan would only see a bare `100 - x` and would miss the very
    boundary it exists to permit, which reads `_FULL_ALLOWANCE - utilization`.
    """
    names: set[str] = set()
    for node in tree.body:
        targets = (
            [node.target]
            if isinstance(node, ast.AnnAssign)
            else node.targets
            if isinstance(node, ast.Assign)
            else []
        )
        value = getattr(node, "value", None)
        if not isinstance(value, ast.Constant) or value.value != FULL_ALLOWANCE:
            continue
        names.update(target.id for target in targets if isinstance(target, ast.Name))
    return names


def _complement_sites(*, path: Path) -> set[tuple[str, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    aliases = _full_allowance_constants(tree=tree)
    enclosing: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            enclosing[child] = node

    found: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Sub):
            continue
        left = node.left
        is_full = (isinstance(left, ast.Constant) and left.value == FULL_ALLOWANCE) or (
            isinstance(left, ast.Name) and left.id in aliases
        )
        if not is_full:
            continue
        owner: ast.AST = node
        while owner in enclosing and not isinstance(owner, ast.FunctionDef):
            owner = enclosing[owner]
        name = owner.name if isinstance(owner, ast.FunctionDef) else "<module>"
        found.add((path.name, name))
    return found


def test_the_spent_to_remaining_complement_happens_only_where_it_is_named():
    """Two named boundaries, and nothing else in the quota path may complement.

    Scoped to the caam modules deliberately: the supervisor tree does its own
    percentage arithmetic about CONTEXT headroom, which is a different quantity
    under a different rule and is not what this ruling governs.
    """
    sites: set[tuple[str, str]] = set()
    for path in sorted(PACKAGE.glob("*caam*.py")):
        sites |= _complement_sites(path=path)

    assert sites == COMPLEMENT_SITES
