"""Helpers and controls for the package dependency constraint test."""

from __future__ import annotations

import ast
import pathlib
import sys
from collections.abc import Iterable
from dataclasses import dataclass

__all__: list[str] = [
    "PackageImportAudit",
    "all_imports",
    "audit_package_imports",
]


@dataclass(frozen=True, kw_only=True)
class PackageImportAudit:
    installed_imports: dict[str, list[str]]
    missing_vendored_sources: dict[str, list[str]]
    runtime_dependency_declarations: list[str]
    vendored_load_imports: dict[str, list[str]]
    hermetic_collisions: dict[str, list[str]]


def _module_load_import_nodes(*, tree: ast.AST) -> Iterable[ast.Import | ast.ImportFrom]:
    """Import nodes evaluated while a module loads.

    Function and lambda bodies are intentionally excluded. Class bodies remain
    in scope because Python executes them while importing the containing module.
    `TYPE_CHECKING` blocks are also excluded because they are false at runtime.
    """

    def _walk(*, node: ast.AST) -> Iterable[ast.Import | ast.ImportFrom]:
        if isinstance(node, ast.Import | ast.ImportFrom):
            yield node
            return
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
            return
        if isinstance(node, ast.If) and _is_type_checking_test(test=node.test):
            for statement in node.orelse:
                yield from _walk(node=statement)
            return
        for child in ast.iter_child_nodes(node):
            yield from _walk(node=child)

    yield from _walk(node=tree)


def _is_type_checking_test(*, test: ast.AST) -> bool:
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    return (
        isinstance(test, ast.Attribute)
        and test.attr == "TYPE_CHECKING"
        and isinstance(test.value, ast.Name)
        and test.value.id == "typing"
    )


def _top_level_imports(*, path: pathlib.Path) -> frozenset[str]:
    """Every module-load top-level module name imported by `path`, absolute imports only."""
    names: set[str] = set()
    for node in _module_load_import_nodes(tree=ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return frozenset(names)


def all_imports(*, path: pathlib.Path) -> frozenset[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return frozenset(names)


def _vendored_imports(*, path: pathlib.Path) -> frozenset[str]:
    names: set[str] = set()
    for node in _module_load_import_nodes(tree=ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(
                parts[2]
                for alias in node.names
                if (parts := alias.name.split("."))[:2] == ["overseer", "_vendor"]
                and len(parts) >= 3
            )
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            parts = node.module.split(".")
            if parts == ["overseer", "_vendor"]:
                names.update(alias.name.split(".")[0] for alias in node.names if alias.name != "*")
            elif parts[:2] == ["overseer", "_vendor"] and len(parts) >= 3:
                names.add(parts[2])
    return frozenset(names)


def _runtime_dependencies(*, repo_root: pathlib.Path) -> frozenset[str]:
    text = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    marker = "dependencies = ["
    start = text.index(marker) + len("dependencies = ")
    end = text.index("]", start) + 1
    dependencies = ast.literal_eval(text[start:end])
    return frozenset(
        str(dependency).split(">", maxsplit=1)[0].split("=", maxsplit=1)[0]
        for dependency in dependencies
    )


def _vendored_names(*, vendor_root: pathlib.Path) -> frozenset[str]:
    if not vendor_root.is_dir():
        return frozenset()
    return frozenset(
        path.name
        for path in vendor_root.iterdir()
        if (path.is_dir() and (path / "__init__.py").is_file()) or path.suffix == ".py"
    )


def _vendored_python_files(*, vendor_root: pathlib.Path) -> tuple[pathlib.Path, ...]:
    if not vendor_root.is_dir():
        return ()
    return tuple(sorted(vendor_root.rglob("*.py")))


def _audit_vendored_load_imports(
    *, vendor_root: pathlib.Path, stdlib: frozenset[str], vendor_names: frozenset[str]
) -> dict[str, list[str]]:
    offenders: dict[str, list[str]] = {}
    for path in _vendored_python_files(vendor_root=vendor_root):
        third_party = sorted(
            name
            for name in _top_level_imports(path=path)
            if name not in stdlib and name not in vendor_names
        )
        if third_party:
            offenders[str(path.relative_to(vendor_root))] = third_party
    return offenders


def audit_package_imports(
    *,
    product_paths: Iterable[pathlib.Path],
    package_root: pathlib.Path,
    out_of_band_imports: dict[str, frozenset[str]],
) -> PackageImportAudit:
    stdlib = frozenset(sys.stdlib_module_names)
    first_party = frozenset({"overseer", *(path.stem for path in package_root.glob("*.py"))})
    vendor_root = package_root / "_vendor"
    vendor_names = _vendored_names(vendor_root=vendor_root)
    runtime_dependencies = _runtime_dependencies(repo_root=package_root.parent)

    installed_imports: dict[str, list[str]] = {}
    missing_vendored_sources: dict[str, list[str]] = {}
    hermetic_collisions: dict[str, list[str]] = {}
    imported_vendor_names: set[str] = set()
    for path in product_paths:
        allowed = out_of_band_imports.get(path.name, frozenset())
        direct_third_party = sorted(
            name
            for name in _top_level_imports(path=path)
            if name not in stdlib and name not in first_party and name not in allowed
        )
        bare_vendored = sorted(name for name in direct_third_party if name in vendor_names)
        if direct_third_party:
            installed_imports[path.name] = direct_third_party
        if bare_vendored:
            hermetic_collisions[path.name] = bare_vendored

        vendored = _vendored_imports(path=path)
        imported_vendor_names.update(vendored)
        missing = sorted(name for name in vendored if name not in vendor_names)
        if missing:
            missing_vendored_sources[path.name] = missing

    vendored_dependencies = sorted(
        name for name in imported_vendor_names if name in runtime_dependencies
    )

    return PackageImportAudit(
        installed_imports=installed_imports,
        missing_vendored_sources=missing_vendored_sources,
        runtime_dependency_declarations=vendored_dependencies,
        vendored_load_imports=_audit_vendored_load_imports(
            vendor_root=vendor_root, stdlib=stdlib, vendor_names=vendor_names
        ),
        hermetic_collisions=hermetic_collisions,
    )
