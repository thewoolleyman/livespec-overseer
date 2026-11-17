"""CI reads of a pull request avoid the REST pulls endpoint.

This repository's mirror of livespec-dev-tooling#4889 / livespec-dev-tooling#4899:
the pulls endpoint answers a transient 422 "too many files changed" right after a
force-push while GitHub computes diff stats. The body is read through the issues
endpoint, and the head sha through GraphQL, which has no diff computation.
"""

from __future__ import annotations

from pathlib import Path

__all__: list[str] = []

_WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"
_CI = (_WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
_LABEL = (_WORKFLOWS / "incident-label-ci.yml").read_text(encoding="utf-8")


def test_ci_reads_the_pr_body_through_the_issues_endpoint() -> None:
    assert 'repos/${GITHUB_REPOSITORY}/issues/${PR_NUMBER}" --jq \'.body // ""\'' in _CI
    assert "/pulls/${PR_NUMBER}" not in _CI


def test_incident_label_ci_reads_the_head_through_graphql_and_fails_closed() -> None:
    assert "pullRequest(number:$n){headRefOid}" in _LABEL
    assert "--jq '.data.repository.pullRequest.headRefOid // empty'" in _LABEL
    assert "/pulls/${PR_NUMBER}" not in _LABEL
    assert '[ -z "$head" ]' in _LABEL
