"""Read Anthropic quota-reset grants with the account's existing OAuth token."""

from __future__ import annotations

from pathlib import Path
from typing import Final, Protocol

from caam_oauth_get import OAuthRequest, OAuthTransport, get_json
from caam_resets import ResetReading, parse_anthropic_resets
from caam_usage import live_token

__all__: list[str] = ["RESET_USAGE_URL", "ResetSource", "read_resets"]

RESET_USAGE_URL: Final = "https://api.anthropic.com/api/oauth/usage?at_wall=1"
_CLAUDE_CLIENT: Final = "claude-cli/2.1.296 (external, cli)"


class ResetSource(Protocol):
    def __call__(
        self, *, creds_path: Path, now: float | None = None
    ) -> tuple[ResetReading | None, str | None]: ...


def read_resets(
    *,
    creds_path: Path,
    now: float | None = None,
    transport: OAuthTransport | None = None,
) -> tuple[ResetReading | None, str | None]:
    """Read reset grants without refreshing the credential or retrying the request."""
    token, reason = live_token(path=creds_path, now=now)
    if token is None:
        return None, reason
    body, reason = get_json(
        request=OAuthRequest(
            url=RESET_USAGE_URL,
            headers={
                "Authorization": "Bearer " + token,
                "User-Agent": _CLAUDE_CLIENT,
            },
        ),
        transport=transport,
    )
    if body is None:
        return None, reason
    return parse_anthropic_resets(body=body), None
