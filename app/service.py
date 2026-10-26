"""Аналитика поверх базы: события гэпов, статистика, ближайшие дивиденды."""
from datetime import date

from . import gap, splits
from .config import INDEXES, MANUAL_SPLITS


def securities(conn) -> dict[str, dict]:
    return {r["secid"]: dict(r) for r in conn.execute("SELECT * FROM securities ORDER BY secid")}


def load_prices(conn, secid: str) -> tuple[list[dict], list[tuple[str, float]]]:
    """Свечи, приведённые к текущему количеству акций, и найденные сплиты."""
    rows = [dict(r) for r in conn.execute(
        "SELECT date, open, high, low, close, volume FROM prices WHERE secid = ? ORDER BY date", (secid,)
    )]
    found = {d: k for d, k in splits.detect(rows)}
    found.update(dict(MANUAL_SPLITS.get(secid, [])))
    split_list = sorted(found.items())
    return splits.adjust(rows, split_list), split_list


def load_dividends(conn, secid: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT registry_date, value, declared_date, period, is_forecast FROM dividends "
        "WHERE secid = ? ORDER BY registry_date", (secid,)
    )]


def ticker_events(prices: list[dict], dividends: list[dict]) -> list[gap.GapEvent]:
    events = []
    for d in dividends:
        if d["is_forecast"] or d["value"] <= 0:
            continue
        ev = gap.compute_event(prices, d["registry_date"], d["value"])
        if ev:
            events.append(ev)
    return events


def ticker_report(conn, secid: str) -> dict | None:
    sec = securities(conn).get(secid)
    if not sec:
        return None
    prices, split_list = load_prices(conn, secid)
    dividends = load_dividends(conn, secid)
    events = ticker_events(prices, dividends)
    return {
        "security": sec,
        "summary": gap.summarize(events),
        "events": [e.to_dict() for e in reversed(events)],
        "dividends": dividends,
        "splits": [{"date": d, "factor": k} for d, k in split_list],
    }


def build_all(conn, today: date | None = None) -> dict:
    """Статистика по всем бумагам + ближайшие дивиденды. Тяжёлый расчёт — кэшируется в main.py."""
    today_iso = (today or date.today()).isoformat()
    per_ticker, all_events, upcoming = [], [], []

    for secid, sec in securities(conn).items():
        prices, _ = load_prices(conn, secid)
        dividends = load_dividends(conn, secid)
        events = ticker_events(prices, dividends)
        all_events.extend(events)
        summary = gap.summarize(events)
        last = prices[-1] if prices else None
        last_ev = events[-1] if events else None
        per_ticker.append({
            "secid": secid,
            "name": sec["name"],
            "sector": sec["sector"],
            **summary,
            "last_event": last_ev.to_dict() if last_ev else None,
        })

        # Прогноз с нулевой суммой на dohod.ru означает «выплаты не ожидается».
        future = [d for d in dividends if d["registry_date"] >= today_iso and d["value"] > 0]
        if not future:
            continue
        # Ближайшая отсечка; объявленный дивиденд приоритетнее прогноза на ту же дату.
        nearest = min(future, key=lambda d: (d["registry_date"], d["is_forecast"]))
        price = last["close"] if last else None
        upcoming.append({
            "secid": secid,
            "name": sec["name"],
            "sector": sec["sector"],
            "registry_date": nearest["registry_date"],
            "cum_date_est": gap.estimate_cum_date(nearest["registry_date"]),
            "value": nearest["value"],
            "declared_date": nearest["declared_date"],
            "period": nearest["period"],
            "is_forecast": bool(nearest["is_forecast"]),
            "price": price,
            "price_date": last["date"] if last else None,
            "yield_pct": round(nearest["value"] / price * 100, 2) if price else None,
            "stats": summary,
        })

    upcoming.sort(key=lambda u: (u["registry_date"], u["secid"]))
    return {
        "today": today_iso,
        "overall": gap.summarize(all_events),
        "tickers": per_ticker,
        "upcoming": upcoming,
    }


def last_update(conn) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = 'last_update'").fetchone()
    return row[0] if row else None


def encode_closes(prices: list[dict]) -> dict:
    """Компактная запись ряда закрытий: первая дата, шаги в днях и цены."""
    if not prices:
        return {"t0": None, "dt": [], "c": []}
    days = [date.fromisoformat(p["date"]) for p in prices]
    return {
        "t0": prices[0]["date"],
        "dt": [0] + [(b - a).days for a, b in zip(days, days[1:])],
        "c": [float(f"{p['close']:.6g}") for p in prices],
    }


def closes(conn) -> dict:
    """Цены закрытия (с учётом сплитов) и даты дивидендов по всем бумагам и индексам.

    Используется вкладкой «Доходность» и графиком в карточке акции.
    """
    result = {}
    for secid, name in INDEXES.items():
        prices, _ = load_prices(conn, secid)
        result[secid] = {"name": name, "sector": "Индекс", "is_index": True, "divs": [], **encode_closes(prices)}
    for secid, sec in securities(conn).items():
        prices, _ = load_prices(conn, secid)
        events = ticker_events(prices, load_dividends(conn, secid))
        result[secid] = {
            "name": sec["name"],
            "sector": sec["sector"],
            "is_index": False,
            # Дивиденд «приходит» в ex-день: с него цена уже без дивиденда.
            "divs": [[e.ex_date, e.value] for e in events],
            **encode_closes(prices),
        }
    return result
