"""Repo-level pairing smoke for the package dependency audit helpers."""

from __future__ import annotations

from overseer.test_package_constraint_audit import PackageImportAudit

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
