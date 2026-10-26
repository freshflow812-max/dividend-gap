"""Выгрузка статической версии сайта (без сервера) в папку site/.

Запуск:  python -m app.export_static [--out site]
         python -m app.export_static --single dividend-gap.html   # один файл со всеми данными

Страница — фрагмент без <html>/<head>/<body>, CSS и JS встроены,
данные лежат рядом в data/*.json. Подходит для любого статического хостинга
(обычный хостинг обернёт фрагмент в документ сам, браузеры это допускают).
"""
import argparse
import json
import re
from pathlib import Path

from . import service
from .config import BASE_DIR
from .db import connect

STATIC_DIR = BASE_DIR / "static"


def _dump(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def build_page(embedded: dict | None = None, standalone: bool = False) -> str:
    """Страница со встроенными CSS и JS.

    standalone=False — фрагмент без <html>/<head>/<body> (обёртку добавит хостинг);
    standalone=True — полноценный документ для открытия файла напрямую.
    """
    src = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    title = re.search(r"<title>.*?</title>", src, re.S).group(0)
    chart = re.search(r'<script src="https://cdnjs[^"]+"></script>', src).group(0)
    body = re.search(r"<body>(.*?)<script src=\"/static/app.js\"></script>", src, re.S).group(1)
    css = (STATIC_DIR / "style.css").read_text(encoding="utf-8")
    js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    head = (
        '<meta charset="utf-8">\n'
        f"{title}\n"
        '<meta name="claude:viewport-fit-sides" content="cover">\n'
        f"<style>\n{css}</style>\n"
        f"{chart}\n"
    )
    scripts = "<script>window.DIVGAP_STATIC = true;</script>\n"
    if embedded:
        scripts += f"<script>window.DIVGAP_DATA = {_embed(embedded)};</script>\n"
    scripts += f"<script>\n{js}</script>\n"

    if not standalone:
        return f"{head}{body.strip()}\n{scripts}"
    return (
        '<!doctype html>\n<html lang="ru">\n<head>\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        f"{head}</head>\n<body>\n{body.strip()}\n{scripts}</body>\n</html>\n"
    )


def _embed(data: dict) -> str:
    # "</" внутри JSON закрыл бы тег <script>.
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def collect() -> dict[str, object]:
    """Все данные сайта: {путь JSON-файла: содержимое}."""
    files = {}
    with connect() as conn:
        data = service.build_all(conn)
        data["last_update"] = service.last_update(conn)
        files["data/upcoming.json"] = {
            "today": data["today"], "last_update": data["last_update"], "items": data["upcoming"],
        }
        files["data/stats.json"] = {
            "today": data["today"], "last_update": data["last_update"],
            "overall": data["overall"], "tickers": data["tickers"],
        }
        for secid in service.securities(conn):
            files[f"data/ticker/{secid}.json"] = service.ticker_report(conn, secid)
    return files


def export(out: Path) -> int:
    files = collect()
    for rel, data in files.items():
        _dump(out / rel, data)
    (out / "index.html").write_text(build_page(), encoding="utf-8")
    return len(files) - 2


def export_single(path: Path) -> int:
    files = collect()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_page(embedded=files, standalone=True), encoding="utf-8")
    return len(files) - 2


def main():
    parser = argparse.ArgumentParser(description="Статическая версия сайта")
    parser.add_argument("--out", default=str(BASE_DIR / "site"))
    parser.add_argument("--single", help="Собрать один HTML-файл со встроенными данными по этому пути")
    args = parser.parse_args()
    if args.single:
        n, target = export_single(Path(args.single)), args.single
    else:
        n, target = export(Path(args.out)), args.out
    print(f"Готово: {n} бумаг -> {target}")


if __name__ == "__main__":
    main()
