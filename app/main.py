"""Веб-приложение «Дивидендный гэп».

Запуск:  uvicorn app.main:app --reload
"""
import threading

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import collector, service
from .config import BASE_DIR
from .db import connect

app = FastAPI(title="Дивидендный гэп")

_cache: dict = {"key": None, "data": None}
_cache_lock = threading.Lock()
_update_lock = threading.Lock()


def _all_data() -> dict:
    """Расчёт по всем бумагам; пересчитывается при новом обновлении данных или смене дня."""
    from datetime import date

    with connect() as conn:
        key = (service.last_update(conn), date.today().isoformat())
        with _cache_lock:
            if _cache["key"] != key:
                _cache["data"] = service.build_all(conn)
                _cache["data"]["last_update"] = key[0]
                _cache["key"] = key
            return _cache["data"]


@app.get("/api/upcoming")
def upcoming(include_forecast: bool = True):
    data = _all_data()
    rows = [u for u in data["upcoming"] if include_forecast or not u["is_forecast"]]
    return {"today": data["today"], "last_update": data["last_update"], "items": rows}


@app.get("/api/stats")
def stats():
    data = _all_data()
    return {
        "today": data["today"],
        "last_update": data["last_update"],
        "overall": data["overall"],
        "tickers": data["tickers"],
    }


@app.get("/api/ticker/{secid}")
def ticker(secid: str):
    with connect() as conn:
        report = service.ticker_report(conn, secid.upper())
    if report is None:
        raise HTTPException(404, "Тикер не найден")
    return report


@app.post("/api/update")
def update(tickers: str | None = None):
    """Запустить сбор данных в фоне (полный сбор занимает несколько минут)."""
    if not _update_lock.acquire(blocking=False):
        return {"status": "already_running"}

    def job():
        try:
            collector.run([t.strip().upper() for t in tickers.split(",")] if tickers else None)
        finally:
            _update_lock.release()

    threading.Thread(target=job, daemon=True).start()
    return {"status": "started"}


@app.get("/api/update/status")
def update_status():
    with connect() as conn:
        return {"running": _update_lock.locked(), "last_update": service.last_update(conn)}


app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/")
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")
