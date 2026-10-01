"""The consumer command runtime: `target`, `provision`, `report` and the attention list.

SPECIFICATION/contracts.md fixes every answer these commands may give — the single-line JSON
object, its exact members, and the exit status each error type maps to — and narrows the typed
failures per command. This module drives all of that through the ONE entry point both launchers
reach, `_lpm_commands.run_manager_command`, so what is pinned here is the behaviour of the
executable rather than of a helper the executable happens to call.

THE HOST IS INJECTED AND NOTHING ELSE IS. There is no SecretStore on this machine, no `op`
executable, no credential and no clock: the records, the credential value, the privileged status
writer, the reference minter and the clock all arrive on `ManagerHost`. That is what makes it
possible to assert the whole consumer wire protocol WITHOUT any host-secret access, which this
work item forbids outright — and it is also why none of this is a "fake manager": the real
decisions are made by the ratified modules, and only the world they read is substituted.

THE THREE PROPERTIES WORTH THE MOST SCRUTINY:

* `target` and `provision` PERSIST WHAT THE CONTRACT SAYS THEY PERSIST. A `target` that returned
  a reference without committing an issuance record would pass any test that only read its JSON,
  and would then make every later `provision` for that reference `invalid-request`. So the
  issuance record and the assignment record are asserted on disk, not inferred from stdout.
* A REPLAYED `report` IS ANSWERED FROM LOCAL STATE ALONE. The replay below runs against a host
  whose record port FAILS, which is the only way to prove the duplicate answer never reaches the
  store: a host that works cannot distinguish "did not need the store" from "used it and agreed".
* NO COMMAND EVER PRINTS CREDENTIAL MATERIAL. The value reader below returns a recognisable
  secret, and the tests assert it appears in the provisioned target file and in NO line of
  output.
"""

from __future__ import annotations

import importlib
import json
import os
import pathlib
from typing import Any

import pytest

__all__: list[str] = []

MODULE_PATH = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_commands.py"

_RUN = "run-1"
_RECORD_ID = "d1f0c2a4-8b6e-4c1a-9f3d-0e7a5b2c4d69"
_GENERATION = "9b3e7c51-0a2d-4f68-b1c4-7e5a2d9f06b8"
_NOW = "2026-09-30T20:00:00Z"
_LATER = "2026-09-30T21:00:00Z"
_REFERENCE = "ref-abcdef0123456789"
_SECRET = b"sk-ant-oat0-the-credential-bytes"
_VALUE_REF = f"op://LPM Values/{_RECORD_ID}.{_GENERATION}/credential"


def _commands() -> Any:
    assert MODULE_PATH.is_file(), "overseer/_lpm_commands.py must exist"
    return importlib.import_module("_lpm_commands")


def _failure(*, message: str) -> Any:
    from _lpm_results import store_unavailable

    from overseer._vendor.returns.result import Failure

    return Failure(store_unavailable(message=message))


def _record(**overrides: object) -> Any:
    from _lpm_record import CredentialRecord

    fields: dict[str, object] = {
        "record_id": _RECORD_ID,
        "provider": "anthropic",
        "account_id": "acct-1",
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "status": "valid",
        "acquired_at": _NOW,
        "expires_at": None,
        "last_validated": _NOW,
        "value_generation": _GENERATION,
        "value_ref": _VALUE_REF,
        "previous_value_ref": None,
    }
    fields.update(overrides)
    return CredentialRecord(**fields)  # pyright: ignore[reportArgumentType]


def _unwritable_status(*, record: Any, next_status: str, now: str) -> Any:
    """A status writer that cannot persist, standing in for a host with no credential store.

    It is defined HERE rather than imported from the product on purpose. `_lpm_manager_host` builds
    the real one out of the ratified prerequisite closure, and its refusal is measured against a
    fixture tree in `tests/test_lpm_console_bootstrap.py`; what this module needs is a double that
    lets the COMMAND's fail-closed ordering be asserted without dragging that closure in.
    """
    _ = (record, next_status, now)
    return _failure(message="this host cannot persist a credential status transition")


def _host(*, tmp_path: pathlib.Path, **overrides: object) -> Any:
    from _lpm_command_host import ManagerHost
    from _lpm_config import default_config

    from overseer._vendor.returns.result import Success

    fields: dict[str, object] = {
        "state_dir": tmp_path / "state",
        "config": default_config(),
        "owner_uid": os.getuid(),
        "now": _NOW,
        "read_input": lambda: "",
        "records": lambda: Success(()),
        "read_value": lambda *, value_ref: Success(_SECRET),
        "write_status": _unwritable_status,
        "new_reference": lambda: _REFERENCE,
        "monotonic": lambda: 0.0,
        "sleep": lambda _seconds: None,
    }
    fields.update(overrides)
    return ManagerHost(**fields)  # pyright: ignore[reportArgumentType]


def _run(*, arguments: list[str], host: Any) -> Any:
    return _commands().run_manager_command(arguments=arguments, host=host)


def _ran(*, arguments: list[str], host: Any) -> dict[str, Any]:
    outcome = _run(arguments=arguments, host=host)
    assert "\n" not in outcome.stdout, "every answer is exactly one line"
    return {"body": json.loads(outcome.stdout), "exit_status": outcome.exit_status}


def _object_host(*, tmp_path: pathlib.Path, body: object, **overrides: object) -> Any:
    return _host(tmp_path=tmp_path, read_input=lambda: json.dumps(body), **overrides)


def _target_request(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {"version": 1, "consumer_run_id": _RUN, "adapter": "isolated-run"}
    body.update(overrides)
    return body


def _provision_request(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "version": 1,
        "provider": "anthropic",
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "consumer_run_id": _RUN,
        "target_ref": _REFERENCE,
    }
    body.update(overrides)
    return body


def _report(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "version": 1,
        "consumer_run_id": _RUN,
        "record_id": _RECORD_ID,
        "occurred_at": _NOW,
        "classification": "unknown",
    }
    body.update(overrides)
    return body


def _issued(*, tmp_path: pathlib.Path) -> dict[str, Any]:
    """Run `target` for real, so every later provision reads an issuance this code wrote."""
    return _ran(
        arguments=["target", "--target-json", "-"],
        host=_object_host(tmp_path=tmp_path, body=_target_request()),
    )


def _established(*, tmp_path: pathlib.Path) -> pathlib.Path:
    """`<manager-state>` as the manager itself would establish it: owner-only, all the way down.

    Pre-seeding a record with a bare `mkdir` would leave the tree at the process umask, which the
    manager correctly refuses -- so a test that seeds state must establish it the same way a
    command does, or it measures the refusal instead of the behaviour it meant to set up.
    """
    from _lpm_command_host import establish_manager_state

    state = tmp_path / "state"
    _ = establish_manager_state(state_dir=state, owner_uid=os.getuid())
    return state


def _one_record() -> Any:
    from overseer._vendor.returns.result import Success

    return Success((_record(),))


def _empty() -> Any:
    from overseer._vendor.returns.result import Success

    return Success(())


def _provisioned(*, tmp_path: pathlib.Path, **overrides: object) -> dict[str, Any]:
    _ = _issued(tmp_path=tmp_path)
    return _ran(
        arguments=["provision", "--request-json", "-"],
        host=_object_host(
            tmp_path=tmp_path, body=_provision_request(), **{"records": _one_record, **overrides}
        ),
    )


# --------------------------------------------------------------------------------------
# The dispatcher: which commands this build serves, and how the rest are typed.
# --------------------------------------------------------------------------------------


def test_the_served_command_set_is_declared(tmp_path: pathlib.Path) -> None:
    assert _commands().SERVED_COMMANDS == ("target", "provision", "report", "attention")


@pytest.mark.parametrize(
    "arguments",
    [
        ["acquire", "--acquisition-json", "-"],
        ["complete", "--completion-json", "-"],
        ["release", "--release-json", "-"],
        ["proof-status"],
        ["attention", "--resolve", "d1f0c2a4-8b6e-4c1a-9f3d-0e7a5b2c4d69"],
        ["attention", "--give-up", "d1f0c2a4-8b6e-4c1a-9f3d-0e7a5b2c4d69"],
    ],
)
def test_a_ratified_but_unserved_command_is_a_typed_internal_bug(
    *, tmp_path: pathlib.Path, arguments: list[str]
) -> None:
    ran = _ran(arguments=arguments, host=_host(tmp_path=tmp_path))

    assert ran["body"]["status"] == "error"
    assert ran["body"]["error_type"] == "internal-bug"
    assert ran["exit_status"] == 70


def test_an_unknown_subcommand_is_refused_before_any_host_use(tmp_path: pathlib.Path) -> None:
    def _explode() -> Any:
        raise AssertionError("the records port must not be reached")

    ran = _ran(arguments=["nonsense"], host=_host(tmp_path=tmp_path, records=_explode))

    assert ran["body"]["error_type"] == "invalid-request"
    assert ran["exit_status"] == 2
    assert not (tmp_path / "state").exists()


# --------------------------------------------------------------------------------------
# attention — the zero-argument operator list.
# --------------------------------------------------------------------------------------


def test_the_attention_list_on_a_fresh_host_is_an_empty_item_array(
    tmp_path: pathlib.Path,
) -> None:
    ran = _ran(arguments=["attention"], host=_host(tmp_path=tmp_path))

    assert ran["body"] == {"version": 1, "status": "ok", "operation": "attention", "items": []}
    assert ran["exit_status"] == 0


def test_an_unreadable_attention_directory_is_store_unavailable_with_exit_four(
    tmp_path: pathlib.Path,
) -> None:
    from _lpm_attention import attention_directory

    state = tmp_path / "state"
    state.mkdir(parents=True, mode=0o700)
    attention_directory(state_dir=state).symlink_to(tmp_path, target_is_directory=True)

    ran = _ran(arguments=["attention"], host=_host(tmp_path=tmp_path))

    assert ran["body"]["error_type"] == "store-unavailable"
    assert ran["exit_status"] == 4


# --------------------------------------------------------------------------------------
# target — issue one reference bound to one run, and persist the issuance.
# --------------------------------------------------------------------------------------


def test_target_answers_the_reference_and_its_expiry_and_persists_the_issuance(
    tmp_path: pathlib.Path,
) -> None:
    from _lpm_command_host import target_destination
    from _lpm_paths import local_record_path

    ran = _issued(tmp_path=tmp_path)

    assert ran["body"] == {
        "version": 1,
        "status": "ok",
        "operation": "target",
        "target_ref": _REFERENCE,
        "expires_at": "2026-10-01T20:00:00Z",
    }
    assert ran["exit_status"] == 0
    state = tmp_path / "state"
    path = local_record_path(state_dir=state, family="issuance", identity=[_REFERENCE]).unwrap()
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["reference"] == _REFERENCE
    assert stored["consumer_run_id"] == _RUN
    assert stored["adapter"] == "isolated-run"
    assert stored["destination"] == str(target_destination(state_dir=state, reference=_REFERENCE))


def test_the_issuance_record_is_owner_only(tmp_path: pathlib.Path) -> None:
    from _lpm_paths import local_record_path

    _ = _issued(tmp_path=tmp_path)
    path = local_record_path(
        state_dir=tmp_path / "state", family="issuance", identity=[_REFERENCE]
    ).unwrap()

    assert path.stat().st_mode & 0o077 == 0


@pytest.mark.parametrize(
    "body",
    [
        ["not", "an", "object"],
        _target_request(version=2),
        _target_request(version=True),
        _target_request(consumer_run_id=""),
        _target_request(adapter=""),
        _target_request(adapter="some-other-adapter"),
        {"version": 1, "consumer_run_id": _RUN},
        {**_target_request(), "extra": 1},
    ],
)
def test_a_defective_target_request_is_invalid_request_with_exit_two(
    *, tmp_path: pathlib.Path, body: object
) -> None:
    ran = _ran(
        arguments=["target", "--target-json", "-"],
        host=_object_host(tmp_path=tmp_path, body=body),
    )

    assert ran["body"]["error_type"] == "invalid-request"
    assert ran["exit_status"] == 2


def test_a_registered_adapter_that_configuration_disables_is_invalid_request(
    tmp_path: pathlib.Path,
) -> None:
    from dataclasses import replace

    from _lpm_config import default_config

    ran = _ran(
        arguments=["target", "--target-json", "-"],
        host=_object_host(
            tmp_path=tmp_path,
            body=_target_request(),
            config=replace(default_config(), enabled_target_adapters=()),
        ),
    )

    assert ran["body"]["error_type"] == "invalid-request"
    assert "not enabled" in ran["body"]["message"]


def test_target_reads_its_object_from_a_path_as_well_as_from_standard_input(
    tmp_path: pathlib.Path,
) -> None:
    request = tmp_path / "request.json"
    _ = request.write_text(json.dumps(_target_request()), encoding="utf-8")

    ran = _ran(arguments=["target", "--target-json", str(request)], host=_host(tmp_path=tmp_path))

    assert ran["body"]["target_ref"] == _REFERENCE


def test_an_unreadable_input_path_is_refused_without_quoting_it(
    tmp_path: pathlib.Path,
) -> None:
    missing = tmp_path / "sk-ant-oat0-looks-like-a-secret.json"

    ran = _ran(arguments=["target", "--target-json", str(missing)], host=_host(tmp_path=tmp_path))

    assert ran["body"]["error_type"] == "invalid-request"
    assert str(missing) not in ran["body"]["message"]


def test_unparsable_input_is_refused(tmp_path: pathlib.Path) -> None:
    ran = _ran(
        arguments=["target", "--target-json", "-"],
        host=_host(tmp_path=tmp_path, read_input=lambda: "{not json"),
    )

    assert ran["body"]["error_type"] == "invalid-request"


def test_an_empty_minted_reference_is_refused_before_anything_is_written(
    tmp_path: pathlib.Path,
) -> None:
    ran = _ran(
        arguments=["target", "--target-json", "-"],
        host=_object_host(tmp_path=tmp_path, body=_target_request(), new_reference=lambda: ""),
    )

    assert ran["body"]["error_type"] == "invalid-request"
    assert list((tmp_path / "state" / "issuances").iterdir()) == []


def test_a_non_canonical_manager_time_is_an_internal_bug(tmp_path: pathlib.Path) -> None:
    ran = _ran(
        arguments=["target", "--target-json", "-"],
        host=_object_host(tmp_path=tmp_path, body=_target_request(), now="not-a-timestamp"),
    )

    assert ran["body"]["error_type"] == "internal-bug"
    assert ran["exit_status"] == 70


def test_a_world_readable_state_directory_is_refused_rather_than_tightened(
    tmp_path: pathlib.Path,
) -> None:
    """The establishment rail: the manager validates what it finds, it does not re-mode it."""
    (tmp_path / "state").mkdir(parents=True, mode=0o755)

    ran = _ran(
        arguments=["target", "--target-json", "-"],
        host=_object_host(tmp_path=tmp_path, body=_target_request()),
    )

    assert ran["body"]["error_type"] == "store-unavailable"
    assert ran["exit_status"] == 4


def test_an_untakeable_destination_lock_is_store_unavailable(tmp_path: pathlib.Path) -> None:
    state = _established(tmp_path=tmp_path)
    _ = (state / "locks" / "destination").write_text("not a directory\n", encoding="utf-8")

    ran = _ran(
        arguments=["target", "--target-json", "-"],
        host=_object_host(tmp_path=tmp_path, body=_target_request()),
    )

    assert ran["body"]["error_type"] == "store-unavailable"
    assert ran["exit_status"] == 4


def test_an_unsafe_existing_issuance_record_is_refused_rather_than_rewritten(
    tmp_path: pathlib.Path,
) -> None:
    """A world-readable record is not overwritten: that would publish the new content through
    the very permissions that made the old one unsafe."""
    from _lpm_paths import local_record_path

    state = _established(tmp_path=tmp_path)
    path = local_record_path(state_dir=state, family="issuance", identity=[_REFERENCE]).unwrap()
    _ = path.write_text("{}", encoding="utf-8")
    path.chmod(0o644)

    ran = _ran(
        arguments=["target", "--target-json", "-"],
        host=_object_host(tmp_path=tmp_path, body=_target_request()),
    )

    assert ran["body"]["error_type"] == "store-unavailable"


def test_an_unregistered_issuance_family_is_an_internal_bug(
    *, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import _lpm_paths

    monkeypatch.delitem(_lpm_paths.LOCAL_PATH_FAMILIES, "issuance")

    ran = _ran(
        arguments=["target", "--target-json", "-"],
        host=_object_host(tmp_path=tmp_path, body=_target_request()),
    )

    assert ran["body"]["error_type"] == "internal-bug"


# --------------------------------------------------------------------------------------
# provision — select, lease, commit the target, record the assignment.
# --------------------------------------------------------------------------------------


def test_provision_answers_the_five_member_receipt_and_commits_the_credential(
    tmp_path: pathlib.Path,
) -> None:
    from _lpm_command_host import target_destination

    ran = _provisioned(tmp_path=tmp_path)

    assert ran["exit_status"] == 0
    assert ran["body"]["operation"] == "provision"
    assert ran["body"]["receipt"] == {
        "record_id": _RECORD_ID,
        "account_id": "acct-1",
        "validated_at": _NOW,
        "purpose": "factory",
        "lease_expires_at": "2026-10-01T02:00:00Z",
    }
    destination = target_destination(state_dir=tmp_path / "state", reference=_REFERENCE)
    assert destination.read_bytes() == _SECRET
    assert destination.stat().st_mode & 0o077 == 0


def test_the_credential_bytes_never_appear_in_the_answer(tmp_path: pathlib.Path) -> None:
    outcome = _run(
        arguments=["attention"],
        host=_host(tmp_path=tmp_path),
    )
    provisioned = _provisioned(tmp_path=tmp_path)

    assert _SECRET.decode() not in outcome.stdout
    assert _SECRET.decode() not in json.dumps(provisioned["body"])


def test_a_successful_provision_records_the_assignment_and_the_incumbency(
    tmp_path: pathlib.Path,
) -> None:
    from _lpm_assignment import read_assignment
    from _lpm_command_host import selection_state_path

    _ = _provisioned(tmp_path=tmp_path)

    assignment = read_assignment(
        state_dir=tmp_path / "state", consumer_run_id=_RUN, owner_uid=os.getuid()
    ).unwrap()
    assert assignment is not None
    assert assignment.record_id == _RECORD_ID
    assert assignment.status == "committed"
    assert assignment.target_committed_at == _NOW
    assert assignment.report_markers == ()
    stored = json.loads(
        selection_state_path(state_dir=tmp_path / "state").read_text(encoding="utf-8")
    )
    assert stored["incumbents"][0]["record_id"] == _RECORD_ID


def test_a_provision_naming_an_unissued_reference_is_invalid_request(
    tmp_path: pathlib.Path,
) -> None:
    ran = _ran(
        arguments=["provision", "--request-json", "-"],
        host=_object_host(tmp_path=tmp_path, body=_provision_request(), records=_one_record),
    )

    assert ran["body"]["error_type"] == "invalid-request"
    assert ran["exit_status"] == 2


def test_an_empty_eligible_pool_is_retryable_exhaustion_with_exit_three(
    tmp_path: pathlib.Path,
) -> None:
    ran = _provisioned(tmp_path=tmp_path, records=_empty)

    assert ran["body"]["error_type"] == "retryable-exhaustion"
    assert ran["exit_status"] == 3


def test_a_record_port_failure_is_reported_unchanged(tmp_path: pathlib.Path) -> None:
    ran = _provisioned(
        tmp_path=tmp_path, records=lambda: _failure(message="the metadata vault is unreachable")
    )

    assert ran["body"]["error_type"] == "store-unavailable"
    assert ran["exit_status"] == 4


def test_a_value_read_failure_leaves_the_target_untouched(tmp_path: pathlib.Path) -> None:
    from _lpm_command_host import target_destination

    ran = _provisioned(
        tmp_path=tmp_path,
        read_value=lambda *, value_ref: _failure(message="the values vault is unreachable"),
    )

    assert ran["body"]["error_type"] == "store-unavailable"
    assert not target_destination(state_dir=tmp_path / "state", reference=_REFERENCE).exists()


def test_a_defective_provision_request_is_invalid_request(tmp_path: pathlib.Path) -> None:
    ran = _ran(
        arguments=["provision", "--request-json", "-"],
        host=_object_host(tmp_path=tmp_path, body=_provision_request(lease_seconds=1)),
    )

    assert ran["body"]["error_type"] == "invalid-request"


def test_unparsable_provision_input_is_invalid_request(tmp_path: pathlib.Path) -> None:
    ran = _ran(
        arguments=["provision", "--request-json", "-"],
        host=_host(tmp_path=tmp_path, read_input=lambda: "nope"),
    )

    assert ran["body"]["error_type"] == "invalid-request"


def test_a_malformed_issuance_record_is_refused(tmp_path: pathlib.Path) -> None:
    from _lpm_paths import local_record_path

    _ = _issued(tmp_path=tmp_path)
    path = local_record_path(
        state_dir=tmp_path / "state", family="issuance", identity=[_REFERENCE]
    ).unwrap()
    _ = path.write_text(json.dumps({"version": 1}), encoding="utf-8")

    ran = _ran(
        arguments=["provision", "--request-json", "-"],
        host=_object_host(tmp_path=tmp_path, body=_provision_request(), records=_one_record),
    )

    assert ran["body"]["error_type"] == "invalid-request"


def test_an_unreadable_issuance_record_is_store_unavailable(tmp_path: pathlib.Path) -> None:
    from _lpm_paths import local_record_path

    _ = _issued(tmp_path=tmp_path)
    path = local_record_path(
        state_dir=tmp_path / "state", family="issuance", identity=[_REFERENCE]
    ).unwrap()
    path.chmod(0o644)

    ran = _ran(
        arguments=["provision", "--request-json", "-"],
        host=_object_host(tmp_path=tmp_path, body=_provision_request(), records=_one_record),
    )

    assert ran["body"]["error_type"] == "store-unavailable"


def test_an_unreadable_selection_state_is_store_unavailable(tmp_path: pathlib.Path) -> None:
    from _lpm_command_host import selection_state_path

    _ = _issued(tmp_path=tmp_path)
    path = selection_state_path(state_dir=tmp_path / "state")
    _ = path.write_text(json.dumps({"version": 1, "incumbents": [], "last_assignments": []}))
    path.chmod(0o644)

    ran = _ran(
        arguments=["provision", "--request-json", "-"],
        host=_object_host(tmp_path=tmp_path, body=_provision_request(), records=_one_record),
    )

    assert ran["body"]["error_type"] == "store-unavailable"


def test_a_provision_whose_state_tree_turned_unusable_is_store_unavailable(
    tmp_path: pathlib.Path,
) -> None:
    _ = _issued(tmp_path=tmp_path)
    state = tmp_path / "state"
    (state / "targets").rmdir()
    _ = (state / "targets").write_text("not a directory\n", encoding="utf-8")

    ran = _ran(
        arguments=["provision", "--request-json", "-"],
        host=_object_host(tmp_path=tmp_path, body=_provision_request(), records=_one_record),
    )

    assert ran["body"]["error_type"] == "store-unavailable"


def test_an_unregistered_issuance_family_is_an_internal_bug_for_provision(
    *, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import _lpm_paths

    _ = _issued(tmp_path=tmp_path)
    monkeypatch.delitem(_lpm_paths.LOCAL_PATH_FAMILIES, "issuance")

    ran = _ran(
        arguments=["provision", "--request-json", "-"],
        host=_object_host(tmp_path=tmp_path, body=_provision_request(), records=_one_record),
    )

    assert ran["body"]["error_type"] == "internal-bug"


def test_a_record_without_a_value_reference_is_an_internal_bug(tmp_path: pathlib.Path) -> None:
    from overseer._vendor.returns.result import Success

    ran = _provisioned(
        tmp_path=tmp_path, records=lambda: Success((_record(value_generation=None),))
    )

    assert ran["body"]["error_type"] == "internal-bug"
    assert ran["exit_status"] == 70


def test_an_account_leased_to_another_run_is_excluded_from_selection(
    tmp_path: pathlib.Path,
) -> None:
    from _lpm_leases import lease_object, new_lease
    from _lpm_localstate import write_local_record
    from _lpm_paths import local_record_path

    lease = new_lease(
        provider="anthropic",
        account_id="acct-1",
        record_id=_RECORD_ID,
        consumer_run_id="some-other-run",
        now=_NOW,
        lease_seconds=3600,
    ).unwrap()
    path = local_record_path(
        state_dir=_established(tmp_path=tmp_path),
        family="lease",
        identity=["anthropic", "acct-1"],
    ).unwrap()
    _ = write_local_record(path=path, value=lease_object(lease=lease), owner_uid=os.getuid())

    ran = _provisioned(tmp_path=tmp_path)

    assert ran["body"]["error_type"] == "retryable-exhaustion"


def test_this_runs_own_live_lease_does_not_exclude_its_own_account(
    tmp_path: pathlib.Path,
) -> None:
    from _lpm_leases import lease_object, new_lease
    from _lpm_localstate import write_local_record
    from _lpm_paths import local_record_path

    lease = new_lease(
        provider="anthropic",
        account_id="acct-1",
        record_id=_RECORD_ID,
        consumer_run_id=_RUN,
        now=_NOW,
        lease_seconds=3600,
    ).unwrap()
    path = local_record_path(
        state_dir=_established(tmp_path=tmp_path),
        family="lease",
        identity=["anthropic", "acct-1"],
    ).unwrap()
    _ = write_local_record(path=path, value=lease_object(lease=lease), owner_uid=os.getuid())

    ran = _provisioned(tmp_path=tmp_path)

    assert ran["exit_status"] == 0


def test_two_records_on_one_account_are_observed_once(tmp_path: pathlib.Path) -> None:
    from overseer._vendor.returns.result import Success

    other = "7c1b4e92-5d3a-4b60-8f2e-1a9c6d4b8305"
    ran = _provisioned(
        tmp_path=tmp_path,
        records=lambda: Success((_record(), _record(record_id=other))),
    )

    assert ran["exit_status"] == 0


def test_an_unreadable_lease_record_is_store_unavailable(tmp_path: pathlib.Path) -> None:
    from _lpm_localstate import write_local_record
    from _lpm_paths import local_record_path

    path = local_record_path(
        state_dir=_established(tmp_path=tmp_path), family="lease", identity=["anthropic", "acct-1"]
    ).unwrap()
    _ = write_local_record(path=path, value={"version": 1}, owner_uid=os.getuid())
    path.chmod(0o644)

    ran = _provisioned(tmp_path=tmp_path)

    assert ran["body"]["error_type"] == "store-unavailable"


def test_an_unregistered_lease_family_is_an_internal_bug(
    *, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import _lpm_paths

    _ = _issued(tmp_path=tmp_path)
    monkeypatch.delitem(_lpm_paths.LOCAL_PATH_FAMILIES, "lease")

    ran = _ran(
        arguments=["provision", "--request-json", "-"],
        host=_object_host(tmp_path=tmp_path, body=_provision_request(), records=_one_record),
    )

    assert ran["body"]["error_type"] == "internal-bug"


def test_a_failed_assignment_write_is_store_unavailable_after_the_commit(
    *, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import _lpm_command_provision

    monkeypatch.setattr(
        _lpm_command_provision,
        "write_assignment",
        lambda **_kwargs: _failure(message="the assignment record was not replaced"),
    )

    ran = _provisioned(tmp_path=tmp_path)

    assert ran["body"]["error_type"] == "store-unavailable"


def test_a_failed_selection_state_commit_is_reported(
    *, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import _lpm_command_provision

    monkeypatch.setattr(
        _lpm_command_provision,
        "committed_selection_state",
        lambda **_kwargs: _failure(message="the selection state could not be advanced"),
    )

    ran = _provisioned(tmp_path=tmp_path)

    assert ran["body"]["error_type"] == "store-unavailable"


# --------------------------------------------------------------------------------------
# report — accept one failure signal, exactly once.
# --------------------------------------------------------------------------------------


def _reported(*, tmp_path: pathlib.Path, body: object, **overrides: object) -> dict[str, Any]:
    return _ran(
        arguments=["report", "--report-json", "-"],
        host=_object_host(tmp_path=tmp_path, body=body, **{"records": _one_record, **overrides}),
    )


def test_a_first_report_is_accepted_and_records_its_marker(tmp_path: pathlib.Path) -> None:
    from _lpm_assignment import read_assignment

    _ = _provisioned(tmp_path=tmp_path)

    ran = _reported(tmp_path=tmp_path, body=_report())

    assert ran["body"] == {
        "version": 1,
        "status": "ok",
        "operation": "report",
        "duplicate": False,
    }
    assert ran["exit_status"] == 0
    assignment = read_assignment(
        state_dir=tmp_path / "state", consumer_run_id=_RUN, owner_uid=os.getuid()
    ).unwrap()
    assert assignment is not None
    assert [marker.classification for marker in assignment.report_markers] == ["unknown"]


def test_an_accepted_report_releases_the_runs_lease(tmp_path: pathlib.Path) -> None:
    from _lpm_paths import local_record_path

    _ = _provisioned(tmp_path=tmp_path)
    path = local_record_path(
        state_dir=tmp_path / "state", family="lease", identity=["anthropic", "acct-1"]
    ).unwrap()
    assert path.is_file()

    _ = _reported(tmp_path=tmp_path, body=_report())

    assert not path.exists()


def test_a_replayed_report_answers_duplicate_without_touching_the_store(
    tmp_path: pathlib.Path,
) -> None:
    _ = _provisioned(tmp_path=tmp_path)
    _ = _reported(tmp_path=tmp_path, body=_report())

    def _explode() -> Any:
        raise AssertionError("a replay must not reach the credential store")

    replay = _ran(
        arguments=["report", "--report-json", "-"],
        host=_object_host(tmp_path=tmp_path, body=_report(), records=_explode),
    )

    assert replay["body"]["duplicate"] is True
    assert replay["exit_status"] == 0


def test_a_report_naming_an_unknown_run_is_invalid_report(tmp_path: pathlib.Path) -> None:
    ran = _reported(tmp_path=tmp_path, body=_report())

    assert ran["body"]["error_type"] == "invalid-report"
    assert ran["exit_status"] == 2


def test_a_report_naming_the_wrong_credential_is_invalid_report(
    tmp_path: pathlib.Path,
) -> None:
    other = "7c1b4e92-5d3a-4b60-8f2e-1a9c6d4b8305"
    _ = _provisioned(tmp_path=tmp_path)

    ran = _reported(tmp_path=tmp_path, body=_report(record_id=other))

    assert ran["body"]["error_type"] == "invalid-report"


def test_a_defective_report_object_is_invalid_report(tmp_path: pathlib.Path) -> None:
    ran = _reported(tmp_path=tmp_path, body=_report(classification="nonsense"))

    assert ran["body"]["error_type"] == "invalid-report"


def test_unparsable_report_input_is_invalid_report(tmp_path: pathlib.Path) -> None:
    ran = _ran(
        arguments=["report", "--report-json", "-"],
        host=_host(tmp_path=tmp_path, read_input=lambda: "{"),
    )

    assert ran["body"]["error_type"] == "invalid-report"
    assert ran["exit_status"] == 2


def test_a_report_outside_the_lease_interval_is_invalid_report(
    tmp_path: pathlib.Path,
) -> None:
    _ = _provisioned(tmp_path=tmp_path)

    ran = _reported(tmp_path=tmp_path, body=_report(occurred_at="2026-09-30T19:59:59Z"))

    assert ran["body"]["error_type"] == "invalid-report"


def test_a_report_for_a_credential_no_longer_stored_is_store_unavailable(
    tmp_path: pathlib.Path,
) -> None:
    _ = _provisioned(tmp_path=tmp_path)

    ran = _ran(
        arguments=["report", "--report-json", "-"],
        host=_object_host(tmp_path=tmp_path, body=_report(), records=_empty),
    )

    assert ran["body"]["error_type"] == "store-unavailable"
    assert ran["exit_status"] == 4


def test_a_report_whose_record_port_fails_is_reported_unchanged(
    tmp_path: pathlib.Path,
) -> None:
    _ = _provisioned(tmp_path=tmp_path)

    ran = _ran(
        arguments=["report", "--report-json", "-"],
        host=_object_host(
            tmp_path=tmp_path,
            body=_report(),
            records=lambda: _failure(message="the metadata vault is unreachable"),
        ),
    )

    assert ran["body"]["error_type"] == "store-unavailable"


def test_a_classification_that_suspects_the_credential_needs_the_status_writer(
    tmp_path: pathlib.Path,
) -> None:
    """The fail-closed boundary: the transition is required, so nothing is recorded without it."""
    from _lpm_assignment import read_assignment

    _ = _provisioned(tmp_path=tmp_path)

    ran = _reported(tmp_path=tmp_path, body=_report(classification="authentication"))

    assert ran["body"]["error_type"] == "store-unavailable"
    assert ran["exit_status"] == 4
    assignment = read_assignment(
        state_dir=tmp_path / "state", consumer_run_id=_RUN, owner_uid=os.getuid()
    ).unwrap()
    assert assignment is not None
    assert assignment.report_markers == ()


def test_a_suspecting_classification_is_accepted_once_the_writer_is_established(
    tmp_path: pathlib.Path,
) -> None:
    from overseer._vendor.returns.result import Success

    moves: list[tuple[str, str]] = []

    def _write_status(*, record: Any, next_status: str, now: str) -> Any:
        moves.append((record.record_id, next_status))
        _ = now
        return Success(None)

    _ = _provisioned(tmp_path=tmp_path)

    ran = _reported(
        tmp_path=tmp_path,
        body=_report(classification="authentication"),
        write_status=_write_status,
    )

    assert ran["body"]["duplicate"] is False
    assert moves == [(_RECORD_ID, "suspect")]


def test_a_report_whose_generation_no_longer_matches_needs_no_transition(
    tmp_path: pathlib.Path,
) -> None:
    from overseer._vendor.returns.result import Success

    other = "2f5c8a16-9b4d-4e70-a3c1-6d8b5e9f0247"
    _ = _provisioned(tmp_path=tmp_path)

    ran = _reported(
        tmp_path=tmp_path,
        body=_report(classification="authentication"),
        records=lambda: Success((_record(value_generation=other),)),
    )

    assert ran["body"]["duplicate"] is False


def test_a_report_against_an_acquiring_credential_is_invalid_report(
    tmp_path: pathlib.Path,
) -> None:
    """`report_effects`' own refusal: an acquiring credential could not have been provisioned."""
    from overseer._vendor.returns.result import Success

    _ = _provisioned(tmp_path=tmp_path)

    ran = _reported(
        tmp_path=tmp_path,
        body=_report(),
        records=lambda: Success((_record(status="acquiring", last_validated=None),)),
    )

    assert ran["body"]["error_type"] == "invalid-report"


def test_the_assigned_credential_is_found_past_an_unrelated_record(
    tmp_path: pathlib.Path,
) -> None:
    from overseer._vendor.returns.result import Success

    other = "7c1b4e92-5d3a-4b60-8f2e-1a9c6d4b8305"
    _ = _provisioned(tmp_path=tmp_path)

    ran = _reported(
        tmp_path=tmp_path,
        body=_report(),
        records=lambda: Success((_record(record_id=other, account_id="acct-2"), _record())),
    )

    assert ran["body"]["duplicate"] is False


def test_a_report_whose_state_tree_turned_unusable_is_store_unavailable(
    tmp_path: pathlib.Path,
) -> None:
    _ = _provisioned(tmp_path=tmp_path)
    state = tmp_path / "state"
    (state / "workers").rmdir()
    _ = (state / "workers").write_text("not a directory\n", encoding="utf-8")

    ran = _reported(tmp_path=tmp_path, body=_report())

    assert ran["body"]["error_type"] == "store-unavailable"


def test_every_registered_classification_releases_the_lease(tmp_path: pathlib.Path) -> None:
    """The invariant `_lpm_command_report._performed` relies on instead of a branch.

    It releases the lease unconditionally because every row of the closed handling table says to.
    If a classification is ever registered that does NOT release it, this fails -- which is the
    signal to reintroduce the guard rather than to relax this assertion.
    """
    from _lpm_signal import CLASSIFICATION_HANDLING

    assert [
        row.classification for row in CLASSIFICATION_HANDLING.values() if row.releases_lease
    ] == list(CLASSIFICATION_HANDLING)


def test_an_unregistered_lease_family_fails_the_release(
    *, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import _lpm_paths

    _ = _provisioned(tmp_path=tmp_path)
    monkeypatch.delitem(_lpm_paths.LOCAL_PATH_FAMILIES, "lease")

    ran = _reported(tmp_path=tmp_path, body=_report())

    assert ran["body"]["error_type"] == "internal-bug"


def test_a_failed_lease_release_is_reported(
    *, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import _lpm_command_report

    _ = _provisioned(tmp_path=tmp_path)
    monkeypatch.setattr(
        _lpm_command_report,
        "release_lease",
        lambda **_kwargs: _failure(message="the lease record could not be removed"),
    )

    ran = _reported(tmp_path=tmp_path, body=_report())

    assert ran["body"]["error_type"] == "store-unavailable"


def test_an_assignment_that_never_committed_a_target_is_invalid_report(
    *, tmp_path: pathlib.Path
) -> None:
    from dataclasses import replace

    from _lpm_assignment import read_assignment, write_assignment

    _ = _provisioned(tmp_path=tmp_path)
    state = tmp_path / "state"
    assignment = read_assignment(
        state_dir=state, consumer_run_id=_RUN, owner_uid=os.getuid()
    ).unwrap()
    assert assignment is not None
    _ = write_assignment(
        state_dir=state,
        assignment=replace(assignment, status="prepared", target_committed_at=None),
        owner_uid=os.getuid(),
    )

    ran = _reported(tmp_path=tmp_path, body=_report())

    assert ran["body"]["error_type"] == "invalid-report"


def test_an_unreadable_assignment_is_store_unavailable(tmp_path: pathlib.Path) -> None:
    from _lpm_assignment import assignment_path

    _ = _provisioned(tmp_path=tmp_path)
    assignment_path(state_dir=tmp_path / "state", consumer_run_id=_RUN).unwrap().chmod(0o644)

    ran = _reported(tmp_path=tmp_path, body=_report())

    assert ran["body"]["error_type"] == "store-unavailable"


# --------------------------------------------------------------------------------------
# The host's own seams.
# --------------------------------------------------------------------------------------


def test_the_lock_path_is_not_a_local_record_path(tmp_path: pathlib.Path) -> None:
    from _lpm_command_host import manager_lock_path

    path = manager_lock_path(state_dir=tmp_path, family="target", identity=["ref-1"])

    assert path.parent == tmp_path / "locks" / "target"
    assert path.suffix == ".lock"


def test_the_eligibility_policy_is_read_entirely_from_configuration() -> None:
    from _lpm_command_host import eligibility_policy
    from _lpm_config import default_config

    config = default_config()
    policy = eligibility_policy(config=config, now=_LATER)

    assert policy.now == _LATER
    assert policy.health_strategy == config.health_strategy
    assert policy.health_floor_percent == config.health_floor_percent
    assert policy.maximum_validation_age_seconds == config.maximum_validation_age_seconds
