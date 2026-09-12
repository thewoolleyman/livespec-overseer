"""The child environment a role starts with: scrubbed, plus at most its own variable.

SPECIFICATION/contracts.md closes the inherited credential-override set — `CLAUDECODE`,
every `ANTHROPIC_*` and `CLAUDE_*` name, all six manager service-account variables and
every `OP_*` variable, matched after ASCII uppercasing — and requires it removed before any
acquisition agent role, terminal, Chrome or browser-control child, again at every
child-spawn boundary, and again inside the launcher before key lookup.

A manager child that kept an inherited `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN`
would authenticate as whoever launched it rather than as the account the manager SELECTED
— which is precisely the confusion this whole operation exists to remove. That is why the
set includes the manager's own six variables too: no role may see another role's token.

The diagnostic reports NAMES ONLY. A diagnostic carrying the values would defeat the scrub
it reports on.
"""

from __future__ import annotations

import importlib
import pathlib

__all__: list[str] = []

# A stand-in for the bytes a real keyring lookup would pipe; never a real credential.
_FRESH_TOKEN = "fresh-metadata-value"


def _modules():
    for name in ("_lpm_env.py", "_lpm_roles.py", "_lpm_launcher.py"):
        assert (
            pathlib.Path(__file__).parents[1] / "overseer" / name
        ).is_file(), f"overseer/{name} must exist"
    return (
        importlib.import_module("_lpm_env"),
        importlib.import_module("_lpm_roles"),
        importlib.import_module("_lpm_launcher"),
    )


def test_the_role_child_environment_is_scrubbed_and_carries_at_most_its_own_variable():
    env, roles, launcher = _modules()
    inherited = {
        "PATH": "/usr/bin",
        "CLAUDECODE": "1",
        "claudecode": "1",
        "ANTHROPIC_API_KEY": "sk-ant-api0-secret",
        "CLAUDE_CODE_OAUTH_TOKEN": "sk-ant-oat0-secret",
        "OP_SERVICE_ACCOUNT_TOKEN": "ops-secret",
        "LPM_VALUE_READER_OP_SERVICE_ACCOUNT_TOKEN": "inherited-secret",
    }

    reader = launcher.role_child_environment(
        role=roles.credential_role(name="metadata-reader"),
        environ=inherited,
        token=_FRESH_TOKEN,
    )
    tokenless = launcher.role_child_environment(
        role=roles.credential_role(name="target-status"), environ=inherited, token=None
    )

    assert reader == {
        "PATH": "/usr/bin",
        "LPM_METADATA_READER_OP_SERVICE_ACCOUNT_TOKEN": _FRESH_TOKEN,
    }
    assert tokenless == {"PATH": "/usr/bin"}
    assert env.removed_override_names(environ=inherited) == (
        "ANTHROPIC_API_KEY",
        "CLAUDECODE",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "LPM_VALUE_READER_OP_SERVICE_ACCOUNT_TOKEN",
        "OP_SERVICE_ACCOUNT_TOKEN",
        "claudecode",
    )


def test_the_override_set_is_closed_and_matched_after_ascii_uppercasing():
    env, _, _ = _modules()

    assert env.is_credential_override(name="CLAUDECODE")
    assert env.is_credential_override(name="claudecode")
    assert env.is_credential_override(name="anthropic_base_url")
    assert env.is_credential_override(name="CLAUDE_CONFIG_DIR")
    assert env.is_credential_override(name="op_format")
    assert env.is_credential_override(name="LPM_ACQUISITION_OP_SERVICE_ACCOUNT_TOKEN")
    assert not env.is_credential_override(name="PATH")
    assert not env.is_credential_override(name="CLAUDECODEX")
    assert len(env.MANAGER_SERVICE_ACCOUNT_VARIABLES) == 6
    assert env.scrubbed_environment(environ={"HOME": "/root"}) == {"HOME": "/root"}


def test_each_role_pre_exec_failure_is_that_role_s_own_closed_object():
    _, _, launcher = _modules()

    assert launcher.pre_exec_failure_object(role_name="metadata-reader") == {
        "version": 1,
        "status": "unavailable",
    }
    assert launcher.pre_exec_failure_object(role_name="browser-control")["status"] == (
        "unavailable"
    )
    assert (
        launcher.pre_exec_failure_object(role_name="provider-observer", observer_mode="health")[
            "status"
        ]
        == "unavailable"
    )
    assert (
        launcher.pre_exec_failure_object(role_name="provider-observer", observer_mode="revalidate")[
            "status"
        ]
        == "inconclusive"
    )
    # Pre-exec, and therefore NOT the ambiguous target-write outcome.
    assert launcher.pre_exec_failure_object(role_name="final-provisioning") == {
        "version": 1,
        "status": "store-unavailable",
    }
    assert launcher.pre_exec_failure_object(role_name="target-status")["status"] == (
        "store-unavailable"
    )
