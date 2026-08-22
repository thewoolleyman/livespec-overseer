"""Alert condition names are explicit event names, never defaults."""

from __future__ import annotations

import ast
import inspect
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from _supervisor_core import Supervisor

__all__: list[str] = []


@dataclass(frozen=True, kw_only=True)
class AlertCall:
    path: Path
    line: int
    condition: str | None


def _overseer_root() -> Path:
    return Path(__file__).resolve().parent.parent / "overseer"


def _call_receiver_name(*, call: ast.Call) -> str | None:
    if not isinstance(call.func, ast.Attribute) or call.func.attr != "alert":
        return None
    if isinstance(call.func.value, ast.Name):
        return call.func.value.id
    if isinstance(call.func.value, ast.Attribute) and isinstance(call.func.value.value, ast.Name):
        return f"{call.func.value.value.id}.{call.func.value.attr}"
    return None


def _constant_string_assignments(*, nodes: Iterable[ast.stmt]) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for node in nodes:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            if not isinstance(node.value.value, str):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments[target.id] = node.value.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                assignments[node.target.id] = node.value.value
    return assignments


def _condition_assignment(*, node: ast.stmt) -> str | None:
    if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
        if not isinstance(node.value.value, str):
            return None
        if any(
            isinstance(target, ast.Name) and target.id == "condition" for target in node.targets
        ):
            return node.value.value
    if (
        isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "condition"
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    ):
        return node.value.value
    return None


def _condition_assignments_in_branch(*, node: ast.If) -> set[str]:
    conditions: set[str] = set()
    for statement in [*node.body, *node.orelse]:
        condition = _condition_assignment(node=statement)
        if condition is not None:
            conditions.add(condition)
        if isinstance(statement, ast.If):
            conditions.update(_condition_assignments_in_branch(node=statement))
    return conditions


def _condition_argument(*, call: ast.Call, assignments: Mapping[str, str]) -> str | None:
    for keyword in call.keywords:
        if keyword.arg != "condition":
            continue
        if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
            return keyword.value.value
        if isinstance(keyword.value, ast.Name):
            return assignments.get(keyword.value.id, f"<dynamic:{keyword.value.id}>")
        return "<dynamic>"
    return None


def _supervisor_alert_calls_in_node(
    *,
    path: Path,
    node: ast.AST,
    assignments: Mapping[str, str],
) -> list[AlertCall]:
    calls: list[AlertCall] = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        if _call_receiver_name(call=child) not in {"sup", "request.sup", "self"}:
            continue
        calls.append(
            AlertCall(
                path=path,
                line=child.lineno,
                condition=_condition_argument(call=child, assignments=assignments),
            )
        )
    return calls


def _supervisor_alert_calls_in_statements(
    *,
    path: Path,
    statements: Iterable[ast.stmt],
    assignments: Mapping[str, str],
) -> list[AlertCall]:
    calls: list[AlertCall] = []
    active_assignments = dict(assignments)
    for statement in statements:
        condition = _condition_assignment(node=statement)
        if condition is not None:
            active_assignments["condition"] = condition
        if isinstance(statement, ast.If):
            calls.extend(
                _supervisor_alert_calls_in_statements(
                    path=path,
                    statements=statement.body,
                    assignments=active_assignments,
                )
            )
            calls.extend(
                _supervisor_alert_calls_in_statements(
                    path=path,
                    statements=statement.orelse,
                    assignments=active_assignments,
                )
            )
            branch_conditions = _condition_assignments_in_branch(node=statement)
            if branch_conditions:
                active_assignments["condition"] = "|".join(sorted(branch_conditions))
            continue
        calls.extend(
            _supervisor_alert_calls_in_node(
                path=path,
                node=statement,
                assignments=active_assignments,
            )
        )
    return calls


def _supervisor_alert_calls(*, sources: Iterable[Path]) -> list[AlertCall]:
    calls: list[AlertCall] = []
    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        module_assignments = _constant_string_assignments(nodes=tree.body)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                calls.extend(
                    _supervisor_alert_calls_in_statements(
                        path=path,
                        statements=node.body,
                        assignments=module_assignments,
                    )
                )
                continue
            calls.extend(
                _supervisor_alert_calls_in_node(
                    path=path,
                    node=node,
                    assignments=module_assignments,
                )
            )
    return calls


def _alert_sources() -> list[Path]:
    return sorted(_overseer_root().glob("*.py"))


def _calls_missing_conditions(*, sources: Iterable[Path]) -> list[AlertCall]:
    return [call for call in _supervisor_alert_calls(sources=sources) if call.condition is None]


def test_supervisor_alert_requires_condition_keyword():
    parameter = inspect.signature(Supervisor.alert).parameters["condition"]

    assert parameter.default is inspect.Parameter.empty


def test_all_supervisor_alert_call_sites_name_their_condition():
    missing = _calls_missing_conditions(sources=_alert_sources())

    assert missing == []


def test_alert_condition_parser_resolves_offer_module_locals():
    offer_path = _overseer_root() / "_supervisor_offer.py"
    conditions = {
        condition
        for call in _supervisor_alert_calls(sources=[offer_path])
        if call.condition is not None
        for condition in call.condition.split("|")
    }

    assert {
        "supervisor-missing",
        "supervision-capture-offer",
        "supervision-offer",
    } <= conditions


def test_missing_condition_control_is_discriminating(*, tmp_path):
    source = (
        "def demo(*, sup):\n"
        "    sup.alert(\n"
        "        repo='repo',\n"
        "        topic='topic',\n"
        "        session='session',\n"
        "        pane='%1',\n"
        "        message='synthetic omitted condition',\n"
        "    )\n"
    )
    path = tmp_path / "synthetic_alert.py"
    path.write_text(source, encoding="utf-8")

    missing = _calls_missing_conditions(sources=[path])

    assert [(call.path, call.line, call.condition) for call in missing] == [(path, 2, None)]
