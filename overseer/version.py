"""Release version for the overseer control-plane tool.

The version LITERAL lives in ``version.json`` beside this module, not in this
file, and that placement is load-bearing rather than stylistic.

``source_trees = ["overseer"]`` (armed 2026-07-27, `overseer-bg2.4`) puts every
``.py`` under this package into `check-red-green-replay`'s product-implementation
bucket. release-please cannot author a Red->Green pair or a green-verified leg,
so any release commit that rewrote a ``.py`` here failed the gate and blocked the
release PR — observed on PR #180, commit `a54e233`. Every other fleet member
already arms ``source_trees`` and generates NO ``.py``; this repo was the sole
outlier. Keeping the generated literal in a non-``.py`` sibling restores that
shape WITHOUT weakening the gate: `check-red-green-replay` still holds every
hand-authored module here to the full ritual.

Read as data rather than imported so the module works in BOTH launch modes —
the installed console script and the in-tree executables, which pin their own
directory onto ``sys.path`` and therefore have no distribution metadata to read.
"""

from __future__ import annotations

import json
from pathlib import Path

__all__: list[str] = ["APP_VERSION"]

APP_VERSION: str = json.loads(
    (Path(__file__).resolve().parent / "version.json").read_text(encoding="utf-8")
)["version"]
