"""Котировки с MOEX ISS (бесплатный публичный API Мосбиржи)."""
from datetime import date

from .config import FREE_FLOAT_URL, ISS_URL, PRIMARY_BOARD
from .http import get


def _rows(block: dict) -> list[dict]:
    cols = block["columns"]
    return [dict(zip(cols, r)) for r in block["data"]]


def tqbr_securities() -> dict[str, str]:
    """Акции, торгующиеся сейчас в режиме TQBR: {SECID: SHORTNAME}."""
    data = get(
        f"{ISS_URL}/engines/stock/markets/shares/boards/TQBR/securities.json",
        {"iss.meta": "off", "iss.only": "securities", "securities.columns": "SECID,SHORTNAME"},
    ).json()
    return {r["SECID"]: r["SHORTNAME"] for r in _rows(data["securities"])}


def history(secid: str, date_from: str, market: str = "shares", board: str = PRIMARY_BOARD) -> list[dict]:
    """Дневные свечи начиная с date_from (включительно); по умолчанию акции в режиме TQBR.

    Свечи ISS по TQBR уже включают историю предшествующего режима EQBR
    и скорректированы на сплиты. Дни без сделок в свечах отсутствуют.
    Сессии выходного дня пропускаем: расчёты по ним идут в ближайший будний день,
    и для анализа гэпа они только мешают определению последнего дня с дивидендом.
    """
    result = []
    start = 0
    while True:
        data = get(
            f"{ISS_URL}/engines/stock/markets/{market}/boards/{board}/securities/{secid}/candles.json",
            {"iss.meta": "off", "interval": 24, "from": date_from, "start": start},
        ).json()
        rows = _rows(data["candles"])
        for r in rows:
            if date.fromisoformat(r["begin"][:10]).weekday() >= 5:
                continue
            result.append({
                "date": r["begin"][:10],
                "open": r["open"],
                "high": r["high"],
                "low": r["low"],
                "close": r["close"],
                "volume": r["volume"],
            })
        if not rows:
            break
        start += len(rows)
    return result


def index_history(secid: str, date_from: str) -> list[dict]:
    """Дневные значения индекса Мосбиржи (режим SNDX)."""
    return history(secid, date_from, market="index", board="SNDX")


def free_floats() -> dict[str, tuple[float, str | None]]:
    """Коэффициенты free-float, которые публикует Мосбиржа: {SECID: (доля 0..1, дата утверждения ISO)}.

    Мосбиржа рассчитывает их только для части бумаг (в основном из индексной базы).
    """
    data = get(FREE_FLOAT_URL, {"pageNumber": 0, "pageSize": 1000}).json()
    result = {}
    for r in data["list"]:
        if r.get("freeFloat") is None or not r.get("tradeCode"):
            continue
        d = r.get("approveDate")  # ДД.ММ.ГГГГ
        iso = f"{d[6:10]}-{d[3:5]}-{d[0:2]}" if d and len(d) == 10 else None
        result[r["tradeCode"]] = (float(r["freeFloat"]), iso)
    return result
