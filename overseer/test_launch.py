"""Beside-tests for the shipped launchers' import-path bootstrap."""

from __future__ import annotations

from pathlib import Path

import launch

__all__: list[str] = []


def test_main_runs_the_named_module_as_main_from_this_plugin_root() -> None:
    calls: list[tuple[str, str, bool]] = []
    argv = ["/plugin/overseer/launch.py", "overseer.start", "--warn-percent", "30"]
    import_path = ["/plugin/overseer", "/some/inherited/entry"]

    rc = launch.main(
        argv=argv,
        import_path=import_path,
        run_module=lambda mod_name, *, run_name, alter_sys: calls.append(
            (mod_name, run_name, alter_sys)
        ),
    )

    assert rc == 0
    assert calls == [("overseer.start", "__main__", True)]
    # The operator's own arguments, with the module name consumed -- exactly the
    # vector `python3 -m overseer.start --warn-percent 30` would have produced.
    assert argv == ["/plugin/overseer/launch.py", "--warn-percent", "30"]


def test_the_plugin_root_is_resolved_from_this_file_and_wins_over_inherited_entries() -> None:
    """Nothing in the environment chooses the root, and nothing inherited precedes it."""
    import_path = ["/a/prior/plugin/cache", "/a/checkout"]

    _ = launch.main(
        argv=["/plugin/overseer/launch.py", "overseer.daemon"],
        import_path=import_path,
        run_module=lambda mod_name, *, run_name, alter_sys: None,
    )

    assert import_path[0] == str(Path(launch.__file__).resolve().parent.parent)
    assert import_path[1:] == ["/a/prior/plugin/cache", "/a/checkout"]
