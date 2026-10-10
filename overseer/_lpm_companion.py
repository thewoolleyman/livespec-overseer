"""Load the adjacent product package, then run one isolated manager command."""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType
from typing import Final

__all__: list[str] = [
    "INTERNAL_BUG_LINE",
    "load_product_package",
    "main",
    "package_root",
    "run",
]

_PACKAGE_NAME: Final = "overseer"
_INTERNAL_BUG_STATUS: Final = 70
INTERNAL_BUG_LINE: Final = (
    '{"version":1,"status":"error","error_type":"internal-bug",'
    '"message":"the manager product package could not be loaded"}'
)


def package_root() -> Path:
    """Return the package directory shipped beside this companion."""
    return Path(__file__).resolve().parent


def load_product_package(*, root: Path) -> ModuleType | None:
    """Load the adjacent initializer as the sole overseer package."""
    initializer = root / "__init__.py"
    if not initializer.is_file():
        return None
    spec = importlib.util.spec_from_file_location(
        _PACKAGE_NAME,
        initializer,
        submodule_search_locations=[str(root)],
    )
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[_PACKAGE_NAME] = module
    spec.loader.exec_module(module)
    return module


def run(*, arguments: Sequence[str], root: Path) -> int:
    """Load this carrier's package and dispatch one command through its runtime."""
    if load_product_package(root=root) is None:
        _write_line(line=INTERNAL_BUG_LINE)
        return _INTERNAL_BUG_STATUS
    return _dispatch(arguments=arguments)


def main() -> int:
    """Run with the real arguments and the package beside this file."""
    return run(arguments=sys.argv[1:], root=package_root())


def _dispatch(*, arguments: Sequence[str]) -> int:
    from _lpm_commands import run_manager_command
    from _lpm_manager_argv import manager_invocation
    from _lpm_runtime import runtime_for_host
    from _lpm_wire import error_outcome, render_outcome

    from overseer._vendor.returns.result import Failure

    parsed = manager_invocation(arguments=arguments)
    if isinstance(parsed, Failure):
        outcome = error_outcome(error=parsed.failure())
    else:
        runtime = runtime_for_host()
        if isinstance(runtime, Failure):
            outcome = error_outcome(error=runtime.failure())
        else:
            outcome = run_manager_command(arguments=arguments, runtime=runtime.unwrap())
    _write_line(line=render_outcome(outcome=outcome))
    return outcome.exit_status


def _write_line(*, line: str) -> None:
    sys.path.insert(0, str(package_root()))
    import streams

    streams.write_stdout(text=f"{line}\n")


if __name__ == "__main__":
    raise SystemExit(main())
