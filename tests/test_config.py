from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from nga.config import ConfigError, settings
from nga.pipelines import common


def test_motherduck_is_the_default_destination() -> None:
    s = settings({"MOTHERDUCK_TOKEN": "t"})
    assert s.destination == "motherduck"
    assert s.motherduck_database == "next_gen_analytics"
    assert s.motherduck_token == "t"


def test_motherduck_without_a_token_is_a_clear_error() -> None:
    with pytest.raises(ConfigError, match="MOTHERDUCK_TOKEN"):
        settings({})
    with pytest.raises(ConfigError, match="MOTHERDUCK_TOKEN"):
        settings({"NGA_DESTINATION": "motherduck", "MOTHERDUCK_TOKEN": "  "})


def test_duckdb_needs_no_environment() -> None:
    """The local destination must run on a fresh clone with no .env and no account."""
    s = settings({"NGA_DESTINATION": "duckdb"})
    assert s.destination == "duckdb"
    assert s.warehouse_path.name == "nga.duckdb"
    assert s.warehouse_path.parent.name == "warehouse"
    assert s.as_of == date(2026, 10, 1)
    assert s.history_days == 365
    assert s.fx_symbols == ("GBP", "CHF")


def test_unknown_destination_is_rejected() -> None:
    with pytest.raises(ConfigError, match="NGA_DESTINATION"):
        settings({"NGA_DESTINATION": "bigquery"})


def test_overrides(tmp_path: Path) -> None:
    s = settings(
        {
            "NGA_DESTINATION": "duckdb",
            "NGA_WAREHOUSE": str(tmp_path / "w.duckdb"),
            "NGA_AS_OF": "2026-12-31",
            "NGA_HISTORY_DAYS": "30",
            "NGA_FX_SYMBOLS": "gbp, usd",
            "NGA_MOTHERDUCK_DATABASE": "other_db",
        }
    )
    assert s.warehouse_path == tmp_path / "w.duckdb"
    assert s.as_of == date(2026, 12, 31)
    assert s.window_start == date(2026, 12, 1)
    assert s.fx_symbols == ("GBP", "USD")
    assert s.motherduck_database == "other_db"


def test_database_name_must_be_a_plain_identifier() -> None:
    with pytest.raises(ConfigError, match="NGA_MOTHERDUCK_DATABASE"):
        settings({"NGA_DESTINATION": "duckdb", "NGA_MOTHERDUCK_DATABASE": "x; drop database y"})


def test_window_end_respects_the_archive_lag() -> None:
    s = settings({"NGA_DESTINATION": "duckdb"})
    assert s.window_end(today=date(2026, 12, 1)) == date(2026, 10, 1)
    assert s.window_end(today=date(2026, 9, 20)) == date(2026, 9, 18)


def test_subprocess_env_carries_the_warehouse_but_not_a_missing_token() -> None:
    local = settings({"NGA_DESTINATION": "duckdb"}).subprocess_env()
    assert local["NGA_DESTINATION"] == "duckdb"
    assert "MOTHERDUCK_TOKEN" not in local
    cloud = settings({"MOTHERDUCK_TOKEN": "t"}).subprocess_env()
    assert cloud["MOTHERDUCK_TOKEN"] == "t"
    assert cloud["NGA_MOTHERDUCK_DATABASE"] == "next_gen_analytics"


def test_token_is_not_in_the_repr() -> None:
    assert "secret-value" not in repr(settings({"MOTHERDUCK_TOKEN": "secret-value"}))


def test_load_path_creates_the_database_first() -> None:
    """dlt makes schemas, not databases: the database must exist before the first load."""
    executed: list[str] = []

    class FakeCon:
        def execute(self, sql: str) -> None:
            executed.append(sql)

        def close(self) -> None:
            executed.append("closed")

    seen: dict = {}

    def fake_connect(target: str, config: dict | None = None) -> FakeCon:
        seen.update(target=target, config=config)
        return FakeCon()

    common.ensure_motherduck_database(settings({"MOTHERDUCK_TOKEN": "t"}), fake_connect)
    assert seen == {"target": "md:", "config": {"motherduck_token": "t"}}
    assert executed == ["CREATE DATABASE IF NOT EXISTS next_gen_analytics", "closed"]


def test_duckdb_destination_never_touches_motherduck(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def boom(*a, **k):
        raise AssertionError("must not connect to MotherDuck")

    monkeypatch.setattr(common, "ensure_motherduck_database", boom)
    s = settings({"NGA_DESTINATION": "duckdb", "NGA_WAREHOUSE": str(tmp_path / "x" / "w.duckdb")})
    common.destination(s)
    assert (tmp_path / "x").is_dir()
