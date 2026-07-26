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

import sys
from pathlib import Path

_PACKAGE_DIR = str(Path(__file__).resolve().parent.parent / "overseer")
if _PACKAGE_DIR not in sys.path:
    sys.path.insert(0, _PACKAGE_DIR)
