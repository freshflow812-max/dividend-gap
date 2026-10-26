from pathlib import Path

from app import dohod

FIXTURE = Path(__file__).parent / "fixtures" / "dohod_sber.html"


def test_parse_ticker_page():
    divs = dohod.parse_ticker_page(FIXTURE.read_text(encoding="utf-8"))
    by_date = {d.registry_date: d for d in divs}

    d2025 = by_date["2025-07-18"]
    assert d2025.value == 34.84
    assert d2025.declared_date == "2025-04-22"
    assert not d2025.is_forecast

    forecast = by_date["2027-07-20"]
    assert forecast.is_forecast
    assert forecast.declared_date is None

    assert [d.registry_date for d in divs] == sorted(d.registry_date for d in divs)


def test_merge_same_registry_date():
    page = """
    <table class="content-table"><tr><th>Дата объявления дивиденда</th><th>Дата закрытия реестра</th></tr>
    <tr><td>23.04.2021</td><td>15.07.2021</td><td>2021</td><td>0.087</td></tr>
    <tr><td>23.04.2021</td><td>15.07.2021</td><td>2021</td><td>6.91</td></tr>
    </table>"""
    divs = dohod.parse_ticker_page(page)
    assert len(divs) == 1
    assert divs[0].value == 6.997
