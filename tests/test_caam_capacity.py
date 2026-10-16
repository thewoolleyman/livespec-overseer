"""An account's capacity class, and the one live read it is determined from.

SPECIFICATION v056 -- spec.md section "Account rotation and quota supervision",
paragraph **Each account's capacity class MUST be observed live and reported**,
and contracts.md section "The account-rotation operation", paragraph **Capacity
class source**.

The three capacity-reporting SCENARIOS are driven through the shipped rotation
pass in `tests/integration/test_caam_capacity_reporting.py`. This file owns the
two units that pass composes, because neither is observable from a rendered
table: the provider-agnostic MAPPING onto the four classes, and the single
read-only request the Anthropic source is permitted to send.

WHY THE REQUEST COUNT IS ASSERTED RATHER THAN ASSUMED. The capacity source runs
once per account on every pass, so a second request hidden inside it -- a token
refresh, a retry, an organization lookup -- would multiply across the whole
vault and, in the refresh case, could revoke a whole token family. "It MUST NOT
itself invoke the OAuth token endpoint under any circumstance" is the rule the
recording transport below exists to hold to one GET.
"""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

__all__: list[str] = []

PROFILE_URL = "https://api.anthropic.com/api/oauth/profile"
OAUTH_BETA = "oauth-2025-04-20"


def capacity_module() -> ModuleType:
    return importlib.import_module("caam_capacity")


def source_module() -> ModuleType:
    return importlib.import_module("caam_capacity_source")


def write_creds(*, path: Path, bearer: str, expires_at_ms: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(
        json.dumps({"claudeAiOauth": {"accessToken": bearer, "expiresAt": expires_at_ms}}),
        encoding="utf-8",
    )


class _Body:
    """One response body, in the context-manager shape the transport seam returns."""

    def __init__(self, *, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> _Body:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


@dataclass(kw_only=True)
class _RecordingTransport:
    """Every request the source sent, with the body it was answered with."""

    body: bytes = b"{}"
    boom: bool = False
    calls: list[tuple[str, dict[str, str]]] = field(default_factory=list)

    def __call__(self, *, request: object, timeout: float) -> _Body:
        del timeout
        url = getattr(request, "url", "")
        headers = getattr(request, "headers", {})
        self.calls.append((url, dict(headers)))
        if self.boom:
            raise OSError("boom")
        return _Body(body=self.body)


def _profile_body(*, tier: object) -> bytes:
    return json.dumps({"organization": {"rate_limit_tier": tier}}).encode()


def test_the_anthropic_tiers_map_onto_the_three_named_classes() -> None:
    """The mapping contracts.md states, in the direction it states it."""
    module = capacity_module()

    assert module.capacity_of(tier="default_claude_ai").capacity_class == "small"
    assert module.capacity_of(tier="default_claude_max_5x").capacity_class == "medium"
    assert module.capacity_of(tier="default_claude_max_20x").capacity_class == "large"


def test_every_mapped_class_keeps_the_providers_own_plan_name_as_detail() -> None:
    """The class is provider-agnostic; the plan name is the provider's own word for it.

    An operator reading `large` cannot tell which plan produced it, which is
    exactly what the detail is for -- and it is the field the host-side proof of
    a plan change is read from.
    """
    module = capacity_module()

    assert module.capacity_of(tier="default_claude_max_20x").plan_name == "default_claude_max_20x"
    assert module.capacity_of(tier="default_claude_ai").plan_name == "default_claude_ai"


def test_a_plan_name_with_no_mapping_is_unknown_and_still_shows_what_was_read() -> None:
    """Any other value maps to `unknown`, and the provider value is still shown.

    Both halves matter. Falling back to a guessed class would weight a candidate
    on a plan nobody has measured; dropping the value would leave an operator
    with no way to tell an unmapped plan from an unreadable one.
    """
    module = capacity_module()

    unmapped = module.capacity_of(tier="default_claude_team_7x")

    assert unmapped.capacity_class == "unknown"
    assert unmapped.plan_name == "default_claude_team_7x"


def test_no_plan_name_at_all_is_unknown_with_no_detail_to_show() -> None:
    """A read that produced nothing has no provider value to report, and invents none."""
    module = capacity_module()

    unread = module.capacity_of(tier=None)

    assert unread.capacity_class == "unknown"
    assert unread.plan_name is None


def test_the_table_cell_carries_the_class_and_its_detail_together() -> None:
    """The one cell the account table shows per row, in all three shapes it takes."""
    module = capacity_module()

    assert (
        module.capacity_cell(capacity=module.capacity_of(tier="default_claude_max_20x"))
        == "large (default_claude_max_20x)"
    )
    assert module.capacity_cell(capacity=module.capacity_of(tier=None)) == "unknown"
    assert module.capacity_cell(capacity=None) == "unknown"


def test_the_live_read_is_one_read_only_get_of_the_profile_endpoint(*, tmp_path: Path) -> None:
    """THE REQUEST CONTRACT: one GET, that URL, that header, that account's token."""
    module = source_module()
    creds = tmp_path / ".credentials.json"
    write_creds(path=creds, bearer="account-token", expires_at_ms=9_000_000)
    transport = _RecordingTransport(body=_profile_body(tier="default_claude_max_5x"))

    tier, why = module.read_rate_limit_tier(creds_path=creds, now=1_000.0, transport=transport)

    assert (tier, why) == ("default_claude_max_5x", None)
    assert transport.calls == [
        (
            PROFILE_URL,
            {"Authorization": "Bearer account-token", "anthropic-beta": OAUTH_BETA},
        )
    ]


def test_a_locally_expired_token_is_skipped_rather_than_sent(*, tmp_path: Path) -> None:
    """The **Never refresh** rule's other half, which this source is subject to.

    The usage endpoint backs off a specific repeatedly-rejected token, so a
    capacity read that sent a dead token would manufacture the error it then
    reported -- and would do it once per account per pass.
    """
    module = source_module()
    creds = tmp_path / ".credentials.json"
    write_creds(path=creds, bearer="stale", expires_at_ms=3_600_000)
    transport = _RecordingTransport()

    tier, why = module.read_rate_limit_tier(creds_path=creds, now=7_200.0, transport=transport)

    assert tier is None
    assert why is not None
    assert "expired" in why
    assert transport.calls == []


def test_a_failed_read_names_its_failure_and_yields_no_plan(*, tmp_path: Path) -> None:
    module = source_module()
    creds = tmp_path / ".credentials.json"
    write_creds(path=creds, bearer="account-token", expires_at_ms=9_000_000)

    tier, why = module.read_rate_limit_tier(
        creds_path=creds, now=1_000.0, transport=_RecordingTransport(boom=True)
    )

    assert tier is None
    assert why == "OSError: boom"


def test_a_response_that_states_no_rate_limit_tier_is_unreadable(*, tmp_path: Path) -> None:
    """Both shapes of "the answer does not carry one": no organization, and no tier in it."""
    module = source_module()
    creds = tmp_path / ".credentials.json"
    write_creds(path=creds, bearer="account-token", expires_at_ms=9_000_000)

    for body in (b"{}", b'{"organization": {}}', _profile_body(tier=7)):
        tier, why = module.read_rate_limit_tier(
            creds_path=creds, now=1_000.0, transport=_RecordingTransport(body=body)
        )

        assert tier is None, body
        assert why == "unexpected response shape", body
