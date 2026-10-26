"""Парсер дивидендов с dohod.ru.

Суммы на dohod.ru уже пересчитаны с учётом сплитов и консолидаций,
поэтому цены для сравнения тоже приводятся к текущему количеству акций (см. splits.py).
"""
import html
import re
from dataclasses import dataclass
from datetime import datetime

from .config import DOHOD_URL
from .http import get


@dataclass
class Dividend:
    registry_date: str  # ISO
    value: float
    declared_date: str | None
    period: str | None
    is_forecast: bool


def _text(cell: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", cell))).strip()


def _iso(ru_date: str) -> str | None:
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", ru_date)
    if not m:
        return None
    return datetime.strptime(m.group(0), "%d.%m.%Y").date().isoformat()


def _num(s: str) -> float | None:
    s = s.replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse_ticker_page(page: str) -> list[Dividend]:
    """Таблица «Дата объявления / Дата закрытия реестра / Год / Дивиденд»."""
    table = None
    for t in re.findall(r"<table[^>]*>.*?</table>", page, re.S):
        if "Дата закрытия реестра" in t and "Дата объявления" in t:
            table = t
            break
    if table is None:
        return []

    result = []
    for attrs, row in re.findall(r"<tr([^>]*)>(.*?)</tr>", table, re.S):
        cells = [_text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) < 4:
            continue
        registry = _iso(cells[1])
        value = _num(cells[3])
        if registry is None or value is None:
            continue
        result.append(Dividend(
            registry_date=registry,
            value=value,
            declared_date=_iso(cells[0]),
            period=cells[2] if cells[2] not in ("", "n/a") else None,
            is_forecast="forecast" in attrs or "прогноз" in cells[1],
        ))
    return _merge_same_date(result)


def _merge_same_date(divs: list[Dividend]) -> list[Dividend]:
    """Несколько выплат с одной датой реестра (напр. разные периоды) суммируем."""
    merged: dict[tuple[str, bool], Dividend] = {}
    for d in divs:
        key = (d.registry_date, d.is_forecast)
        if key in merged:
            merged[key].value = round(merged[key].value + d.value, 6)
        else:
            merged[key] = d
    return sorted(merged.values(), key=lambda d: d.registry_date)


def parse_overview(page: str) -> list[dict]:
    """Список бумаг со сводной страницы: slug (= тикер), название, сектор."""
    m = re.search(r'<table id="table-dividend".*?</table>', page, re.S)
    if not m:
        return []
    seen = {}
    for row in re.findall(r"<tr>(.*?)</tr>", m.group(0), re.S):
        link = re.search(r'href="/ik/analytics/dividend/([a-z0-9_\-]+)"[^>]*>(.*?)</a>', row, re.S)
        if not link:
            continue
        cells = [_text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        slug = link.group(1)
        seen.setdefault(slug, {
            "secid": slug.upper(),
            "name": _text(link.group(2)),
            "sector": cells[1] if len(cells) > 1 else None,
        })
    return list(seen.values())


def fetch_overview() -> list[dict]:
    return parse_overview(get(DOHOD_URL).text)


def fetch_dividends(secid: str) -> list[Dividend]:
    return parse_ticker_page(get(f"{DOHOD_URL}/{secid.lower()}").text)
