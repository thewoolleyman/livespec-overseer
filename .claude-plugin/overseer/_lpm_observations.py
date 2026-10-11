"""Fail-closed acquisition observation sanitization and opaque token provenance."""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass, field

from _lpm_canonical import canonical_json_bytes

__all__: list[str] = [
    "ObservationOutcome",
    "ObservationSanitizer",
]


@dataclass(frozen=True, kw_only=True)
class ObservationOutcome:
    """One closed observation result and service-private fingerprint state."""

    response: dict[str, object]
    fingerprint: str | None
    stop_reason: str | None


@dataclass(kw_only=True)
class ObservationSanitizer:
    """Sanitize browser and terminal fields before constructing an observable result."""

    token_handles: dict[str, str]
    sensitive_values: frozenset[str]
    _fingerprint: str | None = field(default=None, init=False, repr=False)

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
        """Return only a fully sanitized browser observation or the closed unavailable shape."""
        if not masking_established:
            return ObservationOutcome(
                response={"version": 1, "status": "unavailable"},
                fingerprint=self._fingerprint,
                stop_reason="flow-unavailable",
            )
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
        return ObservationOutcome(
            response=fields,
            fingerprint=self._fingerprint,
            stop_reason=None,
        )

    def terminal_observation(
        self,
        *,
        running: bool,
        exit_status: int | None,
        stdout: str,
        stderr: str,
    ) -> ObservationOutcome:
        """Return a closed terminal observation with both streams sanitized."""
        return ObservationOutcome(
            response={
                "version": 1,
                "status": "ok",
                "running": running,
                "exit_status": exit_status,
                "stdout": self._sanitize(text=stdout),
                "stderr": self._sanitize(text=stderr),
            },
            fingerprint=self._fingerprint,
            stop_reason=None,
        )

    def _sanitize(self, *, text: str) -> str:
        sanitized = text
        for handle, value in self.token_handles.items():
            sanitized = sanitized.replace(value, f"[[redacted-token:{handle}]]")
        for value in self.sensitive_values:
            sanitized = sanitized.replace(value, "[[redacted-sensitive]]")
        return sanitized
