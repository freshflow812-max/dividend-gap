from app import moex


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


def test_free_floats(monkeypatch):
    data = {"list": [
        {"tradeCode": "SBER", "freeFloat": 0.48, "approveDate": "02.06.2026"},
        {"tradeCode": "SBERP", "freeFloat": 1.0, "approveDate": None},
        {"tradeCode": "XXXX", "freeFloat": None, "approveDate": "01.01.2026"},
    ]}
    monkeypatch.setattr(moex, "get", lambda url, params=None: FakeResponse(data))
    assert moex.free_floats() == {"SBER": (0.48, "2026-06-02"), "SBERP": (1.0, None)}
