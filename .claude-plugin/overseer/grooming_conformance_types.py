"""Typed result models for grooming ledger conformance."""

from __future__ import annotations

from dataclasses import dataclass

from grooming_plan_budget import PlanBudgetResolution

__all__: list[str] = [
    "GroomingConformanceReport",
    "GroomingMeasurement",
    "GroomingStageReport",
    "InvariantCheck",
]


@dataclass(frozen=True, kw_only=True)
class InvariantCheck:
    key: str
    title: str
    status: str
    breaching_item_ids: tuple[str, ...]
    scanned_item_count: int
    scope: str
    reason: str = ""


@dataclass(frozen=True, kw_only=True)
class GroomingConformanceReport:
    repo: str
    scanned_item_count: int
    scanned_item_ids: tuple[str, ...]
    invariants: tuple[InvariantCheck, ...]


@dataclass(frozen=True, kw_only=True)
class GroomingMeasurement:
    repo: str
    open_item_ids: tuple[str, ...]
    untriaged_item_ids: tuple[str, ...]
    unparented_item_ids: tuple[str, ...]
    live_thread_slugs: tuple[str, ...]
    open_item_digest: str
    plan_budget: PlanBudgetResolution


@dataclass(frozen=True, kw_only=True)
class GroomingStageReport:
    measurement: GroomingMeasurement
    conformance: GroomingConformanceReport
