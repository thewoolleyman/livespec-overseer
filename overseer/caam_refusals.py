"""Provider-agnostic refusal records, read out of tracked sessions' transcripts.

A refusal for a usage limit is GROUND TRUTH about an account's allowance, where
a usage percentage is a report about it: on 2026-10-13 the report read 45%
remaining nine minutes before the account refused every session on the host.
This module turns one provider's refusal records into the provider-agnostic
value the rest of the operation reasons with, and it sends NO request of its
own -- every fact it reports was written to disk by a session that had already
made the request.

WHAT IS MATCHED, AND WHY AGAINST THE RAW RECORD. The patterns below read the
record's own TEXT rather than a parsed envelope, for the same reason
``_caam_transcript_model`` reads a ``/model`` answer that way: the text is the
provider's, while the JSON shape around it is the harness's and is free to move
between releases. Two things are required together, and the conjunction is what
keeps a transcript that merely DISCUSSES a rate limit -- which the sessions this
operation watches do constantly -- from being read as having hit one: an API
ERROR MARKER, and a usage-limit PHRASE.

THE MARKER IS STRUCTURAL AND THE PHRASE IS NOT, and that asymmetry is the
conjunction. A phrase is the provider's prose and a session can write any of it
on purpose; only the ENVELOPE's own error keys say a request actually failed, so
the marker is matched against JSON structure (``"isApiErrorMessage": true``,
``"type": "error"``) and never against a word a sentence could carry. A provider
error TYPE such as ``rate_limit_error`` names the window on the phrase side and
is NOT a marker on its own -- a real rate-limit envelope carries ``"type":
"error"`` around it -- because a session discussing this very module would
otherwise be read as having been refused by it.

THE RESET A REFUSAL REPORTS is taken from the error's own epoch
(``… limit reached|1760568600``) or, for a rate limit, from the time the record
was written plus its retry-after interval, per the ratified clause that reads a
rate limit as a short-window refusal. Anything else -- including the TUI's
wall-clock phrasing, ``resets 3:30am (Europe/Berlin)``, whose instant cannot be
resolved without a host time-zone database this reader deliberately does not
depend on -- is read as a refusal that reported NO reset. That is the
conservative direction: such a refusal holds its account until a later reading
of the named window shows it actually replenished, which outlasts any reset a
guess would have produced.

A record this reader cannot parse contributes NO refusal rather than a guessed
one, and a record carrying no time of its own contributes none either:
attribution turns on WHEN a refusal was recorded, so an invented instant would
be attributed to whichever account happened to be active.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from caam_decision import resets_at

__all__: list[str] = [
    "PROVIDER_ANTHROPIC",
    "WINDOW_FIVE_HOUR",
    "WINDOW_SEVEN_DAY",
    "Refusal",
    "RefusalReader",
    "TrackedSession",
    "TrackedSessionSource",
    "session_refusals",
    "window_label",
]

PROVIDER_ANTHROPIC: Final = "anthropic"
WINDOW_FIVE_HOUR: Final = "five_hour"
WINDOW_SEVEN_DAY: Final = "seven_day"

_WINDOW_LABELS: Final = {
    WINDOW_FIVE_HOUR: "5-hour window",
    WINDOW_SEVEN_DAY: "weekly window",
}

# The tail bound the model read uses, for the same reason: a transcript is a
# whole session and a refusal older than this tail is older than any activation
# a pass can attribute against.
_TAIL_BYTES: Final = 65_536

_ERROR_MARKER_RE: Final = re.compile(
    r'"isApiErrorMessage"\s*:\s*true|"type"\s*:\s*"error"',
    re.IGNORECASE,
)
_WEEKLY_LIMIT_RE: Final = re.compile(
    r"weekly limit reached|hit your weekly limit|weekly usage limit",
    re.IGNORECASE,
)
_SHORT_WINDOW_LIMIT_RE: Final = re.compile(
    r"usage limit reached|hit your session limit|hit your usage limit|"
    r"rate_limit_error|rate limit exceeded",
    re.IGNORECASE,
)
_TIMESTAMP_RE: Final = re.compile(r'"timestamp"\s*:\s*"([^"]+)"')
_EPOCH_RESET_RE: Final = re.compile(r"limit reached\|(\d{9,11})")
_RETRY_AFTER_RE: Final = re.compile(r"retry[-_ ]after\D{0,4}(\d{1,6})", re.IGNORECASE)
_ACCOUNT_RE: Final = re.compile(r'"accountUuid"\s*:\s*"([^"]+)"')


@dataclass(frozen=True, kw_only=True)
class Refusal:
    """One provider refusal, in the terms every provider's refusals share.

    ``resets_at`` is None where the provider reported no reset, which is a
    different fact from a reset that has already passed and is kept distinct:
    the hold rules read the two completely differently. ``account`` is None
    where the record named no account identity, which is the usual case.
    """

    recorded_at: float
    window: str
    resets_at: float | None
    account: str | None = None


@dataclass(frozen=True, kw_only=True)
class TrackedSession:
    """A session whose transcript the operation may read refusals from.

    ``config_dir`` is the session's AGENT CONFIGURATION DIRECTORY, and it is the
    whole discriminator for which credential that session authenticates with:
    the host's default directory holds the live credential, while the
    refresh-maintenance sandbox and any separately provisioned credential have
    directories of their own, whose refusals belong to other accounts.
    """

    session_id: str
    config_dir: Path
    provider: str = PROVIDER_ANTHROPIC


class RefusalReader(Protocol):
    def __call__(self, *, session: TrackedSession) -> tuple[Refusal, ...]: ...


class TrackedSessionSource(Protocol):
    """Where a pass gets its tracked sessions: discovery in production, a seam in a test.

    Production walks tmux and `/proc` for them, which is a host read a scenario
    cannot usefully fake; the seam is what lets one be stated instead.
    """

    def __call__(self, *, home: Path) -> tuple[TrackedSession, ...]: ...


def window_label(*, window: str) -> str:
    """The operator-facing name of one allowance window."""
    return _WINDOW_LABELS[window]


def session_refusals(*, session: TrackedSession) -> tuple[Refusal, ...]:
    """Every usage-limit refusal the session's own transcript carries.

    A provider this reader has no parser for contributes nothing, per the
    ratified rule that an unparseable provider MUST contribute no refusals
    rather than a guessed one.
    """
    if session.provider != PROVIDER_ANTHROPIC:
        return ()
    return tuple(
        refusal
        for line in _transcript_tail(session=session)
        for refusal in _line_refusals(line=line)
    )


def _transcript_tail(*, session: TrackedSession) -> tuple[str, ...]:
    for path in sorted((session.config_dir / "projects").glob(f"*/{session.session_id}.jsonl")):
        return _read_tail(path=path)
    return ()


def _read_tail(*, path: Path) -> tuple[str, ...]:
    try:
        with path.open("rb") as handle:
            _ = handle.seek(0, os.SEEK_END)
            end = handle.tell()
            _ = handle.seek(max(0, end - _TAIL_BYTES))
            raw = handle.read()
    except OSError:
        return ()
    lines = raw.decode(errors="replace").splitlines()
    # A tail that began mid-record carries a leading fragment, which is dropped:
    # half a record can match a phrase while its own timestamp sits above the cut.
    return tuple(lines if end <= _TAIL_BYTES else lines[1:])


def _line_refusals(*, line: str) -> tuple[Refusal, ...]:
    if _ERROR_MARKER_RE.search(line) is None:
        return ()
    window = _refused_window(line=line)
    recorded_at = _recorded_at(line=line)
    if window is None or recorded_at is None:
        return ()
    account = _ACCOUNT_RE.search(line)
    return (
        Refusal(
            recorded_at=recorded_at,
            window=window,
            resets_at=_reported_reset(line=line, recorded_at=recorded_at),
            account=None if account is None else account.group(1),
        ),
    )


def _refused_window(*, line: str) -> str | None:
    if _WEEKLY_LIMIT_RE.search(line) is not None:
        return WINDOW_SEVEN_DAY
    if _SHORT_WINDOW_LIMIT_RE.search(line) is not None:
        return WINDOW_FIVE_HOUR
    return None


def _recorded_at(*, line: str) -> float | None:
    match = _TIMESTAMP_RE.search(line)
    if match is None:
        return None
    at = resets_at(timestamp=match.group(1))
    return None if at == float("inf") else at


def _reported_reset(*, line: str, recorded_at: float) -> float | None:
    epoch = _EPOCH_RESET_RE.search(line)
    if epoch is not None:
        return float(epoch.group(1))
    retry_after = _RETRY_AFTER_RE.search(line)
    if retry_after is not None:
        return recorded_at + float(retry_after.group(1))
    return None
