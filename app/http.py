import time

import requests

from .config import USER_AGENT

_session = requests.Session()
_session.headers["User-Agent"] = USER_AGENT


def get(url: str, params: dict | None = None, retries: int = 4) -> requests.Response:
    """GET с повторами и экспоненциальной паузой при сетевых сбоях и 5xx."""
    delay = 2.0
    for attempt in range(retries + 1):
        try:
            resp = _session.get(url, params=params, timeout=30)
            if resp.status_code < 500:
                resp.raise_for_status()
                return resp
        except (requests.ConnectionError, requests.Timeout):
            if attempt == retries:
                raise
        if attempt == retries:
            resp.raise_for_status()
        time.sleep(delay)
        delay *= 2
    raise RuntimeError("unreachable")
