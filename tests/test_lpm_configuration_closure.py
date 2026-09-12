"""The configuration boundary refuses BEFORE anything is opened, resolved or launched.

SPECIFICATION/contracts.md lists every way a configuration can
be wrong — unreadable file, invalid UTF-8, malformed JSON, duplicate member name, unknown
key or version, wrong JSON type, invalid enum, non-unique array, out-of-bounds value,
unregistered adapter or backend — and requires `invalid-request` with exit `2` for all of
them BEFORE any store, health-adapter, acquisition-browser or provisioning-target access.

The same contract adds the one relation no per-field check can see:
`acquisition_worker_timeout_seconds` must reserve all three possible validation probes,
their one- and two-second waits, browser-control startup and terminal store/lock work. A
configuration whose every field is individually in-bounds can still be unsatisfiable, and
the cost of finding that out late is a worker that cannot finish what it was launched to
do.

An ABSENT file means the default object; an EXISTING but unreadable one never does. The
difference matters because the default `health_strategy` is `none`, which applies no
health-based exclusion at all — silently defaulting a file the operator wrote would run
the manager under a policy nobody chose.
"""

from __future__ import annotations

import importlib
import pathlib

__all__: list[str] = []


def _config():
    for name in ("_lpm_config.py", "_lpm_config_fields.py"):
        assert (
            pathlib.Path(__file__).parents[1] / "overseer" / name
        ).is_file(), f"overseer/{name} must exist"
    return importlib.import_module("_lpm_config")


def _refusal(*, text: str) -> tuple[str, str]:
    failure = _config().parse_manager_config(text=text).failure()
    return failure.error_type, failure.message


def test_the_default_object_is_the_contract_s_declared_defaults():
    accepted = _config().default_config()

    assert accepted.account_reservations == {}
    assert accepted.maximum_validation_age_seconds == 300
    assert accepted.backend_cache_interval_seconds == 300
    assert accepted.provider_probe_timeout_seconds == 30
    assert accepted.external_call_timeout_seconds == 30
    assert accepted.acquisition_worker_timeout_seconds == 7200
    assert accepted.acquisition_step_limit == 50
    assert accepted.health_floor_percent == 10
    assert accepted.browser_attention_wait_seconds == 600
    assert accepted.health_strategy == "none"
    assert accepted.enabled_target_adapters == ("isolated-run",)
    assert accepted.secret_store_backend == "onepassword"


def test_an_absent_file_means_the_default_object_and_an_unreadable_one_never_does(tmp_path):
    config = _config()

    absent = config.load_manager_config(path=tmp_path / "missing.json")
    unreadable = config.load_manager_config(path=tmp_path)
    invalid_utf8 = tmp_path / "bytes.json"
    invalid_utf8.write_bytes(b'{"version":1,"health_strategy":"\xff"}')

    assert absent.unwrap().health_strategy == "none"
    assert unreadable.failure().error_type == "invalid-request"
    assert "unreadable" in unreadable.failure().message
    assert config.load_manager_config(path=invalid_utf8).failure().error_type == "invalid-request"


def test_a_present_and_valid_file_is_read_through_the_same_validation(tmp_path):
    path = tmp_path / "llm-provider-manager.json"
    path.write_text('{"version":1,"acquisition_step_limit":7}', encoding="utf-8")

    assert _config().load_manager_config(path=path).unwrap().acquisition_step_limit == 7


def test_malformed_text_and_a_duplicate_member_name_are_both_invalid_request():
    assert _refusal(text="{")[0] == "invalid-request"
    assert _refusal(text="{")[1] == "configuration is malformed JSON"
    duplicate = _refusal(text='{"version":1,"version":1}')
    assert duplicate[1] == "configuration is duplicate member name: version"


def test_the_envelope_admits_only_a_json_object_with_version_one_and_known_keys():
    assert _refusal(text="[]")[1] == "configuration must be a JSON object"
    assert _refusal(text="{}")[1] == "configuration version must be the integer 1"
    assert _refusal(text='{"version":2}')[1] == "configuration version must be the integer 1"
    assert _refusal(text='{"version":true}')[1] == "configuration version must be the integer 1"
    assert _refusal(text='{"version":"1"}')[1] == "configuration version must be the integer 1"
    assert _refusal(text='{"version":1,"cache":1}')[1] == "unknown configuration key: cache"


def test_an_integer_key_rejects_booleans_and_out_of_range_values():
    # `true` is an `int` subclass in Python; accepting it would configure a one-second
    # validation age from a configuration that never named a number.
    assert _refusal(text='{"version":1,"acquisition_step_limit":true}')[1] == (
        "acquisition_step_limit must be an integer"
    )
    assert _refusal(text='{"version":1,"acquisition_step_limit":"5"}')[1] == (
        "acquisition_step_limit must be an integer"
    )
    assert _refusal(text='{"version":1,"acquisition_step_limit":0}')[1] == (
        "acquisition_step_limit must be from 1 through 200"
    )
    assert _refusal(text='{"version":1,"health_floor_percent":101}')[1] == (
        "health_floor_percent must be from 0 through 100"
    )
    assert (
        _config()
        .parse_manager_config(text='{"version":1,"health_floor_percent":0}')
        .unwrap()
        .health_floor_percent
        == 0
    )


def test_enums_and_the_adapter_array_name_only_registered_values():
    assert _refusal(text='{"version":1,"health_strategy":"best-effort"}')[1] == (
        "health_strategy must be one of: none, remaining-percent"
    )
    assert _refusal(text='{"version":1,"health_strategy":7}')[1] == (
        "health_strategy must be one of: none, remaining-percent"
    )
    assert _refusal(text='{"version":1,"secret_store_backend":"vault"}')[1] == (
        "secret_store_backend must be one of: onepassword"
    )
    assert _refusal(text='{"version":1,"enabled_target_adapters":[]}')[1] == (
        "enabled_target_adapters must be a non-empty array"
    )
    assert _refusal(text='{"version":1,"enabled_target_adapters":"isolated-run"}')[1] == (
        "enabled_target_adapters must be a non-empty array"
    )
    assert _refusal(text='{"version":1,"enabled_target_adapters":[""]}')[1] == (
        "enabled_target_adapters entries must be non-empty strings"
    )
    assert _refusal(text='{"version":1,"enabled_target_adapters":[1]}')[1] == (
        "enabled_target_adapters entries must be non-empty strings"
    )
    assert (
        _refusal(text='{"version":1,"enabled_target_adapters":["isolated-run","isolated-run"]}')[1]
        == "enabled_target_adapters entries must be unique"
    )
    assert _refusal(text='{"version":1,"enabled_target_adapters":["shared-run"]}')[1] == (
        "enabled_target_adapters names an unregistered shared-run"
    )


def test_a_malformed_reservation_is_refused_through_the_same_pre_access_boundary():
    assert _refusal(text='{"version":1,"account_reservations":[]}')[1] == (
        "account_reservations must be an object"
    )


def test_the_acquisition_deadline_relation_is_checked_after_every_field_is_in_bounds():
    config = _config()

    required = config.required_acquisition_worker_timeout(
        provider_probe_timeout_seconds=30, external_call_timeout_seconds=30
    )
    # Three probes, their one- and two-second waits, browser-control startup and terminal
    # store/lock work: 3 * probe + 6 * external + 3.
    assert required == 273
    refusal = _refusal(
        text=(
            '{"version":1,"acquisition_worker_timeout_seconds":60,'
            '"provider_probe_timeout_seconds":30,"external_call_timeout_seconds":30}'
        )
    )
    assert refusal[0] == "invalid-request"
    assert refusal[1] == (
        "acquisition_worker_timeout_seconds must be at least 273 for the configured "
        "probe and external-call timeouts"
    )
    accepted = config.parse_manager_config(
        text=(
            '{"version":1,"acquisition_worker_timeout_seconds":273,'
            '"provider_probe_timeout_seconds":30,"external_call_timeout_seconds":30}'
        )
    )
    assert accepted.unwrap().acquisition_worker_timeout_seconds == 273
