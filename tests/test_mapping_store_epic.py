"""Assignment-time mapping epic population."""

import registry
import supervisor
from test_supervisor_builders import isolate_store, make_plan

__all__: list[str] = []


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
