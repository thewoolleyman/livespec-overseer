"""Every declared console script must import from an INSTALLED package.

WHY THIS TEST EXISTS AND WHY IT LOOKS EXPENSIVE. The defect it guards
(overseer-tdfe.28) is invisible to every other test in this repo by
construction: modules under `overseer/` import their siblings as TOP-LEVEL
modules (`import jsonio`, `from foreman_act_dispatch import ...`), and a flat
checkout already has that directory on `sys.path`. So the whole existing test
population exercises the layout that HIDES the defect. A test that exercises
the entrypoints in the checkout is a check that cannot fail.

The only discriminating instrument is to BUILD the package, INSTALL it into a
throwaway venv, and resolve the entrypoints from there. That is what the
fixture below does, and it is why this module spawns subprocesses.

ENUMERATED FROM THE TREE, NOT HARDCODED. The inventory is read from
`pyproject.toml`'s `[project.scripts]`, which is the single source of truth that
actually ships the entrypoints. An earlier draft of this harness hardcoded a
ten-entry table; within seven days the tree had grown to fourteen scripts, two
of the new ones were broken and unlisted, and one entry the table asserted was
healthy had regressed. A hardcoded inventory of a growing tree is a measurement
with an expiry date.

WHY THE PROBE IS AN IMPORT RATHER THAN `--help`. The row's criterion (1) is
worded as "responds to --help with exit 0", and that was the natural proxy for
"the module imported". It is not a safe one here: `caam-anthropic-loop` does not
handle `--help` at all and falls through to its real main(), which reaches out
to live Anthropic usage endpoints. Probing it that way made this suite depend on
a network round-trip -- it passed when those reads succeeded and failed with a
TimeoutError when they did not, which is a flaky gate rather than a measurement.
Importing each script's DECLARED target module is both hermetic and strictly
more discriminating: it isolates the import failure this defect is about from
whatever each script's argument handling happens to do. The `--help` behaviour
of `caam-anthropic-loop` is a separate defect and is tracked on its own row.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# The sole declared console script whose module CANNOT import from a plain
# install, and the module whose absence stops it. This is a DIFFERENT defect
# from the sibling-import one this file guards: `overseer-scan-homelab-charters`
# imports `livespec_dev_tooling`, which pyproject declares only in the `dev`
# dependency group, so a runtime install legitimately lacks it. It is listed
# here rather than silently skipped, and the test below asserts it fails for
# EXACTLY this reason -- a one-directional exclusion would hide the day it
# starts failing for another.
KNOWN_NON_RUNTIME_ENTRYPOINTS: dict[str, str] = {
    "overseer-scan-homelab-charters": "livespec_dev_tooling",
}

# A parse that silently yielded nothing would make every parametrized test below
# vanish, and a suite with no cases passes. Anchor the floor to the inventory
# measured when this harness was written so a pyproject reshuffle fails loudly.
_MINIMUM_DECLARED_SCRIPTS = 10


def _declared_console_scripts() -> dict[str, str]:
    """Map each `[project.scripts]` name to the module its entrypoint imports.

    `tomllib` is stdlib only from 3.11 and this project supports 3.10.16, so the
    one simple table this test needs is read directly rather than adding a
    parser dependency to reach it.
    """
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    section = re.search(
        r"^\[project\.scripts\]\s*$(.*?)(?=^\[)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert section is not None, "pyproject.toml has no [project.scripts] table"
    scripts: dict[str, str] = {}
    for line in section.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name, separator, target = stripped.partition("=")
        assert separator, f"unparsable [project.scripts] entry: {stripped!r}"
        module, _colon, _attr = target.strip().strip('"').partition(":")
        scripts[name.strip().strip('"')] = module
    assert len(scripts) >= _MINIMUM_DECLARED_SCRIPTS, (
        f"parsed only {len(scripts)} console scripts from [project.scripts]; "
        f"expected at least {_MINIMUM_DECLARED_SCRIPTS}. A parse regression here "
        "would empty this suite silently, so it fails instead."
    )
    return scripts


DECLARED_CONSOLE_SCRIPTS = _declared_console_scripts()


@pytest.fixture(scope="module")
def installed_package_python(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build and install this package into a throwaway venv; return its python."""
    uv = shutil.which("uv")
    if uv is None:  # pragma: no cover - environment-dependent
        pytest.skip("uv is not on PATH; cannot build an installed-package venv")
    venv_dir = tmp_path_factory.mktemp("installed-console-entrypoints")
    python = venv_dir / "bin" / "python"
    subprocess.run(  # noqa: S603
        [
            uv,
            "venv",
            str(venv_dir),
            "--python",
            f"{sys.version_info.major}.{sys.version_info.minor}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(  # noqa: S603
        [uv, "pip", "install", "--python", str(python), str(REPO_ROOT)],
        check=True,
        capture_output=True,
        text=True,
    )
    return python


def _import_module(*, python: Path, module: str) -> subprocess.CompletedProcess[str]:
    """Import `module` in the installed venv, with the checkout kept off sys.path.

    `-I` isolates the interpreter: it ignores PYTHONPATH and the user site
    directory, so the flat checkout cannot leak back in and re-hide the defect.
    It also stops an inherited COVERAGE_PROCESS_START from instrumenting the
    child, whose `.coverage.*` writes would race the parent run.
    """
    return subprocess.run(  # noqa: S603
        [str(python), "-I", "-c", f"import {module}"],
        check=False,
        cwd=python.parent,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("script", sorted(DECLARED_CONSOLE_SCRIPTS))
def test_declared_console_script_imports_from_installed_package(
    *, installed_package_python: Path, script: str
) -> None:
    """Each declared entrypoint's module imports cleanly once installed."""
    if script in KNOWN_NON_RUNTIME_ENTRYPOINTS:
        pytest.skip(f"{script} is covered by its own controlled test")
    module = DECLARED_CONSOLE_SCRIPTS[script]
    completed = _import_module(python=installed_package_python, module=module)
    assert completed.returncode == 0, (
        f"{script} resolves to {module}, which must import from an INSTALLED "
        f"package and not only from the flat checkout that hides sibling-import "
        f"breakage.\nstderr:\n{completed.stderr}"
    )


@pytest.mark.parametrize(
    ("script", "missing_module"), sorted(KNOWN_NON_RUNTIME_ENTRYPOINTS.items())
)
def test_known_non_runtime_entrypoint_fails_only_for_its_declared_reason(
    *, installed_package_python: Path, script: str, missing_module: str
) -> None:
    """The excluded entrypoint must fail for its declared reason and no other.

    This is the control on the exclusion above. If the missing dependency is
    promoted to a runtime dependency the module starts importing and this test
    fails, prompting its removal from the exclusion; if it breaks for a NEW
    reason -- a sibling import, say -- this test fails rather than absorbing it.
    """
    module = DECLARED_CONSOLE_SCRIPTS[script]
    completed = _import_module(python=installed_package_python, module=module)
    assert completed.returncode != 0, (
        f"{script} now imports from an installed package. Remove it from "
        "KNOWN_NON_RUNTIME_ENTRYPOINTS so it is gated like every other script."
    )
    assert f"No module named '{missing_module}'" in completed.stderr, (
        f"{script} is excluded only because {missing_module} is a dev-group "
        f"dependency, but it failed for a different reason.\n"
        f"stderr:\n{completed.stderr}"
    )
