from datetime import date, timedelta

from app import gap, splits


def make_prices(start: str, closes: list[float], opens: list[float] | None = None) -> list[dict]:
    """Свечи по будним дням начиная со start."""
    d = date.fromisoformat(start)
    rows = []
    for i, c in enumerate(closes):
        while d.weekday() >= 5:
            d += timedelta(days=1)
        o = opens[i] if opens else c
        rows.append({"date": d.isoformat(), "open": o, "high": max(o, c), "low": min(o, c), "close": c, "volume": 1})
        d += timedelta(days=1)
    return rows


def test_cum_day_t1_registry_on_friday():
    # Реальный случай SBER 2025: реестр пт 18.07.2025, последний день с дивидендом — чт 17.07.
    prices = make_prices("2025-07-14", [318, 320, 321, 327.05, 309, 310, 311])
    ev = gap.compute_event(prices, "2025-07-18", 34.84)
    assert ev.cum_date == "2025-07-17"
    assert ev.ex_date == "2025-07-18"


def test_cum_day_t1_registry_on_weekend():
    # Реестр в воскресенье: расчёты в пятницу, значит купить нужно в четверг.
    prices = make_prices("2025-07-14", [100, 100, 100, 100, 90, 90])
    ev = gap.compute_event(prices, "2025-07-20", 10)
    assert ev.cum_date == "2025-07-17"


def test_cum_day_t2_before_switch():
    # До 31.07.2023 действовал T+2: реестр вт 13.06.2023 -> cum-день пт 09.06.
    prices = make_prices("2023-06-05", [100, 100, 100, 100, 100, 90, 90])
    ev = gap.compute_event(prices, "2023-06-13", 5)
    assert ev.cum_date == "2023-06-09"
    assert ev.ex_date == "2023-06-12"


def test_gap_closed():
    closes = [100, 92, 95, 99, 101, 98]
    opens = [100, 91, 92, 95, 99, 101]
    prices = make_prices("2025-07-14", closes, opens)  # пн..пн
    ev = gap.compute_event(prices, "2025-07-15", 8)    # cum = пн 14.07
    assert ev.cum_date == "2025-07-14"
    assert round(ev.gap_pct, 2) == 9.0
    assert round(ev.div_yield_pct, 2) == 8.0
    assert ev.closed
    assert ev.close_date == "2025-07-18"
    assert ev.days_to_close == 3
    assert ev.trading_days_to_close == 3


def test_gap_not_closed():
    prices = make_prices("2025-07-14", [100, 90, 92, 95])
    ev = gap.compute_event(prices, "2025-07-15", 10)
    assert not ev.closed
    assert ev.days_open == 2
    assert round(ev.remaining_pct, 2) == round((100 / 95 - 1) * 100, 2)


def test_future_registry_returns_none():
    prices = make_prices("2025-07-14", [100, 100])
    assert gap.compute_event(prices, "2025-08-01", 10) is None


def test_summarize_windows_ignore_fresh_events():
    prices_a = make_prices("2024-01-01", [100] + [90] * 5 + [100] * 3)  # закрылся
    prices_b = make_prices("2024-01-01", [100] + [90] * 5)              # открыт, прошло мало дней
    a = gap.compute_event(prices_a, "2024-01-02", 10)
    b = gap.compute_event(prices_b, "2024-01-02", 10)
    s = gap.summarize([a, b])
    assert s["events"] == 2 and s["closed"] == 1
    assert s["close_rate"] == 50.0
    # b открыт меньше 30 дней — не участвует в доле «закрылся за 30 дней».
    assert s["closed_within"]["30"] == 100.0


def test_estimate_cum_date():
    assert gap.estimate_cum_date("2026-12-20") == "2026-12-17"  # вс -> пт расчёты -> чт
    assert gap.estimate_cum_date("2026-12-15") == "2026-12-14"


def test_split_detect_and_adjust():
    prices = make_prices("2024-04-01", [15054, 15054, 152.96, 155], [15120, 15054, 152.5, 153])
    found = splits.detect(prices)
    assert found == [(prices[2]["date"], 100)]
    adj = splits.adjust(prices, found)
    assert adj[0]["close"] == 150.54
    assert adj[2]["close"] == 152.96


def test_consolidation_detect():
    prices = make_prices("2024-07-08", [0.0218, 0.0218, 109.0], [0.0219, 0.0218, 108.5])
    assert splits.detect(prices) == [(prices[2]["date"], 1 / 5000)]


def test_market_drop_is_not_split():
    prices = make_prices("2022-02-21", [100, 100, 60], [100, 100, 55])
    assert splits.detect(prices) == []


def test_cum_day_t0_before_2013():
    # До 02.09.2013 основной режим EQBR — T+0: купить можно в сам день реестра.
    prices = make_prices("2013-04-08", [100, 100, 100, 100, 97, 97])
    ev = gap.compute_event(prices, "2013-04-11", 2.57)
    assert ev.cum_date == "2013-04-11"
    assert ev.ex_date == "2013-04-12"
