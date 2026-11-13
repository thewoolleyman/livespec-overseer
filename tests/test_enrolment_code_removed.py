"""Guard that the enrolment code the ssh-push revision left unspecified is gone.

SPECIFICATION v099 replaced enrolled-host HTTPS pull (enrolment, a per-host
enrolment credential, a host client) with delivery by ssh PUSH from the
credential-rotation role holder. Nothing in the specification calls for an
enrolment command or an enrolment registry any more, so neither ships
(work-item overseer-w5h24j, plan central-credential-service). The push service
keeps the one thing it borrowed from the registry module, a lock serialising
its delivery sequence, as a lock of its own.
"""

from __future__ import annotations

import re
from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "overseer"
CARRIER = ROOT / ".claude-plugin" / "overseer"

REMOVED_MODULES = ("caam_delivery_enrol", "caam_delivery_registry")

REMOVED_PATHS = (
    *(PACKAGE / f"{name}.py" for name in REMOVED_MODULES),
    *(CARRIER / f"{name}.py" for name in REMOVED_MODULES),
    ROOT / "tests" / "integration" / "test_enrolment_registry.py",
)


def test_the_enrolment_modules_and_their_test_are_deleted() -> None:
    assert [str(path.relative_to(ROOT)) for path in REMOVED_PATHS if path.exists()] == []


def test_no_shipped_module_imports_the_enrolment_code() -> None:
    pattern = re.compile(rf"^\s*(?:import|from)\s+(?:overseer\.)?({'|'.join(REMOVED_MODULES)})\b")
    offenders = sorted(
        str(path.relative_to(ROOT))
        for directory in (PACKAGE, CARRIER)
        for path in directory.glob("*.py")
        if any(pattern.match(line) for line in path.read_text(encoding="utf-8").splitlines())
    )
    assert offenders == []


def test_no_caam_delivery_enrol_console_script_remains() -> None:
    # `tomllib` is stdlib only from 3.11 and this project supports 3.10.16, so the
    # one table this test needs is read directly, as the foreman-removal guard does.
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    section = re.search(r"^\[project\.scripts\]\s*$(.*?)(?=^\[)", text, re.MULTILINE | re.DOTALL)
    assert section is not None, "pyproject.toml has no [project.scripts] table"
    assert [line for line in section.group(1).splitlines() if "enrol" in line] == []
