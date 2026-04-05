# -*- coding: utf-8 -*-
"""Unit tests for src/pipeline/thesis_stats.py"""
import pytest

from src.pipeline.thesis_stats import get_sig


@pytest.mark.parametrize("p_value, expected", [
    (0.001, "***"),
    (0.009, "***"),
    (0.01,  "**"),
    (0.049, "**"),
    (0.05,  "*"),
    (0.09,  "*"),
    (0.1,   ""),
    (0.5,   ""),
    (1.0,   ""),
])
def test_get_sig(p_value, expected):
    """get_sig should return the correct significance stars for p-values."""
    assert get_sig(p_value) == expected
