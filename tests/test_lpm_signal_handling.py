"""Typed signal handling for the four report classifications, and mechanical redaction.

SPECIFICATION/contracts.md states each classification's consequences separately: all four release
a live reporting-run lease; `authentication`, `rate-limit` and `provider-outage` suspect a live
credential; and only `authentication` evicts the metadata cache entry. `unknown` is NOT a weaker
outage — these tests pin the table flat so a severity ordering cannot grow into it and start
costing credentials their validity.

Redaction is mechanical and refuses rather than strips: a diagnostic carrying a registered
credential literal is rejected whole, because a stripping rule that misses one spelling has
already published the credential while reporting success.
"""

from __future__ import annotations

import importlib
import pathlib

__all__: list[str] = []


def _modules():
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_signal.py"
    assert module_path.is_file(), "overseer/_lpm_signal.py must exist"
    return (
        importlib.import_module("_lpm_signal"),
        importlib.import_module("_lpm_registry"),
    )


def test_the_four_classifications_all_release_the_lease_and_only_three_suspect():
    signal, _ = _modules()

    released = {name for name, row in signal.CLASSIFICATION_HANDLING.items() if row.releases_lease}
    suspecting = {
        name for name, row in signal.CLASSIFICATION_HANDLING.items() if row.suspects_credential
    }

    assert set(signal.REPORT_CLASSIFICATIONS) == set(signal.CLASSIFICATION_HANDLING)
    assert released == set(signal.REPORT_CLASSIFICATIONS)
    assert suspecting == {"authentication", "rate-limit", "provider-outage"}


def test_only_an_authentication_report_evicts_the_cache_entry():
    signal, _ = _modules()

    evicting = {
        name for name, row in signal.CLASSIFICATION_HANDLING.items() if row.evicts_cache_entry
    }

    assert evicting == {signal.AUTHENTICATION_CLASSIFICATION}
    assert signal.handling_for(classification="unknown").suspects_credential is False
    assert signal.handling_for(classification="unknown").releases_lease is True
    assert signal.handling_for(classification="timeout") is None


def test_every_registered_provider_row_declares_what_its_credential_values_look_like():
    signal, registry = _modules()

    declared = set(signal.REDACTION_MATCHERS_BY_ROW)
    rows = {(row.provider, row.kind) for row in registry.PROVIDER_REGISTRY}

    assert declared == rows
    assert all(matchers != () for matchers in signal.REDACTION_MATCHERS_BY_ROW.values())


def test_a_diagnostic_carrying_a_registered_credential_literal_is_refused_whole():
    signal, _ = _modules()

    assert signal.is_redacted_diagnostic(diagnostic="HTTP 401 from the messages endpoint") is True
    assert signal.is_redacted_diagnostic(diagnostic="") is True
    assert signal.is_redacted_diagnostic(diagnostic="token sk-ant-oat01-abc rejected") is False


def test_an_oversize_or_control_bearing_diagnostic_is_refused():
    signal, _ = _modules()
    at_limit = "x" * signal.MAXIMUM_DIAGNOSTIC_BYTES

    assert signal.is_redacted_diagnostic(diagnostic=at_limit) is True
    assert signal.is_redacted_diagnostic(diagnostic=at_limit + "x") is False
    assert signal.is_redacted_diagnostic(diagnostic="two\nlines") is False
    assert signal.is_redacted_diagnostic(diagnostic="delete\x7fhere") is False


def test_the_byte_bound_is_on_utf8_bytes_not_on_code_points():
    signal, _ = _modules()
    multibyte = "é" * (signal.MAXIMUM_DIAGNOSTIC_BYTES // 2)

    assert len(multibyte) < signal.MAXIMUM_DIAGNOSTIC_BYTES
    assert len(multibyte.encode("utf-8")) == signal.MAXIMUM_DIAGNOSTIC_BYTES
    assert signal.is_redacted_diagnostic(diagnostic=multibyte) is True
    assert signal.is_redacted_diagnostic(diagnostic=multibyte + "é") is False
