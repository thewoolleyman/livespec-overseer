"""Non-blocking OTLP export runner for daemon event records."""

from __future__ import annotations

import concurrent.futures
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

import _supervisor_otel
import _supervisor_otel_report

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["OtelAsyncExporter"]

_MAX_IN_FLIGHT: Final = 64
_FAST_RESULT_GRACE_SECONDS: Final = 0.005


@dataclass(kw_only=True)
class OtelAsyncExporter:
    """Run OTLP sends away from the daemon tick path.

    A blackholing endpoint can hold one worker for the transport timeout. The daemon
    still owns timely supervision, so the queue is bounded. Further events are reported
    as local capacity failures rather than silently dropped.
    """

    _lock: threading.Lock = field(default_factory=threading.Lock)
    _pending: list[concurrent.futures.Future[_supervisor_otel.EmitResult]] = field(
        default_factory=list
    )

    def export(
        self,
        *,
        sup: Supervisor,
        record: Mapping[str, object],
        config: _supervisor_otel.OtelConfig,
        emitter: Callable[[dict[str, object]], object],
    ) -> None:
        self._drain(sup=sup)
        with self._lock:
            if len(self._pending) >= _MAX_IN_FLIGHT:
                _supervisor_otel_report.report_export_result(
                    sup=sup,
                    result=_supervisor_otel.EmitResult(
                        sent=False,
                        span_count=1,
                        rejected_spans=1,
                        error="OTLP export queue full",
                    ),
                    state=sup.otel.failure_state,
                )
                return
            future = concurrent.futures.Future[_supervisor_otel.EmitResult]()
            self._pending.append(future)
        worker = threading.Thread(
            target=self._emit,
            kwargs={
                "future": future,
                "record": dict(record),
                "config": config,
                "emitter": emitter,
            },
            daemon=True,
        )
        worker.start()
        self._drain(sup=sup, timeout=_FAST_RESULT_GRACE_SECONDS)

    def _emit(
        self,
        *,
        future: concurrent.futures.Future[_supervisor_otel.EmitResult],
        record: Mapping[str, object],
        config: _supervisor_otel.OtelConfig,
        emitter: Callable[[dict[str, object]], object],
    ) -> None:
        result = _supervisor_otel.emit_daemon_event(
            record=record,
            config=config,
            emitter=emitter,
        )
        future.set_result(result)

    def _drain(self, *, sup: Supervisor, timeout: float = 0.0) -> None:
        with self._lock:
            pending = list(self._pending)
        if not pending:
            return
        done, _not_done = concurrent.futures.wait(pending, timeout=timeout)
        for future in done:
            _supervisor_otel_report.report_export_result(
                sup=sup,
                result=future.result(),
                state=sup.otel.failure_state,
            )
        if done:
            with self._lock:
                self._pending = [future for future in self._pending if future not in done]
