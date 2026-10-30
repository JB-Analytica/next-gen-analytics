"""ECB euro reference rates from Frankfurter, as one row per (rate_date, base, quote).

No key needed. The ECB publishes on business days only, so weekends and bank holidays are simply
absent: what the API returns is what lands, and filling the gaps is a modelling decision for dbt.
Re-fetching the last few days on every run picks up any late correction; merge keeps it
idempotent.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import dlt
from dlt.common.pipeline import LoadInfo

from nga.config import DLT_PIPELINES_DIR, RAW_FX, Settings
from nga.pipelines import http
from nga.pipelines.common import build_pipeline as _build_pipeline
from nga.pipelines.common import destination

BASE_URL = "https://api.frankfurter.dev/v1"
BASE_CURRENCY = "EUR"
LOOKBACK_DAYS = 7
# Frankfurter groups long time series by week; asking in chunks shorter than that keeps every
# business day.
CHUNK_DAYS = 80


def fetch_rates(start: date, end: date, symbols: tuple[str, ...]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    chunk_start = start
    while chunk_start <= end:
        chunk_end = min(chunk_start + timedelta(days=CHUNK_DAYS - 1), end)
        body = http.get_json(
            f"{BASE_URL}/{chunk_start.isoformat()}..{chunk_end.isoformat()}",
            {"base": BASE_CURRENCY, "symbols": ",".join(symbols)},
        )
        for day, quotes in (body or {}).get("rates", {}).items():
            for quote, rate in quotes.items():
                rows.append(
                    {
                        "rate_date": date.fromisoformat(day),
                        "base": body["base"],
                        "quote": quote,
                        "rate": rate,
                    }
                )
        chunk_start = chunk_end + timedelta(days=1)
    return rows


@dlt.resource(
    name="rates",
    write_disposition="merge",
    primary_key=("rate_date", "base", "quote"),
)
def rates(
    settings: Settings,
    today: date | None = None,
    cursor: dlt.sources.incremental[date] = dlt.sources.incremental(
        "rate_date", initial_value=date(1970, 1, 1), lag=LOOKBACK_DAYS
    ),
) -> Iterator[list[dict[str, Any]]]:
    today = today or date.today()
    end = min(settings.as_of, today)
    start = max(settings.window_start, cursor.start_value or settings.window_start)
    if start > end:
        return
    yield fetch_rates(start, end, settings.fx_symbols)


def fx_source(settings: Settings, today: date | None = None):
    return rates(settings, today)


def build_pipeline(dest: Any, pipelines_dir: Path = DLT_PIPELINES_DIR) -> dlt.Pipeline:
    return _build_pipeline("frankfurter", RAW_FX, dest, pipelines_dir)


def run(settings: Settings) -> LoadInfo:
    pipeline = build_pipeline(destination(settings))
    info = pipeline.run(fx_source(settings))
    info.raise_on_failed_jobs()
    return info
