"""The manager executable's subcommand and flag grammar, and its two refusal TYPES.

SPECIFICATION/contracts.md fixes a pre-recovery validation ORDER whose first two steps are
argv-only: recognize the subcommand, then validate that command's flag cardinality. Both
steps run BEFORE configuration is read, before any recovery and before any external access,
so they are the only part of the wire protocol that can be settled from a string list — and
therefore the only part worth pinning without a filesystem.

THE REFUSAL TYPE IS NOT UNIFORM, AND THAT IS THE POINT OF THIS MODULE. Every command
refuses a bad flag list with `invalid-request` EXCEPT `report`, which refuses with
`invalid-report` once the subcommand has been recognized. The contract states the
discriminator precisely: "A missing, repeated or unexpected flag for any command except
recognized `report` MUST be `invalid-request`; after recognizing `report`, the equivalent
flag, input-read, UTF-8, JSON, shape, version, type or diagnostic failure MUST be
`invalid-report`." A single refusal type would be the easy wrong implementation and would
be invisible to a coarser test that only checked the exit status, because BOTH types map to
exit `2`.

AN UNKNOWN SUBCOMMAND IS `invalid-request` EVEN WHEN IT IS `report`-SHAPED. Recognition
happens first, so a misspelled subcommand has no command-specific refusal type to inherit.

NOTHING THE CALLER SUPPLIED IS ECHOED BACK. The manager's every output is required to be
secret-free, and an argument vector is caller-controlled: a consumer that passes a
credential where a path belongs must not have it quoted back out of a refusal message. So
the messages name only the closed-table flag and command names, and the tests below assert
that the offending VALUE never appears in the message.
"""

from __future__ import annotations

import importlib
import pathlib
from typing import Any

import pytest

__all__: list[str] = []

MODULE_PATH = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_manager_argv.py"

_SECRET = "sk-ant-oat0-not-a-path"


def _argv() -> Any:
    assert MODULE_PATH.is_file(), "overseer/_lpm_manager_argv.py must exist"
    return importlib.import_module("_lpm_manager_argv")


def _failure(*, arguments: list[str]) -> Any:
    outcome = _argv().manager_invocation(arguments=arguments)
    assert not isinstance(outcome, _success_type()), f"{arguments!r} must be refused"
    return outcome.failure()


def _success(*, arguments: list[str]) -> Any:
    outcome = _argv().manager_invocation(arguments=arguments)
    assert isinstance(outcome, _success_type()), f"{arguments!r} must be accepted"
    return outcome.unwrap()


def _success_type() -> Any:
    from overseer._vendor.returns.result import Success

    return Success


def test_the_closed_command_table_is_exactly_the_ratified_consumer_surface() -> None:
    module = _argv()

    assert module.MANAGER_COMMANDS == (
        "acquire",
        "complete",
        "provision",
        "release",
        "report",
        "target",
        "attention",
        "proof-status",
    )
    assert module.JSON_FLAG_BY_COMMAND == {
        "target": "--target-json",
        "provision": "--request-json",
        "report": "--report-json",
        "complete": "--completion-json",
        "release": "--release-json",
        "acquire": "--acquisition-json",
    }
    assert module.ATTENTION_ACTIONS == ("--resolve", "--give-up")


@pytest.mark.parametrize(
    ("command", "flag"),
    [
        ("target", "--target-json"),
        ("provision", "--request-json"),
        ("report", "--report-json"),
        ("complete", "--completion-json"),
        ("release", "--release-json"),
        ("acquire", "--acquisition-json"),
    ],
)
def test_each_json_command_accepts_exactly_its_own_flag_and_one_source(
    *, command: str, flag: str
) -> None:
    accepted = _success(arguments=[command, flag, "-"])

    assert accepted.command == command
    assert accepted.source == "-"
    assert accepted.action is None
    assert accepted.record_id is None


def test_a_path_source_is_carried_through_verbatim() -> None:
    accepted = _success(arguments=["provision", "--request-json", "/tmp/request.json"])

    assert accepted.source == "/tmp/request.json"


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["Target", "--target-json", "-"],
        ["--target-json", "-"],
        ["reports", "--report-json", "-"],
    ],
)
def test_a_missing_or_unknown_subcommand_is_invalid_request(*, arguments: list[str]) -> None:
    error = _failure(arguments=arguments)

    assert error.error_type == "invalid-request"


@pytest.mark.parametrize(
    "arguments",
    [
        ["target"],
        ["target", "--target-json"],
        ["target", "--request-json", "-"],
        ["target", "--target-json", "-", "--target-json", "-"],
        ["target", "--target-json", ""],
        ["target", "-"],
    ],
)
def test_a_wrong_flag_list_is_invalid_request_for_every_command_but_report(
    *, arguments: list[str]
) -> None:
    error = _failure(arguments=arguments)

    assert error.error_type == "invalid-request"


@pytest.mark.parametrize(
    "arguments",
    [
        ["report"],
        ["report", "--report-json"],
        ["report", "--target-json", "-"],
        ["report", "--report-json", "-", "--report-json", "-"],
        ["report", "--report-json", ""],
    ],
)
def test_a_wrong_flag_list_for_a_recognized_report_is_invalid_report(
    *, arguments: list[str]
) -> None:
    error = _failure(arguments=arguments)

    assert error.error_type == "invalid-report"


def test_proof_status_accepts_no_argument_and_refuses_any() -> None:
    accepted = _success(arguments=["proof-status"])
    assert accepted.command == "proof-status"
    assert accepted.source is None

    assert _failure(arguments=["proof-status", "--resolve"]).error_type == "invalid-request"


def test_attention_accepts_the_bare_list_form() -> None:
    accepted = _success(arguments=["attention"])

    assert accepted.command == "attention"
    assert accepted.source is None
    assert accepted.action is None
    assert accepted.record_id is None


@pytest.mark.parametrize("action", ["--resolve", "--give-up"])
def test_attention_accepts_exactly_one_local_operator_action(*, action: str) -> None:
    accepted = _success(arguments=["attention", action, "d1f0c2a4-8b6e-4c1a-9f3d-0e7a5b2c4d69"])

    assert accepted.action == action
    assert accepted.record_id == "d1f0c2a4-8b6e-4c1a-9f3d-0e7a5b2c4d69"


@pytest.mark.parametrize(
    "arguments",
    [
        ["attention", "--resolve"],
        ["attention", "--resolve", ""],
        ["attention", "--unknown", "x"],
        ["attention", "--resolve", "a", "--give-up", "b"],
        ["attention", "extra"],
    ],
)
def test_any_other_attention_shape_is_invalid_request(*, arguments: list[str]) -> None:
    error = _failure(arguments=arguments)

    assert error.error_type == "invalid-request"


@pytest.mark.parametrize(
    "arguments",
    [
        [_SECRET],
        ["target", "--target-json", "-", _SECRET],
        ["report", "--report-json", "-", _SECRET],
        ["attention", "--resolve", _SECRET, "--give-up", _SECRET],
        ["proof-status", _SECRET],
    ],
)
def test_no_refusal_message_ever_echoes_a_caller_supplied_value(*, arguments: list[str]) -> None:
    error = _failure(arguments=arguments)

    assert _SECRET not in error.message
