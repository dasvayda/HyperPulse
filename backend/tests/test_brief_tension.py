from app.services.brief_report import price_vs_book_tension


def test_tension_fires_on_down_price_and_long_book():
    text = price_vs_book_tension(-2.1, 66.0)
    assert text is not None
    assert "long-heavy" in text
    assert "-2.1" in text


def test_tension_none_when_move_small():
    assert price_vs_book_tension(-0.3, 66.0) is None


def test_tension_none_when_book_balanced():
    assert price_vs_book_tension(-2.1, 50.0) is None


def test_tension_none_when_same_direction():
    assert price_vs_book_tension(-2.1, 38.0) is None
