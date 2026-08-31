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


def test_report_only_artifact_producer_gate_is_wired_into_the_aggregate():
    source = _JUSTFILE.read_text(encoding="utf-8")
    recipe = re.search(r"^check:\n(.*?)^\S", source, re.MULTILINE | re.DOTALL)
    assert recipe is not None

    assert "check-report-only-artifact-producers" in recipe.group(1)


# ---------------------------------------------------------------------------
# The retired-root half of the gate (work-item overseer-764a.10).
#
# `overseer-764a.9` retired two producerless artifact roots rather than giving
# them writers, and the reader-without-writer contracts above cannot see a root
# that no longer has a reader. These tests pin the registry, the code-versus-
# prose discriminator, and both sides of the exit status.
# ---------------------------------------------------------------------------

_LEDGER_ITEMS_ROOT = "tmp/overseer/ledger-items/<item-id>.json"
_CAAM_QUOTA_ROOT = "tmp/overseer/caam-quota.json"

_PROSE_ONLY_MODULE = "\n".join(
    (
        '"""A module that only NAMES the retired roots.',
        "",
        "``tmp/overseer/ledger-items/<item-id>.json`` and",
        "``tmp/overseer/caam-quota.json`` were retired rather than given",
        "producers; this docstring is the durable record of why, and it must",
        "survive the gate untouched.",
        '"""',
        "",
        "# A comment naming tmp/overseer/caam-quota.json as well.",
        "",
        "VALUE = 1",
        "",
    )
)

_CODE_READ_MODULE = "\n".join(
    (
        '"""A module that actually READS one of the retired roots."""',
        "",
        "from pathlib import Path",
        "",
        "",
        "def read(*, repo: Path, item_id: str) -> str:",
        '    """The docstring here is prose; the line below is a read."""',
        '    return (repo / "tmp" / "overseer" / "ledger-items" / f"{item_id}.json").read_text()',
        "",
    )
)

_FSTRING_QUOTA_READ_MODULE = "\n".join(
    (
        "from pathlib import Path",
        "",
        "",
        "def read(*, repo: Path) -> str:",
        '    return Path(f"{repo}/tmp/overseer/caam-quota.json").read_text()',
        "",
    )
)


def _retired_root_gate(checker: types.ModuleType):
    assert hasattr(checker, "find_retired_root_reads"), (
        "check-report-only-artifact-producers.py has no retired-root gate; "
        "a future reader of a retired root would ship silently"
    )
    return checker.find_retired_root_reads


def _write_module(*, repo: pathlib.Path, relative_path: str, source: str) -> None:
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def test_both_retired_final_ruling_roots_are_registered():
    checker = _checker()
    assert hasattr(checker, "DEFAULT_RETIRED_ROOTS"), (
        "the retired-root registry is missing; nothing pins the two roots "
        "overseer-764a.9 retired"
    )

    registered = {root.name: root for root in checker.DEFAULT_RETIRED_ROOTS}

    assert set(registered) == {_LEDGER_ITEMS_ROOT, _CAAM_QUOTA_ROOT}
    assert all(root.retired_by == "overseer-764a.9" for root in registered.values())
    assert all(root.code_needles for root in registered.values())
    assert all(root.reason for root in registered.values())


def test_the_shipped_tree_reads_no_retired_artifact_root():
    """The exit-0 side, measured against the real repository.

    The live tree still DOCUMENTS both roots — `_supervisor_final_ruling_sources`
    and `ledger_comments` name them in their module docstrings — so a pass here
    is simultaneously the prose-is-not-a-read demonstration on real files.
    """
    checker = _checker()
    find_retired_root_reads = _retired_root_gate(checker)

    assert find_retired_root_reads(repo=_REPO_ROOT) == ()


def test_prose_and_comments_naming_a_retired_root_do_not_trip_the_gate(
    tmp_path: pathlib.Path,
):
    checker = _checker()
    find_retired_root_reads = _retired_root_gate(checker)
    _write_module(repo=tmp_path, relative_path="overseer/_prose.py", source=_PROSE_ONLY_MODULE)
    _write_module(repo=tmp_path, relative_path="overseer/_empty.py", source="")

    assert find_retired_root_reads(repo=tmp_path, source_roots=("overseer",)) == ()


def test_a_code_read_of_a_retired_root_is_reported_naming_the_file_and_the_root(
    tmp_path: pathlib.Path,
):
    checker = _checker()
    find_retired_root_reads = _retired_root_gate(checker)
    _write_module(
        repo=tmp_path,
        relative_path="overseer/_supervisor_reader.py",
        source=_CODE_READ_MODULE,
    )

    findings = find_retired_root_reads(repo=tmp_path, source_roots=("overseer",))

    assert len(findings) == 1
    assert "overseer/_supervisor_reader.py" in findings[0]
    assert _LEDGER_ITEMS_ROOT in findings[0]
    assert "overseer-764a.9" in findings[0]


def test_an_f_string_read_of_the_retired_quota_root_is_reported(tmp_path: pathlib.Path):
    """A path spelled inside an f-string is still a read, not prose."""
    checker = _checker()
    find_retired_root_reads = _retired_root_gate(checker)
    _write_module(
        repo=tmp_path,
        relative_path="overseer/_supervisor_quota.py",
        source=_FSTRING_QUOTA_READ_MODULE,
    )

    findings = find_retired_root_reads(repo=tmp_path, source_roots=("overseer",))

    assert len(findings) == 1
    assert "overseer/_supervisor_quota.py" in findings[0]
    assert _CAAM_QUOTA_ROOT in findings[0]


def test_a_beside_test_asserting_the_retired_branch_is_dead_does_not_trip_the_gate(
    tmp_path: pathlib.Path,
):
    """Tests legitimately drop the retired file to prove nothing reads it."""
    checker = _checker()
    find_retired_root_reads = _retired_root_gate(checker)
    _write_module(
        repo=tmp_path,
        relative_path="overseer/test_supervisor_reader.py",
        source=_CODE_READ_MODULE,
    )

    assert find_retired_root_reads(repo=tmp_path, source_roots=("overseer",)) == ()


def test_the_registry_script_naming_the_roots_is_not_itself_a_read(
    tmp_path: pathlib.Path,
):
    checker = _checker()
    find_retired_root_reads = _retired_root_gate(checker)
    _write_module(
        repo=tmp_path,
        relative_path=checker.SELF_RELATIVE_PATH,
        source=_CODE_READ_MODULE,
    )

    assert find_retired_root_reads(repo=tmp_path, source_roots=("scripts",)) == ()


def test_a_source_root_absent_from_the_tree_is_skipped(tmp_path: pathlib.Path):
    checker = _checker()
    find_retired_root_reads = _retired_root_gate(checker)

    assert find_retired_root_reads(repo=tmp_path, source_roots=("nowhere",)) == ()


def test_find_problems_is_non_empty_while_a_retired_root_is_read_and_empty_once_it_is_not(
    tmp_path: pathlib.Path,
):
    """Both sides of the exit status, on the same tree before and after repair."""
    checker = _checker()
    _ = _retired_root_gate(checker)
    assert hasattr(checker, "find_problems"), "main has no single findings source"
    reader = tmp_path / "overseer" / "_supervisor_reader.py"
    _write_module(
        repo=tmp_path,
        relative_path="overseer/_supervisor_reader.py",
        source=_CODE_READ_MODULE,
    )

    before = checker.find_problems(repo=tmp_path, contracts=(), source_roots=("overseer",))
    reader.write_text(_PROSE_ONLY_MODULE, encoding="utf-8")
    after = checker.find_problems(repo=tmp_path, contracts=(), source_roots=("overseer",))

    assert len(before) == 1
    assert _LEDGER_ITEMS_ROOT in before[0]
    assert after == ()


def test_find_problems_reports_a_missing_producer_alongside_a_retired_root_read(
    tmp_path: pathlib.Path,
):
    checker = _checker()
    _ = _retired_root_gate(checker)
    _write_module(
        repo=tmp_path,
        relative_path="overseer/_supervisor_reader.py",
        source=_CODE_READ_MODULE,
    )

    problems = checker.find_problems(
        repo=tmp_path,
        contracts=(
            checker.ArtifactContract(
                name="synthetic-root",
                reader_paths=("overseer/_supervisor_reader.py",),
                reader_needles=("ledger-items",),
                producer_paths=("overseer/_absent_producer.py",),
                producer_needles=("ledger-items",),
            ),
        ),
        source_roots=("overseer",),
    )

    assert len(problems) == 2
    assert "no non-test producer: synthetic-root" in problems[0]
    assert _LEDGER_ITEMS_ROOT in problems[1]
