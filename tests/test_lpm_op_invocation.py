"""The `op` child boundary: fixed vectors, one token, one vault, no shell.

SPECIFICATION/contracts.md puts four separate controls on the single external command this
backend is allowed to run, and they are only testable together because each one is about
the SAME child process.

ONE TOKEN. "Before spawning `op`, the role process MUST construct a child environment by
removing all six manager-named variables and every inherited `OP_*` variable, then set
exactly `OP_SERVICE_ACCOUNT_TOKEN` to the bytes from its one manager-named role variable.
The `op` child MUST receive no other `OP_*` or manager service-account variable."

ONE EXECUTABLE. "every registry role's complete external-executable allowlist is the one
retained canonical `op` path: each role MUST require its `op_executable` to equal that
retained canonical regular executable, invoke only that absolute path".

ONE VAULT PER ROW. The same sentence continues: "constrain the vault to its table row and
reject every other prefix."

CREATE ONLY. "MUST NOT use `op item edit`, delete a metadata revision or rely on 1Password
item-title uniqueness."

THE ASSERTIONS READ WHAT THE CHILD ACTUALLY GOT, not what the parent intended to send. A
test that checked the dict `op_child_environment` returned would pass just as happily if
the spawn then handed the child `os.environ` instead — which is the whole defect the
explicit `env=` exists to prevent. So the fixture `op` records its own environment and the
assertions below read that recording.
"""

from __future__ import annotations

import hashlib
import importlib
import pathlib

__all__: list[str] = []

_TOKEN = "fixture-op-service-account-token-4b1e"
_IMPOSTOR = "inherited-op-value-that-must-be-scrubbed"
_READER_VARIABLE = "LPM_METADATA_READER_OP_SERVICE_ACCOUNT_TOKEN"
_METADATA_VAULT = "llm-provider-manager-token-metadata"
_VALUES_VAULT = "llm-provider-manager-token-values"


def _op_module():
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_op.py"
    assert module_path.is_file(), "overseer/_lpm_op.py must exist"
    return importlib.import_module("_lpm_op")


def _role(*, name):
    return importlib.import_module("_lpm_roles").credential_role(name=name)


def _child(*, module, variable=_READER_VARIABLE, installed=True):
    """A production `op` child whose environment carries the impostor it must scrub.

    The inherited `OP_SERVICE_ACCOUNT_TOKEN` is the control: a scrub that merely ADDED the
    role's token would leave the impostor in place, and the digest below would catch it
    where an absence check could not. No `COVERAGE_PROCESS_START` is present, so the real
    Python child cannot self-instrument and race the suite's coverage data.

    `installed` says whether the launcher got as far as installing this role's own variable.
    It has to be separable from the NAME, or the absence case below would be handed an
    environment that still carries a token under the very name it claims is missing.
    """
    environ = {
        "PATH": "/usr/bin:/bin",
        "OP_SERVICE_ACCOUNT_TOKEN": _IMPOSTOR,
        "OP_FORMAT": _IMPOSTOR,
        "LPM_VALUE_READER_OP_SERVICE_ACCOUNT_TOKEN": _IMPOSTOR,
        "ANTHROPIC_API_KEY": _IMPOSTOR,
    }
    if installed:
        environ[variable] = _TOKEN
    return module.HostOpChild(environ=environ, variable=variable, timeout_seconds=30.0)


def test_the_three_argument_vectors_are_the_only_verbs_this_backend_knows():
    """List, get and create — and no mutation verb other than `item create`."""
    module = _op_module()
    onepassword = importlib.import_module("_lpm_onepassword")

    assert module.op_item_list_argv(op_executable="/usr/bin/op", vault=_METADATA_VAULT) == (
        "/usr/bin/op",
        "item",
        "list",
        "--vault",
        _METADATA_VAULT,
        "--format",
        "json",
    )
    # Addressed by ITEM ID, never by title: the contract forbids relying on 1Password
    # item-title uniqueness, and two physical revision items may legitimately share a
    # title. A get by title would have to choose between them.
    assert module.op_item_get_argv(
        op_executable="/usr/bin/op", vault=_METADATA_VAULT, item_id="fixture-1"
    ) == (
        "/usr/bin/op",
        "item",
        "get",
        "fixture-1",
        "--vault",
        _METADATA_VAULT,
        "--format",
        "json",
    )
    verbs = {
        vector[1:3]
        for vector in (
            module.op_item_list_argv(op_executable="/usr/bin/op", vault=_METADATA_VAULT),
            module.op_item_get_argv(
                op_executable="/usr/bin/op", vault=_METADATA_VAULT, item_id="fixture-1"
            ),
            onepassword.op_item_create_argv(op_executable="/usr/bin/op", vault=_VALUES_VAULT),
        )
    }
    assert verbs == {("item", "list"), ("item", "get"), ("item", "create")}


def test_the_child_environment_carries_exactly_this_role_s_one_token():
    """Every manager variable and every inherited `OP_*` is gone; one name replaces them."""
    module = _op_module()

    built = module.op_child_environment(
        environ={
            "PATH": "/usr/bin:/bin",
            _READER_VARIABLE: _TOKEN,
            "OP_SERVICE_ACCOUNT_TOKEN": _IMPOSTOR,
            "OP_CONNECT_HOST": _IMPOSTOR,
            "LPM_VALUE_READER_OP_SERVICE_ACCOUNT_TOKEN": _IMPOSTOR,
        },
        token=_TOKEN,
    )

    assert built["OP_SERVICE_ACCOUNT_TOKEN"] == _TOKEN
    assert sorted(name for name in built if name.startswith(("OP_", "LPM_"))) == [
        module.OP_SERVICE_ACCOUNT_VARIABLE
    ]
    assert built["PATH"] == "/usr/bin:/bin", "the scrub removes credentials, not the whole env"


def test_only_the_one_retained_canonical_path_is_an_acceptable_op_executable():
    """A supplied `op_executable` that is not the retained path is refused, not resolved."""
    module = _op_module()

    assert module.retained_executable_defect(supplied="/usr/bin/op", retained="/usr/bin/op") is None
    # A sibling install, a relative name, a trailing space and nothing at all. The near
    # misses matter most: a role that normalized or resolved them would be re-deciding a
    # question the manager already answered when it retained one canonical path.
    defects = {
        module.retained_executable_defect(supplied=supplied, retained="/usr/bin/op")
        for supplied in ("/usr/local/bin/op", "op", "/usr/bin/op ", "")
    }

    # ONE FIXED PHRASE FOR ALL FOUR, which is how this asserts the secret-free requirement
    # without guessing at substrings: a reason that varied with its input would collapse to
    # more than one member here, and a reason identical across four different inputs cannot
    # be carrying any of them. Testing `supplied not in defect` instead reads as the same
    # check and is not one — `"op"` is a substring of the word `op_executable`, so that
    # spelling fails against a diagnostic that quotes nothing at all.
    assert len(defects) == 1, "the diagnostic varies with the value it was handed"
    (defect,) = defects
    assert defect is not None and "/usr/local/bin/op" not in defect


def test_each_role_may_address_only_the_vaults_its_registry_row_scopes_it_to():
    """The vault constraint comes from the closed registry row, not from the caller."""
    module = _op_module()

    assert (
        module.vault_scope_defect(role=_role(name="metadata-reader"), vault=_METADATA_VAULT) is None
    )
    assert (
        module.vault_scope_defect(role=_role(name="metadata-reader"), vault=_VALUES_VAULT)
        is not None
    ), "the selection brain's reader must never address the values vault"
    assert (
        module.vault_scope_defect(role=_role(name="final-provisioning"), vault=_VALUES_VAULT)
        is None
    )
    assert (
        module.vault_scope_defect(role=_role(name="final-provisioning"), vault=_METADATA_VAULT)
        is not None
    )
    # Tokenless by construction, so it has no `op` scope at all and may address nothing.
    assert (
        module.vault_scope_defect(role=_role(name="target-status"), vault=_METADATA_VAULT)
        is not None
    )


def test_a_real_op_child_receives_the_fixed_vector_and_only_its_own_token(op_fixture):
    """The production child, spawned for real, asserted on what the child itself saw."""
    module = _op_module()
    op_fixture.seed(
        items=[
            {
                "id": "fixture-1",
                "title": "llm-provider-manager-namespace",
                "vault": _METADATA_VAULT,
                "fields": {"version": "1"},
            }
        ]
    )

    outcome = _child(module=module)(
        argv=module.op_item_list_argv(op_executable=op_fixture.executable, vault=_METADATA_VAULT),
        stdin_bytes=None,
    )

    assert outcome.exit_status == 0
    assert b"llm-provider-manager-namespace" in outcome.stdout
    (call,) = op_fixture.calls()
    assert call["argv"] == ["item", "list", "--vault", _METADATA_VAULT, "--format", "json"]
    assert call["credential_names"] == [
        module.OP_SERVICE_ACCOUNT_VARIABLE
    ], "the child inherited a credential variable the contract removes"
    assert (
        hashlib.sha256(call["token"].encode("utf-8")).hexdigest()
        == hashlib.sha256(_TOKEN.encode("utf-8")).hexdigest()
    )
    assert call["token"] != _IMPOSTOR, "the inherited impostor survived under the same name"


def test_a_refusing_op_child_reports_its_status_rather_than_an_empty_answer(op_fixture):
    """A non-zero `op` exit is the caller's signal that the outcome is UNKNOWN.

    Reported as a status rather than as an empty answer because an empty answer is how a
    backend outage comes to be read as authoritative absence — the one reading the contract
    forbids, since absence is what permits a genesis create.
    """
    module = _op_module()
    op_fixture.seed(refuse=("item list",))

    outcome = _child(module=module)(
        argv=module.op_item_list_argv(op_executable=op_fixture.executable, vault=_METADATA_VAULT),
        stdin_bytes=None,
    )

    assert outcome.exit_status != 0
    assert op_fixture.argvs() == [["item", "list", "--vault", _METADATA_VAULT, "--format", "json"]]


def test_an_unspawnable_child_and_a_missing_role_variable_are_both_non_zero(op_fixture):
    """Neither a failed spawn nor an absent token may raise, and neither spawns anything.

    The launcher installs exactly one manager-named variable before the exec, so its
    absence is a manager defect rather than a backend answer — but the role still owes its
    caller a closed result, and an exception here would become an abnormal role exit that
    the parent must map to a DIFFERENT, ambiguous outcome.
    """
    module = _op_module()

    missing = _child(module=module, variable=_READER_VARIABLE, installed=False)(
        argv=module.op_item_list_argv(op_executable=op_fixture.executable, vault=_METADATA_VAULT),
        stdin_bytes=None,
    )
    unspawnable = _child(module=module)(
        argv=module.op_item_list_argv(op_executable="/nonexistent/op", vault=_METADATA_VAULT),
        stdin_bytes=None,
    )

    assert missing.exit_status != 0
    assert unspawnable.exit_status != 0
    assert op_fixture.calls() == [], "nothing may be spawned without this role's own token"


def test_the_parent_deadline_terminates_an_op_child_that_outlives_it(op_fixture):
    """A bounded wait, because an `op` child holds a service-account token while it runs."""
    module = _op_module()
    op_fixture.seed()
    slow = pathlib.Path(op_fixture.executable).parent / "slow-op"
    slow.write_text("#!/bin/sh\nsleep 120\n", encoding="utf-8")
    slow.chmod(0o755)

    child = module.HostOpChild(
        environ={"PATH": "/usr/bin:/bin", _READER_VARIABLE: _TOKEN},
        variable=_READER_VARIABLE,
        timeout_seconds=1.0,
    )
    outcome = child(
        argv=module.op_item_list_argv(op_executable=str(slow), vault=_METADATA_VAULT),
        stdin_bytes=None,
    )

    assert outcome.exit_status != 0
    assert outcome.stdout == b"", "a partial answer is not a shorter answer"
