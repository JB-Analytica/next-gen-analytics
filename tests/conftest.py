from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import pytest

from nga.config import Settings


def make_settings(tmp_path: Path, **overrides) -> Settings:
    """Settings for a throwaway DuckDB warehouse, with a fixed as_of and a one-month window."""
    values = {
        "destination": "duckdb",
        "warehouse_path": tmp_path / "warehouse.duckdb",
        "motherduck_database": "next_gen_analytics",
        "as_of": date(2026, 10, 1),
        "history_days": 30,
        "fx_symbols": ("GBP", "CHF"),
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def source_db(tmp_path: Path) -> Path:
    """A miniature operational database with the same shape model2data produces.

    Money columns and currency hold the placeholders the DBML leaves for align_source.
    """
    path = tmp_path / "noordkust.duckdb"
    con = duckdb.connect(str(path))
    con.execute("create schema raw")
    con.execute(
        """
        create table raw.customers as
        select * from (values
            (1, 'Ann', 'Peeters', 'ann@example.be', 'BE', 'Gent', true,
             timestamp '2026-01-01 09:00', timestamp '2026-01-01 09:00'),
            (2, 'Tom', 'Smith', 'tom@example.co.uk', 'GB', 'Leeds', false,
             timestamp '2026-02-01 09:00', timestamp '2026-02-01 09:00'),
            (3, 'Eva', 'Meier', 'eva@example.ch', 'CH', 'Bern', false,
             timestamp '2026-02-02 09:00', timestamp '2026-02-02 09:00')
        ) t(id, first_name, last_name, email, country, city, is_marketing_opt_in,
            created_at, updated_at)
        """
    )
    con.execute(
        """
        create table raw.products as
        select * from (values
            (1, '5400000000017', 'word', 'rain_gear', 10000, true,
             timestamp '2026-01-01', timestamp '2026-01-01'),
            (2, '5400000000024', 'word', 'camping', 2000, true,
             timestamp '2026-01-01', timestamp '2026-01-01')
        ) t(id, sku, name, category, list_price_cents, is_active, created_at, updated_at)
        """
    )
    con.execute(
        """
        create table raw.orders as
        select * from (values
            (10, 1, 'delivered', 'EUR', 0, 0, 0, 'NL', timestamp '2026-03-01 10:00',
             timestamp '2026-03-02 10:00', timestamp '2026-03-04 10:00',
             timestamp '2026-03-01 10:00', timestamp '2026-03-04 10:00'),
            (11, 2, 'pending', 'EUR', 0, 0, 0, 'NL', timestamp '2026-03-05 10:00', null, null,
             timestamp '2026-03-05 10:00', timestamp '2026-03-05 10:00'),
            (12, 3, 'paid', 'EUR', 0, 0, 0, 'NL', timestamp '2026-03-06 10:00', null, null,
             timestamp '2026-03-06 10:00', timestamp '2026-03-06 10:00'),
            (13, 1, 'paid', 'EUR', 0, 0, 0, 'NL', timestamp '2026-03-07 10:00', null, null,
             timestamp '2026-03-07 10:00', timestamp '2026-03-07 10:00')
        ) t(id, customer_id, status, currency, subtotal_minor, shipping_minor, total_minor,
            shipping_country, ordered_at, shipped_at, delivered_at, created_at, updated_at)
        """
    )
    con.execute(
        """
        create table raw.order_items as
        select * from (values
            (100, 10, 1, 2, 1, 0, timestamp '2026-03-01 10:00'),
            (101, 10, 2, 1, 1, 0, timestamp '2026-03-01 10:00'),
            (102, 11, 1, 1, 1, 0, timestamp '2026-03-05 10:00'),
            (103, 12, 1, 1, 1, 0, timestamp '2026-03-06 10:00')
        ) t(id, order_id, product_id, quantity, unit_price_minor, discount_minor, created_at)
        """
    )
    con.execute(
        """
        create table raw.returns as
        select * from (values
            (1, 100, 'wrong_size', timestamp '2026-03-10 10:00', timestamp '2026-03-10 10:00',
             timestamp '2026-03-10 10:00')
        ) t(id, order_item_id, reason, returned_at, created_at, updated_at)
        """
    )
    con.close()
    return path
