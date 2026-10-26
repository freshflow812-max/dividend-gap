"""Определение сплитов/консолидаций и приведение истории цен к текущему числу акций."""

# «Круглые» коэффициенты сплитов: n * 10^k.
_NICE = sorted({round(n * 10**k, 6) for k in range(0, 5) for n in (1, 2, 2.5, 3, 4, 5, 8)} - {1})

MIN_RATIO = 2.5   # меньшие скачки считаем рыночными движениями, а не сплитом
TOLERANCE = 0.08  # допустимое отклонение от «круглого» коэффициента


def _snap(ratio: float) -> float | None:
    for k in _NICE:
        if abs(ratio / k - 1) <= TOLERANCE:
            return k
    return None


def detect(prices: list[dict]) -> list[tuple[str, float]]:
    """Ищет ночные скачки цены в «круглое» число раз.

    Возвращает [(дата первого дня после сплита, k)], где k = старая цена / новая.
    """
    found = []
    for prev, cur in zip(prices, prices[1:]):
        if not prev["close"] or not cur["open"]:
            continue
        ratio = prev["close"] / cur["open"]
        if ratio >= MIN_RATIO:
            k = _snap(ratio)
            if k:
                found.append((cur["date"], k))
        elif ratio <= 1 / MIN_RATIO:
            k = _snap(1 / ratio)
            if k:
                found.append((cur["date"], 1 / k))
    return found


def adjust(prices: list[dict], splits: list[tuple[str, float]]) -> list[dict]:
    """Делит цены до каждого сплита на его коэффициент."""
    if not splits:
        return prices
    result = []
    for row in prices:
        factor = 1.0
        for day, k in splits:
            if row["date"] < day:
                factor *= k
        if factor == 1.0:
            result.append(row)
        else:
            result.append({
                **row,
                **{f: row[f] / factor for f in ("open", "high", "low", "close") if row[f] is not None},
            })
    return result
