"""Сбор данных: список акций, дивиденды (dohod.ru) и котировки (MOEX ISS).

Запуск:  python -m app.collector                 # все бумаги
         python -m app.collector --tickers SBER,LKOH
"""
import argparse
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from . import dohod, moex
from .config import ALL_INDEXES, DOHOD_DELAY_SEC, INDEX_HISTORY_FROM, PRICE_WORKERS
from .db import connect

log = logging.getLogger("collector")
MSK = ZoneInfo("Europe/Moscow")


def update_universe(conn) -> list[str]:
    """Бумаги, по которым есть данные на dohod.ru и которые торгуются в TQBR."""
    tqbr = moex.tqbr_securities()
    items = [i for i in dohod.fetch_overview() if i["secid"] in tqbr]
    now = datetime.now().isoformat(timespec="seconds")
    conn.executemany(
        "INSERT INTO securities (secid, name, sector, updated_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(secid) DO UPDATE SET name=excluded.name, sector=excluded.sector, updated_at=excluded.updated_at",
        [(i["secid"], i["name"], i["sector"], now) for i in items],
    )
    log.info("Бумаг с дивидендами в TQBR: %d", len(items))
    return [i["secid"] for i in items]


def update_free_floats(conn) -> None:
    """Обновляет коэффициенты free-float. Ошибка не критична: остаются прошлые значения."""
    try:
        ff = moex.free_floats()
    except Exception:
        log.exception("Free-float: ошибка загрузки, оставляем прежние значения")
        return
    conn.execute("DELETE FROM free_float")
    conn.executemany(
        "INSERT INTO free_float (secid, value, approve_date) VALUES (?, ?, ?)",
        [(secid, value, day) for secid, (value, day) in ff.items()],
    )
    conn.commit()
    log.info("Free-float: %d бумаг", len(ff))


def update_dividends(conn, secid: str) -> int:
    divs = dohod.fetch_dividends(secid)
    conn.execute("DELETE FROM dividends WHERE secid = ?", (secid,))
    conn.executemany(
        "INSERT INTO dividends (secid, registry_date, value, declared_date, period, is_forecast) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [(secid, d.registry_date, d.value, d.declared_date, d.period, int(d.is_forecast)) for d in divs],
    )
    return len(divs)


def price_start(conn, secid: str) -> str:
    last = conn.execute("SELECT MAX(date) FROM prices WHERE secid = ?", (secid,)).fetchone()[0]
    if last:
        return last  # перезаписываем последний день: он мог быть незавершённым
    if secid in ALL_INDEXES:
        return INDEX_HISTORY_FROM
    first_div = conn.execute("SELECT MIN(registry_date) FROM dividends WHERE secid = ?", (secid,)).fetchone()[0]
    start = date.fromisoformat(first_div) - timedelta(days=30) if first_div else date.today() - timedelta(days=365)
    return start.isoformat()


def save_prices(conn, secid: str, rows: list[dict]) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO prices (secid, date, open, high, low, close, volume) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(secid, r["date"], r["open"], r["high"], r["low"], r["close"], r["volume"]) for r in rows],
    )


def run(tickers: list[str] | None = None, skip_dividends: bool = False) -> None:
    with connect() as conn:
        universe = update_universe(conn)
        conn.commit()
        update_free_floats(conn)
        if tickers:
            universe = [t for t in universe if t in tickers]

        # Дивиденды — последовательно и с паузой, чтобы не нагружать dohod.ru.
        if not skip_dividends:
            for n, secid in enumerate(universe, 1):
                try:
                    ndiv = update_dividends(conn, secid)
                    conn.commit()
                    log.info("[%d/%d] %s: дивидендов %d", n, len(universe), secid, ndiv)
                except Exception:
                    conn.rollback()
                    log.exception("[%d/%d] %s: ошибка загрузки дивидендов", n, len(universe), secid)
                time.sleep(DOHOD_DELAY_SEC)

        # Котировки — параллельно; запись в базу только из этого потока.
        starts = {secid: price_start(conn, secid) for secid in universe}
        with ThreadPoolExecutor(max_workers=PRICE_WORKERS) as pool:
            futures = {pool.submit(moex.history, secid, starts[secid]): secid for secid in universe}
            for n, fut in enumerate(as_completed(futures), 1):
                secid = futures[fut]
                try:
                    rows = fut.result()
                    save_prices(conn, secid, rows)
                    conn.commit()
                    log.info("[%d/%d] %s: свечей %d", n, len(universe), secid, len(rows))
                except Exception:
                    log.exception("[%d/%d] %s: ошибка загрузки котировок", n, len(universe), secid)

        for secid in ALL_INDEXES:
            try:
                rows = moex.index_history(secid, price_start(conn, secid))
                save_prices(conn, secid, rows)
                conn.commit()
                log.info("Индекс %s: свечей %d", secid, len(rows))
            except Exception:
                log.exception("Индекс %s: ошибка загрузки", secid)

        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('last_update', ?)",
            (datetime.now(MSK).isoformat(timespec="seconds"),),
        )


def main():
    parser = argparse.ArgumentParser(description="Сбор дивидендов и котировок")
    parser.add_argument("--tickers", help="Список тикеров через запятую (по умолчанию все)")
    parser.add_argument("--skip-dividends", action="store_true", help="Обновить только котировки")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    tickers = [t.strip().upper() for t in args.tickers.split(",")] if args.tickers else None
    run(tickers, args.skip_dividends)


if __name__ == "__main__":
    main()
