"""Repo-level pairing smoke for the package dependency audit helpers."""

from __future__ import annotations

import pathlib

from overseer.test_package_constraint_audit import (
    PackageImportAudit,
    audit_package_imports,
)

__all__: list[str] = []


def test_package_import_audit_value_object_starts_empty():
    audit = PackageImportAudit(
        installed_imports={},
        missing_vendored_sources={},
        runtime_dependency_declarations=[],
        vendored_load_imports={},
        hermetic_collisions={},
    )

    assert audit.installed_imports == {}


def _write_text(*, path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_conforming_vendored_import_passes_the_dependency_constraint(*, tmp_path):
    package_root = tmp_path / "overseer"
    _write_text(path=tmp_path / "pyproject.toml", text='[project]\ndependencies = ["other"]\n')
    _write_text(path=package_root / "consumer.py", text="from overseer._vendor import pytest\n")
    _write_text(
        path=package_root / "_vendor" / "pytest" / "__init__.py",
        text=(
            "import json\n"
            "from . import sibling\n"
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n"
            "    import anyio\n"
            "def late_import():\n"
            "    import hypothesis\n"
            "    return hypothesis\n"
        ),
    )
    _write_text(path=package_root / "_vendor" / "pytest" / "sibling.py", text="import pathlib\n")

    audit = audit_package_imports(
        product_paths=(package_root / "consumer.py",),
        package_root=package_root,
        out_of_band_imports={},
    )

    assert audit == PackageImportAudit(
        installed_imports={},
        missing_vendored_sources={},
        runtime_dependency_declarations=[],
        vendored_load_imports={},
        hermetic_collisions={},
    )


def test_non_vendored_installed_import_fails_the_dependency_constraint(*, tmp_path):
    package_root = tmp_path / "overseer"
    _write_text(path=tmp_path / "pyproject.toml", text="[project]\ndependencies = []\n")
    _write_text(path=package_root / "consumer.py", text="import pytest\n")

    audit = audit_package_imports(
        product_paths=(package_root / "consumer.py",),
        package_root=package_root,
        out_of_band_imports={},
    )

    assert audit.installed_imports == {"consumer.py": ["pytest"]}


def test_missing_vendored_source_fails_the_dependency_constraint(*, tmp_path):
    package_root = tmp_path / "overseer"
    _write_text(path=tmp_path / "pyproject.toml", text="[project]\ndependencies = []\n")
    _write_text(path=package_root / "consumer.py", text="from overseer._vendor import pytest\n")

    audit = audit_package_imports(
        product_paths=(package_root / "consumer.py",),
        package_root=package_root,
        out_of_band_imports={},
    )

    assert audit.missing_vendored_sources == {"consumer.py": ["pytest"]}


def test_declared_runtime_dependency_fails_the_dependency_constraint(*, tmp_path):
    package_root = tmp_path / "overseer"
    _write_text(path=tmp_path / "pyproject.toml", text='[project]\ndependencies = ["pytest"]\n')
    _write_text(path=package_root / "consumer.py", text="from overseer._vendor import pytest\n")
    _write_text(path=package_root / "_vendor" / "pytest" / "__init__.py", text="import json\n")

    audit = audit_package_imports(
        product_paths=(package_root / "consumer.py",),
        package_root=package_root,
        out_of_band_imports={},
    )

    assert audit.runtime_dependency_declarations == ["pytest"]


def test_vendored_module_load_import_fails_the_dependency_constraint(*, tmp_path):
    package_root = tmp_path / "overseer"
    _write_text(path=tmp_path / "pyproject.toml", text="[project]\ndependencies = []\n")
    _write_text(path=package_root / "consumer.py", text="from overseer._vendor import sample\n")
    _write_text(path=package_root / "_vendor" / "sample" / "__init__.py", text="import pytest\n")

    audit = audit_package_imports(
        product_paths=(package_root / "consumer.py",),
        package_root=package_root,
        out_of_band_imports={},
    )

    assert audit.vendored_load_imports == {"sample/__init__.py": ["pytest"]}


def test_bare_vendored_import_fails_the_hermetic_constraint(*, tmp_path):
    package_root = tmp_path / "overseer"
    _write_text(path=tmp_path / "pyproject.toml", text="[project]\ndependencies = []\n")
    _write_text(path=package_root / "consumer.py", text="import pytest\n")
    _write_text(path=package_root / "_vendor" / "pytest" / "__init__.py", text="import json\n")

    audit = audit_package_imports(
        product_paths=(package_root / "consumer.py",),
        package_root=package_root,
        out_of_band_imports={},
    )

    assert audit.hermetic_collisions == {"consumer.py": ["pytest"]}
