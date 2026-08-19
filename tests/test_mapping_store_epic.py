"""Assignment-time mapping epic population."""

import ast
import json
import subprocess
from pathlib import Path

import _registry_epic
import pytest
import registry
import supervisor
from test_supervisor_builders import isolate_store, make_plan

__all__: list[str] = []


def _ledger_timeout_constant(*, path: Path) -> int:
    module = ast.parse(path.read_text(encoding="utf-8"))
    for node in module.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "_LEDGER_TIMEOUT_SECONDS"
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, int)
        ):
            return node.value.value
    raise AssertionError(f"{path} does not define _LEDGER_TIMEOUT_SECONDS as an int")


def test_ledger_epic_lookup_timeout_has_wrapped_bd_margin_and_plugin_lockstep():
    package_timeout = _ledger_timeout_constant(path=Path("overseer/_registry_epic.py"))
    plugin_timeout = _ledger_timeout_constant(
        path=Path(".claude-plugin/overseer/_registry_epic.py")
    )

    assert package_timeout == plugin_timeout
    assert package_timeout >= 20


def test_set_epic_rewrites_only_the_matching_row_and_preserves_unknown_keys(*, tmp_path):
    """set_epic is the field-scoped alternative to racy remove+append epic correction."""
    store = tmp_path / "map.jsonl"
    store.write_text(
        json.dumps({"topic": "a", "repo": "/r", "epic": None, "operator_note": "keep"})
        + "\n"
        + json.dumps({"topic": "b", "repo": "/r", "epic": "overseer-other"})
        + "\n",
        encoding="utf-8",
    )

    assert registry.set_epic(repo="/r", topic="a", epic="overseer-au3pt3", store_path=store)

    rows = {row.topic: row.epic for row in registry.read_valid_mapping(store_path=store)}
    assert rows == {"a": "overseer-au3pt3", "b": "overseer-other"}
    raw_a = next(
        json.loads(line)
        for line in store.read_text(encoding="utf-8").splitlines()
        if json.loads(line)["topic"] == "a"
    )
    assert raw_a["operator_note"] == "keep"

    before = store.stat().st_mtime_ns
    assert (
        registry.set_epic(repo="/r", topic="a", epic="overseer-au3pt3", store_path=store) is False
    )
    assert store.stat().st_mtime_ns == before
    assert registry.set_epic(repo="/r", topic="missing", epic="x", store_path=store) is False


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


def test_epic_from_plan_anchor_prefers_open_ledger_epic_over_closed_match(*, tmp_path, monkeypatch):
    repo = tmp_path / "ledger-binder"
    topic = "ledger-only"
    _ = (repo / "plan" / topic).mkdir(parents=True)

    def fake_run(argv, **_kwargs):
        return subprocess.CompletedProcess(
            args=argv,
            returncode=0,
            stdout=json.dumps(
                [
                    {
                        "id": "overseer-superseded",
                        "issue_type": "epic",
                        "status": "closed",
                        "metadata": {"plan_slug": topic},
                    },
                    {
                        "id": "overseer-live",
                        "issue_type": "epic",
                        "status": "backlog",
                        "spec_id": "plan:ledger-only",
                    },
                ]
            ),
            stderr="",
        )

    monkeypatch.setattr(_registry_epic.subprocess, "run", fake_run)

    assert registry.epic_from_plan_anchor(repo=repo, topic=topic) == "overseer-live"


def test_epic_from_plan_anchor_keeps_ambiguous_open_ledger_epics_closed(*, tmp_path, monkeypatch):
    repo = tmp_path / "ledger-binder"
    topic = "ledger-only"
    _ = (repo / "plan" / topic).mkdir(parents=True)

    def fake_run(argv, **_kwargs):
        return subprocess.CompletedProcess(
            args=argv,
            returncode=0,
            stdout=json.dumps(
                [
                    {
                        "id": "overseer-first",
                        "issue_type": "epic",
                        "status": "backlog",
                        "spec_id": "plan:ledger-only",
                    },
                    {
                        "id": "overseer-second",
                        "issue_type": "epic",
                        "status": "ready",
                        "metadata": {"plan_slug": topic},
                    },
                ]
            ),
            stderr="",
        )

    monkeypatch.setattr(_registry_epic.subprocess, "run", fake_run)

    assert registry.epic_from_plan_anchor(repo=repo, topic=topic) is None


def test_epic_from_plan_anchor_ignores_all_closed_ledger_epics(*, tmp_path, monkeypatch):
    repo = tmp_path / "ledger-binder"
    topic = "ledger-only"
    _ = (repo / "plan" / topic).mkdir(parents=True)

    def fake_run(argv, **_kwargs):
        return subprocess.CompletedProcess(
            args=argv,
            returncode=0,
            stdout=json.dumps(
                [
                    {
                        "id": "overseer-first",
                        "issue_type": "epic",
                        "status": "closed",
                        "spec_id": "plan:ledger-only",
                    },
                    {
                        "id": "overseer-second",
                        "issue_type": "epic",
                        "status": "closed",
                        "metadata": {"plan_slug": topic},
                    },
                ]
            ),
            stderr="",
        )

    monkeypatch.setattr(_registry_epic.subprocess, "run", fake_run)

    assert registry.epic_from_plan_anchor(repo=repo, topic=topic) is None


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
        for track in registry.read_valid_mapping(store_path=store)
    }
    assert tracks[("anchored", "alpha")].epic == "overseer-pfpfty"
    assert tracks[("unanchored", "beta")].epic is None
    assert tracks[("missing", "gamma")].epic is None


def test_read_mapping_rewrites_plan_handoff_resume_overrides_to_ledger_epics(*, tmp_path):
    store = tmp_path / "map.jsonl"
    store.write_text(
        json.dumps(
            {
                "topic": "alpha",
                "repo": "/data/projects/livespec-overseer",
                "resume": (
                    "read /data/projects/livespec-overseer/plan/alpha/handoff.md " "and follow it"
                ),
                "epic": "overseer-alpha",
                "added_at": "keep",
            }
        )
        + "\n"
        + json.dumps(
            {
                "topic": "beta",
                "repo": "/data/projects/livespec",
                "resume": "read /data/projects/livespec/plan/beta/supervisor-handoff.md",
                "epic": "livespec-beta",
            }
        )
        + "\n"
        + json.dumps(
            {
                "topic": "gamma",
                "repo": "/data/projects/livespec-dev-tooling",
                "resume": "operator-authored resume prompt",
                "epic": "dev-gamma",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    tracks = {track.topic: track for track in registry.read_valid_mapping(store_path=store)}
    assert tracks["alpha"].resume == (
        "resume plan epic overseer-alpha in repository /data/projects/livespec-overseer; "
        "read its ledger-held plan state"
    )
    assert tracks["beta"].resume == (
        "resume plan epic livespec-beta in repository /data/projects/livespec; "
        "read its ledger-held plan state"
    )
    assert tracks["gamma"].resume == "operator-authored resume prompt"

    rows = [json.loads(line) for line in store.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["resume"] == tracks["alpha"].resume
    assert rows[0]["added_at"] == "keep"
    assert rows[1]["resume"] == tracks["beta"].resume
    assert rows[2]["resume"] == "operator-authored resume prompt"
    assert "handoff.md" not in store.read_text(encoding="utf-8")


def test_read_mapping_clears_plan_handoff_resume_override_without_epic(*, tmp_path):
    store = tmp_path / "map.jsonl"
    store.write_text(
        json.dumps(
            {
                "topic": "alpha",
                "repo": "/data/projects/livespec-overseer",
                "resume": (
                    "read /data/projects/livespec-overseer/plan/alpha/handoff.md " "and follow it"
                ),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    tracks = registry.read_valid_mapping(store_path=store)
    assert tracks[0].resume is None

    rows = [json.loads(line) for line in store.read_text(encoding="utf-8").splitlines()]
    assert "resume" not in rows[0]
    assert "handoff.md" not in store.read_text(encoding="utf-8")
