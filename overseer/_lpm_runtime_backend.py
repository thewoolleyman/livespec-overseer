"""Production role-port identity assembled by the installed manager runtime."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import _lpm_role_service
from _lpm_config import ManagerConfig

_ = _lpm_role_service.__all__

__all__: list[str] = [
    "RolePorts",
]


@dataclass(frozen=True, kw_only=True)
class RolePorts:
    """The shared host facts used by every isolated credential role."""

    config: ManagerConfig
    owner_uid: int
    state_dir: Path
    environ: Mapping[str, str]
