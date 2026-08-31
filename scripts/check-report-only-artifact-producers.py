#!/usr/bin/env python3
"""Fail when a report-only artifact reader has no shipped producer.

TWO GATES, ONE DEFECT CLASS. :func:`find_missing_producers` is the original:
per-artifact contracts asserting that a shipped READER has a shipped, non-test
WRITER. Its recorded residual was that coverage is BY ENUMERATION — nothing
forces a NEW reader to be registered — and on 2026-08-30 (work-item
``overseer-764a.8``) the class had already recurred twice inside
``overseer/_supervisor_final_ruling_sources.py``, in roots no registered
contract could see.

:func:`find_retired_root_reads` closes that recurrence from the other side. A
root that was RETIRED rather than given a producer is registered once in
:data:`DEFAULT_RETIRED_ROOTS`, and any later CODE READ of it fails the
aggregate naming both the file and the root. Enumeration is still the shape,
but a retired root is a bounded, known list, whereas future readers are not.

PROSE IS NOT A READ. Both retirements are documented in module docstrings —
that is the record of why re-adding a producer would be the wrong repair, and
it must survive. So the scan looks only at string constants the RUNTIME can
use: comments never reach the AST, and module/class/function docstrings are
dropped explicitly. See :func:`code_string_literals`.
"""

import argparse
import ast
import pathlib
import sys
from collections.abc import Sequence
from dataclasses import dataclass

__all__: list[str] = [
    "DEFAULT_CONTRACTS",
    "DEFAULT_RETIRED_ROOTS",
    "DEFAULT_SOURCE_ROOTS",
    "ArtifactContract",
    "RetiredArtifactRoot",
    "code_string_literals",
    "find_missing_producers",
    "find_problems",
    "find_retired_root_reads",
    "main",
]

# This file NAMES every retired root by construction, so scanning it would
# report its own registry as a read. Declaring a root is not reading it.
SELF_RELATIVE_PATH = "scripts/check-report-only-artifact-producers.py"


@dataclass(frozen=True, kw_only=True)
class ArtifactContract:
    name: str
    reader_paths: tuple[str, ...]
    reader_needles: tuple[str, ...]
    producer_paths: tuple[str, ...]
    producer_needles: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class RetiredArtifactRoot:
    """A tmp artifact root whose readers were removed rather than given writers.

    ``code_needles`` are the path SEGMENTS a read has to spell, not the whole
    root: a reader may build the path as ``repo / "tmp" / "overseer" / "x"``,
    as ``repo / "tmp/overseer/x"``, or inside an f-string, and the segment is
    the one part common to all three.
    """

    name: str
    code_needles: tuple[str, ...]
    retired_by: str
    reason: str


DEFAULT_CONTRACTS: tuple[ArtifactContract, ...] = (
    ArtifactContract(
        name="convene-obligations",
        reader_paths=("overseer/_supervisor_consensus_overdue.py",),
        reader_needles=("convene-obligations",),
        producer_paths=(
            "overseer/foreman_convene_obligations.py",
            ".claude-plugin/bin/foreman-convene-obligation",
            ".claude-plugin/prose/foreman.md",
            "pyproject.toml",
        ),
        producer_needles=(
            "write_convene_obligation",
            "foreman-convene-obligation obligation",
            "tmp/overseer/foreman/convene-obligations/<topic>/",
            "foreman-convene-obligation =",
        ),
    ),
    ArtifactContract(
        name="final-ruling-relay",
        reader_paths=("overseer/_supervisor_final_ruling_attention.py",),
        reader_needles=("latest_final_relay", "relay_from_record"),
        producer_paths=(
            "overseer/foreman_relay_strikes.py",
            "overseer/foreman_blocked_answer.py",
        ),
        producer_needles=(
            "final=final",
            'record["final"] = True',
            "append_journal(repo=Path(repo), record=relay.record)",
        ),
    ),
)


DEFAULT_RETIRED_ROOTS: tuple[RetiredArtifactRoot, ...] = (
    RetiredArtifactRoot(
        name="tmp/overseer/ledger-items/<item-id>.json",
        code_needles=("ledger-items",),
        retired_by="overseer-764a.9",
        reason=(
            "nothing in this repository writes it and it exists in none of the watched "
            "repositories, so every read answered False; the seat's answer now comes "
            "from the live ledger through the ledger_comments.CommentReader seam"
        ),
    ),
    RetiredArtifactRoot(
        name="tmp/overseer/caam-quota.json",
        code_needles=("caam-quota",),
        retired_by="overseer-764a.9",
        reason=(
            "CAAM keeps its state host-wide under "
            "$HOME/.local/state/caam-usage-rotate/state.json and projects nothing per "
            "repository, and the retired reader carried no recency floor, so a file "
            "dropped there once would have exempted the seat forever"
        ),
    ),
)

# The shipped supervision package, its tracked plugin mirror, and the gate
# scripts. `tmp/`, `SPECIFICATION/` and `plan/` hold no importable readers.
DEFAULT_SOURCE_ROOTS: tuple[str, ...] = (
    "overseer",
    ".claude-plugin/overseer",
    "scripts",
)

_DOCSTRING_OWNERS = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def find_missing_producers(
    *, repo: pathlib.Path, contracts: Sequence[ArtifactContract] = DEFAULT_CONTRACTS
) -> tuple[str, ...]:
    missing: list[str] = []
    for contract in contracts:
        if _reader_shipped(repo=repo, contract=contract) and not _producer_shipped(
            repo=repo, contract=contract
        ):
            missing.append(contract.name)
    return tuple(missing)


def find_retired_root_reads(
    *,
    repo: pathlib.Path,
    roots: Sequence[RetiredArtifactRoot] = DEFAULT_RETIRED_ROOTS,
    source_roots: Sequence[str] = DEFAULT_SOURCE_ROOTS,
) -> tuple[str, ...]:
    """Every code read of a retired artifact root, named by file AND by root."""
    findings: list[str] = []
    for relative_path in _scanned_python_paths(repo=repo, source_roots=source_roots):
        # `_scanned_python_paths` yields files it just walked, so a read that
        # fails here is a vanished file — a bug, and bugs raise.
        literals = code_string_literals(source=(repo / relative_path).read_text(encoding="utf-8"))
        for root in roots:
            if _root_is_read(root=root, literals=literals):
                findings.append(
                    f"{relative_path} reads retired artifact root {root.name}: "
                    f"retired by {root.retired_by} because {root.reason}. "
                    "Do not give it a producer; read the shipped source instead."
                )
    return tuple(findings)


def code_string_literals(*, source: str) -> tuple[str, ...]:
    """The string constants a RUNTIME read could use — docstrings excluded.

    Comments never enter the AST at all, so prose in a comment is dropped for
    free; docstrings do enter it, as the first statement of a module, class or
    function, and are removed here by identity. What is left is every literal
    the code can actually hand to a path constructor, f-string included.
    """
    tree = ast.parse(source)
    docstring_ids = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, _DOCSTRING_OWNERS) and _leads_with_a_string(node=node)
    }
    return tuple(
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstring_ids
    )


def _leads_with_a_string(
    *, node: ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
) -> bool:
    first = node.body[0] if node.body else None
    return (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    )


def _root_is_read(*, root: RetiredArtifactRoot, literals: Sequence[str]) -> bool:
    return any(needle in literal for literal in literals for needle in root.code_needles)


def _scanned_python_paths(*, repo: pathlib.Path, source_roots: Sequence[str]) -> tuple[str, ...]:
    paths: list[str] = []
    for source_root in source_roots:
        base = repo / source_root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            relative = path.relative_to(repo).as_posix()
            if _is_test_path(relative_path=relative) or relative == SELF_RELATIVE_PATH:
                continue
            paths.append(relative)
    return tuple(paths)


def find_problems(
    *,
    repo: pathlib.Path,
    contracts: Sequence[ArtifactContract] = DEFAULT_CONTRACTS,
    roots: Sequence[RetiredArtifactRoot] = DEFAULT_RETIRED_ROOTS,
    source_roots: Sequence[str] = DEFAULT_SOURCE_ROOTS,
) -> tuple[str, ...]:
    """Both gates' findings, as the lines :func:`main` prints and exits on."""
    missing = tuple(
        f"report-only artifact reader has no non-test producer: {name}"
        for name in find_missing_producers(repo=repo, contracts=contracts)
    )
    return missing + find_retired_root_reads(repo=repo, roots=roots, source_roots=source_roots)


def _reader_shipped(*, repo: pathlib.Path, contract: ArtifactContract) -> bool:
    return _needles_covered(
        repo=repo,
        relative_paths=contract.reader_paths,
        needles=contract.reader_needles,
        include_tests=True,
    )


def _producer_shipped(*, repo: pathlib.Path, contract: ArtifactContract) -> bool:
    return _needles_covered(
        repo=repo,
        relative_paths=contract.producer_paths,
        needles=contract.producer_needles,
        include_tests=False,
    )


def _needles_covered(
    *,
    repo: pathlib.Path,
    relative_paths: Sequence[str],
    needles: Sequence[str],
    include_tests: bool,
) -> bool:
    sources = tuple(
        _read_source(repo=repo, relative_path=relative_path)
        for relative_path in relative_paths
        if include_tests or not _is_test_path(relative_path=relative_path)
    )
    present = tuple(source for source in sources if source is not None)
    return len(present) == len(sources) and all(
        any(needle in source for source in present) for needle in needles
    )


def _read_source(*, repo: pathlib.Path, relative_path: str) -> str | None:
    path = repo / relative_path
    if not path.is_file():  # pragma: no cover
        return None
    return path.read_text(encoding="utf-8")


def _is_test_path(*, relative_path: str) -> bool:
    parts = pathlib.PurePosixPath(relative_path).parts
    return "tests" in parts or pathlib.PurePosixPath(relative_path).name.startswith("test_")


def main(*, argv: Sequence[str] | None = None) -> int:  # pragma: no cover
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--repo", default=".", type=pathlib.Path)
    args = parser.parse_args(argv)
    problems = find_problems(repo=pathlib.Path(args.repo))
    for problem in problems:
        _ = sys.stderr.write(f"{problem}\n")
    return 1 if problems else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
