"""One HTTP helper for the public APIs: a shared session with a timeout and sane retries."""

from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

TIMEOUT_SECONDS = 60
USER_AGENT = "next-gen-analytics (JB Analytica reference architecture)"


def session() -> requests.Session:
    retry = Retry(
        total=5,
        backoff_factor=2,  # 0s, 4s, 8s, 16s... between attempts
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        respect_retry_after_header=True,
    )
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def get_json(url: str, params: dict[str, Any] | None = None) -> Any:
    """GET `url` and return its JSON body; an empty 204 response returns None.

    Raises requests.HTTPError for any other non-2xx answer, so a failed call fails the load
    instead of landing nothing.
    """
    with session() as s:
        response = s.get(url, params=params, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    if response.status_code == 204 or not response.content:
        return None
    return response.json()
