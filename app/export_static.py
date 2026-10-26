"""Выгрузка статической версии сайта (без сервера) в папку site/.

Запуск:  python -m app.export_static [--out site]

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


def build_page() -> str:
    src = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    title = re.search(r"<title>.*?</title>", src, re.S).group(0)
    chart = re.search(r'<script src="https://cdnjs[^"]+"></script>', src).group(0)
    body = re.search(r"<body>(.*?)<script src=\"/static/app.js\"></script>", src, re.S).group(1)
    css = (STATIC_DIR / "style.css").read_text(encoding="utf-8")
    js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    return (
        '<meta charset="utf-8">\n'
        f"{title}\n"
        '<meta name="claude:viewport-fit-sides" content="cover">\n'
        f"<style>\n{css}</style>\n"
        f"{chart}\n"
        f"{body.strip()}\n"
        "<script>window.DIVGAP_STATIC = true;</script>\n"
        f"<script>\n{js}</script>\n"
    )


def export(out: Path) -> int:
    with connect() as conn:
        data = service.build_all(conn)
        data["last_update"] = service.last_update(conn)
        _dump(out / "data" / "upcoming.json", {
            "today": data["today"], "last_update": data["last_update"], "items": data["upcoming"],
        })
        _dump(out / "data" / "stats.json", {
            "today": data["today"], "last_update": data["last_update"],
            "overall": data["overall"], "tickers": data["tickers"],
        })
        for secid in service.securities(conn):
            _dump(out / "data" / "ticker" / f"{secid}.json", service.ticker_report(conn, secid))
    (out / "index.html").write_text(build_page(), encoding="utf-8")
    return len(data["tickers"])


def main():
    parser = argparse.ArgumentParser(description="Статическая версия сайта")
    parser.add_argument("--out", default=str(BASE_DIR / "site"))
    args = parser.parse_args()
    n = export(Path(args.out))
    print(f"Готово: {n} бумаг -> {args.out}")


if __name__ == "__main__":
    main()
