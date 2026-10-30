"""The three public-API resources, run for real against a DuckDB warehouse with canned responses."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import duckdb
import pytest

from nga.config import Settings
from nga.pipelines import fx, holidays, http, weather

CITIES = {"BE": ("Brussels", 50.85, 4.35), "GB": ("London", 51.5, -0.12)}
TODAY = date(2026, 10, 27)


class FakeApi:
    """Stands in for the network: records every call and answers from a routing function."""

    def __init__(self, router) -> None:
        self.router = router
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, url: str, params: dict[str, Any] | None = None) -> Any:
        self.calls.append((url, params or {}))
        return self.router(url, params or {})


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch):
    def install(router) -> FakeApi:
        fake = FakeApi(router)
        monkeypatch.setattr(http, "get_json", fake)
        return fake

    return install


def _rows(settings: Settings, sql: str):
    con = duckdb.connect(str(settings.warehouse_path), read_only=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


# --- weather ---------------------------------------------------------------------------------
def _weather_router(url: str, params: dict[str, Any]) -> dict[str, Any]:
    assert url == weather.ARCHIVE_URL
    days = ["2026-09-29", "2026-09-30", "2026-10-01"]
    base = 10.0 if params["latitude"] == 50.85 else 12.0
    return {
        "daily": {
            "time": days,
            **{v: [base + i for i, _ in enumerate(days)] for v in weather.DAILY_VARIABLES},
        }
    }


def _run_weather(settings: Settings, tmp_path: Path, today: date = TODAY) -> None:
    from nga.pipelines.common import destination

    pipeline = weather.build_pipeline(destination(settings), tmp_path / "pipelines")
    pipeline.run(weather.weather_source(settings, today, CITIES)).raise_on_failed_jobs()


def test_weather_row_shape_and_key(settings: Settings, tmp_path: Path, api) -> None:
    fake = api(_weather_router)
    _run_weather(settings, tmp_path)

    # one request per city, asking for the whole window ending at as_of
    assert len(fake.calls) == 2
    assert fake.calls[0][1]["start_date"] == "2026-09-01"
    assert fake.calls[0][1]["end_date"] == "2026-10-01"
    assert fake.calls[0][1]["daily"].split(",") == list(weather.DAILY_VARIABLES)

    rows = _rows(
        settings,
        "select country_code, city, latitude, longitude, date, temperature_2m_max, "
        "sunshine_duration, _dlt_load_id is not null from raw_open_meteo.daily_weather "
        "order by country_code, date",
    )
    assert len(rows) == 6
    assert rows[0] == ("BE", "Brussels", 50.85, 4.35, date(2026, 9, 29), 10.0, 10.0, True)
    keys = _rows(
        settings,
        "select count(*) - count(distinct (country_code, date)) from raw_open_meteo.daily_weather",
    )
    assert keys == [(0,)]


def test_weather_second_run_merges_and_looks_back_a_week(
    settings: Settings, tmp_path: Path, api
) -> None:
    fake = api(_weather_router)
    _run_weather(settings, tmp_path)
    fake.calls.clear()
    _run_weather(settings, tmp_path)

    assert _rows(settings, "select count(*) from raw_open_meteo.daily_weather") == [(6,)]
    # incremental: starts a week before the newest date it already holds, not at window start
    assert fake.calls[0][1]["start_date"] == "2026-09-24"


def test_weather_window_never_passes_the_archive_lag(
    settings: Settings, tmp_path: Path, api
) -> None:
    fake = api(_weather_router)
    _run_weather(settings, tmp_path, today=date(2026, 9, 20))
    # today - 2 days is before as_of, so that is the end of the window
    assert fake.calls[0][1]["end_date"] == "2026-09-18"


# --- fx --------------------------------------------------------------------------------------
def _fx_router(url: str, params: dict[str, Any]) -> dict[str, Any]:
    assert url.startswith(fx.BASE_URL)
    assert params == {"base": "EUR", "symbols": "GBP,CHF"}
    # a Friday and the following Monday: no weekend rows, as the ECB publishes
    return {
        "base": "EUR",
        "start_date": "2026-09-25",
        "end_date": "2026-09-28",
        "rates": {
            "2026-09-25": {"CHF": 0.94, "GBP": 0.86},
            "2026-09-28": {"CHF": 0.95, "GBP": 0.857},
        },
    }


def _run_fx(settings: Settings, tmp_path: Path) -> None:
    from nga.pipelines.common import destination

    pipeline = fx.build_pipeline(destination(settings), tmp_path / "pipelines")
    pipeline.run(fx.fx_source(settings, TODAY)).raise_on_failed_jobs()


def test_fx_unpivots_to_one_row_per_date_and_quote(settings: Settings, tmp_path: Path, api) -> None:
    api(_fx_router)
    _run_fx(settings, tmp_path)
    rows = _rows(
        settings,
        "select rate_date, base, quote, rate from raw_frankfurter.rates order by rate_date, quote",
    )
    assert rows == [
        (date(2026, 9, 25), "EUR", "CHF", 0.94),
        (date(2026, 9, 25), "EUR", "GBP", 0.86),
        (date(2026, 9, 28), "EUR", "CHF", 0.95),
        (date(2026, 9, 28), "EUR", "GBP", 0.857),
    ]


def test_fx_does_not_fill_weekend_gaps(settings: Settings, tmp_path: Path, api) -> None:
    api(_fx_router)
    _run_fx(settings, tmp_path)
    assert _rows(
        settings, "select count(*) from raw_frankfurter.rates where rate_date = '2026-09-26'"
    ) == [(0,)]


def test_fx_second_run_merges_a_revised_rate(settings: Settings, tmp_path: Path, api) -> None:
    api(_fx_router)
    _run_fx(settings, tmp_path)

    def revised(url: str, params: dict[str, Any]) -> dict[str, Any]:
        body = _fx_router(url, params)
        body["rates"]["2026-09-28"]["GBP"] = 0.9
        return body

    api(revised)
    _run_fx(settings, tmp_path)
    assert _rows(settings, "select count(*) from raw_frankfurter.rates") == [(4,)]
    assert _rows(
        settings,
        "select rate from raw_frankfurter.rates where rate_date = '2026-09-28' and quote = 'GBP'",
    ) == [(0.9,)]


def test_fx_long_windows_are_requested_in_chunks(api) -> None:
    fake = api(lambda url, params: {"base": "EUR", "rates": {}})
    rows = fx.fetch_rates(date(2025, 10, 1), date(2026, 10, 1), ("GBP",))
    assert rows == []
    assert len(fake.calls) == 5
    assert fake.calls[0][0].endswith("2025-10-01..2025-12-19")
    assert fake.calls[-1][0].endswith("2026-10-01")


# --- holidays --------------------------------------------------------------------------------
def _holiday(country: str, day: str, local: str, counties: list[str] | None) -> dict[str, Any]:
    return {
        "date": day,
        "localName": local,
        "name": local + " (en)",
        "countryCode": country,
        "fixed": True,
        "global": counties is None,
        "counties": counties,
        "launchYear": None,
        "types": ["Public"],
    }


def _holidays_router(url: str, params: dict[str, Any]) -> list[dict[str, Any]] | None:
    _, _, tail = url.partition("PublicHolidays/")
    year, country = tail.split("/")
    if country == "NL" and year == "2026":
        return None  # the API answers 204 with no body for a year it has nothing for
    return [
        _holiday(country, f"{year}-01-01", "Nieuwjaar", None),
        _holiday(country, f"{year}-08-01", "Regional day", ["GB-SCT", "GB-NIR"]),
    ]


def _run_holidays(settings: Settings, tmp_path: Path) -> None:
    from nga.pipelines.common import destination

    pipeline = holidays.build_pipeline(destination(settings), tmp_path / "pipelines")
    pipeline.run(holidays.holidays_source(settings)).raise_on_failed_jobs()


def test_holidays_fetch_every_country_for_every_year_in_the_window(
    settings: Settings, tmp_path: Path, api
) -> None:
    fake = api(_holidays_router)
    _run_holidays(settings, tmp_path)
    # window 2026-09-01..2026-10-01 is one calendar year
    assert [c[0].rsplit("PublicHolidays/", 1)[1] for c in fake.calls] == [
        f"2026/{c}" for c in holidays.COUNTRIES
    ]


def test_holidays_row_shape_counties_and_key(settings: Settings, tmp_path: Path, api) -> None:
    api(_holidays_router)
    _run_holidays(settings, tmp_path)
    rows = _rows(
        settings,
        "select country_code, date, local_name, name, is_fixed, is_global "
        "from raw_nager_date.holidays order by country_code, date",
    )
    assert len(rows) == 8  # NL has none
    assert rows[0] == ("BE", date(2026, 1, 1), "Nieuwjaar", "Nieuwjaar (en)", True, True)
    counties = _rows(
        settings,
        "select country_code, from_json(counties, '[\"VARCHAR\"]') from raw_nager_date.holidays "
        "where counties is not null and country_code = 'GB'",
    )
    assert counties == [("GB", ["GB-SCT", "GB-NIR"])]
    # a national holiday has no counties: the field stays null, nothing is invented
    assert _rows(
        settings,
        "select count(*) from raw_nager_date.holidays where is_global and counties is not null",
    ) == [(0,)]
    # lists stay on the row: no dlt child tables, which would lack _dlt_load_id
    assert _rows(
        settings,
        "select count(*) from information_schema.tables "
        "where table_schema = 'raw_nager_date' and table_name like 'holidays\\_\\_%' escape '\\'",
    ) == [(0,)]


def test_holidays_second_run_merges(settings: Settings, tmp_path: Path, api) -> None:
    api(_holidays_router)
    _run_holidays(settings, tmp_path)
    _run_holidays(settings, tmp_path)
    assert _rows(settings, "select count(*) from raw_nager_date.holidays") == [(8,)]
    assert _rows(
        settings, "select count(*) from raw_nager_date.holidays where counties is not null"
    ) == [(4,)]  # one regional holiday per country with data
