"""Regression coverage: a CLI `start` must not write into the real stamp sidecar."""

from pathlib import Path

import _registry_core
import registry
import supervisor
from test_supervisor_builders import idle_capture, isolate_store, make_plan
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def test_isolate_store_redirects_the_stamp_sidecar_away_from_the_real_home(
    *, tmp_path: Path, monkeypatch
) -> None:
    """`isolate_store` must redirect the stamp sidecar, not only the mapping store.

    FOUND IN A LIVE OPERATOR FILE, not in a test run: 120 of the 138 entries in
    ``~/.livespec-overseer-stamps.json`` were keyed by pytest temp directories that no
    longer existed, and every one carried exactly a launch statusline baseline and
    nothing else -- which is what identified the writer.

    The gap was LATENT. ``isolate_store`` redirected ``DEFAULT_STORE_PATH`` but not
    ``DEFAULT_STAMP_PATH``, and until a launch-time statusline baseline began being
    recorded on the START path (2026-08-21) no CLI ``start`` wrote a stamp at all, so
    an unredirected stamp path never showed. Both defaults are read as bare module
    globals by their resolvers, so both need the identical treatment.

    The assertion is on the RESOLVED default rather than on the home file's contents,
    so this states the property without depending on -- or touching -- whatever the
    developer's real sidecar happens to hold.
    """
    isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)

    resolved = _registry_core.resolve_stamp_store(stamp_path=None)

    assert tmp_path in resolved.parents, resolved
    assert Path.home() not in resolved.parents, resolved


def test_a_cli_start_leaves_no_stamp_outside_the_isolated_tmp_tree(
    *, tmp_path: Path, monkeypatch
) -> None:
    """End to end: the write that exposed the gap lands in the isolated tree.

    The unit above pins the resolver; this drives the actual CLI path that was
    polluting the real sidecar, so the guard covers the behavior and not merely the
    configuration it depends on.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture())
    monkeypatch.setattr(supervisor.tmuxio, "TmuxIO", lambda: fake)

    assert supervisor.main(argv=["start", "--force", "--repo", str(repo), "--topic", topic]) == 0

    assert tmp_path in _registry_core.resolve_stamp_store(stamp_path=None).parents
