"""Run the real dlt source against a throwaway DuckDB warehouse, one per test."""

from __future__ import annotations

from pathlib import Path

import dlt
import duckdb

from nga.config import RAW_SHOP
from nga.pipelines.shop import TABLES, build_pipeline, shop_source


def _pipeline(tmp_path: Path):
    dest = dlt.destinations.duckdb(str(tmp_path / "warehouse.duckdb"))
    return build_pipeline(dest, pipelines_dir=tmp_path / "pipelines")


def _query(tmp_path: Path, sql: str):
    con = duckdb.connect(str(tmp_path / "warehouse.duckdb"), read_only=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def _count(tmp_path: Path, table: str) -> int:
    return _query(tmp_path, f"select count(*) from {RAW_SHOP}.{table}")[0][0]


def test_first_load_brings_every_table(tmp_path: Path, source_db: Path) -> None:
    info = _pipeline(tmp_path).run(shop_source(source_db))
    info.raise_on_failed_jobs()
    assert {t: _count(tmp_path, t) for t in TABLES} == {
        "customers": 3,
        "products": 2,
        "orders": 4,
        "order_items": 4,
        "returns": 1,
    }


def test_lineage_columns_are_present(tmp_path: Path, source_db: Path) -> None:
    _pipeline(tmp_path).run(shop_source(source_db))
    nulls = _query(
        tmp_path,
        f"select count(*) from {RAW_SHOP}.orders where _dlt_load_id is null or _dlt_id is null",
    )
    assert nulls == [(0,)]


def test_rerun_is_idempotent(tmp_path: Path, source_db: Path) -> None:
    p = _pipeline(tmp_path)
    p.run(shop_source(source_db))
    p.run(shop_source(source_db))
    assert _count(tmp_path, "orders") == 4
    assert _count(tmp_path, "order_items") == 4


def test_updated_row_is_merged_not_duplicated(tmp_path: Path, source_db: Path) -> None:
    p = _pipeline(tmp_path)
    p.run(shop_source(source_db))

    con = duckdb.connect(str(source_db))
    con.execute(
        "update raw.orders set status = 'cancelled', updated_at = timestamp '2026-04-01' "
        "where id = 11"
    )
    con.execute("insert into raw.order_items values (104, 11, 2, 3, 1, 0, timestamp '2026-04-01')")
    con.close()

    p.run(shop_source(source_db))
    assert _count(tmp_path, "orders") == 4
    assert _count(tmp_path, "order_items") == 5
    assert _query(tmp_path, f"select status from {RAW_SHOP}.orders where id = 11") == [
        ("cancelled",)
    ]
