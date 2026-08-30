"""Importable package for the livespec overseer control-plane tool."""

import sys
from pathlib import Path

# Modules in this package import their siblings as TOP-LEVEL names -- `import
# jsonio`, `from foreman_act_dispatch import ...` -- across 227 files. In a flat
# checkout that works because the checkout puts this directory on `sys.path`; in
# an INSTALLED package nothing does, so five of the ten console scripts crashed
# at import (overseer-tdfe.28; nine of fourteen by the time it was fixed).
#
# This bootstrap is the package-level replacement for the per-module preambles
# four modules already carried. It is deliberately UNCONDITIONAL: guarding it
# with `if _PACKAGE_DIR not in sys.path` leaves one branch unexecuted under this
# repo's 100%-branch coverage floor, and `__init__` runs once per interpreter,
# so there is nothing to guard against.
sys.path.insert(0, str(Path(__file__).resolve().parent))

__all__: list[str] = []
