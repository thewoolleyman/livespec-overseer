"""_caam_span_seam — the caam span config and transport bound into ONE emitter.

The caam half of the fleet's OTLP convention needs the same two things every
export needs, and never one without the other: where to send (resolved from the
environment by the SHARED reader, `_supervisor_otel.config_from_env`) and how to
send (`_supervisor_otel.default_emitter`). Binding them here keeps model
enforcement holding a single callable that answers nothing, so no enforcement
branch can ever depend on whether a collector was reachable.

This mirrors `_supervisor_otel_seam` for the daemon half, and for the same
reason: `caam_enforcement` is the pass's orchestrator, not a place for wire
concerns to accumulate.

WHY THE SEND IS SYNCHRONOUS HERE, where the daemon's is not. The daemon exports
from its tick path, so a blackholing endpoint holding a worker for the transport
timeout would cost it timely supervision -- hence `_supervisor_otel_async`. Model
enforcement runs on the rotation cadence over a handful of foreman panes, and its
own actuator already spends seconds per pane driving a tmux picker, so an
in-line send is not the thing that would make it late. The far commoner case
costs nothing at all: with no `OTEL_EXPORTER_OTLP_ENDPOINT` set,
`emit_caam_event` returns before any transport is touched.

The transport adapter is a lambda rather than a `def` on purpose. `emit_caam_event`
calls its emitter POSITIONALLY so a test can inject `list.append` as the whole
seam, while `default_emitter` is keyword-only like every other function in this
package. A named `def` bridging the two would need a positional parameter, which
the repo's keyword-only-args gate correctly refuses.
"""

from __future__ import annotations

from collections.abc import Mapping

import _caam_span
import _supervisor_otel
from _caam_pane_decision import PaneEventEmitter

__all__: list[str] = ["emitter_from_env"]


def emitter_from_env() -> PaneEventEmitter:
    """An emitter bound to this host's OTLP configuration, resolved once per pass."""

    config = _supervisor_otel.config_from_env()

    def emit(*, record: Mapping[str, object]) -> None:
        # The result is deliberately dropped. `emit_caam_event` is already fail-open,
        # and enforcement has no correct response to an export failure: reporting one
        # in the operator's rotation table would make a healthy pass look broken.
        _ = _caam_span.emit_caam_event(
            record=record,
            config=config,
            emitter=lambda request: _supervisor_otel.default_emitter(request=request),
        )

    return emit
