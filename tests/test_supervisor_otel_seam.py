"""The OTEL seam bundles config and transport as ONE injectable unit."""

from __future__ import annotations

import importlib
import pathlib

__all__: list[str] = []


def _seam_module():
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_supervisor_otel_seam.py"
    assert module_path.is_file()
    return importlib.import_module("overseer._supervisor_otel_seam")


def test_an_unconfigured_environment_yields_a_seam_that_exports_nowhere(*, monkeypatch):
    """The item's own bar: with nothing configured the daemon runs and does not fail."""
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

    seam = _seam_module().from_env()

    assert seam.config.endpoint is None
    assert callable(seam.emitter)


def test_the_seam_transport_bridges_a_positional_call_to_the_keyword_only_emitter(*, monkeypatch):
    """Covers the adapter, which exists ONLY to reconcile two calling conventions.

    `emit_daemon_event` calls its emitter POSITIONALLY so a test can inject `list.append`
    as the whole seam, while `default_emitter` is keyword-only like everything else in the
    package. Without this leg the adapter is never executed by any test, and a bridge that
    forwards to the wrong parameter would ship green.
    """
    seam_module = _seam_module()
    seen: list[object] = []
    # Patch the module object the seam itself holds. This package imports FLAT
    # (`import _supervisor_otel`), so `overseer._supervisor_otel` is a different module
    # object than the one the adapter resolves at call time, and patching that one
    # silently does nothing.
    monkeypatch.setattr(
        seam_module._supervisor_otel, "default_emitter", lambda *, request: seen.append(request)
    )
    request = {"url": "http://localhost:4318/v1/traces", "headers": {}, "payload": {}}

    _ = seam_module.from_env().emitter(request)

    assert seen == [request]
