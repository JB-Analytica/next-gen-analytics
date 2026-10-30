"""Extract the Noordkust operational database into the warehouse with dlt.

The source is dlt's generic `sql_database` source over a SQLAlchemy URL. Here that URL points
at the DuckDB file model2data produced; against a real system it would be that Postgres or MySQL,
and nothing else in this module changes -- nothing downstream needs to know the shop is
synthetic.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import dlt
from dlt.common.pipeline import LoadInfo
from dlt.sources.sql_database import sql_database

from nga import generate as generate_stage
from nga.config import DLT_PIPELINES_DIR, RAW_SHOP, SOURCE_DUCKDB, SOURCE_SCHEMA, Settings
from nga.pipelines.common import build_pipeline as _build_pipeline
from nga.pipelines.common import destination

# Table -> cursor column. Mutable tables carry an `updated_at` the source keeps current, so only
# rows touched since the last run are read and merged in. `order_items` is append-only, so its
# monotonically increasing key is the cursor. Every table merges on `id`, which also makes the
# load idempotent: re-running never duplicates a row.
TABLES: dict[str, str] = {
    "customers": "updated_at",
    "products": "updated_at",
    "orders": "updated_at",
    "order_items": "id",
    "returns": "updated_at",
}


def shop_source(duckdb_path: Path = SOURCE_DUCKDB, schema: str = SOURCE_SCHEMA):
    warnings.filterwarnings("ignore", message="duckdb-engine doesn't yet support reflection")
    source = sql_database(
        credentials=f"duckdb:///{duckdb_path}",
        schema=schema,
        table_names=list(TABLES),
        backend="pyarrow",
    )
    for table, cursor in TABLES.items():
        source.resources[table].apply_hints(
            primary_key="id",
            write_disposition="merge",
            incremental=dlt.sources.incremental(cursor),
        )
    return source


def build_pipeline(dest: Any, pipelines_dir: Path = DLT_PIPELINES_DIR) -> dlt.Pipeline:
    return _build_pipeline("noordkust", RAW_SHOP, dest, pipelines_dir)


def ensure_source(duckdb_path: Path = SOURCE_DUCKDB) -> None:
    """Generate the synthetic source if it is not there.

    Orchestra runs on ephemeral compute with a fresh clone each time, so `nga load shop` has to
    work from a clean checkout in one command. The data is deterministic, so rebuilding it is
    safe.
    """
    if not duckdb_path.exists():
        generate_stage.generate()


def run(settings: Settings) -> LoadInfo:
    ensure_source()
    pipeline = build_pipeline(destination(settings))
    info = pipeline.run(shop_source())
    info.raise_on_failed_jobs()
    return info
