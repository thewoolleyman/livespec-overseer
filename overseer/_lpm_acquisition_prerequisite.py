"""Closed acquisition-vault prerequisite classification for browser acquisition."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final, cast

from _lpm_canonical import length_prefixed_digest, parse_canonical_json
from _lpm_onepassword import ACQUISITION_VAULT
from _lpm_op_items import OpItem
from _lpm_op_vault import VaultAccess, namespace_bound_summaries

from overseer._vendor.returns.result import Failure

__all__: list[str] = [
    "acquisition_prerequisite_result",
]

_LOGIN_MEMBERS: Final = frozenset({"provider", "account_id", "login_identifier", "login_secret"})
_MAILBOX_MEMBERS: Final = frozenset({"oauth_authorization", "oauth_scope"})
_AUTHORIZATION_MEMBERS: Final = frozenset(
    {"version", "client_id", "client_secret", "refresh_token", "token_uri"}
)
_MAILBOX_TITLE: Final = "gmail-primary"
_MAILBOX_SCOPE: Final = "https://www.googleapis.com/auth/gmail.readonly"
_OAUTH_ENDPOINT: Final = "https://oauth2.googleapis.com/token"


def acquisition_prerequisite_result(
    *,
    access: VaultAccess,
    namespace: Mapping[str, str],
    provider: str,
    account_id: str,
    kind: str,
) -> dict[str, object]:
    """Classify the matching login and required mailbox without returning either."""
    _ = kind
    listed = namespace_bound_summaries(
        access=access,
        vault=ACQUISITION_VAULT,
        expected=namespace,
    )
    if isinstance(listed, Failure):
        return {"version": 1, "status": "unavailable"}
    summaries = listed.unwrap()
    login_title = f"login-{length_prefixed_digest(values=(provider, account_id))}"
    matching_login = tuple(item for item in summaries if item.title == login_title)
    matching_mailbox = tuple(item for item in summaries if item.title == _MAILBOX_TITLE)
    if len(matching_login) > 1 or len(matching_mailbox) > 1:
        return {"version": 1, "status": "malformed"}
    if len(matching_login) == 0 or len(matching_mailbox) == 0:
        return {"version": 1, "status": "absent"}
    login_items = tuple(item for item in summaries if item.title.startswith("login-"))
    read_items = (*login_items, *matching_mailbox)
    fields = {
        item.item_id: access.fields(vault=ACQUISITION_VAULT, item_id=item.item_id).value_or(None)
        for item in read_items
    }
    unavailable = any(value is None for value in fields.values())
    malformed = not _logins_valid(
        items=login_items,
        fields=fields,
        provider=provider,
        account_id=account_id,
    ) or not _mailbox_valid(items=matching_mailbox, fields=fields)
    status = {
        (False, False): "present",
        (False, True): "malformed",
        (True, False): "unavailable",
        (True, True): "unavailable",
    }[(unavailable, malformed)]
    return {"version": 1, "status": status}


def _logins_valid(
    *,
    items: tuple[OpItem, ...],
    fields: Mapping[str, dict[str, str] | None],
    provider: str,
    account_id: str,
) -> bool:
    valid = tuple(
        member
        for item in items
        if (member := fields[item.item_id]) is not None and _login_valid(item=item, fields=member)
    )
    matching = tuple(
        member
        for member in valid
        if member["provider"] == provider and member["account_id"] == account_id
    )
    identifiers = tuple(
        member["login_identifier"] for member in valid if member["provider"] == provider
    )
    return (
        len(valid) == len(items)
        and len(matching) == 1
        and len(set(identifiers)) == len(identifiers)
    )


def _login_valid(*, item: OpItem, fields: dict[str, str]) -> bool:
    values_are_present = all(value != "" for value in fields.values())
    provider = fields.get("provider", "")
    account_id = fields.get("account_id", "")
    expected_title = f"login-{length_prefixed_digest(values=(provider, account_id))}"
    return (
        frozenset(fields) == _LOGIN_MEMBERS and values_are_present and item.title == expected_title
    )


def _mailbox_valid(
    *,
    items: tuple[OpItem, ...],
    fields: Mapping[str, dict[str, str] | None],
) -> bool:
    member = fields[items[0].item_id]
    return member is not None and _mailbox_fields_valid(fields=member)


def _mailbox_fields_valid(*, fields: dict[str, str]) -> bool:
    authorization = fields.get("oauth_authorization", "")
    parsed = parse_canonical_json(text=authorization).value_or(None)
    return (
        frozenset(fields) == _MAILBOX_MEMBERS
        and fields.get("oauth_scope") == _MAILBOX_SCOPE
        and isinstance(parsed, dict)
        and _authorization_valid(members=cast("dict[str, object]", parsed))
    )


def _authorization_valid(*, members: dict[str, object]) -> bool:
    return (
        frozenset(members) == _AUTHORIZATION_MEMBERS
        and members.get("version") == 1
        and not isinstance(members.get("version"), bool)
        and members.get("token_uri") == _OAUTH_ENDPOINT
        and all(
            isinstance(members.get(name), str) and members.get(name) != ""
            for name in ("client_id", "client_secret", "refresh_token")
        )
    )
