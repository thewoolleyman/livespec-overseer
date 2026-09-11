"""The environment a daemon hands the immutable runtime it switches into.

Release adoption and rollback both replace the daemon's process image with a
SELECTED immutable runtime, whose `overseer` package is installed non-editable
inside that runtime's own venv. The inherited environment is not neutral about
that selection: CPython searches `PYTHONPATH` AHEAD of a venv's site-packages,
so a daemon launched from the plugin cache or from a checkout hands its
successor an import path that shadows the very runtime it just chose.

MEASURED 2026-09-11, work-item overseer-xgfhuf. After release v5.4.10 the acting
top-pane daemon execed the correct
`~/.local/share/livespec-overseer/runtime/9e6d115f.../venv/bin/overseerd` while
still carrying
`PYTHONPATH=~/.claude/plugins/cache/livespec-overseer/livespec-overseer/ae7e9dd9b9ae`
— the PRIOR v5.4.9 plugin cache, exported by the plugin's own `bin/overseerd`
launcher. Every successor therefore imported the OLD package, published a status
snapshot still naming version 5.4.9 and that cache as its `package_dir`, found
itself out of date against the release, and execed again. The pid and the top
pane never changed; the daemon instance id changed every few seconds.

THE ARGV WAS CORRECT THROUGHOUT, which is why this layer exists at all: the
executable named on the command line had nothing to do with the package the
successor imported. A switch is only a switch if the environment agrees with it.

So the import path is DROPPED rather than filtered. The runtime is a
non-editable `--no-deps` install of one stdlib-only package; it needs no import
path of its own, and an inherited one can only ever shadow it. Nothing else is
touched — the daemon's tmux coordinates, credentials, locale and telemetry
settings are the operator's environment and are handed on verbatim.
"""

from __future__ import annotations

from collections.abc import Mapping

__all__: list[str] = ["IMPORT_PATH_VAR", "runtime_exec_env"]

IMPORT_PATH_VAR = "PYTHONPATH"


def runtime_exec_env(*, env: Mapping[str, str]) -> dict[str, str]:
    """`env` minus the one variable that could override the selected runtime's package."""
    return {name: value for name, value in env.items() if name != IMPORT_PATH_VAR}
