"""Momentum / score normalization should survive ROI outliers."""

from app.services.ranking import _normalize, _robust_bounds


def test_robust_bounds_ignore_extreme_roi_outlier():
    rois = [1.4, 20.0, 32.0, 55.0, 74.0, 178.0, 193.0, 266_816.0]
    low, high = _robust_bounds(rois)
    assert high < 10_000
    mid = _normalize(55.0, low, high)
    assert mid > 10.0
    top = _normalize(193.0, low, high)
    assert top >= mid


def test_robust_bounds_many_ties_plus_outlier():
    rois = [40.0] * 40 + [1.4, 20.0, 55.0, 193.0, 266_816.0]
    low, high = _robust_bounds(rois)
    assert high < 10_000
    assert _normalize(55.0, low, high) > 5.0


def test_robust_bounds_single_value():
    low, high = _robust_bounds([12.0])
    assert low == 12.0
    assert high == 12.0
    assert _normalize(12.0, low, high) == 50.0
