"""Acquisition prerequisites are checked inside the acquisition-reader role."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Protocol

from overseer._vendor.returns.result import Failure, Success

__all__: list[str] = []

_VAULT = "llm-provider-manager-acquisition"
_VARIABLE = "LPM_ACQUISITION_READER_OP_SERVICE_ACCOUNT_TOKEN"
_TOKEN = "isolated-acquisition-reader"
_PROVIDER = "anthropic"
_ACCOUNT = "acct-1"
_KIND = "claude-code-oauth"
_MACHINE = "a" * 64
_STATE = "/home/operator/.local/state/livespec-overseer/llm-provider-manager"


class _OpFixture(Protocol):
    executable: str

    def seed(
        self,
        *,
        items: list[dict[str, object]] | None = None,
        refuse: tuple[str, ...] = (),
        garble: tuple[str, ...] = (),
    ) -> None: ...

    def argvs(self) -> list[list[str]]: ...


def _namespace_fields() -> dict[str, str]:
    onepassword = importlib.import_module("_lpm_onepassword")
    return onepassword.namespace_item_fields(
        machine_id_sha256=_MACHINE,
        effective_uid=1000,
        manager_state=_STATE,
    )


def _namespace() -> dict[str, object]:
    onepassword = importlib.import_module("_lpm_onepassword")
    return {
        "id": "namespace-acquisition",
        "title": onepassword.NAMESPACE_ITEM_TITLE,
        "vault": _VAULT,
        "fields": _namespace_fields(),
    }


def _login_title(*, provider: str = _PROVIDER, account_id: str = _ACCOUNT) -> str:
    canonical = importlib.import_module("_lpm_canonical")
    return f"login-{canonical.length_prefixed_digest(values=(provider, account_id))}"


def _login(
    *,
    item_id: str = "login-1",
    provider: str = _PROVIDER,
    account_id: str = _ACCOUNT,
    identifier: str = "operator@example.test",
) -> dict[str, object]:
    return {
        "id": item_id,
        "title": _login_title(provider=provider, account_id=account_id),
        "vault": _VAULT,
        "fields": {
            "provider": provider,
            "account_id": account_id,
            "login_identifier": identifier,
            "login_secret": "never-return-this-password",
        },
    }


def _mailbox(*, authorization: str | None = None) -> dict[str, object]:
    value = authorization or json.dumps(
        {
            "version": 1,
            "client_id": "gmail-client",
            "client_secret": "never-return-this-client-secret",
            "refresh_token": "never-return-this-refresh-token",
            "token_uri": "https://oauth2.googleapis.com/token",
        },
        separators=(",", ":"),
    )
    return {
        "id": "gmail-1",
        "title": "gmail-primary",
        "vault": _VAULT,
        "fields": {
            "oauth_authorization": value,
            "oauth_scope": "https://www.googleapis.com/auth/gmail.readonly",
        },
    }


def _access(*, op_fixture: _OpFixture):
    op = importlib.import_module("_lpm_op")
    roles = importlib.import_module("_lpm_roles")
    vault = importlib.import_module("_lpm_op_vault")
    return vault.VaultAccess(
        runner=op.HostOpChild(
            environ={_VARIABLE: _TOKEN},
            variable=_VARIABLE,
            timeout_seconds=30.0,
        ),
        op_executable=op_fixture.executable,
        retained_executable=op_fixture.executable,
        role=roles.credential_role(name="acquisition-prerequisite"),
    )


def _checked(*, checker, op_fixture: _OpFixture) -> dict[str, object]:
    return checker.acquisition_prerequisite_result(
        access=_access(op_fixture=op_fixture),
        namespace=_namespace_fields(),
        provider=_PROVIDER,
        account_id=_ACCOUNT,
        kind=_KIND,
    )


def test_acquisition_prerequisite_role_closes_presence_and_ambiguity(
    op_fixture: _OpFixture,
) -> None:
    module_path = Path(__file__).parents[1] / "overseer" / "_lpm_acquisition_prerequisite.py"
    assert module_path.is_file(), "the acquisition prerequisite role must exist"
    checker = importlib.import_module("_lpm_acquisition_prerequisite")

    op_fixture.seed(items=[_namespace(), _login(), _mailbox()])
    present = _checked(checker=checker, op_fixture=op_fixture)
    assert present == {"version": 1, "status": "present"}
    assert "never-return" not in json.dumps(present)

    op_fixture.seed(items=[_namespace(), _mailbox()])
    assert _checked(checker=checker, op_fixture=op_fixture)["status"] == "absent"

    op_fixture.seed(items=[_namespace(), _login(), _login(item_id="login-duplicate"), _mailbox()])
    assert _checked(checker=checker, op_fixture=op_fixture)["status"] == "malformed"
    assert len(op_fixture.argvs()) == 2, "duplicates are not opened after enumeration"

    malformed_login = _login()
    malformed_login["fields"] = {"provider": _PROVIDER}
    op_fixture.seed(items=[_namespace(), malformed_login, _mailbox()])
    assert _checked(checker=checker, op_fixture=op_fixture)["status"] == "malformed"

    op_fixture.seed(
        items=[
            _namespace(),
            _login(),
            _login(item_id="login-2", account_id="acct-2"),
            _mailbox(),
        ]
    )
    assert _checked(checker=checker, op_fixture=op_fixture)["status"] == "malformed"

    op_fixture.seed(items=[_namespace(), _login(), _mailbox(authorization="{}")])
    assert _checked(checker=checker, op_fixture=op_fixture)["status"] == "malformed"

    op_fixture.seed(items=[_namespace(), _login(), _mailbox(), dict(_mailbox(), id="gmail-2")])
    assert _checked(checker=checker, op_fixture=op_fixture)["status"] == "malformed"

    op_fixture.seed(items=[_namespace(), _login(), _mailbox()], refuse=("item list",))
    assert _checked(checker=checker, op_fixture=op_fixture)["status"] == "unavailable"


def test_installed_role_service_routes_only_closed_acquisition_requests(
    monkeypatch,
) -> None:
    module_path = Path(__file__).parents[1] / "overseer" / "_lpm_role_acquisition_service.py"
    assert module_path.is_file(), "the installed role needs an acquisition service boundary"
    acquisition = importlib.import_module("_lpm_role_acquisition_service")
    context_module = importlib.import_module("_lpm_role_context")
    results = importlib.import_module("_lpm_results")
    service = importlib.import_module("_lpm_role_service")
    calls: list[dict[str, object]] = []
    access = object()

    def check(**request):
        calls.append(request)
        return {"version": 1, "status": "present"}

    monkeypatch.setattr(acquisition, "acquisition_prerequisite_result", check)
    monkeypatch.setattr(
        acquisition,
        "role_context",
        lambda: Success(
            context_module.RoleContext(
                state_dir=Path(_STATE),
                owner_uid=1000,
                machine_id_sha256=_MACHINE,
            )
        ),
    )
    monkeypatch.setattr(acquisition, "role_vault_access", lambda **_kwargs: access)
    request = {
        "version": 1,
        "provider": _PROVIDER,
        "account_id": _ACCOUNT,
        "kind": _KIND,
        "op_executable": "/usr/bin/op",
    }

    assert service.role_result(
        role_name="acquisition-prerequisite",
        request=request,
        environ={_VARIABLE: _TOKEN},
        lock_descriptor=None,
    ) == {"version": 1, "status": "present"}
    assert calls[0]["provider"] == _PROVIDER
    assert calls[0]["access"] is access

    malformed = service.role_result(
        role_name="acquisition-prerequisite",
        request={**request, "extra": True},
        environ={_VARIABLE: _TOKEN},
        lock_descriptor=None,
    )
    assert malformed == {"version": 1, "status": "unavailable"}
    assert len(calls) == 1

    monkeypatch.setattr(acquisition, "role_vault_access", lambda **_kwargs: None)
    unavailable = service.role_result(
        role_name="acquisition-prerequisite",
        request=request,
        environ={_VARIABLE: _TOKEN},
        lock_descriptor=None,
    )
    assert unavailable == {"version": 1, "status": "unavailable"}

    monkeypatch.setattr(
        acquisition,
        "role_context",
        lambda: Failure(results.store_unavailable(message="context unavailable")),
    )
    context_failure = service.role_result(
        role_name="acquisition-prerequisite",
        request=request,
        environ={_VARIABLE: _TOKEN},
        lock_descriptor=None,
    )
    assert context_failure == {"version": 1, "status": "unavailable"}
