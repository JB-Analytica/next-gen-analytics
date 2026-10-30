# dbt Charts

[dbt Charts](https://docs.dbtcharts.com) is dbt Labs' open-source command line tool, `dct`
(PyPI package `dbt-charts`). You describe a dashboard as a YAML "board": SQL queries, charts
bound to those queries, and a layout. `dct render` runs the queries and writes one
self-contained HTML file with no external scripts, no server and no account. Fonts are inlined
too, so the file opens from disk or any static host.

This repository ships one board, `charts/noordkust_kpis.yml`. It shows the same four headline
figures and three breakdowns as the Claude dashboard in `dashboard/`:

- realised revenue, orders, average order value and return rate for the latest quarter;
- realised revenue by month, stacked by shipping country;
- realised revenue by product category over the last four quarters;
- rain gear revenue per day on rainy and on dry days, by country.

## It reads the marts, not MetricFlow

dbt Charts has no connection to the dbt Semantic Layer. A board queries tables, and it reaches
them through `{{ ref('fct_orders') }}`, so the schema comes from the dbt manifest rather than
being typed into the board. The board computes each figure with plain SQL over `nga_marts`:

| Figure | SQL |
|---|---|
| Realised revenue | `sum(realised_net_amount_eur)` on `fct_orders` |
| Orders | `count(*) filter (where not is_cancelled)` on `fct_orders` |
| Average order value | realised revenue divided by orders |
| Return rate | `sum(returned_quantity) / sum(sold_quantity)` on `fct_order_items` |

These follow the definitions in `dbt/models/marts/_marts__metrics.yml`, but they are a copy, not
a reference. Change a metric definition and the board does not follow; edit its SQL too. The
board says so in its own header. The latest-quarter figures agree with the MetricFlow ones today. If you need one governed
definition behind every front end, use the dashboard or another MetricFlow-aware tool, and
treat the board as a mart-level view.

## Commands

You need the marts built in the `prod` target (schema `nga_marts`) and a manifest parsed
against the same target.

Install nothing globally; `uvx` runs the pinned versions on demand:

```bash
export DO_NOT_TRACK=1                       # dct 0.10.0 sends usage statistics otherwise
DCT="uvx --from dbt-charts==0.10.0 --with sqlglot==30.21.0 dct"
```

### Locally (DuckDB file, no accounts)

```bash
export NGA_DESTINATION=duckdb DBT_TARGET=prod
uv run nga run                  # first time only: generate, load, build warehouse/nga.duckdb
uv run nga transform            # or, if the file exists, just rebuild the marts in prod
uv run dbt parse --project-dir dbt --profiles-dir dbt   # writes dbt/target/manifest.json

cd charts
mkdir -p renders                # dct render does not create the output directory
$DCT validate --strict --project-dir . noordkust_kpis.yml
$DCT render --project-dir . noordkust_kpis.yml --format html --output renders/noordkust_kpis.html
python embed_brand_fonts.py renders/noordkust_kpis.html   # optional: Poppins
open renders/noordkust_kpis.html
```

`nga transform` already runs `dbt build` and leaves a manifest behind, so the separate `dbt parse`
only matters if you last built a different target. Run `dct` from `charts/`: `--output` is
resolved against `--project-dir`, so from the repository root the file would land in
`charts/charts/renders/`.

### Against MotherDuck

`dct 0.10.0` cannot connect to MotherDuck directly (see below). Copy the marts into a local file
with the same name the manifest expects, then render from that. Only `SELECT`s run against
MotherDuck; the attach is read-only.

```bash
export MOTHERDUCK_TOKEN=...      # from .env or your shell; a read-only token is enough
mkdir -p warehouse/motherduck
uv run python - <<'PY'
import duckdb
con = duckdb.connect("warehouse/motherduck/nga.duckdb")
con.execute("ATTACH 'md:next_gen_analytics' AS md (READ_ONLY)")
con.execute("create schema if not exists nga")
con.execute("create schema if not exists nga_marts")
tables = [r[0] for r in con.sql(
    "select table_name from information_schema.tables "
    "where table_catalog = 'md' and table_schema = 'nga_marts'").fetchall()]
for t in tables:
    con.execute(f"create or replace table nga_marts.{t} as select * from md.nga_marts.{t}")
PY

export DBT_TARGET=prod NGA_DESTINATION=duckdb NGA_WAREHOUSE=../warehouse/motherduck/nga.duckdb
uv run dbt parse --project-dir dbt --profiles-dir dbt
cd charts && mkdir -p renders
$DCT validate --strict --project-dir . noordkust_kpis.yml
$DCT render --no-cache --project-dir . noordkust_kpis.yml --format html --output renders/noordkust_kpis.html
```

The file is named `nga.duckdb` on purpose: dbt records the database name in the manifest, and for
a local file that is the file name without its extension. Keep it `nga`, in a directory of its
own, or the board looks for a catalog that does not exist. The path is relative because `dct`
resolves it against the dbt project directory, and an absolute path gets that directory glued in
front of it. The snapshot reflects MotherDuck as of the copy; repeat the copy to refresh it.

## Version pins, and why

| Pin | Why |
|---|---|
| `dbt-charts==0.10.0` | The tool is pre-1.0 and its YAML surface still moves; the compiler rejects unknown keys, so an unpinned upgrade can fail a board nobody touched. 0.10.0 is also the first release that accepts a euro prefix (`format: { spec: ",.0f", prefix: "€" }`) on a chart axis. |
| `sqlglot==30.21.0` | dbt Charts requires `sqlglot>=30.0.0` and checks every `ref()` column with it. From sqlglot 30.22.0 that check silently gives up (every query warns `WARN-DBT-QUERY-COLUMNS-INDETERMINATE`, and a missing column stops being an error), so it is pinned beside dbt Charts. |
| `DO_NOT_TRACK=1` | 0.10.0 sends anonymous usage statistics unless told not to. |

Raise a pin deliberately: bump it, run `validate --strict` and `render`, misspell a column the
board reads and confirm `ERR-DBT-MODEL-COLUMN-MISSING`, then read the release notes.

## What held up

- Installs with `uvx` alone. No account, no Node, no server.
- `dct validate` checks every column a query takes from a mart against the model SQL in the
  manifest, with no warehouse connection. Misspelling `is_cancelled` as `is_cancelledx` fails
  with `ERR-DBT-MODEL-COLUMN-MISSING` and a "did you mean" hint, before any data is touched.
- The render is one file of about 0.9 MB with the fonts embedded, and makes no network requests.
- Euro axes and KPIs print `€814,507` and `€174.60` with the pinned version, no workaround.
- Against the local warehouse the board shows, for the latest quarter (Q3 2026): realised revenue
  €814,507, 4,665 orders, average order value €174.60, return rate 5.15%. Q4 2025 realised
  revenue is €831,611. The same values come out of a copy of the MotherDuck marts.

## What did not

- **No MotherDuck connection.** A `dbt_profile` source opens the DuckDB path read-only as a file
  and prefixes the dbt directory, so `md:next_gen_analytics` becomes a path that does not exist;
  a plain `type: duckdb` source with `path: md:...` fails the same way. Hence the snapshot above.
- **Query cache.** `dct` keeps a per-user query cache shared by every project. While switching
  between warehouses a render failed with a stale connection error until `--no-cache` was used.
  Use `--no-cache` when you change the warehouse a board reads.
- **Brand fonts need a post-step.** dbt Charts has a closed font registry. A board asking for
  Poppins gets a bare `font-family: Poppins` with no font behind it, so `charts/embed_brand_fonts.py`
  appends the Poppins files (SIL Open Font License, in `charts/fonts/`) to the rendered HTML. It
  only fixes HTML output, and dbt Charts measures text with a narrower font than the one painted,
  so check dense charts for clipped labels.
- **The target must match the manifest.** `ref()` takes its schema from `dbt/target/manifest.json`.
  Parse against `dev` and render against `prod` and every query looks for `nga_dev_marts`. The
  board pins `target: prod`; parse with `DBT_TARGET=prod`.
- **Board discovery.** With `dbt_charts.yml` inside `charts/`, a bare `dct validate` does not find
  the board; name the file and pass `--project-dir .` (from `charts/`).
- **Hosted dbt Charts Cloud** connects only to BigQuery, Postgres, Redshift and Snowflake, so it
  cannot read this DuckDB or MotherDuck warehouse. The local HTML output is the deliverable.
