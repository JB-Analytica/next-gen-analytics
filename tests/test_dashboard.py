"""The dashboard SQL: one MetricFlow-compiled query per dataset, wrapped with text periods."""

from __future__ import annotations

from pathlib import Path

from nga import dashboard

EXPLAIN = (
    "$ mf query ...\n"
    "🔎 SQL (remove --explain to see data or add --show-dataflow-plan):\n\n"
    "SELECT 1 AS x\n"
)


def test_export_writes_one_compiled_query_per_dataset(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_mf(args: list[str]) -> str:
        calls.append(args)
        return EXPLAIN

    files = dashboard.export({}, sql_dir=tmp_path, runner=fake_mf)
    assert [f.stem for f in files] == [d.id for d in dashboard.DATASETS]
    assert all(a[0] == "query" and a[-1] == "--explain" for a in calls)
    assert "SELECT 1 AS x" in files[0].read_text()


def test_compiled_sql_is_wrapped_with_text_periods() -> None:
    ds = dashboard.DATASETS[0]
    sql = dashboard.wrap_sql(ds, dashboard.compiled_sql(EXPLAIN))
    assert "strftime(CAST(metric_time__quarter AS DATE), '%Y-%m-%d') AS metric_time__quarter" in sql
    assert "SELECT 1 AS x" in sql
    assert sql.rstrip().endswith("ORDER BY metric_time__quarter")
    for col in ds.metrics:
        assert f", {col}" in sql


ARTIFACT = dashboard.SQL_DIR.parent / "artifact"


def test_backup_queries_are_the_compiled_sql() -> None:
    """The dashboard's backed-up live queries must be exactly what MetricFlow compiled."""
    import json

    for ds in dashboard.DATASETS:
        doc = json.loads((ARTIFACT / "datasets" / f"{ds.id}.json").read_text())
        assert doc["source"]["connector"] == "MotherDuck", ds.id
        compiled = (dashboard.SQL_DIR / f"{ds.id}.sql").read_text().rstrip("\n")
        assert doc["source"]["args"]["sql"] == compiled, (
            f"{ds.id}: the dashboard runs different SQL than dashboard/queries; "
            "set the compiled query in the dashboard and refresh the backup"
        )


def test_backup_page_loads_every_dataset() -> None:
    page = (ARTIFACT / "index.html").read_text()
    for ds in dashboard.DATASETS:
        assert f"'{ds.id}'" in page, f"{ds.id} is missing from the page's MotherDuck loader"
