"""Import-path setup for foreman vendored dependencies."""

from __future__ import annotations

import sys
from pathlib import Path

__all__: list[str] = ["VENDOR_PATHS_INSTALLED"]

_HERE = Path(__file__).resolve().parent
for path in (_HERE.parent, _HERE / "_vendor"):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

VENDOR_PATHS_INSTALLED = True
