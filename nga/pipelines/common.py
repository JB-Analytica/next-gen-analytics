"""What every pipeline shares: the destination, the pipeline factory and the lineage columns."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import dlt
import duckdb

from nga.config import DLT_PIPELINES_DIR, Settings

# The pyarrow backend hands dlt whole Arrow tables, and dlt will not rewrite them to add its
# lineage columns unless asked. Without _dlt_load_id there is nothing recording *when* a row
# arrived, which is exactly what dbt source freshness needs. Set as environment defaults rather
# than in .dlt/config.toml so the setting travels with the code and applies no matter which
# directory the pipeline is invoked from (tests included).
os.environ.setdefault("NORMALIZE__PARQUET_NORMALIZER__ADD_DLT_LOAD_ID", "true")
os.environ.setdefault("NORMALIZE__PARQUET_NORMALIZER__ADD_DLT_ID", "true")


def ensure_motherduck_database(
    settings: Settings, connect: Callable[..., Any] = duckdb.connect
) -> None:
    """Create the MotherDuck database if it is not there yet.

    dlt creates schemas, not databases, so a first run against a fresh account would fail
    without this. The name was validated as a plain identifier in `settings()`.
    """
    con = connect("md:", config={"motherduck_token": settings.motherduck_token or ""})
    try:
        con.execute(f"CREATE DATABASE IF NOT EXISTS {settings.motherduck_database}")
    finally:
        con.close()


def destination(settings: Settings) -> Any:
    """The dlt destination for the configured warehouse.

    MotherDuck in the cloud, a DuckDB file for tests and local runs. It is the only place the
    two differ: sources, hints and dbt models are the same for both.
    """
    if settings.destination == "duckdb":
        settings.warehouse_path.parent.mkdir(parents=True, exist_ok=True)
        return dlt.destinations.duckdb(str(settings.warehouse_path))
    ensure_motherduck_database(settings)
    return dlt.destinations.motherduck(
        credentials={
            "database": settings.motherduck_database,
            "password": settings.motherduck_token,
        }
    )


def build_pipeline(
    name: str, dataset: str, dest: Any, pipelines_dir: Path = DLT_PIPELINES_DIR
) -> dlt.Pipeline:
    if pipelines_dir == DLT_PIPELINES_DIR:
        # One local state per destination: the incremental cursors from a local DuckDB run must
        # never decide what a MotherDuck load skips (dlt only warns and ignores them today).
        pipelines_dir = pipelines_dir / str(getattr(dest, "destination_name", None) or "default")
    return dlt.pipeline(
        pipeline_name=name,
        destination=dest,
        dataset_name=dataset,
        pipelines_dir=str(pipelines_dir),
    )
