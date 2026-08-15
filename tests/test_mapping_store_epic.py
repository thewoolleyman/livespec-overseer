"""Assignment-time mapping epic population."""

import json
import subprocess

import _registry_epic
import pytest
import registry
import supervisor
from test_supervisor_builders import isolate_store, make_plan

__all__: list[str] = []


def test_epic_from_plan_anchor_accepts_observed_labels_and_wrapped_ids(*, tmp_path, monkeypatch):
    cases = {
        "ledger": b"**Ledger anchor:** epic **`overseer-ledger`**\n",
        "ledger-epic": b"**Ledger epic anchor:** epic **`overseer-ledger-epic`**\n",
        "epic": b"**Epic anchor:** epic **`overseer-epic`**\n",
        "wrapped": b"**Epic anchor:** epic\n**`overseer-wrapped`**\n",
    }
    monkeypatch.setattr(
        _registry_epic.subprocess,
        "run",
        lambda argv, **_kwargs: subprocess.CompletedProcess(
            args=argv, returncode=0, stdout="[]", stderr=""
        ),
    )

    for topic, epic in cases.items():
        repo = tmp_path / topic
        plan_topic = "alpha"
        plan = repo / "plan" / plan_topic
        plan.mkdir(parents=True)
        (plan / "epic.md").write_bytes(b"# Plan\n\n" + epic)

        assert registry.epic_from_plan_anchor(repo=repo, topic=plan_topic) == f"overseer-{topic}"


def test_epic_from_plan_anchor_fails_closed_for_malformed_epic_file(*, tmp_path, monkeypatch):
    repo = tmp_path / "malformed"
    topic = "alpha"
    plan = repo / "plan" / topic
    plan.mkdir(parents=True)
    (plan / "epic.md").write_text("# Plan\n\nNo ledger anchor declaration yet.\n")
    monkeypatch.setattr(
        _registry_epic.subprocess,
        "run",
        lambda argv, **_kwargs: subprocess.CompletedProcess(
            args=argv, returncode=0, stdout="[]", stderr=""
        ),
    )

    assert registry.epic_from_plan_anchor(repo=repo, topic=topic) is None


def test_epic_from_plan_anchor_reads_ledger_tag_when_handoff_is_absent(*, tmp_path, monkeypatch):
    repo = tmp_path / "ledger-binder"
    topic = "ledger-only"
    _ = (repo / "plan" / topic).mkdir(parents=True)

    def fake_run(argv, **kwargs):
        assert argv == ["bd", "list", "--type", "epic", "--status", "all", "--json"]
        assert kwargs["cwd"] == repo
        return subprocess.CompletedProcess(
            args=argv,
            returncode=0,
            stdout=json.dumps(
                [
                    {
                        "id": "overseer-ledger-only",
                        "issue_type": "epic",
                        "spec_id": "plan:ledger-only",
                        "metadata": {"plan_slug": topic},
                    }
                ]
            ),
            stderr="",
        )

    monkeypatch.setattr(_registry_epic.subprocess, "run", fake_run)

    assert registry.epic_from_plan_anchor(repo=repo, topic=topic) == "overseer-ledger-only"


def test_epic_from_plan_anchor_prefixes_ledger_lookup_with_credential_wrapper(
    *, tmp_path, monkeypatch
):
    repo = tmp_path / "ledger-binder"
    topic = "ledger-only"
    _ = (repo / "plan" / topic).mkdir(parents=True)
    (repo / ".livespec.jsonc").write_text(
        '{\n  "credential_wrapper": ["/usr/local/bin/with-livespec-env.sh", "--"]\n}\n',
        encoding="utf-8",
    )
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        assert kwargs["cwd"] == repo
        return subprocess.CompletedProcess(
            args=argv,
            returncode=0,
            stdout=json.dumps(
                [
                    {
                        "id": "overseer-ledger-only",
                        "issue_type": "epic",
                        "spec_id": "plan:ledger-only",
                    }
                ]
            ),
            stderr="",
        )

    monkeypatch.setattr(_registry_epic.subprocess, "run", fake_run)

    assert registry.epic_from_plan_anchor(repo=repo, topic=topic) == "overseer-ledger-only"
    assert calls == [
        [
            "/usr/local/bin/with-livespec-env.sh",
            "--",
            "bd",
            "list",
            "--type",
            "epic",
            "--status",
            "all",
            "--json",
        ]
    ]


@pytest.mark.parametrize(
    ("result", "raises"),
    [
        (subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr=""), None),
        (subprocess.CompletedProcess(args=[], returncode=0, stdout="not-json", stderr=""), None),
        (subprocess.CompletedProcess(args=[], returncode=0, stdout="{}", stderr=""), None),
        (
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout='["not-a-record"]', stderr=""
            ),
            None,
        ),
        (
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=json.dumps(
                    [
                        {"id": "not-epic", "issue_type": "task", "spec_id": "plan:ledger-only"},
                        {"id": "wrong-tag", "issue_type": "epic", "spec_id": "plan:other"},
                    ]
                ),
                stderr="",
            ),
            None,
        ),
        (
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=json.dumps(
                    [
                        {"id": "first", "issue_type": "epic", "spec_id": "plan:ledger-only"},
                        {
                            "id": "second",
                            "issue_type": "epic",
                            "metadata": {"plan_slug": "ledger-only"},
                        },
                    ]
                ),
                stderr="",
            ),
            None,
        ),
        (None, OSError("bd unavailable")),
    ],
)
def test_epic_from_plan_anchor_fails_closed_for_unusable_ledger_response(
    *, tmp_path, monkeypatch, result, raises
):
    repo = tmp_path / "ledger-binder"
    topic = "ledger-only"
    _ = (repo / "plan" / topic).mkdir(parents=True)

    def fake_run(_argv, **_kwargs):
        if raises is not None:
            raise raises
        return result

    monkeypatch.setattr(_registry_epic.subprocess, "run", fake_run)

    assert registry.epic_from_plan_anchor(repo=repo, topic=topic) is None


def test_epic_from_plan_anchor_uses_ledger_when_handoff_cannot_be_read(*, tmp_path, monkeypatch):
    repo = tmp_path / "ledger-binder"
    topic = "ledger-only"
    handoff = repo / "plan" / topic / "handoff.md"
    handoff.mkdir(parents=True)
    monkeypatch.setattr(
        _registry_epic.subprocess,
        "run",
        lambda argv, **_kwargs: subprocess.CompletedProcess(
            args=argv,
            returncode=0,
            stdout=json.dumps(
                [
                    {
                        "id": "overseer-ledger-only",
                        "issue_type": "epic",
                        "spec_id": "plan:ledger-only",
                    }
                ]
            ),
            stderr="",
        ),
    )

    assert registry.epic_from_plan_anchor(repo=repo, topic=topic) == "overseer-ledger-only"


def test_cli_assignment_populates_epic_from_plan_anchor_with_null_control(*, tmp_path, monkeypatch):
    anchored_repo, anchored_topic = make_plan(
        tmp_path=tmp_path,
        repo_name="anchored",
        topic="alpha",
        handoff=(
            b"# Plan\n\n"
            b"**Owning repo:** `livespec-overseer`. **Ledger anchor:** epic\n"
            b"**`overseer-pfpfty`**.\n"
        ),
    )
    null_repo, null_topic = make_plan(
        tmp_path=tmp_path,
        repo_name="unanchored",
        topic="beta",
        handoff=b"# Plan\n\nNo ledger anchor declaration yet.\n",
    )
    missing_repo = tmp_path / "missing"
    missing_topic = "gamma"
    _ = (missing_repo / "plan" / missing_topic).mkdir(parents=True)
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)

    monkeypatch.setattr(
        _registry_epic.subprocess,
        "run",
        lambda argv, **_kwargs: subprocess.CompletedProcess(
            args=argv, returncode=0, stdout="[]", stderr=""
        ),
    )

    assert (
        supervisor.main(argv=["add", "--repo", str(anchored_repo), "--topic", anchored_topic]) == 0
    )
    assert supervisor.main(argv=["add", "--repo", str(null_repo), "--topic", null_topic]) == 0
    assert supervisor.main(argv=["add", "--repo", str(missing_repo), "--topic", missing_topic]) == 0

    tracks = {
        (registry.repo_slug(repo=track.repo), track.topic): track
        for track in registry.read_mapping(store_path=store)
    }
    assert tracks[("anchored", "alpha")].epic == "overseer-pfpfty"
    assert tracks[("unanchored", "beta")].epic is None
    assert tracks[("missing", "gamma")].epic is None
