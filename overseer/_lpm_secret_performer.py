"""Descriptor-only local secret typing and credential persistence effects."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Protocol

__all__: list[str] = [
    "DescriptorSecretPerformer",
]


class DescriptorTyper(Protocol):
    def __call__(self, *, element_handle: str, descriptor: int) -> bool:
        """Type bytes from one descriptor without returning or recording them."""
        ...


class DescriptorPersister(Protocol):
    def __call__(self, *, descriptor: int) -> bool:
        """Persist bytes from one descriptor without returning or recording them."""
        ...


@dataclass(frozen=True, kw_only=True)
class DescriptorSecretPerformer:
    """Consume secret descriptors and expose only closed secret-free outcomes."""

    type_descriptor: DescriptorTyper = field(repr=False)
    persist_descriptor: DescriptorPersister = field(repr=False)

    def type_login_material(self, *, element_handle: str, descriptor: int) -> dict[str, object]:
        """Apply descriptor-held login material and close the caller's descriptor."""
        try:
            completed = self.type_descriptor(
                element_handle=element_handle,
                descriptor=descriptor,
            )
        finally:
            os.close(descriptor)
        return _outcome(completed=completed)

    def persist_token(self, *, descriptor: int) -> dict[str, object]:
        """Persist descriptor-held token bytes and close the caller's descriptor."""
        try:
            completed = self.persist_descriptor(descriptor=descriptor)
        finally:
            os.close(descriptor)
        return _outcome(completed=completed)


def _outcome(*, completed: bool) -> dict[str, object]:
    return {"version": 1, "status": "ok" if completed else "unavailable"}
