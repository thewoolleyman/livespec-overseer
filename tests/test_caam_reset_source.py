"""Anthropic quota-reset observation boundary."""

from __future__ import annotations

import importlib
from pathlib import Path

__all__: list[str] = []


def test_reset_observation_uses_the_quota_credential_and_claude_client_identity(
    *, tmp_path: Path
) -> None:
    """The reset-aware usage read carries both provider-required request details."""
    module_path = Path(__file__).resolve().parents[1] / "overseer" / "caam_reset_source.py"
    assert module_path.is_file()
    module = importlib.import_module("caam_reset_source")
    credentials = tmp_path / "credentials.json"
    credentials.write_text(
        '{"claudeAiOauth":{"accessToken":"token","expiresAt":2000000000000}}',
        encoding="utf-8",
    )
    seen: list[object] = []

    class Response:
        def __enter__(self) -> Response:
            return self

        def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
            return False

        def read(self, *, size: int = -1) -> bytes:
            del size
            return b'{"cedar_ember":{"eligible":true,"grants":[]}}'

    def transport(*, request, timeout: float) -> Response:
        del timeout
        seen.append(request)
        return Response()

    reading, reason = module.read_resets(
        creds_path=credentials,
        now=1_800_000_000.0,
        transport=transport,
    )

    assert reason is None
    assert reading.unreadable_reason is None
    request = seen[0]
    assert request.url.endswith("/api/oauth/usage?at_wall=1")
    assert request.headers["User-Agent"].startswith("claude-cli/")
    assert request.headers["Authorization"] == "Bearer token"


def test_reset_observation_does_not_send_an_expired_credential(*, tmp_path: Path) -> None:
    """An expired snapshot remains unreadable instead of being sent to the provider."""
    module = importlib.import_module("caam_reset_source")
    credentials = tmp_path / "credentials.json"
    credentials.write_text(
        '{"claudeAiOauth":{"accessToken":"token","expiresAt":1}}', encoding="utf-8"
    )

    reading, reason = module.read_resets(creds_path=credentials, now=1_800_000_000.0)

    assert reading is None
    assert reason is not None and reason.startswith("token expired")


def test_reset_observation_reports_a_transport_failure(*, tmp_path: Path) -> None:
    """A failed reset read leaves the quota pass operational and names the reason."""
    module = importlib.import_module("caam_reset_source")
    credentials = tmp_path / "credentials.json"
    credentials.write_text(
        '{"claudeAiOauth":{"accessToken":"token","expiresAt":2000000000000}}',
        encoding="utf-8",
    )

    def transport(*, request, timeout: float) -> object:
        del request, timeout
        raise OSError("offline")

    reading, reason = module.read_resets(
        creds_path=credentials,
        now=1_800_000_000.0,
        transport=transport,
    )

    assert reading is None
    assert reason == "OSError: offline"
