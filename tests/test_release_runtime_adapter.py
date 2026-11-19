"""Direct coverage for the daemon release-runtime adapter."""

from __future__ import annotations

import importlib
import json
import subprocess
from pathlib import Path

import pytest

__all__: list[str] = []


class Completed:
    def __init__(self, *, stdout: str) -> None:
        self.stdout = stdout


def adapter_module():
    return importlib.import_module("overseer._supervisor_release_runtime")


def test_adapter_computes_one_green_verdict_and_installs_that_target(*, tmp_path) -> None:
    mod = adapter_module()
    release = "2222222222222222222222222222222222222222"
    current = "1111111111111111111111111111111111111111"
    calls: list[list[str]] = []
    installs: list[str] = []

    def run(argv, *, capture_output, text, check, timeout):
        calls.append(list(argv))
        assert capture_output is True
        assert text is True
        assert check is True
        assert timeout == 30
        if argv[:2] == ["git", "ls-remote"]:
            return Completed(stdout=f"{current}\trefs/tags/v{mod.APP_VERSION}^{{}}\n")
        endpoint = argv[-1]
        if endpoint.endswith("/commits/release"):
            return Completed(stdout=json.dumps({"sha": release}))
        if endpoint.endswith(f"/commits/v{mod.APP_VERSION}"):
            return Completed(stdout=json.dumps({"sha": current}))
        assert endpoint.endswith(f"/commits/{release}/check-runs?per_page=100")
        return Completed(
            stdout=json.dumps(
                {
                    "check_runs": [
                        {"name": "ci-green", "conclusion": "success"},
                        {"name": "", "conclusion": "success"},
                    ]
                }
            )
        )

    def ensure_release_runtime(*, release: str) -> Path:
        installs.append(release)
        return tmp_path / release / "venv" / "bin" / "overseerd"

    adapter = mod.ReleaseRuntimeAdapter(
        sup=object(),
        run=run,
        ensure_release_runtime=ensure_release_runtime,
    )

    assert adapter.reexec_target() is None
    verdict = adapter.currency_check()

    assert verdict["eligible"] is True
    assert verdict["target"] == release
    assert installs == []
    assert adapter.reexec_target() == tmp_path / release / "venv" / "bin" / "overseerd"
    assert adapter.reexec_target() == tmp_path / release / "venv" / "bin" / "overseerd"
    assert installs == [release]
    assert len(calls) == 3


def test_adapter_accepts_superseded_skipped_duplicate_check_runs(*, tmp_path) -> None:
    """Later successful runs make each duplicate check name green."""
    mod = adapter_module()
    release = "2222222222222222222222222222222222222222"
    current = "1111111111111111111111111111111111111111"

    def run(argv, *, capture_output, text, check, timeout):
        endpoint = argv[-1]
        if endpoint.endswith("/commits/release"):
            return Completed(stdout=json.dumps({"sha": release}))
        if endpoint.endswith(f"/commits/v{mod.APP_VERSION}"):
            return Completed(stdout=json.dumps({"sha": current}))
        return Completed(
            stdout=json.dumps(
                {
                    "check_runs": [
                        {
                            "id": 102,
                            "name": "check-doctor-static",
                            "conclusion": "success",
                            "completed_at": "2026-11-19T02:36:07Z",
                        },
                        {
                            "id": 101,
                            "name": "check-doctor-static",
                            "conclusion": "skipped",
                            "completed_at": "2026-11-19T02:34:40Z",
                        },
                        {
                            "id": 202,
                            "name": "check-python-batch",
                            "conclusion": "success",
                            "completed_at": "2026-11-19T02:36:48Z",
                        },
                        {
                            "id": 201,
                            "name": "check-python-batch",
                            "conclusion": "skipped",
                            "completed_at": "2026-11-19T02:34:40Z",
                        },
                        {
                            "id": 302,
                            "name": "check-metadata-batch",
                            "conclusion": "success",
                            "completed_at": "2026-11-19T02:37:40Z",
                        },
                        {
                            "id": 301,
                            "name": "check-metadata-batch",
                            "conclusion": "skipped",
                            "completed_at": "2026-11-19T02:34:40Z",
                        },
                        {
                            "id": 400,
                            "name": "ci-green",
                            "conclusion": "success",
                            "completed_at": "2026-11-19T02:38:00Z",
                        },
                    ]
                }
            )
        )

    adapter = mod.ReleaseRuntimeAdapter(
        sup=object(),
        run=run,
        ensure_release_runtime=lambda *, release: tmp_path / release,
    )

    verdict = adapter.currency_check()

    assert verdict["eligible"] is True
    assert verdict["target"] == release


def test_release_runtime_adapter_factory_returns_adapter() -> None:
    mod = adapter_module()

    adapter = mod.release_runtime_adapter(sup=object())

    assert isinstance(adapter, mod.ReleaseRuntimeAdapter)


def test_adapter_prefers_a_peeled_git_tag_and_ignores_malformed_lines(*, tmp_path) -> None:
    mod = adapter_module()
    tag = f"v{mod.APP_VERSION}"
    tag_sha = "1111111111111111111111111111111111111111"
    peeled_sha = "2222222222222222222222222222222222222222"

    def run(argv, *, capture_output, text, check, timeout):
        assert argv == [
            "git",
            "ls-remote",
            "https://github.com/livespec-ai/livespec-overseer.git",
            f"refs/tags/{tag}",
            f"refs/tags/{tag}^{{}}",
        ]
        assert capture_output is True
        assert text is True
        assert check is True
        assert timeout == 30
        return Completed(
            stdout=(
                "missing-tab\n"
                "\tmissing-sha\n"
                f"{tag_sha}\t\n"
                f"{tag_sha}\trefs/tags/{tag}\n"
                f"{peeled_sha}\trefs/tags/{tag}^{{}}\n"
            )
        )

    adapter = mod.ReleaseRuntimeAdapter(
        sup=object(),
        run=run,
        ensure_release_runtime=lambda *, release: tmp_path / release,
    )

    assert adapter._running_commit() == peeled_sha


def test_adapter_ineligible_verdict_does_not_install(*, tmp_path) -> None:
    mod = adapter_module()
    release = "1111111111111111111111111111111111111111"

    def run(argv, *, capture_output, text, check, timeout):
        if argv[:2] == ["git", "ls-remote"]:
            return Completed(stdout=f"{release}\trefs/tags/v{mod.APP_VERSION}^{{}}\n")
        endpoint = argv[-1]
        if endpoint.endswith("/check-runs?per_page=100"):
            return Completed(stdout=json.dumps({"check_runs": []}))
        return Completed(stdout=json.dumps({"sha": release}))

    def ensure_release_runtime(*, release: str) -> Path:
        raise AssertionError("ineligible release must not install")

    adapter = mod.ReleaseRuntimeAdapter(
        sup=object(),
        run=run,
        ensure_release_runtime=ensure_release_runtime,
    )

    verdict = adapter.currency_check()

    assert verdict["eligible"] is False
    assert verdict["blocked"] is False
    assert adapter.reexec_target() is None


def test_adapter_treats_unreadable_shape_as_ineligible(*, tmp_path) -> None:
    mod = adapter_module()
    release = "2222222222222222222222222222222222222222"

    def run(argv, *, capture_output, text, check, timeout):
        if argv[:2] == ["git", "ls-remote"]:
            return Completed(stdout="")
        endpoint = argv[-1]
        if endpoint.endswith("/commits/release"):
            return Completed(stdout=json.dumps({"sha": release}))
        if endpoint.endswith(f"/commits/v{mod.APP_VERSION}"):
            return Completed(stdout=json.dumps([]))
        return Completed(stdout=json.dumps({"check_runs": "not a list"}))

    adapter = mod.ReleaseRuntimeAdapter(
        sup=object(),
        run=run,
        ensure_release_runtime=lambda *, release: tmp_path / release,
    )

    verdict = adapter.currency_check()

    assert verdict["eligible"] is False
    assert verdict["blocked"] is True
    assert "could not be read" in str(verdict["reason"])
    assert adapter.reexec_target() is None


def test_adapter_treats_unresolvable_release_as_ineligible(*, tmp_path) -> None:
    mod = adapter_module()

    def run(argv, *, capture_output, text, check, timeout):
        if argv[:2] == ["git", "ls-remote"]:
            return Completed(stdout="")
        endpoint = argv[-1]
        if endpoint.endswith("/commits/release"):
            return Completed(stdout=json.dumps({"sha": ""}))
        assert endpoint.endswith(f"/commits/v{mod.APP_VERSION}")
        return Completed(stdout=json.dumps({"sha": "1111111111111111111111111111111111111111"}))

    adapter = mod.ReleaseRuntimeAdapter(
        sup=object(),
        run=run,
        ensure_release_runtime=lambda *, release: tmp_path / release,
    )

    verdict = adapter.currency_check()

    assert verdict["eligible"] is False
    assert verdict["blocked"] is True
    assert "release ref did not resolve" in str(verdict["reason"])


def test_adapter_rejects_malformed_check_run_and_bad_target(*, tmp_path) -> None:
    mod = adapter_module()
    release = "2222222222222222222222222222222222222222"

    def run(argv, *, capture_output, text, check, timeout):
        if argv[:2] == ["git", "ls-remote"]:
            return Completed(stdout="")
        endpoint = argv[-1]
        if endpoint.endswith("/commits/release"):
            return Completed(stdout=json.dumps({"sha": release}))
        if endpoint.endswith(f"/commits/v{mod.APP_VERSION}"):
            return Completed(stdout=json.dumps({"sha": "1111111111111111111111111111111111111111"}))
        return Completed(stdout=json.dumps({"check_runs": [None]}))

    adapter = mod.ReleaseRuntimeAdapter(
        sup=object(),
        run=run,
        ensure_release_runtime=lambda *, release: tmp_path / release,
    )

    verdict = adapter.currency_check()
    adapter._cached_verdict = {"eligible": True, "target": None}

    assert verdict["eligible"] is False
    assert "<malformed>" in str(verdict["reason"])
    assert adapter.reexec_target() is None


def test_adapter_does_not_install_an_eligible_verdict_with_a_malformed_target(
    *, monkeypatch, tmp_path
) -> None:
    mod = adapter_module()

    def update_target(*, current, release, checks):
        assert current
        assert release
        assert checks is not None
        return {"eligible": True, "target": None, "blocked": False, "reason": "bad target"}

    monkeypatch.setattr(mod.release_currency, "update_target", update_target)

    def run(argv, *, capture_output, text, check, timeout):
        if argv[:2] == ["git", "ls-remote"]:
            return Completed(stdout="")
        endpoint = argv[-1]
        if endpoint.endswith("/check-runs?per_page=100"):
            return Completed(stdout=json.dumps({"check_runs": [{"conclusion": "success"}]}))
        return Completed(stdout=json.dumps({"sha": "1111111111111111111111111111111111111111"}))

    def ensure_release_runtime(*, release: str) -> Path:
        raise AssertionError("malformed target must not install")

    adapter = mod.ReleaseRuntimeAdapter(
        sup=object(),
        run=run,
        ensure_release_runtime=ensure_release_runtime,
    )

    assert adapter.currency_check() == {
        "eligible": True,
        "target": None,
        "blocked": False,
        "reason": "bad target",
    }
    assert adapter.reexec_target() is None


def test_adapter_propagates_forge_read_failures_to_currency_degradation(*, tmp_path) -> None:
    mod = adapter_module()

    def run(argv, *, capture_output, text, check, timeout):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)

    adapter = mod.ReleaseRuntimeAdapter(
        sup=object(),
        run=run,
        ensure_release_runtime=lambda *, release: tmp_path / release,
    )

    with pytest.raises(subprocess.TimeoutExpired) as excinfo:
        _ = adapter.currency_check()

    assert excinfo.value.timeout == 30


def test_adapter_surfaces_release_runtime_install_failure_on_the_next_currency_check(
    *, tmp_path
) -> None:
    mod = adapter_module()
    release = "2222222222222222222222222222222222222222"
    current = "1111111111111111111111111111111111111111"
    installs: list[str] = []

    def run(argv, *, capture_output, text, check, timeout):
        if argv[:2] == ["git", "ls-remote"]:
            return Completed(stdout=f"{current}\trefs/tags/v{mod.APP_VERSION}^{{}}\n")
        endpoint = argv[-1]
        if endpoint.endswith("/commits/release"):
            return Completed(stdout=json.dumps({"sha": release}))
        if endpoint.endswith(f"/commits/v{mod.APP_VERSION}"):
            return Completed(stdout=json.dumps({"sha": current}))
        return Completed(stdout=json.dumps({"check_runs": [{"conclusion": "success"}]}))

    def ensure_release_runtime(*, release: str) -> Path | None:
        installs.append(release)
        return None

    adapter = mod.ReleaseRuntimeAdapter(
        sup=object(),
        run=run,
        ensure_release_runtime=ensure_release_runtime,
    )

    assert adapter.currency_check()["eligible"] is True
    assert installs == []
    assert adapter.reexec_target() is None

    verdict = adapter.currency_check()

    assert verdict == {
        "eligible": False,
        "target": release,
        "blocked": True,
        "reason": "release runtime provisioning failed",
    }
    assert adapter.reexec_target() is None
    assert installs == [release]


def test_adapter_keeps_a_final_verdict_without_a_forge_reread_within_one_minute(
    *, tmp_path
) -> None:
    """A settled release must not spend forge budget again on the next tick."""
    mod = adapter_module()
    release = "2222222222222222222222222222222222222222"
    current = "1111111111111111111111111111111111111111"
    calls: list[list[str]] = []

    def run(argv, *, capture_output, text, check, timeout):
        calls.append(list(argv))
        if argv[:2] == ["git", "ls-remote"]:
            return Completed(stdout=f"{current}\trefs/tags/v{mod.APP_VERSION}^{{}}\n")
        endpoint = argv[-1]
        if endpoint.endswith("/commits/release"):
            return Completed(stdout=json.dumps({"sha": release}))
        if endpoint.endswith(f"/commits/v{mod.APP_VERSION}"):
            return Completed(stdout=json.dumps({"sha": current}))
        assert endpoint.endswith(f"/commits/{release}/check-runs?per_page=100")
        return Completed(
            stdout=json.dumps({"check_runs": [{"name": "ci-green", "conclusion": "success"}]})
        )

    adapter = mod.ReleaseRuntimeAdapter(
        sup=object(),
        run=run,
        ensure_release_runtime=lambda *, release: tmp_path / release,
    )

    first = adapter.currency_check()
    assert adapter.currency_check() == first
    assert len(calls) == 3
