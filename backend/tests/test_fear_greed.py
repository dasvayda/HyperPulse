"""Fear & Greed fetch + schema smoke."""

import asyncio

import pytest

from app.models.schemas import FearGreedIndex
from app.services.fear_greed import _tone


def test_tone_mapping():
    assert _tone("Greed") is True
    assert _tone("Extreme Greed") is True
    assert _tone("Fear") is False
    assert _tone("Extreme Fear") is False
    assert _tone("Neutral") is None


def test_fetch_fear_greed_live():
    from app.services.fear_greed import fetch_fear_greed

    item = asyncio.run(fetch_fear_greed(force=True))
    if item is None:
        pytest.skip("CMC unreachable")
    assert isinstance(item, FearGreedIndex)
    assert 0 <= item.value <= 100
    assert item.classification
    assert item.source == "cmc"
