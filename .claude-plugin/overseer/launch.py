"""Run this plugin's own ``overseer`` entry point, never the caller's checkout.

MEASURED 2026-10-14 ~05:03Z (work-item overseer-uzvcbn.2). Just after v5.28.3
shipped, the overseer bottom pane ran the 5.28.3 plugin's
``bin/overseer-start`` -- which was ``exec python3 -m overseer.start`` with
``PYTHONPATH=$PLUGIN_ROOT`` -- while the operator's current directory was
``/data/projects/livespec-overseer``. CPython's ``-m`` puts the CURRENT
DIRECTORY at ``sys.path[0]``, AHEAD of every ``PYTHONPATH`` entry, so the
CHECKOUT's ``overseer`` package won the import. Its ``version.json`` still read
5.28.2, one commit behind the release, so :func:`runtime_prefix.runtime_prefix`
chose ``runtime/5.28.2`` -- a prefix that already existed -- and the daemon
started from the PRE-FIX build and had to be stopped. The argv named the 5.28.3
plugin cache throughout, which is why no argv assertion could see this; the only
wrong thing was which package the process imported.

The overseer's bottom pane naturally sits inside this repository, so every
release AHEAD of the primary checkout was silently not adopted by a bootstrap
run there.

``python3 -P`` and ``PYTHONSAFEPATH=1`` say exactly this to CPython, and both
arrived in 3.11; ``pyproject.toml`` requires 3.10.16 and ``.python-version`` pins
it, so a shipped launcher cannot reach for either. Running a FILE inside the
plugin can, and needs no interpreter version at all: CPython puts THAT FILE's own
directory at ``sys.path[0]``, so the caller's directory never enters the import
path. This module is that file. The launchers exec it instead of ``-m``, and it
puts its own plugin root -- resolved from ``__file__``, never from the
environment -- at the front of the import path before running the module they
name.

Deliberately thin and stdlib-only: it runs BEFORE the package it launches, so it
imports no sibling of that package.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path
from typing import Protocol

__all__: list[str] = [
    "ModuleRunner",
    "main",
]


class ModuleRunner(Protocol):
    """Run a module as ``__main__`` -- the :func:`runpy.run_module` call shape.

    ``mod_name`` is POSITIONAL because this seam is declared by the STDLIB rather
    than by this package: ``runpy.run_module`` is the function bound to it on the
    shipped path, and a seam we do not own keeps its own calling convention -- the
    same asymmetry ``_seams`` records for ``time.sleep``, ``shutil.which`` and
    ``subprocess.run``.
    """

    def __call__(self, mod_name: str, /, *, run_name: str, alter_sys: bool) -> object: ...


def main(
    *,
    argv: list[str],
    import_path: list[str],
    run_module: ModuleRunner = runpy.run_module,
) -> int:
    """Run the module named by ``argv[1]`` as ``__main__`` out of this plugin root.

    ``argv`` and ``import_path`` are the process's own ``sys.argv`` and
    ``sys.path`` on the shipped path, and both are consumed IN PLACE. The plugin
    root goes to the FRONT of the import path, so the named module and every
    sibling it imports resolve inside this plugin; the module name is REMOVED
    from ``argv``, so that module parses exactly the operator's own arguments --
    the vector ``python3 -m <module>`` would have handed it.

    The insert is UNCONDITIONAL, matching the package initializer's own
    bootstrap: this process launches one module and exits, so there is nothing a
    guard would protect against, and a guard would leave one branch unexercised
    under this repo's 100%-branch floor.

    Returns 0 only if ``run_module`` returns at all. Every module the launchers
    name ends in ``raise SystemExit(main())``, so on the shipped path that
    exception propagates straight through here and carries the module's own exit
    status out to the operator's shell.
    """
    import_path.insert(0, str(Path(__file__).resolve().parent.parent))
    module_name = argv.pop(1)
    _ = run_module(module_name, run_name="__main__", alter_sys=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(argv=sys.argv, import_path=sys.path))
