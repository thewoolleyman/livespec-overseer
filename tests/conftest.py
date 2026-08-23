"""Test bootstrap for the top-of-pyramid `tests/` tree.

The supervision package uses BARE sibling imports (`overseer/registry.py` does
`import jsonio`, not `from . import jsonio`), so it resolves only with the
package directory itself on `sys.path`. The beside-tests get that from
`overseer/conftest.py`; collecting from `tests/` reaches the same modules by a
different route, so it needs the same insertion.

Without this, `from overseer import registry` fails at import with
`ModuleNotFoundError: No module named 'jsonio'` — the package imports fine as a
package only because something already put its directory on the path.
"""

import os
import sys
from pathlib import Path

import pytest

_PACKAGE_DIR = str(Path(__file__).resolve().parent.parent / "overseer")
if _PACKAGE_DIR not in sys.path:
    sys.path.insert(0, _PACKAGE_DIR)


@pytest.fixture(autouse=True)
def fake_claude_on_path(
    *, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    claude = tmp_path_factory.mktemp("fake-claude-bin") / "claude"
    claude.parent.mkdir(exist_ok=True)
    claude.write_text("#!/bin/sh\n", encoding="utf-8")
    claude.chmod(0o755)
    path = os.environ.get("PATH", "")
    monkeypatch.setenv("PATH", f"{claude.parent}{os.pathsep}{path}" if path else str(claude.parent))
