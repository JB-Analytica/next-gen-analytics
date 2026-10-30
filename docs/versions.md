# Version pins

Two dependencies are held back on purpose. Revisit them when the reason below stops being true,
not before.

## `dbt-core>=1.12,<2`

dbt Core 2.0 is a release candidate and no adapter (dbt-duckdb, dbt-metricflow) accepts it yet.
The project uses features that need 1.12: `config.freshness.build_after` on models, the
`time_spine` block on a model, `loaded_at_field` under source `config`, and `data_tests:` with
`arguments:`. Raise the cap when dbt-duckdb and dbt-metricflow publish releases that declare
support for 2.x, then run `uv run nga run` and `uv run nga metrics validate-configs` before
merging.

## `sqlalchemy>=2.0,<2.0.55`

dlt reads the generated source system (a DuckDB file) through SQLAlchemy and `duckdb-engine`.

- **2.0.55** added a `pg_description` join to primary-key reflection that contains
  `CAST ... AS REGCLASS`. DuckDB has no `regclass` type, so reflecting the tables fails.
- **2.1** fails differently, on `pg_collation`, which DuckDB's PostgreSQL catalog emulation does
  not provide.
- **2.0.54** is the newest release that works.

Raise the cap when `duckdb-engine` reflects keys on a newer SQLAlchemy; the check is
`uv run pytest tests/test_shop_pipeline.py` and `uv run nga load shop`.
