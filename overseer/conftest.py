"""Test bootstrap for the host-only overseer modules.

These beside-tests live next to their modules rather than in the product
``tests/`` tree, but they ARE collected by an ordinary run: ``testpaths`` in
pyproject.toml names both ``overseer`` and ``tests``. To run only this tier:

    uv run pytest overseer/ -q

Adding this directory to ``sys.path`` lets ``import registry`` / ``import
signals`` resolve when pytest collects the beside-tests.
"""

import sys
from pathlib import Path

_HERE = str(Path(__file__).parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
