"""Расчёт дивидендного гэпа и статистики его закрытия.

Термины:
  cum-день  — последний день, когда покупка акции даёт право на дивиденд;
  ex-день   — следующий торговый день, в который и возникает гэп;
  закрытие  — первый день (начиная с ex-дня), когда цена закрытия >= закрытия cum-дня.
"""
import bisect
import statistics
from dataclasses import asdict, dataclass
from datetime import date, timedelta

from .config import CLOSE_WINDOWS_DAYS, T1_SWITCH_DATE, T2_SWITCH_DATE


@dataclass
class GapEvent:
    registry_date: str
    value: float
    cum_date: str
    ex_date: str
    close_before: float
    open_ex: float
    close_ex: float
    gap_pct: float          # (закрытие cum-дня - открытие ex-дня) / закрытие cum-дня
    div_yield_pct: float    # дивиденд / закрытие cum-дня
    closed: bool
    close_date: str | None
    days_to_close: int | None          # календарные дни от ex-дня
    trading_days_to_close: int | None  # торговые дни от ex-дня (0 — закрылся в день гэпа)
    days_open: int          # сколько календарных дней прошло от ex-дня (до закрытия или до сегодня)
    last_close: float
    remaining_pct: float | None  # сколько ещё нужно вырасти до закрытия (для незакрытых)

    def to_dict(self):
        return asdict(self)


def settlement_lag(registry_date: str) -> int:
    if registry_date >= T1_SWITCH_DATE:
        return 1
    return 2 if registry_date >= T2_SWITCH_DATE else 0


def cum_index(dates: list[str], registry_date: str) -> int | None:
    """Индекс cum-дня в списке торговых дат.

    Расчёты по сделке проходят через lag торговых дней (T+0, T+2 или T+1),
    и должны завершиться не позже даты закрытия реестра.
    """
    settle = bisect.bisect_right(dates, registry_date) - 1  # последний торговый день <= реестра
    idx = settle - settlement_lag(registry_date)
    return idx if idx >= 0 else None


def compute_event(prices: list[dict], registry_date: str, value: float) -> GapEvent | None:
    """prices — свечи по возрастанию даты (уже скорректированные на сплиты)."""
    dates = [p["date"] for p in prices]
    ci = cum_index(dates, registry_date)
    if ci is None or ci + 1 >= len(prices):
        return None  # нет истории до отсечки или ex-день ещё не наступил
    # Если торговли не было больше недели до реестра — данных о cum-дне нет.
    if (date.fromisoformat(registry_date) - date.fromisoformat(dates[ci])).days > 10:
        return None

    cum, ex = prices[ci], prices[ci + 1]
    target = cum["close"]
    close_idx = next((i for i in range(ci + 1, len(prices)) if prices[i]["close"] >= target), None)

    ex_day = date.fromisoformat(ex["date"])
    last = prices[-1]
    if close_idx is not None:
        close_date = prices[close_idx]["date"]
        days = (date.fromisoformat(close_date) - ex_day).days
        days_open = days
        trading_days = close_idx - (ci + 1)
        remaining = None
    else:
        close_date = days = trading_days = None
        days_open = (date.fromisoformat(last["date"]) - ex_day).days
        remaining = (target / last["close"] - 1) * 100

    return GapEvent(
        registry_date=registry_date,
        value=value,
        cum_date=cum["date"],
        ex_date=ex["date"],
        close_before=target,
        open_ex=ex["open"],
        close_ex=ex["close"],
        gap_pct=(target - ex["open"]) / target * 100,
        div_yield_pct=value / target * 100,
        closed=close_idx is not None,
        close_date=close_date,
        days_to_close=days,
        trading_days_to_close=trading_days,
        days_open=days_open,
        last_close=last["close"],
        remaining_pct=remaining,
    )


def summarize(events: list[GapEvent]) -> dict:
    """Сводная статистика закрытия гэпов по набору событий."""
    n = len(events)
    closed = [e for e in events if e.closed]
    days = [e.days_to_close for e in closed]

    within = {}
    for w in CLOSE_WINDOWS_DAYS:
        # Учитываем только события, у которых уже прошло w дней (или гэп закрыт раньше),
        # иначе свежие отсечки занижали бы долю.
        eligible = [e for e in events if e.days_open >= w or (e.closed and e.days_to_close <= w)]
        hit = [e for e in eligible if e.closed and e.days_to_close <= w]
        within[str(w)] = round(len(hit) / len(eligible) * 100, 1) if eligible else None

    def avg(xs):
        return round(statistics.fmean(xs), 2) if xs else None

    return {
        "events": n,
        "closed": len(closed),
        "close_rate": round(len(closed) / n * 100, 1) if n else None,
        "median_days": statistics.median(days) if days else None,
        "mean_days": avg(days),
        "median_trading_days": statistics.median([e.trading_days_to_close for e in closed]) if closed else None,
        "avg_gap_pct": avg([e.gap_pct for e in events]),
        "avg_yield_pct": avg([e.div_yield_pct for e in events]),
        "closed_within": within,
        "open_now": n - len(closed),
        # Период, за который посчитаны средние: первая и последняя отсечка с данными о ценах.
        "first_ex_date": min((e.ex_date for e in events), default=None),
        "last_ex_date": max((e.ex_date for e in events), default=None),
    }


def estimate_cum_date(registry_date: str) -> str:
    """Оценка последнего дня покупки для будущей отсечки (только будни, без учёта праздников)."""
    d = date.fromisoformat(registry_date)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    lag = settlement_lag(registry_date)
    while lag:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            lag -= 1
    return d.isoformat()
