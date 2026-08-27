"""Beside-tests for the convene-obligation CLI's argument-to-writer routing.

The module this covers shipped with every function marked `# pragma: no cover`,
which is how it reached the coverage floor at 0%: the pragmas exclude the
function bodies, and nothing imported the module, so even its module-level
statements went unexecuted. The annotations are removed and the routing is
pinned here instead.

The routing is the whole of this module's behaviour — it parses arguments and
picks one of three writers — so a control that does not distinguish WHICH
writer ran would pass against a module that always called the same one.
"""

from __future__ import annotations

import argparse
import importlib
from pathlib import Path
from typing import Any

import pytest

__all__: list[str] = []

_COMMON = (
    "--repo",
    "/data/projects/livespec-overseer",
    "--topic",
    "a-topic",
    "--question-fingerprint",
    "fp-1",
    "--observed-at-epoch",
    "1756000000.0",
    "--request-json",
    '{"kind": "picker"}',
)


def _cli() -> Any:
    return importlib.import_module("foreman_convene_obligations_cli")


def _arm(*, monkeypatch: pytest.MonkeyPatch, calls: list[str]) -> None:
    """Redirect all three writers on the module that READS them."""
    cli = _cli()
    for name in ("write_convene_obligation", "write_convene_discharge", "write_convene_escalation"):

        def record(*, _name: str = name, **kwargs: object) -> Path:
            calls.append(_name)
            return Path("/tmp") / _name

        monkeypatch.setattr(cli, name, record)


def test_the_cli_module_is_importable_and_declares_its_surface() -> None:
    assert Path(__file__).with_name("foreman_convene_obligations_cli.py").is_file()
    cli = _cli()
    assert set(cli.__all__) == {"add_common_arguments", "main", "write_for_args"}


@pytest.mark.parametrize(
    ("command", "extra", "expected"),
    [
        (
            "obligation",
            ("--action-id", "plan_start", "--human-valve-category", "blocked"),
            "write_convene_obligation",
        ),
        ("discharge", ("--reason", "answered"), "write_convene_discharge"),
        (
            "escalation",
            ("--reason", "cross_vendor_reviewers_unavailable"),
            "write_convene_escalation",
        ),
    ],
)
def test_each_subcommand_routes_to_its_own_writer(
    *,
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    extra: tuple[str, ...],
    expected: str,
) -> None:
    """Each of the three commands reaches a DIFFERENT writer.

    Asserting only that a writer ran would pass against a module that routed
    every command to one of them, which is the defect this pins.
    """
    calls: list[str] = []
    _arm(monkeypatch=monkeypatch, calls=calls)
    assert _cli().main(argv=[command, *_COMMON, *extra]) == 0
    assert calls == [expected]


def test_a_non_object_request_json_is_refused(*, monkeypatch: pytest.MonkeyPatch) -> None:
    """A JSON scalar parses but is not a request; it must raise, not route."""
    calls: list[str] = []
    _arm(monkeypatch=monkeypatch, calls=calls)
    args = argparse.Namespace(
        command="discharge",
        repo="/data/projects/livespec-overseer",
        topic="a-topic",
        question_fingerprint="fp-1",
        observed_at_epoch=1756000000.0,
        request_json="[]",
        reason="answered",
    )
    with pytest.raises(TypeError, match="request-json must be a JSON object"):
        _ = _cli().write_for_args(args=args)
    assert calls == []


def test_add_common_arguments_declares_every_shared_flag() -> None:
    parser = argparse.ArgumentParser()
    _cli().add_common_arguments(command=parser)
    declared = {action.dest for action in parser._actions}
    assert {
        "repo",
        "topic",
        "question_fingerprint",
        "observed_at_epoch",
        "request_json",
    } <= declared
