"""One key, one descriptor set, one exec vector — and no token bytes for the parent.

SPECIFICATION/contracts.md makes the credential-role launcher a short-lived child created
BEFORE any token retrieval, states the role registry as closed, and requires that token
bytes NEVER return across the launcher pipe or enter the parent manager or selection-brain
process. That is why this module exposes validation, description checking, argv
construction and the child environment, and nothing that returns a payload — the surface
itself is the guarantee.

THE KEYRING PERMISSION CHECK IS EXACT. The raw `rdescribe` line must carry exactly five
semicolon-separated fields with permission `3f0b0000`; owning-user bits alone are
insufficient, and any group or other permission fails the lookup BEFORE the payload is
piped. A sixth field or an extra word in the description fails the same way rather than
being ignored, because a key whose identity was only partly recognized is not the key the
role was promised.

A PRE-EXEC FAILURE IS THE ROLE'S OWN CLOSED OBJECT, not a generic error — and for final
provisioning that distinction is load-bearing: its pre-exec `store-unavailable` must not
be reinterpreted as the ambiguous target-write outcome, which applies only after a
successful exec.
"""

from __future__ import annotations

import importlib
import pathlib

__all__: list[str] = []


def _modules():
    for name in ("_lpm_roles.py", "_lpm_launcher.py"):
        assert (
            pathlib.Path(__file__).parents[1] / "overseer" / name
        ).is_file(), f"overseer/{name} must exist"
    return importlib.import_module("_lpm_roles"), importlib.import_module("_lpm_launcher")


def test_the_registry_is_the_ten_declared_roles_with_their_declared_keys():
    roles, _ = _modules()

    assert sorted(roles.CREDENTIAL_ROLES) == [
        "acquisition-prerequisite",
        "acquisition-writer",
        "browser-control",
        "final-provisioning",
        "lifecycle-writer",
        "metadata-reader",
        "provider-observer",
        "recovery-writer",
        "report-writer",
        "target-status",
    ]
    assert roles.credential_role(name="metadata-reader").key_description == (
        "lpm-op-metadata-reader"
    )
    assert roles.credential_role(name="final-provisioning").variable == (
        "LPM_VALUE_READER_OP_SERVICE_ACCOUNT_TOKEN"
    )
    assert roles.credential_role(name="unregistered") is None
    assert roles.LIFECYCLE_ROLES == ("lifecycle-writer", "report-writer", "recovery-writer")


def test_target_status_is_tokenless_and_still_holds_only_the_target_reference_lock():
    roles, _ = _modules()
    role = roles.credential_role(name="target-status")

    # Answering "did that write commit?" needs no secret at all; requiring one would put a
    # value-reading capability on the recovery path of every ambiguous write.
    assert role.key_description is None
    assert role.variable is None
    assert role.op_scope == ()
    assert role.descriptors == ("target-reference-lock",)


def test_a_role_name_maps_to_exactly_one_isolated_execution_vector():
    roles, _ = _modules()

    assert roles.role_execution_vector(
        python_executable="/usr/bin/python3",
        packaged_companion="/pkg/_lpm_role_main.py",
        name="metadata-reader",
    ) == (
        "/usr/bin/python3",
        "-I",
        "-S",
        "/pkg/_lpm_role_main.py",
        "--credential-role",
        "metadata-reader",
    )
    assert (
        roles.role_execution_vector(
            python_executable="/usr/bin/python3",
            packaged_companion="/pkg/_lpm_role_main.py",
            name="caller-supplied",
        )
        is None
    )


def test_a_launch_is_refused_before_key_lookup_when_anything_does_not_match_the_registry():
    _, launcher = _modules()

    unregistered = launcher.validated_launch(
        role_name="value-reader", key_description=None, descriptors=()
    )
    wrong_key = launcher.validated_launch(
        role_name="metadata-reader", key_description="lpm-op-value-reader", descriptors=()
    )
    extra_descriptor = launcher.validated_launch(
        role_name="metadata-reader",
        key_description="lpm-op-metadata-reader",
        descriptors=("target-reference-lock",),
    )
    accepted = launcher.validated_launch(
        role_name="final-provisioning",
        key_description="lpm-op-value-reader",
        descriptors=("target-reference-lock",),
    )

    assert unregistered.failure().error_type == "internal-bug"
    assert "unregistered credential role" in unregistered.failure().message
    assert "requires key description" in wrong_key.failure().message
    assert "may inherit exactly" in extra_descriptor.failure().message
    assert accepted.unwrap().name == "final-provisioning"
    assert (
        launcher.validated_launch(
            role_name="acquisition-prerequisite",
            key_description="lpm-op-acquisition-reader",
            descriptors=(),
        )
        .unwrap()
        .descriptors
        == ()
    )


def test_the_keyring_description_must_match_all_five_fields_exactly():
    _, launcher = _modules()
    expected = "lpm-op-metadata-reader"

    def _matches(raw: str) -> bool:
        return launcher.user_keyring_description_matches(
            raw=raw, effective_uid=1000, expected_description=expected
        )

    assert _matches(f"user;1000;1000;3f0b0000;{expected}")
    assert _matches(f"user;1000;1000;0x3f0b0000;{expected}"), "only the 0x prefix is normalized"
    assert not _matches(f"keyring;1000;1000;3f0b0000;{expected}")
    assert not _matches(f"user;1001;1000;3f0b0000;{expected}")
    assert not _matches(f"user;root;1000;3f0b0000;{expected}")
    assert not _matches(f"user;1000;staff;3f0b0000;{expected}")
    # Owning-user bits alone are insufficient: any group or other permission fails here,
    # before the payload is piped.
    assert not _matches(f"user;1000;1000;3f010000;{expected}")
    assert not _matches(f"user;1000;1000;3f0b0000;{expected} extra")
    assert not _matches(f"user;1000;1000;3f0b0000;{expected};6")
    assert not _matches(f"user;1000;1000;{expected}")


def test_the_keyctl_sequence_addresses_the_user_keyring_and_inspects_before_piping():
    _, launcher = _modules()

    assert launcher.keyctl_search_argv(description="lpm-op-acquisition") == (
        "/usr/bin/keyctl",
        "search",
        "@u",
        "user",
        "lpm-op-acquisition",
    )
    assert launcher.keyctl_rdescribe_argv(serial="12345") == (
        "/usr/bin/keyctl",
        "rdescribe",
        "12345",
    )
    assert launcher.keyctl_pipe_argv(serial="12345") == ("/usr/bin/keyctl", "pipe", "12345")
