"""_supervisor_otel_seam — the OTEL config and transport as ONE injectable unit.

They are never used apart: every export needs both, and `_supervisor_otel.emit_daemon_event`
takes them together. Bundling them keeps `Supervisor` to a SINGLE field.

That is not cosmetic. `_supervisor_core.py` sits within a few lines of the 250-LLOC hard
ceiling and is written by several tracks a day — six commits touched it in the 24 hours
before this module was added — so every seam that costs it six lines instead of one brings
the next unrelated change closer to a gate failure it did not cause.

It lives beside `_supervisor_otel` rather than inside it because that module was itself at
249 LLOC when this was written, one line under the same ceiling.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import _supervisor_otel
import _supervisor_otel_report

__all__: list[str] = ["OtelSeam", "from_env"]


@dataclass(frozen=True, kw_only=True)
class OtelSeam:
    """What the daemon needs to export one event: where to send it, and how."""

    config: _supervisor_otel.OtelConfig
    emitter: Callable[[dict[str, object]], object]
    failure_state: _supervisor_otel_report.OtelExportFailureState = field(
        default_factory=_supervisor_otel_report.OtelExportFailureState
    )


def from_env() -> OtelSeam:
    """Resolve config from the environment; degrade to local-only when unconfigured.

    The transport adapter is a lambda rather than a `def` on purpose. `emit_daemon_event`
    calls its emitter POSITIONALLY so a test can inject `list.append` as the seam, while
    `default_emitter` is keyword-only like every other function in this package. A named
    `def` bridging the two would need a positional parameter, which the repo's
    keyword-only-args gate correctly refuses.
    """
    return OtelSeam(
        config=_supervisor_otel.config_from_env(),
        emitter=lambda request: _supervisor_otel.default_emitter(request=request),
    )
