"""The overseer's expected-failure surface.

Per livespec/SPECIFICATION/non-functional-requirements.md, expected
failures travel as failure-track values carrying structured detail;
unexpected failures, which are programming bugs, propagate as raised
built-ins to the outermost supervisor.

`OverseerSourceError` is the single domain error for every expected
failure the overseer's source readers can report: a gather command whose
stdout is not a JSON object, a dispatch journal carrying a malformed
JSONL record, or a filing subprocess returning an unusable payload.

It is deliberately one type rather than one per reader. Converting a
repo of this size one bespoke failure dataclass at a time yields a type
per call site and no shared vocabulary; the rest of the fleet already
settled on a single `detail`-carrying domain error per package
(`GithubAppAuthError` in livespec-runtime, `CrossRepoSchemaError` in
livespec-orchestrator-beads-fabro) and this follows that shape.

A source being unavailable is not an error here. An absent command, a
spawn failure, a timeout, a non-zero exit, and a missing journal file
are answers the gatherer already models as skip payloads on the success
track. Only output that is present but unusable is a failure.
"""

from __future__ import annotations

__all__: list[str] = ["OverseerSourceError"]


class OverseerSourceError(Exception):
    """An overseer source produced output it could not use.

    `detail` is an actionable diagnostic naming the source and what was
    wrong with its output; callers may surface it verbatim.
    """

    def __init__(self, *, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail
