"""Load the adjacent product package, then run one isolated manager command."""

from __future__ import annotations

import importlib.util
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType
from typing import Final, cast

__all__: list[str] = [
    "INTERNAL_BUG_LINE",
    "load_product_package",
    "main",
    "package_root",
    "run",
]

_PACKAGE_NAME: Final = "overseer"
_INTERNAL_BUG_STATUS: Final = 70
_ROLE_VECTOR_LENGTH: Final = 2
_FIRST_INHERITED_DESCRIPTOR: Final = 3
_ROLE_EXEC_MARKER: Final = "LIVESPEC_LPM_EXECUTED_ROLE"
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
    if len(arguments) == _ROLE_VECTOR_LENGTH and arguments[0] == "--credential-role":
        return _dispatch_role(role_name=arguments[1])
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


def _dispatch_role(*, role_name: str) -> int:
    from _lpm_canonical import canonical_json_text, parse_canonical_json
    from _lpm_launcher import pre_exec_failure_object
    from _lpm_role_child import ClosedRoleInput, HostProcessOS, launch_credential_role
    from _lpm_role_service import role_result
    from _lpm_roles import CredentialRole, PackagedCompanion, credential_role

    role = cast("CredentialRole", credential_role(name=role_name))
    if _needs_role_exec(variable=role.variable):
        os.environ[_ROLE_EXEC_MARKER] = role.name
        refusal = launch_credential_role(
            role_input=ClosedRoleInput(
                role_name=role.name,
                key_description=role.key_description,
                descriptors=role.descriptors,
                descriptor_fds=_inherited_descriptors(names=role.descriptors),
            ),
            companion=PackagedCompanion(
                python_executable=str(Path(sys.executable).resolve()),
                packaged_companion=str(Path(__file__).resolve()),
            ),
            environ=os.environ,
            process_os=HostProcessOS(),
        )
        result = refusal.failure_object
    else:
        parsed = parse_canonical_json(text=sys.stdin.read())
        result = parsed.map(
            lambda request: role_result(
                role_name=role.name,
                request=request,
                environ=os.environ,
                lock_descriptor=next(
                    iter(_inherited_descriptors(names=role.descriptors).values()), None
                ),
            )
        ).value_or(pre_exec_failure_object(role_name=role.name))
    encoded = canonical_json_text(value=result).unwrap()
    _write_line(line=encoded)
    return 0


def _inherited_descriptors(*, names: tuple[str, ...]) -> dict[str, int]:
    descriptors: list[int] = []
    for candidate in os.listdir("/proc/self/fd"):
        if candidate.isdigit() and int(candidate) >= _FIRST_INHERITED_DESCRIPTOR:
            descriptor = int(candidate)
            try:
                _ = os.fstat(descriptor)
            except OSError:
                continue
            descriptors.append(descriptor)
    return _descriptor_mapping(names=names, descriptors=tuple(sorted(descriptors)))


def _descriptor_mapping(*, names: tuple[str, ...], descriptors: tuple[int, ...]) -> dict[str, int]:
    try:
        return dict(zip(names, descriptors, strict=True))
    except ValueError:
        return {}


def _needs_role_exec(*, variable: str | None) -> bool:
    return (variable or _ROLE_EXEC_MARKER) not in os.environ


def _write_line(*, line: str) -> None:
    sys.path.insert(0, str(package_root()))
    import streams

    streams.write_stdout(text=f"{line}\n")


if __name__ == "__main__":
    raise SystemExit(main())
