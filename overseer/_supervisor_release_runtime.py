"""Production release-currency adapter for the daemon runtime."""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import jsonio
import release_currency
import runtime_prefix
from version import APP_VERSION

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["ReleaseRuntimeAdapter", "release_runtime_adapter"]

_REPO = "livespec-ai/livespec-overseer"
_REPO_URL = f"https://github.com/{_REPO}.git"
_REFRESH_SECONDS = 60
_HTTP_NOT_MODIFIED = 304
SubprocessRun = Callable[..., subprocess.CompletedProcess[str]]
EnsureReleaseRuntime = Callable[..., Path | None]
Clock = Callable[[], float]


@dataclass(kw_only=True)
class ReleaseRuntimeAdapter:
    """Compute one release-currency verdict and feed both daemon seams."""

    sup: Supervisor
    run: SubprocessRun = subprocess.run
    ensure_release_runtime: EnsureReleaseRuntime = runtime_prefix.ensure_release_runtime
    clock: Clock = time.monotonic
    _cached_verdict: Mapping[str, object] | None = field(default=None, init=False)
    _cached_release: str | None = field(default=None, init=False)
    _cached_target: Path | None = field(default=None, init=False)
    _failed_release: str | None = field(default=None, init=False)
    _current: str | None = field(default=None, init=False)
    _current_resolved: bool = field(default=False, init=False)
    _release: str | None = field(default=None, init=False)
    _release_etag: str | None = field(default=None, init=False)
    _release_read_at: float | None = field(default=None, init=False)
    _final_verdicts: dict[str, Mapping[str, object]] = field(default_factory=dict, init=False)

    def currency_check(self) -> Mapping[str, object] | None:
        """Return the current verdict without polling the forge on every tick.

        The release ref is the only mutable input after the running build is
        identified.  It is conditionally refreshed at most once per minute;
        a final verdict is immutable for that release SHA, while a pending
        check rollup is retried on the same bounded cadence.
        """
        now = self.clock()
        if (
            self._cached_verdict is not None
            and self._release_read_at is not None
            and now - self._release_read_at < _REFRESH_SECONDS
        ):
            return self._usable_verdict(verdict=self._cached_verdict)

        # Set the deadline before the request so even a failing forge read is
        # not immediately retried on every daemon tick.
        self._release_read_at = now
        release = self._release_for_refresh()
        current = self._running_commit()

        if release is not None:
            final = self._final_verdicts.get(release)
            if final is not None:
                self._cached_verdict = final
                return self._usable_verdict(verdict=final)

        self._cached_target = None
        self._cached_release = None
        verdict, checks_final = self._resolve_verdict(release=release, current=current)
        self._cached_verdict = verdict
        if release is not None and checks_final:
            self._final_verdicts[release] = verdict
        return self._usable_verdict(verdict=verdict)

    def reexec_target(self) -> Path | None:
        if self._cached_target is not None:
            return self._cached_target
        if self._cached_release is None:
            return None
        installed = self.ensure_release_runtime(release=self._cached_release)
        if installed is None:
            self._failed_release = self._cached_release
            self._cached_release = None
            return None
        self._cached_target = installed
        return self._cached_target

    def _resolve_verdict(
        self, *, release: str | None, current: str | None
    ) -> tuple[Mapping[str, object], bool]:
        checks = self._checks_for_commit(commit=release) if release is not None else None
        verdict = release_currency.update_target(
            current=current or APP_VERSION, release=release, checks=checks
        )
        if verdict.get("eligible") is not True:
            return verdict, _final_check_rollup(release=release, current=current, checks=checks)
        target = verdict.get("target")
        if not isinstance(target, str) or not target:
            return verdict, _final_check_rollup(release=release, current=current, checks=checks)
        if target == self._failed_release:
            return (
                {
                    "eligible": False,
                    "target": target,
                    "blocked": True,
                    "reason": "release runtime provisioning failed",
                },
                _final_check_rollup(release=release, current=current, checks=checks),
            )
        self._cached_release = target
        return verdict, _final_check_rollup(release=release, current=current, checks=checks)

    def _usable_verdict(self, *, verdict: Mapping[str, object]) -> Mapping[str, object]:
        """Surface a failed runtime installation without invalidating its cache."""
        target = verdict.get("target")
        if isinstance(target, str) and target and target == self._failed_release:
            return {
                "eligible": False,
                "target": target,
                "blocked": True,
                "reason": "release runtime provisioning failed",
            }
        if isinstance(target, str) and target:
            self._cached_release = target
        return verdict

    def _running_commit(self) -> str | None:
        """Resolve the running build once for this adapter process."""
        if not self._current_resolved:
            self._current = self._commit_for_ref(ref=f"v{APP_VERSION}")
            self._current_resolved = True
        return self._current

    def _release_for_refresh(self) -> str | None:
        """Conditionally refresh the release ref and retain its validator."""
        command = ["gh", "api", "--include"]
        if self._release_etag is not None:
            command.extend(["-H", f"If-None-Match: {self._release_etag}"])
        command.append(f"/repos/{_REPO}/commits/release")
        status, headers, data = self._run_response(command=command)
        if status == _HTTP_NOT_MODIFIED:
            return self._release
        etag = headers.get("etag")
        if etag:
            self._release_etag = etag
        sha = data.get("sha")
        release = sha if isinstance(sha, str) and sha else None
        self._release = release
        return release

    def _commit_for_ref(self, *, ref: str) -> str | None:
        """Resolve an immutable tag without spending GitHub REST budget."""
        completed = self.run(
            ["git", "ls-remote", _REPO_URL, f"refs/tags/{ref}", f"refs/tags/{ref}^{{}}"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        refs: dict[str, str] = {}
        for line in completed.stdout.splitlines():
            sha, separator, name = line.partition("\t")
            if separator and sha and name:
                refs[name] = sha
        return refs.get(f"refs/tags/{ref}^{{}}") or refs.get(f"refs/tags/{ref}")

    def _checks_for_commit(self, *, commit: str) -> Sequence[Mapping[str, object]] | None:
        data = self._run_json(
            command=["gh", "api", f"/repos/{_REPO}/commits/{commit}/check-runs?per_page=100"]
        )
        runs = jsonio.as_list(value=data.get("check_runs"))
        if runs is None:
            return None
        return tuple(_check_summary(value=run) for run in runs)

    def _run_json(self, *, command: Sequence[str]) -> Mapping[str, object]:
        _status, _headers, data = self._run_response(command=command)
        return data

    def _run_response(
        self, *, command: Sequence[str]
    ) -> tuple[int, Mapping[str, str], Mapping[str, object]]:
        completed = self.run(
            list(command),
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        status, headers, body = _http_response_parts(text=completed.stdout)
        if status == _HTTP_NOT_MODIFIED or not body.strip():
            return status, headers, {}
        parsed = json.loads(body)
        data = jsonio.as_object(value=parsed)
        return status, headers, {} if data is None else data


def _http_response_parts(*, text: str) -> tuple[int, Mapping[str, str], str]:
    """Split ``gh api --include`` output, accepting old JSON-only fixtures."""
    if not text.startswith("HTTP/"):
        return 200, {}, text
    head, separator, body = text.partition("\r\n\r\n")
    if not separator:
        head, separator, body = text.partition("\n\n")
    lines = head.splitlines()
    status = 200
    parts = lines[0].split()
    if len(parts) > 1 and parts[1].isdigit():
        status = int(parts[1])
    headers: dict[str, str] = {}
    for line in lines[1:]:
        name, separator, value = line.partition(":")
        if separator:
            headers[name.lower()] = value.strip()
    return status, headers, body


def _final_check_rollup(
    *,
    release: str | None,
    current: str | None,
    checks: Sequence[Mapping[str, object]] | None,
) -> bool:
    """A final rollup cannot change for the immutable release SHA."""
    if release is not None and release == current:
        return True
    return bool(checks) and all(
        isinstance(check.get("conclusion"), str) and bool(check.get("conclusion"))
        for check in checks
    )


def _check_summary(*, value: object) -> Mapping[str, object]:
    check = jsonio.as_object(value=value)
    if check is None:
        return {"name": "<malformed>", "conclusion": ""}
    return {
        "name": check.get("name") or "<unnamed>",
        "conclusion": check.get("conclusion") or "",
    }


def release_runtime_adapter(*, sup: Supervisor) -> ReleaseRuntimeAdapter:
    """Build the daemon's production release-runtime adapter."""
    return ReleaseRuntimeAdapter(sup=sup)
