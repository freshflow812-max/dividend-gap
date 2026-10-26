import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("DIVGAP_DB", BASE_DIR / "data" / "divgap.sqlite"))

ISS_URL = "https://iss.moex.com/iss"
DOHOD_URL = "https://www.dohod.ru/ik/analytics/dividend"
USER_AGENT = "Mozilla/5.0 (dividend-gap collector)"

# Основной режим торгов акциями.
PRIMARY_BOARD = "TQBR"

# Индексы для сравнения: SECID -> название. Котировки берутся с режима SNDX.
INDEXES = {
    "IMOEX": "Индекс МосБиржи",
    "MCFTR": "Индекс МосБиржи полной доходности",
}
INDEX_HISTORY_FROM = "2003-01-01"

# Пауза между запросами к dohod.ru, чтобы не нагружать сайт.
DOHOD_DELAY_SEC = float(os.environ.get("DIVGAP_DOHOD_DELAY", "0.7"))

# Число параллельных загрузок котировок с MOEX ISS.
PRICE_WORKERS = int(os.environ.get("DIVGAP_PRICE_WORKERS", "6"))

# Режимы расчётов основного рынка акций: до 02.09.2013 — T+0 (EQBR),
# с 02.09.2013 — T+2 (TQBR), с 31.07.2023 — T+1.
T2_SWITCH_DATE = "2013-09-02"
T1_SWITCH_DATE = "2023-07-31"

# Окна, для которых считается доля закрытых гэпов.
CLOSE_WINDOWS_DAYS = (7, 30, 90, 365)

# Ручные сплиты/консолидации на случай, если автоопределение не сработало:
# {"SECID": [("YYYY-MM-DD" первый день после сплита, коэффициент)]}.
# Коэффициент > 1 — сплит (цена упала в k раз), < 1 — консолидация.
MANUAL_SPLITS: dict[str, list[tuple[str, float]]] = {}
