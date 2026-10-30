"""Stage 1: turn the DBML data model into a running "operational database".

model2data generates relationship-preserving synthetic data plus a small dbt project around it;
building that project materialises the seeds into a DuckDB file, which then stands in for the
source system that dlt extracts from. Against a real database this whole module drops out and
the dlt source points at that Postgres / MySQL / SaaS API instead.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

from nga.config import (
    DEFAULT_AS_OF,
    GENERATED_DIR,
    GENERATED_PROJECT_DIR,
    SOURCE_DBML,
    SOURCE_DUCKDB,
    SOURCE_SYSTEM_NAME,
)


@dataclass(frozen=True)
class BusinessShape:
    """The knobs that make the synthetic data look like a business rather than noise.

    Every value is deliberate and deterministic: the same shape + seed always produces the
    same rows, so a demo, a test fixture and a CI run all see identical data.
    """

    seed: int = 42
    # Anchor for every generated date; pinned so runs are reproducible. NGA_AS_OF overrides it.
    as_of: str = field(default_factory=lambda: os.environ.get("NGA_AS_OF", DEFAULT_AS_OF))
    locale: str = "nl_BE"  # a Benelux shop: Belgian names, cities and postcodes
    rows: int = 100
    # orders is generated high on purpose: model2data leaves two in five without items and
    # align_source drops those, which lands on roughly 12,000 orders.
    rows_for: dict[str, int] = field(
        default_factory=lambda: {
            "customers": 1500,
            "products": 80,
            "orders": 30000,
            "order_items": 26000,
            "returns": 2600,  # about half survive align_source: one per line, delivered orders only
        }
    )
    business_hours: bool = True  # orders cluster in waking hours and on weekdays
    growth: float = 0.6  # the shop grows ~60% over the window
    seasonality: float = 0.4  # Q4 peak and a spring bump: the shape outdoor retail has
    skew: float = 0.5  # a minority of customers place most of the orders

    def cli_args(self, dbml: Path = SOURCE_DBML, name: str = SOURCE_SYSTEM_NAME) -> list[str]:
        args = [
            "--file",
            str(dbml),
            "--name",
            name,
            "--rows",
            str(self.rows),
            "--seed",
            str(self.seed),
            "--as-of",
            self.as_of,
            "--locale",
            self.locale,
            "--growth",
            str(self.growth),
            "--seasonality",
            str(self.seasonality),
            "--skew",
            str(self.skew),
            "--force",
        ]
        if self.business_hours:
            args.append("--business-hours")
        for table, n in self.rows_for.items():
            args += ["--rows-for", f"{table}={n}"]
        return args


# dbt reads these straight from the environment, so whatever this repo's own dbt run needs
# would otherwise leak into the *generated* project -- which is a separate dbt project with
# its own profile and only a `dev` target.
_INHERITED_DBT_VARS = ("DBT_TARGET", "DBT_PROFILES_DIR", "DBT_PROJECT_DIR")


def _generated_project_env() -> dict[str, str]:
    """The environment for the generated project: this one, minus anything aimed at our own dbt.

    The interpreter's own bin directory goes first on PATH so `model2data` and `dbt` resolve
    to the ones this environment installed, with or without `uv run` around us.
    """
    env = {k: v for k, v in os.environ.items() if k not in _INHERITED_DBT_VARS}
    env["PATH"] = os.pathsep.join([str(Path(sys.executable).parent), env.get("PATH", "")])
    return env


# --- what model2data cannot express ------------------------------------------------------------
# Currency, shipping country and the money columns depend on other tables (the customer's
# country, the order's items), which a DBML hint cannot say. They are set here, deterministically,
# straight after generation, so the file dlt reads is internally consistent.
LIST_PRICE_RATE = {"EUR": 1.0, "GBP": 0.85, "CHF": 0.95}  # list price in euro -> order currency
SHIPPING_FEE_MINOR = {"EUR": 495, "GBP": 450, "CHF": 695}
FREE_SHIPPING_FROM_MINOR = {"EUR": 7500, "GBP": 6500, "CHF": 7500}
GIFT_EVERY = 25  # one order in 25 ships to a country other than the customer's

PRODUCT_NOUNS = {
    "rain_gear": ["Rain Jacket", "Rain Trousers", "Poncho", "Overshoes", "Cape", "Shell"],
    "cycling_apparel": ["Jersey", "Bib Shorts", "Gilet", "Base Layer", "Gloves", "Thermal Tights"],
    "bike_parts": ["Tyre", "Inner Tube", "Chain", "Saddle", "Pedals", "Bar Tape", "Light Set"],
    "camping": ["Tent", "Sleeping Bag", "Stove", "Mat", "Headlamp", "Backpack", "Flask"],
    "footwear": ["Trail Shoe", "Hiking Boot", "Cycling Shoe", "Sandal", "Gaiter", "Insole"],
}
PRODUCT_SERIES = ["Kust", "Duin", "Polder", "Ardennen", "Noord", "Zeeland", "Fjord", "Heide"]


def align_source(db_path: Path = SOURCE_DUCKDB) -> None:
    """Make the generated tables consistent in the ways a DBML hint cannot express."""
    con = duckdb.connect(str(db_path))
    try:
        # Orders without any item are not orders a shop would have; drop them.
        con.execute("delete from raw.orders where id not in (select order_id from raw.order_items)")
        con.execute(
            f"""
            update raw.orders o set
                currency = case c.country when 'GB' then 'GBP' when 'CH' then 'CHF' else 'EUR' end,
                shipping_country = case when o.id % {GIFT_EVERY} = 0 then o.shipping_country
                                        else c.country end
            from raw.customers c where c.id = o.customer_id
            """
        )
        rates = ", ".join(f"('{k}', {v})" for k, v in LIST_PRICE_RATE.items())
        con.execute(
            f"""
            update raw.order_items i set
                unit_price_minor = cast(round(p.list_price_cents * r.rate) as integer),
                discount_minor = case when i.id % 4 = 0 then
                    cast(least(round(i.discount_minor * r.rate),
                               round(p.list_price_cents * r.rate) * i.quantity // 2) as integer)
                    else 0 end
            from raw.products p, raw.orders o, (values {rates}) r(currency, rate)
            where p.id = i.product_id and o.id = i.order_id and r.currency = o.currency
            """
        )
        fees = ", ".join(
            f"('{k}', {SHIPPING_FEE_MINOR[k]}, {FREE_SHIPPING_FROM_MINOR[k]})"
            for k in SHIPPING_FEE_MINOR
        )
        con.execute(
            f"""
            update raw.orders o set
                subtotal_minor = t.subtotal,
                shipping_minor = case when t.subtotal >= f.free_from then 0 else f.fee end,
                total_minor = t.subtotal + case when t.subtotal >= f.free_from then 0 else f.fee end
            from (select order_id, sum(quantity * unit_price_minor - discount_minor) as subtotal
                  from raw.order_items group by order_id) t,
                 (values {fees}) f(currency, fee, free_from)
            where t.order_id = o.id and f.currency = o.currency
            """
        )
        # Dates that depend on another table. model2data's cross-table "after" draws the child's
        # date first and then picks only parents older than it, so it is not used for these.
        con.execute(
            "update raw.order_items i set created_at = o.ordered_at "
            "from raw.orders o where o.id = i.order_id"
        )
        # The catalogue predates the first order of each product.
        con.execute(
            """
            update raw.products p set
                created_at = least(p.created_at, f.first_ordered_at - interval 1 day),
                updated_at = greatest(p.updated_at, least(p.created_at,
                                                         f.first_ordered_at - interval 1 day))
            from (select product_id, min(created_at) as first_ordered_at
                  from raw.order_items group by product_id) f
            where f.product_id = p.id
            """
        )
        # A line is returned at most once, only once delivered, 1-28 days later, and never after
        # the last order in the data (the as-of moment).
        con.execute(
            """
            delete from raw.returns r where r.id not in (
                select min(r2.id) from raw.returns r2 group by r2.order_item_id)
            or r.order_item_id not in (
                select i.id from raw.order_items i join raw.orders o on o.id = i.order_id
                where o.status = 'delivered')
            """
        )
        con.execute(
            """
            update raw.returns r set
                returned_at = o.delivered_at + to_days(1 + r.id % 28) + to_hours(r.id % 10),
                created_at = o.delivered_at + to_days(1 + r.id % 28) + to_hours(r.id % 10),
                updated_at = o.delivered_at + to_days(1 + r.id % 28) + to_hours(r.id % 10)
            from raw.order_items i, raw.orders o
            where i.id = r.order_item_id and o.id = i.order_id
            """
        )
        con.execute(
            "delete from raw.returns where returned_at > (select max(ordered_at) from raw.orders)"
        )
        # Readable product names in place of single random words.
        seen: dict[str, int] = {}
        rows = con.execute("select id, category from raw.products order by id").fetchall()
        for product_id, category in rows:
            n = seen.get(category, 0)
            seen[category] = n + 1
            nouns = PRODUCT_NOUNS[category]
            name = (
                f"{PRODUCT_SERIES[(n // len(nouns)) % len(PRODUCT_SERIES)]} {nouns[n % len(nouns)]}"
            )
            con.execute("update raw.products set name = ? where id = ?", [name, product_id])
    finally:
        con.close()


def generate(shape: BusinessShape | None = None) -> None:
    """Generate the synthetic source system and materialise it as a DuckDB database."""
    shape = shape or BusinessShape()
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    if GENERATED_PROJECT_DIR.exists():
        shutil.rmtree(GENERATED_PROJECT_DIR)

    env = _generated_project_env()
    subprocess.run(["model2data", *shape.cli_args()], cwd=GENERATED_DIR, check=True, env=env)
    # One `dbt build` loads the seeds, builds model2data's staging views and runs its tests --
    # the generated project's own verification that the data is internally consistent.
    # Not --quiet: when this fails, the reason is the only thing worth having.
    subprocess.run(
        ["dbt", "build", "--profiles-dir", "."],
        cwd=GENERATED_PROJECT_DIR,
        check=True,
        env=env,
    )
    if not SOURCE_DUCKDB.exists():
        raise RuntimeError(f"Expected {SOURCE_DUCKDB} after building the generated project")
    align_source()
