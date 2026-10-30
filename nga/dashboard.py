"""Compile the SQL behind the Noordkust KPI dashboard with MetricFlow.

Every dashboard dataset is one MetricFlow query over the governed metrics in dbt. This writes the
SQL MetricFlow compiles for it (`mf query --explain`) to dashboard/queries/<id>.sql, wrapped only
to format period columns as YYYY-MM-DD. The dashboard runs those queries live on the MotherDuck
connector, so it shows the same numbers as `nga metrics query`; they are committed so that a
change to a metric shows up as a diff here.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from nga.config import DBT_DIR, ROOT

SQL_DIR = ROOT / "dashboard" / "queries"


@dataclass(frozen=True)
class Dataset:
    id: str
    title: str
    metrics: tuple[str, ...]
    group_by: tuple[str, ...]

    def mf_args(self) -> list[str]:
        return [
            "query",
            "--metrics",
            ",".join(self.metrics),
            "--group-by",
            ",".join(self.group_by),
            "--order",
            ",".join(self.group_by),
            "--explain",
        ]

    def columns(self) -> tuple[str, ...]:
        return (*self.group_by, *self.metrics)

    def command(self) -> str:
        """The query as a person would type it, for the dashboard's source descriptions."""
        return (
            f"nga metrics query --metrics {','.join(self.metrics)} "
            f"--group-by {','.join(self.group_by)}"
        )


DATASETS = (
    Dataset(
        "kpi_quarterly",
        "Headline KPIs by quarter",
        ("realised_revenue_eur", "orders", "average_order_value_eur", "return_rate"),
        ("metric_time__quarter",),
    ),
    Dataset(
        "revenue_monthly_country",
        "Monthly revenue by country",
        ("realised_revenue_eur",),
        ("metric_time__month", "order__shipping_country"),
    ),
    Dataset(
        "category_quarterly",
        "Revenue by category and quarter",
        ("line_revenue_eur",),
        ("metric_time__quarter", "product__category"),
    ),
    Dataset(
        "weather_by_country",
        "Rainy vs dry days by country",
        (
            "rainy_day_share",
            "revenue_per_rainy_day_eur",
            "revenue_per_dry_day_eur",
            "rain_gear_revenue_per_rainy_day_eur",
            "rain_gear_revenue_per_dry_day_eur",
        ),
        ("country_day__country",),
    ),
)


def compiled_sql(explain_output: str) -> str:
    """The SQL from `mf query --explain` output (everything after its "SQL" banner line)."""
    lines = explain_output.splitlines()
    for i, line in enumerate(lines):
        if "SQL" in line and "--explain" in line:
            return "\n".join(lines[i + 1 :]).strip()
    raise ValueError("no SQL found in mf --explain output")


def wrap_sql(ds: Dataset, sql: str) -> str:
    """Select the dataset's columns from MetricFlow's query, periods as YYYY-MM-DD text."""
    cols = [
        f"strftime(CAST({c} AS DATE), '%Y-%m-%d') AS {c}" if c.startswith("metric_time") else c
        for c in ds.columns()
    ]
    select = "\n  , ".join(cols)
    body = "\n".join(("  " + line).rstrip() for line in sql.splitlines())
    return (
        f"-- {ds.title}: compiled by MetricFlow from `{ds.command()}`.\n"
        "-- Regenerate with `nga dashboard-sql`; do not edit by hand.\n"
        f"SELECT\n  {select}\n"
        f"FROM (\n{body}\n) AS metricflow\n"
        f"ORDER BY {', '.join(ds.group_by)}\n"
    )


Runner = Callable[[list[str]], str]


def _run_mf(args: list[str], env: Mapping[str, str]) -> str:
    result = subprocess.run(
        ["mf", *args], cwd=DBT_DIR, env=dict(env), check=True, capture_output=True, text=True
    )
    return result.stdout


def export(
    env: Mapping[str, str], sql_dir: Path = SQL_DIR, runner: Runner | None = None
) -> list[Path]:
    """Compile every dataset's query and write it to sql_dir; returns the files written."""
    run = runner or (lambda args: _run_mf(args, env))
    sql_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for ds in DATASETS:
        target = sql_dir / f"{ds.id}.sql"
        target.write_text(wrap_sql(ds, compiled_sql(run(ds.mf_args()))))
        written.append(target)
    return written
