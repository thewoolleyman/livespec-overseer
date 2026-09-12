"""The signal-source axis: who may raise a lifecycle event, and what a report implies.

SPECIFICATION/contracts.md closes the consumer report's `classification` set to `authentication`,
`rate-limit`, `provider-outage` and `unknown`, and states each one's consequences separately: all
four release a live reporting-run lease; the first three transition a `valid` or `revalidating`
record to `suspect`; and only an authentication report that ACTUALLY makes that transition evicts
the metadata cache entry. Its redaction rule additionally admits a `diagnostic` only when it is at
most 1024 UTF-8 bytes, carries no ASCII control character and matches no registered provider-kind
token matcher.

THE FOUR CLASSIFICATIONS ARE A HANDLING TABLE, NOT A SEVERITY LADDER. `unknown` is not a
weaker `provider-outage`: it releases the lease and changes nothing else, deliberately,
because a consumer that cannot say what went wrong has given no evidence about the
credential. Ordering these by severity and deriving the consequences from the order is how
`unknown` starts suspecting credentials — the table is flat so that cannot happen.

THE SIGNAL SOURCE IS A SEPARATE AXIS FROM THE EVENT, and keeping it separate is what stops
a consumer from spending a lifecycle move that belongs to a worker. A consumer report may
raise exactly one event; provider validation, worker recovery, credential expiry and the
operator each own their own set, and together they PARTITION the lifecycle event set. A
caller therefore cannot reach `revalidation-succeeds` by relabelling a consumer report,
and a new event added to the lifecycle table with no source is visible as a hole rather
than as something any caller may raise.

REDACTION IS MECHANICAL AND FAILS CLOSED. It answers only "can this text be stored", never
"let me clean this up": a diagnostic carrying a credential literal is REFUSED, not stripped,
because a stripping rule that misses one spelling has published the credential while
reporting success.

THE MATCHERS ARE KEYED BY REGISTERED PROVIDER-AND-KIND ROW, and a repo test asserts the
table covers EVERY row in the provider registry. That pairing is what the contract's
"registered provider-kind token matcher" means operationally: a new credential kind cannot
ship without declaring what its values look like, because the coverage test goes red rather
than the new kind quietly gaining a diagnostic channel its own values pass through. The
table lives here rather than as a registry field because it is an input to REDACTION, not an
adapter the registry dispatches to, and every matcher is swept for every report — a report
names a `record_id`, and the consumer that wrote its text may hold credentials of several
kinds.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from _lpm_lifecycle import (
    INCONCLUSIVE_FINAL_EVENT,
    INCONCLUSIVE_RETRY_EVENT,
    REPORT_EVENT,
    REVALIDATION_STARTS_EVENT,
    REVALIDATION_SUCCEEDS_EVENT,
)

__all__: list[str] = [
    "AUTHENTICATION_CLASSIFICATION",
    "CLASSIFICATION_HANDLING",
    "EVENTS_BY_SIGNAL_SOURCE",
    "MAXIMUM_DIAGNOSTIC_BYTES",
    "REDACTION_MATCHERS_BY_ROW",
    "REPORT_CLASSIFICATIONS",
    "SIGNAL_SOURCES",
    "ClassificationHandling",
    "handling_for",
    "is_redacted_diagnostic",
    "source_may_raise",
]

AUTHENTICATION_CLASSIFICATION: Final = "authentication"

REDACTION_MATCHERS_BY_ROW: Final[dict[tuple[str, str], tuple[str, ...]]] = {
    ("anthropic", "claude-code-oauth"): ("sk-ant-",),
}

REPORT_CLASSIFICATIONS: Final = (
    AUTHENTICATION_CLASSIFICATION,
    "rate-limit",
    "provider-outage",
    "unknown",
)

MAXIMUM_DIAGNOSTIC_BYTES: Final = 1024

EVENTS_BY_SIGNAL_SOURCE: Final[dict[str, tuple[str, ...]]] = {
    "consumer-report": (REPORT_EVENT,),
    "provider-validation": (
        "acquisition-succeeds",
        "acquisition-fails",
        REVALIDATION_SUCCEEDS_EVENT,
        "revalidation-rejects",
        INCONCLUSIVE_RETRY_EVENT,
        INCONCLUSIVE_FINAL_EVENT,
    ),
    "worker-recovery": (
        "acquisition-worker-lost",
        "acquisition-fence-recovery",
        "revalidation-worker-lost",
        "revalidation-fence-recovery",
    ),
    "credential-expiry": ("credential-expires",),
    "operator": (
        "acquisition-starts",
        "operator-reacquires",
        "replacement-starts",
        REVALIDATION_STARTS_EVENT,
    ),
}

SIGNAL_SOURCES: Final = tuple(EVENTS_BY_SIGNAL_SOURCE)


@dataclass(frozen=True, kw_only=True)
class ClassificationHandling:
    """What one report classification does, stated as three independent consequences."""

    classification: str
    releases_lease: bool
    suspects_credential: bool
    evicts_cache_entry: bool


CLASSIFICATION_HANDLING: Final[dict[str, ClassificationHandling]] = {
    AUTHENTICATION_CLASSIFICATION: ClassificationHandling(
        classification=AUTHENTICATION_CLASSIFICATION,
        releases_lease=True,
        suspects_credential=True,
        evicts_cache_entry=True,
    ),
    "rate-limit": ClassificationHandling(
        classification="rate-limit",
        releases_lease=True,
        suspects_credential=True,
        evicts_cache_entry=False,
    ),
    "provider-outage": ClassificationHandling(
        classification="provider-outage",
        releases_lease=True,
        suspects_credential=True,
        evicts_cache_entry=False,
    ),
    "unknown": ClassificationHandling(
        classification="unknown",
        releases_lease=True,
        suspects_credential=False,
        evicts_cache_entry=False,
    ),
}


def handling_for(*, classification: str) -> ClassificationHandling | None:
    """This classification's handling row, or None when it is not one of the four."""
    return CLASSIFICATION_HANDLING.get(classification)


def source_may_raise(*, source: str, event: str) -> bool:
    """Whether `source` is a registered signal source permitted to raise `event`."""
    return event in EVENTS_BY_SIGNAL_SOURCE.get(source, ())


def is_redacted_diagnostic(*, diagnostic: str) -> bool:
    """Whether `diagnostic` satisfies every mechanical-redaction condition.

    All three conditions are checked; none is a sampling heuristic. The token check sweeps
    EVERY registered row rather than only the reported record's own row, because a report
    names a `record_id` and the text it carries was written by a consumer that may hold
    credentials of several kinds.
    """
    if len(diagnostic.encode("utf-8")) > MAXIMUM_DIAGNOSTIC_BYTES:
        return False
    if any(character < " " or character == "\x7f" for character in diagnostic):
        return False
    return not any(
        matcher in diagnostic
        for matchers in REDACTION_MATCHERS_BY_ROW.values()
        for matcher in matchers
    )
