"""Public holidays per country and year, from Nager.Date.

No key needed. Holidays are small and revised rarely, so every run fetches every year in the
window and merges on (country_code, date, local_name). `counties` (the regions a holiday applies
to, null when it is national) and `types` are kept as the API sends them, as JSON lists on the
holiday row. Not as dlt child tables: those carry no `_dlt_load_id`, and dbt source freshness
(which Orchestra's state-aware runs read) is derived from it.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import dlt
from dlt.common.pipeline import LoadInfo

from nga.config import DLT_PIPELINES_DIR, RAW_HOLIDAYS, Settings
from nga.pipelines import http
from nga.pipelines.common import build_pipeline as _build_pipeline
from nga.pipelines.common import destination

BASE_URL = "https://date.nager.at/api/v3/PublicHolidays"
COUNTRIES = ("BE", "NL", "DE", "GB", "CH")


def years(settings: Settings) -> range:
    return range(settings.window_start.year, settings.as_of.year + 1)


def fetch_holidays(year: int, country_code: str) -> list[dict[str, Any]]:
    body = http.get_json(f"{BASE_URL}/{year}/{country_code}") or []
    return [
        {
            "country_code": h["countryCode"],
            "date": h["date"],
            "local_name": h["localName"],
            "name": h["name"],
            "is_fixed": h["fixed"],
            "is_global": h["global"],
            "launch_year": h["launchYear"],
            "counties": h["counties"],
            "types": h["types"],
        }
        for h in body
    ]


@dlt.resource(
    name="holidays",
    write_disposition="merge",
    primary_key=("country_code", "date", "local_name"),
    columns={
        "date": {"data_type": "date"},
        "counties": {"data_type": "json"},
        "types": {"data_type": "json"},
    },
)
def holidays(
    settings: Settings, countries: tuple[str, ...] = COUNTRIES
) -> Iterator[list[dict[str, Any]]]:
    for year in years(settings):
        for country_code in countries:
            yield fetch_holidays(year, country_code)


def holidays_source(settings: Settings):
    return holidays(settings)


def build_pipeline(dest: Any, pipelines_dir: Path = DLT_PIPELINES_DIR) -> dlt.Pipeline:
    return _build_pipeline("nager_date", RAW_HOLIDAYS, dest, pipelines_dir)


def run(settings: Settings) -> LoadInfo:
    pipeline = build_pipeline(destination(settings))
    info = pipeline.run(holidays_source(settings))
    info.raise_on_failed_jobs()
    return info
