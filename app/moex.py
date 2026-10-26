"""Котировки с MOEX ISS (бесплатный публичный API Мосбиржи)."""
from datetime import date

from .config import ISS_URL, PRIMARY_BOARD
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


def history(secid: str, date_from: str) -> list[dict]:
    """Дневные свечи режима TQBR начиная с date_from (включительно).

    Свечи ISS по TQBR уже включают историю предшествующего режима EQBR
    и скорректированы на сплиты. Дни без сделок в свечах отсутствуют.
    Сессии выходного дня пропускаем: расчёты по ним идут в ближайший будний день,
    и для анализа гэпа они только мешают определению последнего дня с дивидендом.
    """
    result = []
    start = 0
    while True:
        data = get(
            f"{ISS_URL}/engines/stock/markets/shares/boards/{PRIMARY_BOARD}/securities/{secid}/candles.json",
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
