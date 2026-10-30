"""Paths and environment-driven settings shared by every stage of the stack.

The MotherDuck token has no default: a fresh clone must not be able to write anywhere. The
local DuckDB destination needs no configuration at all.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# --- the synthetic source system -------------------------------------------------------------
SOURCE_SYSTEM_NAME = "noordkust"
SOURCE_DBML = ROOT / "source_system" / f"{SOURCE_SYSTEM_NAME}.dbml"
GENERATED_DIR = ROOT / "source_system" / "generated"
# model2data writes dbt_<name>/ into its working directory and names the DuckDB file after the
# profile it generates; this is the file that plays the role of the operational database.
GENERATED_PROJECT_DIR = GENERATED_DIR / f"dbt_{SOURCE_SYSTEM_NAME}"
SOURCE_DUCKDB = GENERATED_PROJECT_DIR / f"{SOURCE_SYSTEM_NAME}_profile.duckdb"
SOURCE_SCHEMA = "raw"  # model2data seeds land here inside the DuckDB file

# --- warehouse and downstream ------------------------------------------------------------------
DBT_DIR = ROOT / "dbt"
DLT_PIPELINES_DIR = ROOT / ".dlt" / "pipelines"
DEFAULT_WAREHOUSE = ROOT / "warehouse" / "nga.duckdb"

# One dlt dataset per source system, named raw_<source>.
RAW_SHOP = "raw_noordkust"
RAW_WEATHER = "raw_open_meteo"
RAW_FX = "raw_frankfurter"
RAW_HOLIDAYS = "raw_nager_date"

DEFAULT_AS_OF = "2026-10-01"
# The synthetic history is one year long (model2data spreads dates over the 365 days before
# as_of), so the reference-data window covers the same year.
DEFAULT_HISTORY_DAYS = 365
DEFAULT_FX_SYMBOLS = ("GBP", "CHF")
# Open-Meteo's archive trails real time by a couple of days; ask for nothing later than this.
WEATHER_LAG_DAYS = 2

DESTINATIONS = ("motherduck", "duckdb")
DEFAULT_MOTHERDUCK_DATABASE = "next_gen_analytics"


class ConfigError(ValueError):
    """The environment is missing something the chosen destination needs."""


@dataclass(frozen=True)
class Settings:
    destination: str
    warehouse_path: Path
    motherduck_database: str
    as_of: date
    history_days: int
    fx_symbols: tuple[str, ...]
    motherduck_token: str | None = field(default=None, repr=False)

    @property
    def window_start(self) -> date:
        """First day of the reference-data window: the start of the synthetic history."""
        return self.as_of - timedelta(days=self.history_days)

    def window_end(self, today: date | None = None) -> date:
        """Last day to ask the weather archive for: as_of, but never past what it has yet."""
        today = today or date.today()
        return min(self.as_of, today - timedelta(days=WEATHER_LAG_DAYS))

    def subprocess_env(self) -> dict[str, str]:
        """Variables a child process (dbt) needs to reach the same warehouse as dlt."""
        env = {
            "NGA_DESTINATION": self.destination,
            "NGA_WAREHOUSE": str(self.warehouse_path),
            "NGA_MOTHERDUCK_DATABASE": self.motherduck_database,
        }
        if self.motherduck_token:
            env["MOTHERDUCK_TOKEN"] = self.motherduck_token
        return env


_DB_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def settings(env: dict[str, str] | None = None) -> Settings:
    """Read the settings from `env` (default: os.environ)."""
    env = dict(os.environ) if env is None else env
    destination = env.get("NGA_DESTINATION", "motherduck").strip().lower()
    if destination not in DESTINATIONS:
        raise ConfigError(f"NGA_DESTINATION must be one of {DESTINATIONS}, got {destination!r}")

    database = env.get("NGA_MOTHERDUCK_DATABASE", DEFAULT_MOTHERDUCK_DATABASE).strip()
    if not _DB_NAME.match(database):
        raise ConfigError(f"NGA_MOTHERDUCK_DATABASE must be a plain identifier, got {database!r}")
    token = env.get("MOTHERDUCK_TOKEN", "").strip() or None
    if destination == "motherduck" and token is None:
        raise ConfigError(
            "NGA_DESTINATION=motherduck needs MOTHERDUCK_TOKEN (create one in the MotherDuck "
            "settings). Use NGA_DESTINATION=duckdb to run locally with no account."
        )

    warehouse = env.get("NGA_WAREHOUSE")
    try:
        as_of = date.fromisoformat(env.get("NGA_AS_OF", DEFAULT_AS_OF))
        history_days = int(env.get("NGA_HISTORY_DAYS", DEFAULT_HISTORY_DAYS))
    except ValueError as exc:
        raise ConfigError(f"Bad NGA_AS_OF / NGA_HISTORY_DAYS: {exc}") from exc
    symbols = tuple(
        s.strip().upper()
        for s in env.get("NGA_FX_SYMBOLS", ",".join(DEFAULT_FX_SYMBOLS)).split(",")
        if s.strip()
    )
    return Settings(
        destination=destination,
        warehouse_path=Path(warehouse).expanduser() if warehouse else DEFAULT_WAREHOUSE,
        motherduck_database=database,
        motherduck_token=token,
        as_of=as_of,
        history_days=history_days,
        fx_symbols=symbols,
    )
