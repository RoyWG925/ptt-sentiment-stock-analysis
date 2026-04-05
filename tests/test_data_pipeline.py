# -*- coding: utf-8 -*-
"""Unit tests for src/pipeline/data_pipeline.py"""
import pytest
import pandas as pd

from src.pipeline.data_pipeline import fix_timestamp


@pytest.mark.parametrize("ts_str, expected_date", [
    ("03/27 08:30", "2025-03-27"),
    ("04/16 23:59", "2025-04-16"),
])
def test_fix_timestamp_mm_dd_format(ts_str, expected_date):
    """fix_timestamp should parse MM/DD HH:MM format into a datetime with the hardcoded year."""
    result = fix_timestamp(ts_str)
    assert not pd.isnull(result)
    assert str(result.date()) == expected_date


def test_fix_timestamp_iso_format():
    """fix_timestamp should handle ISO 8601 strings."""
    result = fix_timestamp("2025-04-03T14:00:00")
    assert not pd.isnull(result)
    assert result.year == 2025
    assert result.month == 4
    assert result.day == 3


def test_fix_timestamp_invalid_returns_nat():
    """fix_timestamp should return NaT for unparseable input."""
    result = fix_timestamp("not-a-date")
    assert pd.isnull(result)


def test_fix_timestamp_non_string_returns_nat():
    """fix_timestamp should return NaT when passed a non-string."""
    assert pd.isnull(fix_timestamp(None))
    assert pd.isnull(fix_timestamp(12345))
