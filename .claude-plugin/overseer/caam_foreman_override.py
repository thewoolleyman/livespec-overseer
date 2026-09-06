"""Compatibility wrapper for the kept bucket-1 caam foreman consumer surface.

The foreman seat itself is retired, but one name-matched module remains because
bucket-1 caam code still imports its shared scoped-model constants and detection
helper. The real implementation lives in :mod:`caam_scoped_model`.
"""

from __future__ import annotations

from caam_scoped_model import OBSERVED_MODELS_KEY as OBSERVED_MODELS_KEY
from caam_scoped_model import SCOPED_MODEL as SCOPED_MODEL
from caam_scoped_model import WANTED_MODELS as WANTED_MODELS
from caam_scoped_model import scoped_model_pinned as scoped_model_pinned

__all__: list[str] = [
    "OBSERVED_MODELS_KEY",
    "SCOPED_MODEL",
    "WANTED_MODELS",
    "scoped_model_pinned",
]
