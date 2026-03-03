"""Tests for compute_docks_from_float helper."""

from zng_simulator.config.station import compute_docks_from_float


def test_basic_computation():
    # 750 fleet × 2 packs × 10% = 150 float packs / 5 stations = 30
    assert compute_docks_from_float(750, 2, 0.10, 5) == 30


def test_rounds_up():
    # 201 × 2 × 0.10 / 5 = 8.04 → ceil = 9
    assert compute_docks_from_float(201, 2, 0.10, 5) == 9


def test_exact_division():
    # 200 × 2 × 0.10 / 5 = 8.0 → exactly 8
    assert compute_docks_from_float(200, 2, 0.10, 5) == 8


def test_minimum_one():
    # Very small float → should still return at least 1
    assert compute_docks_from_float(1, 1, 0.001, 100) == 1


def test_zero_float_returns_one():
    # Edge case: 0% float → max(1, ceil(0)) = 1
    assert compute_docks_from_float(100, 2, 0.0, 5) == 1


def test_large_fleet():
    # 10000 × 2 × 0.50 / 10 = 1000
    assert compute_docks_from_float(10000, 2, 0.50, 10) == 1000


def test_single_station():
    # 100 × 2 × 0.20 / 1 = 40
    assert compute_docks_from_float(100, 2, 0.20, 1) == 40
