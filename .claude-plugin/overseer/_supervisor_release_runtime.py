"""Production release-currency adapter for the daemon runtime."""

from __future__ import annotations

import json
import subprocess
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

_REPO = "thewoolleyman/livespec-overseer"
SubprocessRun = Callable[..., subprocess.CompletedProcess[str]]
EnsureReleaseRuntime = Callable[..., Path | None]


@dataclass(kw_only=True)
class ReleaseRuntimeAdapter:
    """Compute one release-currency verdict and feed both daemon seams."""

    sup: Supervisor
    run: SubprocessRun = subprocess.run
    ensure_release_runtime: EnsureReleaseRuntime = runtime_prefix.ensure_release_runtime
    _cached_verdict: Mapping[str, object] | None = field(default=None, init=False)
    _cached_target: Path | None = field(default=None, init=False)

    def currency_check(self) -> Mapping[str, object] | None:
        self._cached_verdict = None
        self._cached_target = None
        self._cached_verdict = self._resolve_verdict()
        return self._cached_verdict

    def reexec_target(self) -> Path | None:
        return self._cached_target

    def _resolve_verdict(self) -> Mapping[str, object]:
        release = self._commit_for_ref(ref="release")
        current = self._commit_for_ref(ref=f"v{APP_VERSION}")
        checks = self._checks_for_commit(commit=release) if release is not None else None
        verdict = release_currency.update_target(
            current=current or APP_VERSION, release=release, checks=checks
        )
        if verdict.get("eligible") is not True:
            return verdict
        target = verdict.get("target")
        if not isinstance(target, str) or not target:
            return verdict
        installed = self.ensure_release_runtime(release=target)
        if installed is None:
            return {
                "eligible": False,
                "target": target,
                "blocked": True,
                "reason": "release runtime provisioning failed",
            }
        self._cached_target = installed
        return verdict

    def _commit_for_ref(self, *, ref: str) -> str | None:
        data = self._run_json(command=["gh", "api", f"/repos/{_REPO}/commits/{ref}"])
        sha = data.get("sha")
        return sha if isinstance(sha, str) and sha else None

    def _checks_for_commit(self, *, commit: str) -> Sequence[Mapping[str, object]] | None:
        data = self._run_json(
            command=["gh", "api", f"/repos/{_REPO}/commits/{commit}/check-runs?per_page=100"]
        )
        runs = jsonio.as_list(value=data.get("check_runs"))
        if runs is None:
            return None
        return tuple(_check_summary(value=run) for run in runs)

    def _run_json(self, *, command: Sequence[str]) -> Mapping[str, object]:
        completed = self.run(
            list(command),
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        parsed = json.loads(completed.stdout)
        data = jsonio.as_object(value=parsed)
        return {} if data is None else data


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
