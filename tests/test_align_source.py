"""align_source sets what a DBML hint cannot: currency, shipping country and the money columns."""

from __future__ import annotations

from pathlib import Path

import duckdb

from nga.generate import align_source


def _align(source_db: Path):
    align_source(source_db)
    return duckdb.connect(str(source_db), read_only=True)


def test_orders_without_items_are_dropped(source_db: Path) -> None:
    con = _align(source_db)
    assert con.execute("select count(*) from raw.orders where id = 13").fetchone() == (0,)
    assert con.execute("select count(*) from raw.orders").fetchone() == (3,)


def test_currency_follows_the_customer_country(source_db: Path) -> None:
    con = _align(source_db)
    rows = con.execute(
        "select c.country, o.currency from raw.orders o join raw.customers c "
        "on c.id = o.customer_id order by o.id"
    ).fetchall()
    assert rows == [("BE", "EUR"), ("GB", "GBP"), ("CH", "CHF")]


def test_shipping_country_is_the_customer_country_except_for_gifts(source_db: Path) -> None:
    con = _align(source_db)
    # order 10..12 are not multiples of 25, so none is a gift
    assert con.execute("select id, shipping_country from raw.orders order by id").fetchall() == [
        (10, "BE"),
        (11, "GB"),
        (12, "CH"),
    ]


def test_amounts_are_minor_units_in_the_order_currency_and_reconcile(source_db: Path) -> None:
    con = _align(source_db)
    # Order 11 (GBP): one 10000-cent product at 0.85 -> 8500 pence; under the 6500 free-shipping
    # threshold? No: 8500 >= 6500, so shipping is free.
    assert con.execute(
        "select unit_price_minor from raw.order_items where id = 102"
    ).fetchone() == (8500,)
    # Order 10 (EUR): 2 x 10000 + 1 x 2000 = 22000, free shipping from 7500.
    assert con.execute(
        "select subtotal_minor, shipping_minor, total_minor from raw.orders where id = 10"
    ).fetchone() == (22000, 0, 22000)
    # Order 12 (CHF): 9500 rappen, over the 7500 threshold.
    assert con.execute(
        "select subtotal_minor, shipping_minor, total_minor from raw.orders where id = 12"
    ).fetchone() == (9500, 0, 9500)
    mismatches = con.execute(
        "select count(*) from raw.orders where total_minor <> subtotal_minor + shipping_minor"
    ).fetchone()
    assert mismatches == (0,)


def test_small_orders_pay_the_flat_shipping_fee(source_db: Path) -> None:
    con = duckdb.connect(str(source_db))
    con.execute("update raw.products set list_price_cents = 1000 where id = 1")
    con.close()
    con = _align(source_db)
    # Order 11 (GBP): 850 pence, under the free-shipping threshold -> 450 pence shipping.
    assert con.execute(
        "select subtotal_minor, shipping_minor, total_minor from raw.orders where id = 11"
    ).fetchone() == (850, 450, 1300)


def test_products_get_readable_names(source_db: Path) -> None:
    con = _align(source_db)
    names = [r[0] for r in con.execute("select name from raw.products order by id").fetchall()]
    assert names == ["Kust Rain Jacket", "Kust Tent"]
