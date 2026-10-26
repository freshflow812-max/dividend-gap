import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS securities (
    secid      TEXT PRIMARY KEY,
    name       TEXT,
    sector     TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS dividends (
    secid         TEXT NOT NULL,
    registry_date TEXT NOT NULL,
    value         REAL NOT NULL,
    declared_date TEXT,
    period        TEXT,
    is_forecast   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (secid, registry_date, is_forecast)
);

CREATE TABLE IF NOT EXISTS prices (
    secid  TEXT NOT NULL,
    date   TEXT NOT NULL,
    open   REAL,
    high   REAL,
    low    REAL,
    close  REAL NOT NULL,
    volume REAL,
    PRIMARY KEY (secid, date)
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


@contextmanager
def connect(path=None):
    path = path or DB_PATH
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
