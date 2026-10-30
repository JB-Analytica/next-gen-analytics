"""Daily weather for one reference city per country, from the Open-Meteo historical archive.

No key needed. The archive trails real time by a couple of days, so the window ends at
min(as_of, today - 2). Re-fetching the last few days on every run picks up the small revisions
the archive makes to its newest values; merge on (country_code, date) keeps that idempotent.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import dlt
from dlt.common.pipeline import LoadInfo

from nga.config import DLT_PIPELINES_DIR, RAW_WEATHER, Settings
from nga.pipelines import http
from nga.pipelines.common import build_pipeline as _build_pipeline
from nga.pipelines.common import destination

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
LOOKBACK_DAYS = 7

# country_code -> (city, latitude, longitude): the reference city for that market.
CITIES: dict[str, tuple[str, float, float]] = {
    "BE": ("Brussels", 50.8503, 4.3517),
    "NL": ("Amsterdam", 52.3676, 4.9041),
    "DE": ("Cologne", 50.9375, 6.9603),
    "GB": ("London", 51.5072, -0.1276),
    "CH": ("Zürich", 47.3769, 8.5417),
}
# The columns land under the API's own variable names; renaming is the staging layer's job.
DAILY_VARIABLES = (
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "precipitation_sum",
    "rain_sum",
    "wind_speed_10m_max",
    "sunshine_duration",
)


def fetch_city(
    country_code: str, start: date, end: date, cities: dict[str, tuple[str, float, float]]
) -> list[dict[str, Any]]:
    city, lat, lon = cities[country_code]
    body = http.get_json(
        ARCHIVE_URL,
        {
            "latitude": lat,
            "longitude": lon,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "daily": ",".join(DAILY_VARIABLES),
            "timezone": "auto",  # days are the city's local calendar days
        },
    )
    daily = body["daily"]
    rows = []
    for i, day in enumerate(daily["time"]):
        rows.append(
            {
                "country_code": country_code,
                "city": city,
                "latitude": lat,
                "longitude": lon,
                "date": date.fromisoformat(day),
                **{v: daily[v][i] for v in DAILY_VARIABLES},
            }
        )
    return rows


@dlt.resource(
    name="daily_weather",
    write_disposition="merge",
    primary_key=("country_code", "date"),
)
def daily_weather(
    settings: Settings,
    today: date | None = None,
    cities: dict[str, tuple[str, float, float]] | None = None,
    cursor: dlt.sources.incremental[date] = dlt.sources.incremental(
        "date", initial_value=date(1970, 1, 1), lag=LOOKBACK_DAYS
    ),
) -> Iterator[list[dict[str, Any]]]:
    cities = cities or CITIES
    end = settings.window_end(today)
    start = max(settings.window_start, cursor.start_value or settings.window_start)
    if start > end:
        return
    for country_code in cities:
        yield fetch_city(country_code, start, end, cities)


def weather_source(settings: Settings, today: date | None = None, cities=None):
    return daily_weather(settings, today, cities)


def build_pipeline(dest: Any, pipelines_dir: Path = DLT_PIPELINES_DIR) -> dlt.Pipeline:
    return _build_pipeline("open_meteo", RAW_WEATHER, dest, pipelines_dir)


def run(settings: Settings) -> LoadInfo:
    pipeline = build_pipeline(destination(settings))
    info = pipeline.run(weather_source(settings))
    info.raise_on_failed_jobs()
    return info
