#!/usr/bin/env python3
"""Fail when a report-only artifact reader has no shipped producer.

Two halves, because a producerless reader has two possible fates.

A CONTRACT (:data:`DEFAULT_CONTRACTS`) pairs a shipped reader with the
non-test producer that must ship beside it, and is the right shape when the
artifact SURVIVES.

A RETIRED ROOT (:data:`RETIRED_ROOTS`) is the other fate: an artifact path that
was read but never written by anything, and whose reader has since been
withdrawn rather than given a producer. Registering a contract for one would be
meaningless — nothing is supposed to write it — so the gate instead refuses to
let any shipped module READ it again. Prose about the retirement is deliberately
exempt: the modules that record WHY a root was withdrawn have to be able to name
it, so docstrings and comments are stripped before the scan.
"""

import argparse
import ast
import pathlib
import sys
from collections.abc import Sequence
from dataclasses import dataclass

__all__: list[str] = [
    "DEFAULT_CONTRACTS",
    "RETIRED_ROOTS",
    "SCANNED_PACKAGE_TREES",
    "ArtifactContract",
    "RetiredRoot",
    "find_missing_producers",
    "find_retired_root_readers",
    "main",
]


@dataclass(frozen=True, kw_only=True)
class ArtifactContract:
    name: str
    reader_paths: tuple[str, ...]
    reader_needles: tuple[str, ...]
    producer_paths: tuple[str, ...]
    producer_needles: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class RetiredRoot:
    name: str
    needle: str
    reason: str


_DocstringOwner = ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
_DOCSTRING_OWNERS: tuple[type[_DocstringOwner], ...] = (
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.FunctionDef,
    ast.Module,
)


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


RETIRED_ROOTS: tuple[RetiredRoot, ...] = (
    RetiredRoot(
        name="final-ruling-ledger-item-cache",
        needle="ledger-items",
        reason=(
            "tmp/overseer/ledger-items/<item-id>.json was read by the final-ruling and "
            "relay-strike paths and written by nothing, in any watched repository, ever. "
            "Read the plan epic's comments live through ledger_comments instead."
        ),
    ),
    RetiredRoot(
        name="caam-quota-surface",
        needle="caam-quota.json",
        reason=(
            "tmp/overseer/caam-quota.json backed the caam-quota-exhausted exemption and was "
            "never built. CAAM keeps its state host-wide under "
            "$HOME/.local/state/caam-usage-rotate/state.json and projects nothing per repo, "
            "so the exemption was removed rather than given an invented producer."
        ),
    ),
)
SCANNED_PACKAGE_TREES: tuple[str, ...] = ("overseer", ".claude-plugin/overseer")


def find_retired_root_readers(
    *,
    repo: pathlib.Path,
    roots: Sequence[RetiredRoot] = RETIRED_ROOTS,
    trees: Sequence[str] = SCANNED_PACKAGE_TREES,
) -> tuple[str, ...]:
    """Every shipped module whose CODE still names a retired artifact root."""
    findings: list[str] = []
    for tree in trees:
        for path in sorted((repo / tree).glob("*.py")):
            if path.name.startswith("test_"):
                continue
            code = _code_without_prose(source=path.read_text(encoding="utf-8"))
            findings.extend(
                f"{root.name}: {path.relative_to(repo)} reads a retired root - {root.reason}"
                for root in roots
                if root.needle in code
            )
    return tuple(findings)


def _code_without_prose(*, source: str) -> str:
    """``source`` with docstrings and comments removed, via a round-trip through ast."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, _DOCSTRING_OWNERS) and _opens_with_docstring(node=node):
            node.body = node.body[1:] if len(node.body) > 1 else [ast.Pass()]
    return ast.unparse(ast.fix_missing_locations(tree))


def _opens_with_docstring(*, node: _DocstringOwner) -> bool:
    first = node.body[0] if node.body else None
    return (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    )


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
    missing = find_missing_producers(repo=args.repo)
    retired = find_retired_root_readers(repo=args.repo)
    if not missing and not retired:
        return 0
    for name in missing:
        _ = sys.stderr.write(f"report-only artifact reader has no non-test producer: {name}\n")
    for finding in retired:
        _ = sys.stderr.write(f"retired report-only artifact root is read again: {finding}\n")
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
