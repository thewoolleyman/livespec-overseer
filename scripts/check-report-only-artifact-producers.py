#!/usr/bin/env python3
"""Fail when a report-only artifact reader has no shipped producer."""

import argparse
import pathlib
import sys
from collections.abc import Sequence
from dataclasses import dataclass

__all__: list[str] = [
    "DEFAULT_CONTRACTS",
    "ArtifactContract",
    "find_missing_producers",
    "main",
]


@dataclass(frozen=True, kw_only=True)
class ArtifactContract:
    name: str
    reader_paths: tuple[str, ...]
    reader_needles: tuple[str, ...]
    producer_paths: tuple[str, ...]
    producer_needles: tuple[str, ...]


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
    if not missing:
        return 0
    for name in missing:
        _ = sys.stderr.write(f"report-only artifact reader has no non-test producer: {name}\n")
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
