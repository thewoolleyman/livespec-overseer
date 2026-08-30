"""Repository gate coverage for report-only artifact readers and producers."""

from __future__ import annotations

import importlib.util
import pathlib
import re
import types

__all__: list[str] = []

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_CHECK = _REPO_ROOT / "scripts" / "check-report-only-artifact-producers.py"
_JUSTFILE = _REPO_ROOT / "justfile"


def _checker() -> types.ModuleType:
    assert _CHECK.is_file(), "report-only artifact producer check script is missing"
    spec = importlib.util.spec_from_file_location("check_report_only_artifact_producers", _CHECK)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_current_tree_has_non_test_producers_for_shipped_report_only_artifact_readers():
    checker = _checker()

    assert checker.find_missing_producers(repo=_REPO_ROOT) == ()


def test_test_only_writer_does_not_satisfy_a_shipped_report_only_artifact_reader(
    tmp_path: pathlib.Path,
):
    checker = _checker()
    reader = tmp_path / "overseer" / "_supervisor_reader.py"
    test_writer = tmp_path / "tests" / "test_supervisor_reader.py"
    reader.parent.mkdir(parents=True)
    test_writer.parent.mkdir(parents=True)
    reader.write_text('"tmp/overseer/foreman/synthetic-root/"\n', encoding="utf-8")
    test_writer.write_text('"tmp/overseer/foreman/synthetic-root/"\n', encoding="utf-8")

    missing = checker.find_missing_producers(
        repo=tmp_path,
        contracts=(
            checker.ArtifactContract(
                name="synthetic-root",
                reader_paths=("overseer/_supervisor_reader.py",),
                reader_needles=("tmp/overseer/foreman/synthetic-root/",),
                producer_paths=("tests/test_supervisor_reader.py",),
                producer_needles=("tmp/overseer/foreman/synthetic-root/",),
            ),
        ),
    )

    assert missing == ("synthetic-root",)


def test_current_tree_reads_no_retired_artifact_root():
    checker = _checker()
    assert hasattr(
        checker, "find_retired_root_readers"
    ), "the gate must register the retired artifact roots so this class stops recurring"

    assert checker.find_retired_root_readers(repo=_REPO_ROOT) == ()


def test_the_two_producerless_roots_of_the_final_ruling_path_are_registered():
    checker = _checker()

    assert {root.name for root in checker.RETIRED_ROOTS} == {
        "caam-quota-surface",
        "final-ruling-ledger-item-cache",
    }
    assert all(root.reason for root in checker.RETIRED_ROOTS)


def test_a_code_read_of_a_retired_root_fails_while_prose_about_it_does_not(
    tmp_path: pathlib.Path,
):
    """The gate must catch the READ without catching the RECORD of its retirement.

    Docstrings and comments are excluded on purpose: the modules that explain why
    a root was withdrawn have to be able to name it.
    """
    checker = _checker()
    package = tmp_path / "overseer"
    package.mkdir(parents=True)
    (package / "reader.py").write_text(
        'x = repo / "tmp" / "overseer" / "ledger-items" / "e.json"\n', encoding="utf-8"
    )
    (package / "recorder.py").write_text(
        '"""Retired: tmp/overseer/ledger-items/<id>.json never had a writer."""\n'
        "# tmp/overseer/ledger-items is dead; read the live ledger instead.\n"
        "y = 1\n",
        encoding="utf-8",
    )
    (package / "test_reader.py").write_text('z = "ledger-items"\n', encoding="utf-8")

    findings = checker.find_retired_root_readers(repo=tmp_path)

    assert [finding.split(":")[0] for finding in findings] == ["final-ruling-ledger-item-cache"]
    assert "overseer/reader.py" in findings[0]


def test_retired_root_scan_skips_absent_trees(tmp_path: pathlib.Path):
    checker = _checker()

    assert checker.find_retired_root_readers(repo=tmp_path) == ()


def test_report_only_artifact_producer_gate_is_wired_into_the_aggregate():
    source = _JUSTFILE.read_text(encoding="utf-8")
    recipe = re.search(r"^check:\n(.*?)^\S", source, re.MULTILINE | re.DOTALL)
    assert recipe is not None

    assert "check-report-only-artifact-producers" in recipe.group(1)
