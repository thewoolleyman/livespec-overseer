"""Repo-level mirror for the foreman session classifier beside-tests."""

from __future__ import annotations

from overseer import test_foreman_session_classifier as beside

__all__: list[str] = []


def test_foreman_session_classifier_is_a_closed_typed_result_surface():
    beside.test_foreman_session_classifier_is_a_closed_typed_result_surface()


def test_foreman_session_classifier_table():
    beside.test_foreman_session_classifier_table()
