"""The isolated manager companion: load the product package by absolute path, then run the command.

SPECIFICATION/non-functional-requirements.md fixes how this module reaches its own code: "Its
isolated companion MUST locate the installed product package root absolutely and load
`<package-root>/__init__.py` as module `overseer` through `importlib.util.spec_from_file_location`,
with `submodule_search_locations` exactly `[<package-root>]`. It MUST NOT add the containing
environment or site-packages directory to its import path before importing manager modules."

WHY AN ORDINARY `import overseer` WOULD BE WRONG HERE, AND WHY IT WOULD ALSO NOT WORK. The
bootstrap re-executes with `-I -S`, so there is no `sys.path` entry that could resolve `overseer`
at all: site-packages discovery is off and this script's own directory is kept off the path. That
is the point. SPECIFICATION/contracts.md requires the plugin executable to resolve its package
"only from `<plugin-root>/overseer/` ... and MUST NOT import a separately installed `overseer`",
and the only way to guarantee that is to load the package whose `__init__.py` sits beside THIS
file. A consumer's `PYTHONPATH` cannot repoint it, because there is no path lookup to repoint.

THE PACKAGE INITIALIZER IS WHAT MAKES THE SIBLING IMPORTS WORK. `overseer/__init__.py` inserts its
own directory on `sys.path`, so once it has executed, `import _lpm_commands` resolves to the module
beside it — the same mechanism every other console entry point in this package relies on, reached
here through an explicit load rather than an implicit one.

THE PRODUCT PACKAGE IS IMPORTED ONLY AFTER THE LOAD, which is why every manager import below is
function-local rather than at module scope. At module scope they would run before the package
existed in `sys.modules`, and `_lpm_commands` imports `overseer._vendor.returns`.

`spec_from_file_location` IS AN INJECTABLE MODULE ATTRIBUTE for the same reason the bootstrap's
`execv` is: a companion that cannot build a spec must answer `internal-bug`, and that is a rail no
real tree can reach, so it is substituted by this module's tests and by nothing else.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from types import ModuleType
from typing import Final

__all__: list[str] = [
    "INTERNAL_BUG_LINE",
    "INTERNAL_BUG_STATUS",
    "PACKAGE_NAME",
    "load_product_package",
    "main",
    "package_root",
    "run",
]

PACKAGE_NAME: Final = "overseer"
INTERNAL_BUG_STATUS: Final = 70

# The same literal the bootstrap carries, for the same reason: `_lpm_results` lives inside the
# package this function may have failed to load, so it cannot be the source of the message that
# reports that failure.
INTERNAL_BUG_LINE: Final = (
    '{"version":1,"status":"error","error_type":"internal-bug",'
    '"message":"the manager product package could not be loaded"}'
)

spec_from_file_location: Callable[..., object] = importlib.util.spec_from_file_location


def package_root() -> Path:
    """The product package directory this companion ships inside."""
    return Path(__file__).resolve().parent


def load_product_package(*, root: Path) -> ModuleType | None:
    """Load `<root>/__init__.py` as module `overseer`, or `None` when no spec can be built."""
    spec = spec_from_file_location(
        PACKAGE_NAME, root / "__init__.py", submodule_search_locations=[str(root)]
    )
    loader = getattr(spec, "loader", None)
    if spec is None or loader is None:
        return None
    module = importlib.util.module_from_spec(spec)  # pyright: ignore[reportArgumentType]
    sys.modules[PACKAGE_NAME] = module
    loader.exec_module(module)
    return module


def run(*, arguments: Sequence[str], root: Path) -> int:
    """Load the package beside `root`, resolve the real host, and run one manager command."""
    if load_product_package(root=root) is None:
        _ = sys.stdout.write(f"{INTERNAL_BUG_LINE}\n")
        return INTERNAL_BUG_STATUS
    return _dispatched(arguments=arguments)


def main() -> int:
    """The companion seam: real argv, the package beside this file, a real host."""
    return run(arguments=sys.argv[1:], root=package_root())


def _dispatched(*, arguments: Sequence[str]) -> int:
    """Run one command against the real host, presenting exactly one line and its exit status."""
    import os

    from _lpm_command_host import error_outcome
    from _lpm_commands import run_manager_command
    from _lpm_manager_host import FILESYSTEM_ROOT, manager_now, real_host

    from overseer._vendor.returns.result import Failure

    host = real_host(environ=os.environ, uid=os.geteuid(), root=FILESYSTEM_ROOT, now=manager_now())
    outcome = (
        error_outcome(error=host.failure())
        if isinstance(host, Failure)
        else run_manager_command(arguments=arguments, host=host.unwrap())
    )
    _ = sys.stdout.write(f"{outcome.stdout}\n")
    return outcome.exit_status


if __name__ == "__main__":
    raise SystemExit(main())
