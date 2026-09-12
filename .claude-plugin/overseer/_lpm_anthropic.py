"""The initial Anthropic validation adapter: one bounded Messages probe, three outcomes.

SPECIFICATION/contracts.md fixes the wire contract exactly — one HTTPS `POST` to
`https://api.anthropic.com/v1/messages` carrying `Authorization: Bearer <credential>`,
`anthropic-beta: oauth-2025-04-20`, `anthropic-version: 2023-06-01` and
`content-type: application/json`, with the UTF-8 JSON body
`{"model":"claude-haiku-4-5-20251001","max_tokens":1,"messages":[{"role":"user","content":"hi"}]}`
— and SPECIFICATION/spec.md fixes the outcome vocabulary at exactly three words: definitive
success, definitive credential rejection, and inconclusive.

THE THREE OUTCOMES ARE NOT A SUCCESS BOOLEAN WITH A DIAGNOSTIC. Rate limiting, provider
outage, transport failure and probe deadline all mean the manager LEARNED NOTHING about the
credential, and the spec requires them to be inconclusive rather than rejection. Collapsing
them into "not valid" would walk a perfectly good credential through `suspect` toward `dead`
every time Anthropic returned a 529, which is the failure this vocabulary exists to prevent.
Only `401` and `403` are the provider telling us the credential itself is refused.

THE PROBE IS INJECTED, AND THAT IS A CONTRACT BOUNDARY RATHER THAN A TEST AFFORDANCE.
spec.md forbids the manager from proxying, relaying or rewriting inference traffic or
entering the inference request path at all. This module therefore DESCRIBES the one request
and CLASSIFIES one response; it opens no socket, imports no transport, and holds no client.
A caller supplies the transport, which keeps the single outbound call this manager is
permitted to make visible at the boundary instead of buried in a module that could grow a
second one.

`ProbeResponse` CARRIES A PARSED BODY, NOT BYTES. Every row of the mapping table below asks
a structural question about an already-decoded object; a malformed body is simply a body
that fails those questions, and it maps to inconclusive by the table's own default. Decoding
belongs to the transport the caller injects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Protocol, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "DEFINITIVE_REJECTION",
    "DEFINITIVE_SUCCESS",
    "INCONCLUSIVE",
    "INFERENCE_CAPABLE_OUTCOME",
    "VALIDATION_ADAPTER",
    "VALIDATION_API_VERSION",
    "VALIDATION_BETA",
    "VALIDATION_BODY",
    "VALIDATION_ENDPOINT",
    "VALIDATION_MODEL",
    "VALIDATION_OUTCOMES",
    "ProbeRequest",
    "ProbeResponse",
    "ValidationProbe",
    "probe_request",
    "validate_credential",
    "validation_outcome",
]

VALIDATION_ADAPTER: Final = "anthropic-messages-probe"

VALIDATION_ENDPOINT: Final = "https://api.anthropic.com/v1/messages"
VALIDATION_MODEL: Final = "claude-haiku-4-5-20251001"
VALIDATION_BETA: Final = "oauth-2025-04-20"
VALIDATION_API_VERSION: Final = "2023-06-01"
VALIDATION_BODY: Final = (
    '{"model":"claude-haiku-4-5-20251001","max_tokens":1,'
    '"messages":[{"role":"user","content":"hi"}]}'
)

DEFINITIVE_SUCCESS: Final = "definitive-success"
DEFINITIVE_REJECTION: Final = "definitive-credential-rejection"
INCONCLUSIVE: Final = "inconclusive"

VALIDATION_OUTCOMES: Final = (DEFINITIVE_SUCCESS, DEFINITIVE_REJECTION, INCONCLUSIVE)

# The one outcome that establishes the credential can actually reach inference. Named
# because callers ask exactly this question and a bare string comparison against
# `DEFINITIVE_SUCCESS` reads as an implementation detail of the table rather than as the
# question being asked.
INFERENCE_CAPABLE_OUTCOME: Final = DEFINITIVE_SUCCESS

_SUCCESS_STATUS: Final = 200
_REJECTION_STATUSES: Final = (401, 403)


@dataclass(frozen=True, kw_only=True)
class ProbeRequest:
    """The exact one request the adapter is permitted to make, ready for a transport."""

    method: str
    url: str
    headers: tuple[tuple[str, str], ...]
    body: str


@dataclass(frozen=True, kw_only=True)
class ProbeResponse:
    """One probe result: an HTTP status and parsed body, or a transport-level miss.

    `reached` is False for a transport failure or an expired probe deadline — the two
    cases where there is no status to classify at all. It is a separate field rather than
    a sentinel status so no real status code can ever be mistaken for "we never asked".
    """

    reached: bool
    status: int = 0
    body: object = None


class ValidationProbe(Protocol):
    """The injected transport that performs the one bounded Messages request."""

    def __call__(self, *, request: ProbeRequest) -> ProbeResponse:
        """Send `request` within the caller's probe deadline and report what came back."""
        ...


def probe_request(*, credential: str) -> ProbeRequest:
    """Build the exact validation request for one credential.

    The credential rides in the `Authorization` header because the provider requires it
    there; nothing in this module logs, stores, digests or returns that header, and the
    request object exists only to be handed straight to the injected transport.
    """
    return ProbeRequest(
        method="POST",
        url=VALIDATION_ENDPOINT,
        headers=(
            ("Authorization", f"Bearer {credential}"),
            ("anthropic-beta", VALIDATION_BETA),
            ("anthropic-version", VALIDATION_API_VERSION),
            ("content-type", "application/json"),
        ),
        body=VALIDATION_BODY,
    )


def validation_outcome(*, response: ProbeResponse) -> str:
    """Map one probe response onto the three-word outcome vocabulary.

    The table is closed and its DEFAULT is inconclusive: every row that is not an
    explicitly successful message or an explicit credential refusal — including any
    unexpected status and any malformed body — falls through to "we learned nothing".
    """
    if not response.reached:
        return INCONCLUSIVE
    if response.status in _REJECTION_STATUSES:
        return DEFINITIVE_REJECTION
    if response.status == _SUCCESS_STATUS and _is_message_body(body=response.body):
        return DEFINITIVE_SUCCESS
    return INCONCLUSIVE


def validate_credential(*, credential: str, probe: ValidationProbe) -> str:
    """Run the one bounded probe for `credential` and return its validation outcome."""
    return validation_outcome(response=probe(request=probe_request(credential=credential)))


def _is_message_body(*, body: object) -> bool:
    if not isinstance(body, dict):
        return False
    source = cast("dict[str, object]", body)
    identifier = source.get("id")
    if not isinstance(identifier, str) or identifier == "":
        return False
    if source.get("type") != "message" or source.get("role") != "assistant":
        return False
    return _has_token_counts(usage=source.get("usage"))


def _has_token_counts(*, usage: object) -> bool:
    if not isinstance(usage, dict):
        return False
    counts = cast("dict[str, object]", usage)
    for member in ("input_tokens", "output_tokens"):
        value = counts.get(member)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return False
    return True
