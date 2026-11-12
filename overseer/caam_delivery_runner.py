"""Change-driven, in-process delivery service for the role holder."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

import caam_delivery_service

__all__: list[str] = ["DeliveryService"]


class DeliveryService:
    """Issue changed deliveries and release local clients waiting for a later sequence.

    P1-C supplies the transport and authentication boundary. Keeping this interface
    in-process now makes the later server a thin adapter rather than a second
    delivery implementation, and makes a waiting request observable without
    coupling a rotation pass to this process.
    """

    def __init__(
        self,
        *,
        home: Path,
        now: Callable[[], float],
        confirm_account: Callable[..., str | None],
    ) -> None:
        self._home = home
        self._now = now
        self._confirm_account = confirm_account
        self._changed = threading.Condition()

    def refresh(self) -> caam_delivery_service.Delivery | None:
        """Issue the next valid delivery, then wake clients waiting for one."""
        delivery = caam_delivery_service.issue_delivery(
            home=self._home,
            now=self._now(),
            confirm_account=self._confirm_account,
        )
        with self._changed:
            self._changed.notify_all()
        return delivery

    def wait_for_delivery(
        self, *, sequence: int, timeout: float
    ) -> caam_delivery_service.Delivery | None:
        """Wait at most ``timeout`` for a delivery beyond ``sequence``."""
        with self._changed:
            _ = self._changed.wait_for(
                lambda: _later_delivery(home=self._home, sequence=sequence) is not None,
                timeout=timeout,
            )
            return _later_delivery(home=self._home, sequence=sequence)


def _later_delivery(*, home: Path, sequence: int) -> caam_delivery_service.Delivery | None:
    delivery = caam_delivery_service.load_current_delivery(home=home)
    return delivery if delivery is not None and delivery.sequence > sequence else None
