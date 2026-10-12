"""Fail-closed acquisition observation sanitization and opaque token provenance."""

from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass, field
from typing import Protocol

from _lpm_canonical import canonical_json_bytes

__all__: list[str] = [
    "ObservationOutcome",
    "ObservationSanitizer",
]

_ANTHROPIC_OAT_MARKER = "sk-ant-oat01-"
_TOKEN = re.compile(r"sk-ant-oat01-[A-Za-z0-9_-]+")
_TOKEN_AT_END = re.compile(r"sk-ant-oat01-[A-Za-z0-9_-]*\Z")
_REDACTED_TOKEN_MARKER = re.compile(r"\[\[redacted-token:[^\[\]\r\n]+\]\]")
_REDACTED_TOKEN_MARKER_AT_END = re.compile(r"\[\[redacted-token:[^\]\r\n]*\]?\Z")
_TOKEN_PREFIXES = tuple(
    _ANTHROPIC_OAT_MARKER[:length] for length in range(1, len(_ANTHROPIC_OAT_MARKER) + 1)
)
_REDACTED_TOKEN_MARKER_PREFIXES = tuple(
    "[[redacted-token:"[:length] for length in range(1, len("[[redacted-token:") + 1)
)


class _TokenHandleFactory(Protocol):
    def __call__(self, *, value: str) -> str: ...


@dataclass(frozen=True, kw_only=True)
class ObservationOutcome:
    """One closed observation result and service-private fingerprint state."""

    response: dict[str, object]
    fingerprint: str | None
    stop_reason: str | None


@dataclass(kw_only=True)
class _StreamState:
    cumulative: str = ""
    released: int = 0


@dataclass(kw_only=True)
class ObservationSanitizer:
    """Sanitize fields before constructing any browser or terminal response."""

    token_handles: dict[str, str]
    sensitive_values: frozenset[str]
    new_token_handle: _TokenHandleFactory
    _fingerprint: str | None = field(default=None, init=False, repr=False)
    _stdout: _StreamState = field(default_factory=_StreamState, init=False, repr=False)
    _stderr: _StreamState = field(default_factory=_StreamState, init=False, repr=False)
    _dynamic_handles: dict[str, str] = field(default_factory=dict, init=False, repr=False)

    def browser_observation(
        self,
        *,
        url: str,
        title: str,
        dom_text: str,
        accessibility_tree: str,
        masked_screenshot_png: bytes,
        masking_established: bool,
    ) -> ObservationOutcome:
        """Return a sanitized browser observation, or no observation fields at all."""
        if not masking_established:
            return self._unavailable()
        fields: dict[str, object] = {
            "version": 1,
            "status": "ok",
            "url": self._sanitize(text=url),
            "title": self._sanitize(text=title),
            "dom_text": self._sanitize(text=dom_text),
            "accessibility_tree": self._sanitize(text=accessibility_tree),
            "screenshot_png": base64.b64encode(masked_screenshot_png).decode("ascii"),
        }
        fingerprint_source = {
            **fields,
            "screenshot_png": hashlib.sha256(masked_screenshot_png).hexdigest(),
        }
        self._fingerprint = hashlib.sha256(
            canonical_json_bytes(value=fingerprint_source).unwrap()
        ).hexdigest()
        fields["state_fingerprint"] = self._fingerprint
        return ObservationOutcome(response=fields, fingerprint=self._fingerprint, stop_reason=None)

    def terminal_observation(
        self,
        *,
        running: bool,
        exit_status: int | None,
        stdout: str,
        stderr: str,
    ) -> ObservationOutcome:
        """Release only the newly safe suffix of each cumulative terminal stream."""
        stdout_piece = self._advance(stream=self._stdout, text=stdout, running=running)
        stderr_piece = self._advance(stream=self._stderr, text=stderr, running=running)
        if stdout_piece is None or stderr_piece is None:
            return self._unavailable()
        fingerprint_source: dict[str, object] = {
            "running": running,
            "exit_status": exit_status,
            "stdout": self._sanitize(text=stdout),
            "stderr": self._sanitize(text=stderr),
        }
        self._fingerprint = hashlib.sha256(
            canonical_json_bytes(value=fingerprint_source).unwrap()
        ).hexdigest()
        return ObservationOutcome(
            response={
                "version": 1,
                "status": "ok",
                "running": running,
                "exit_status": exit_status,
                "stdout": stdout_piece,
                "stderr": stderr_piece,
            },
            fingerprint=self._fingerprint,
            stop_reason=None,
        )

    def _advance(self, *, stream: _StreamState, text: str, running: bool) -> str | None:
        if not text.startswith(stream.cumulative):
            return None
        safe_end = len(text) if not running else self._safe_end(text=text)
        released = self._sanitize(text=text[stream.released : safe_end])
        stream.cumulative = text
        stream.released = safe_end
        return released

    def _safe_end(self, *, text: str) -> int:
        known_values = frozenset(self.token_handles.values())
        token_tails = (match.group() for match in _TOKEN_AT_END.finditer(text))
        marker_tails = (match.group() for match in _REDACTED_TOKEN_MARKER_AT_END.finditer(text))
        protected_prefixes = (
            prefix
            for value in (*known_values, *self.sensitive_values)
            for length in range(1, len(value))
            if (prefix := value[:length])
        )
        ambiguous_lengths = [
            len(suffix)
            for suffix in (
                *_TOKEN_PREFIXES,
                *_REDACTED_TOKEN_MARKER_PREFIXES,
                *token_tails,
                *marker_tails,
                *protected_prefixes,
            )
            if text.endswith(suffix)
        ]
        return len(text) - max(ambiguous_lengths, default=0)

    def _sanitize(self, *, text: str) -> str:
        replacements: dict[str, str] = {}
        for handle, value in self.token_handles.items():
            replacements[value] = f"[[redacted-token:{handle}]]"
        for value in frozenset(_TOKEN.findall(text)):
            if value in replacements:
                continue
            handle = self._dynamic_handles.get(value)
            if handle is None:
                handle = self.new_token_handle(value=value)
                self._dynamic_handles[value] = handle
            replacements[value] = f"[[redacted-token:{handle}]]"
        for value in self.sensitive_values:
            _ = replacements.setdefault(value, "[[redacted-sensitive]]")
        for marker in frozenset(_REDACTED_TOKEN_MARKER.findall(text)):
            replacements[marker] = "<redacted-untrusted-marker>"
        ordered_values = sorted(replacements, key=len, reverse=True)
        pattern = re.compile("|".join([*(re.escape(value) for value in ordered_values), r"(?!)"]))
        return pattern.sub(lambda match: replacements[match.group()], text)

    def _unavailable(self) -> ObservationOutcome:
        return ObservationOutcome(
            response={"version": 1, "status": "unavailable"},
            fingerprint=self._fingerprint,
            stop_reason="flow-unavailable",
        )
