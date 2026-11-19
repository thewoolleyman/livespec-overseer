"""Refresh and cache coverage for the release-runtime adapter."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

__all__: list[str] = []


class Completed:
    def __init__(self, *, stdout: str) -> None:
        self.stdout = stdout


def adapter_module():
    return importlib.import_module("overseer._supervisor_release_runtime")


def test_final_release_refresh_uses_etag_without_rereading_checks(*, tmp_path: Path) -> None:
    mod = adapter_module()
    release = "2222222222222222222222222222222222222222"
    current = "1111111111111111111111111111111111111111"
    now = [0.0]
    calls: list[list[str]] = []

    def run(argv, *, capture_output, text, check, timeout):
        del capture_output, text, check, timeout
        calls.append(list(argv))
        endpoint = argv[-1]
        if endpoint.endswith("/commits/release") and len(calls) == 1:
            return Completed(
                stdout=(
                    'HTTP/2 200 OK\r\netag: "release-v1"\r\n\r\n' + json.dumps({"sha": release})
                )
            )
        if endpoint.endswith(f"/commits/v{mod.APP_VERSION}"):
            return Completed(stdout=json.dumps({"sha": current}))
        if endpoint.endswith("/commits/release"):
            assert argv[-3:] == ["-H", 'If-None-Match: "release-v1"', endpoint]
            return Completed(stdout="HTTP/2 304 Not Modified\r\n\r\n")
        assert endpoint.endswith(f"/commits/{release}/check-runs?per_page=100")
        return Completed(stdout=json.dumps({"check_runs": [{"conclusion": "success"}]}))

    adapter = mod.ReleaseRuntimeAdapter(
        sup=object(),
        run=run,
        ensure_release_runtime=lambda *, release: tmp_path / release,
        clock=lambda: now[0],
    )

    assert adapter.currency_check()["eligible"] is True
    now[0] = 60.0
    assert adapter.currency_check()["eligible"] is True
    assert len(calls) == 4


def test_initial_final_verdict_spends_at_most_two_rest_responses(*, tmp_path: Path) -> None:
    """The running release tag must not consume a third REST response."""
    mod = adapter_module()
    release = "2222222222222222222222222222222222222222"
    current = "1111111111111111111111111111111111111111"
    calls: list[list[str]] = []

    def run(argv, *, capture_output, text, check, timeout):
        del capture_output, text, check, timeout
        calls.append(list(argv))
        if argv[:2] == ["git", "ls-remote"]:
            return Completed(stdout=f"{current}\trefs/tags/v{mod.APP_VERSION}^{{}}\n")
        endpoint = argv[-1]
        if endpoint.endswith("/commits/release"):
            return Completed(stdout=json.dumps({"sha": release}))
        assert endpoint.endswith(f"/commits/{release}/check-runs?per_page=100")
        return Completed(stdout=json.dumps({"check_runs": [{"conclusion": "success"}]}))

    adapter = mod.ReleaseRuntimeAdapter(
        sup=object(),
        run=run,
        ensure_release_runtime=lambda *, release: tmp_path / release,
    )

    assert adapter.currency_check()["eligible"] is True
    assert sum(call[:2] == ["gh", "api"] for call in calls) <= 2


def test_provisioning_failure_stays_blocked_after_a_refresh(*, tmp_path: Path) -> None:
    mod = adapter_module()
    release = "2222222222222222222222222222222222222222"
    now = [0.0]

    def run(argv, *, capture_output, text, check, timeout):
        del capture_output, text, check, timeout
        endpoint = argv[-1]
        if endpoint.endswith("/commits/release"):
            if "If-None-Match" in argv:
                return Completed(stdout="HTTP/2 304 Not Modified\n\n")
            return Completed(
                stdout='HTTP/2 200 OK\netag: "release-v1"\n\n' + json.dumps({"sha": release})
            )
        if endpoint.endswith(f"/commits/v{mod.APP_VERSION}"):
            return Completed(stdout=json.dumps({"sha": "1111111111111111111111111111111111111111"}))
        return Completed(stdout=json.dumps({"check_runs": [{"conclusion": "success"}]}))

    adapter = mod.ReleaseRuntimeAdapter(
        sup=object(),
        run=run,
        ensure_release_runtime=lambda *, release: None,
        clock=lambda: now[0],
    )

    assert adapter.currency_check()["eligible"] is True
    assert adapter.reexec_target() is None
    adapter._final_verdicts.clear()
    now[0] = 60.0

    assert adapter.currency_check()["reason"] == "release runtime provisioning failed"


def test_http_response_parts_handles_lf_headers_and_malformed_values() -> None:
    mod = adapter_module()

    assert mod._http_response_parts(text="plain") == (200, {}, "plain")
    assert mod._http_response_parts(text="HTTP/2 no-status\nheader\n\n") == (
        200,
        {},
        "",
    )
    assert mod._http_response_parts(text="HTTP/2 201 Created\nA: one\nB:\n\nbody") == (
        201,
        {"a": "one", "b": ""},
        "body",
    )
