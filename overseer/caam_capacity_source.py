"""The Anthropic capacity source: one read-only profile read, per account, per pass.

`GET https://api.anthropic.com/api/oauth/profile` with the account's own OAuth
access token and the `anthropic-beta: oauth-2025-04-20` header answers with
`organization.rate_limit_tier` -- the provider's own SERVER-SIDE record of the
plan the account is on right now.

WHY NOT THE STORED CREDENTIAL. A vault snapshot carries `claudeAiOauth`
`subscriptionType` and `rateLimitTier`, which are written at LOGIN and never
again. Measured 2026-10-13 on host hp: an account downgraded from $200 to $20
went on reporting `max` / `default_claude_max_20x` in its snapshot while the
loop's own usage readings showed the downgrade plainly. Those fields are
therefore not a source for a CURRENT plan at all, and this module reads none of
them.

IT SENDS EXACTLY ONE REQUEST, and the **Never refresh** rule is why. A
locally-expired token is skipped rather than sent, because the provider backs
off a specific repeatedly-rejected token; and the OAuth token endpoint is never
invoked, because rotating a refresh token outside the agent's own control can
revoke the whole token family. The one GET goes through `caam_usage.get_json`,
the same transport the usage poll uses, so neither read can acquire a retry the
other does not have.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import jsonio
from caam_oauth_get import OAuthRequest, OAuthTransport, get_json
from caam_usage import live_token

__all__: list[str] = [
    "OAUTH_BETA_HEADER",
    "PROFILE_URL",
    "read_rate_limit_tier",
]

PROFILE_URL: Final = "https://api.anthropic.com/api/oauth/profile"
OAUTH_BETA_HEADER: Final = "oauth-2025-04-20"
_UNREADABLE = "unexpected response shape"


def read_rate_limit_tier(
    *,
    creds_path: Path,
    now: float | None = None,
    transport: OAuthTransport | None = None,
) -> tuple[str | None, str | None]:
    """Return (rate_limit_tier, None) or (None, reason). Never raises.

    The reason is carried back rather than reported: an unknown class must not
    on its own fail the pass, so every caller turns a reason into `unknown`
    rather than into an exit code.
    """

    token, why = live_token(path=creds_path, now=now)
    if token is None:
        return None, why

    body, why = get_json(
        request=OAuthRequest(
            url=PROFILE_URL,
            headers={
                "Authorization": "Bearer " + token,
                "anthropic-beta": OAUTH_BETA_HEADER,
            },
        ),
        transport=transport,
    )
    if body is None:
        return None, why

    organization = jsonio.as_object(value=body.get("organization"))
    tier = None if organization is None else organization.get("rate_limit_tier")
    if not isinstance(tier, str) or not tier:
        return None, _UNREADABLE
    return tier, None
