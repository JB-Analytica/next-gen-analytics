# Lightdash front end

Lightdash can sit on top of the same dbt project and MotherDuck database as every other front
end here, and show the same numbers. The 29 business metrics are defined once, in dbt's
MetricFlow YAML (`dbt/models/marts/_marts__semantic_models.yml` and `_marts__metrics.yml`).
On deploy, Lightdash's CLI translates them into Lightdash metrics. There is no second copy of
a definition to keep in step.

This page was checked against `@lightdash/cli` 3.109.0, dbt Core 1.12.6 and dbt-duckdb 1.11.1,
on Lightdash Cloud against the MotherDuck prod marts. Every chart in `lightdash/` returns the
same figures as MetricFlow.

## How the translation works

Reference: <https://docs.lightdash.com/references/integrations/dbt-metricflow>

- It reads dbt's `target/manifest.json`, not `semantic_manifest.json`. `lightdash compile`,
  `preview` and `deploy` run `dbt` for you (`dbt ls`, which parses the project) and then
  translate the `semantic_models:` and `metrics:` found in the manifest.
- No flag turns it on and there is no config file for it. If the manifest has MetricFlow
  metrics, they are translated. Git-connected projects get the same translation server-side
  when Lightdash refreshes dbt.
- Needs dbt Core 1.6 or later. The legacy spec used here (top-level `semantic_models:` and
  `metrics:` with `type_params`) is supported, and so is the 1.12 inline spec.
- A metric with the same name in a model's `meta.metrics` overrides the translated one. This
  repo defines none, so everything comes from MetricFlow.
- Dimensions are not translated. Lightdash builds dimensions from each model's columns (all of
  them are documented in `_marts__models.yml`). Date columns get day, week, month, quarter and
  year automatically.
- Joins are not translated either; Lightdash joins are declared per model. One is declared,
  from `fct_order_items` to `dim_products` (`config.meta.joins` in `_marts__models.yml`, ignored
  by dbt and MetricFlow), so order-line metrics can be grouped by product category.
- Skipped metrics are reported as warnings. Add `--verbose` to see which and why.

What translates: `simple` metrics (sum, count, count_distinct, average, min, max, median,
percentile), `ratio` and `derived` metrics whose inputs are on the same semantic model, and
`filter:` on a metric when it only uses `Dimension()` of the same model. What does not:
`cumulative` and `conversion` metrics, ratio or derived inputs from different models, offset
windows, filters that reach into another model or use `TimeDimension()`, `Entity()` or
`Metric()`, `join_to_timespine`, `fill_nulls_with`, `non_additive_dimension`, and saved
queries.

### Our 29 metrics

All 29 translate. Running `lightdash compile` reports "Translated 29 MetricFlow metric(s) into Lightdash metrics".

| Lightdash explore | Translated metrics |
|---|---|
| `fct_orders` | `orders`, `orders_placed`, `cancelled_orders`, `cancellation_rate`, `realised_revenue_eur`, `booked_revenue_eur`, `shipping_revenue_eur`, `average_order_value_eur`, `active_customers` |
| `fct_order_items` | `units_sold`, `units_returned`, `return_rate`, `line_revenue_eur`, `rain_gear_revenue_eur`, `rain_gear_share_of_revenue` |
| `fct_returns` | `refunded_amount_eur` |
| `dim_customers` | `new_customers` |
| `fct_daily_country_sales` | `country_days`, `rainy_days`, `rainy_day_share`, `rainy_day_revenue_eur`, `revenue_per_rainy_day_eur`, `dry_days`, `dry_day_revenue_eur`, `revenue_per_dry_day_eur`, `rain_gear_revenue_on_rainy_days_eur`, `rain_gear_revenue_per_rainy_day_eur`, `rain_gear_revenue_on_dry_days_eur`, `rain_gear_revenue_per_dry_day_eur` |

The explore is the semantic model's underlying table (a metric is attached to the model its
measure comes from). That grouping follows from the documented behaviour; confirm it in the
explore list after the first deploy.

### Keeping filters on one semantic model

Lightdash's translator resolves a filter's `{{ Dimension('entity__dimension') }}` against the
metric's own semantic model only. It doesn't follow MetricFlow's entity joins. A filter that
reaches into another semantic model makes the translator skip the metric with a warning. Any
ratio or derived metric built on that metric is skipped too. Lightdash explores themselves
filter across joins; the restriction applies only to filters baked into a translated metric.

This repo first defined rain gear revenue with a filter on `Dimension('product__category')`.
`category` lives on the `products` semantic model, so the translator skipped
`rain_gear_revenue_eur`, and with it `rain_gear_share_of_revenue`:

```
Skipped MetricFlow metric "rain_gear_revenue_eur": filter references dimension "product__category" which does not resolve on semantic model "order_items" (cross-model filters are not supported).
```

The fix is in the model, not in Lightdash:

- `fct_order_items` carries `product_category`, copied from `dim_products`.
- The `order_items` semantic model exposes it as a dimension.
- The metric filters on `Dimension('order_item__product_category')`.

MetricFlow returns the same figures as before. The definition still lives in one place, and all
29 metrics translate. Apply the same pattern to any new filtered metric: put the column it
filters on into the measure's own model.

Do not work around a skip by recreating the metric in `meta.metrics`. That creates the second
copy of the definition that this setup exists to avoid.

## Connect Lightdash to MotherDuck

Docs: <https://motherduck.com/docs/integrations/bi-tools/lightdash/>. Works the same on Lightdash
Cloud and self-hosted (the instance needs outbound access to MotherDuck).

1. In MotherDuck, create an access token for Lightdash. Make it read-only; Lightdash only
   queries. Use a dedicated token (or service account) for Lightdash alone. The dbt job that builds the marts uses a separate read/write token.
2. In Lightdash, create a project and choose warehouse **DuckDB**, then the **MotherDuck**
   option at the top of the form.
3. Fill in:

   | Field | Value |
   |---|---|
   | Database | `next_gen_analytics` (the `NGA_MOTHERDUCK_DATABASE` value, with no `md:` prefix) |
   | Schema | `nga` (the dbt `prod` target schema; the marts themselves sit in `nga_marts`) |
   | Access token | the read-only token |
   | Threads | `1`, raise later |

   Lightdash queries each model at the schema recorded in the dbt manifest (`nga_marts`), so the
   connection's schema is only the default.
4. Do not point Lightdash at the dev schemas (`nga_dev_*`); only the prod marts are the
   contract.

dbt needs to be 1.8 or later for this connection; this repo uses 1.12.

## Deploy the dbt project

Requirements: Node 24 or later (`@lightdash/cli` declares `node >= 24`), and the project's
Python environment on `PATH` first so the CLI finds this repo's `dbt` (not a shell shim).

```bash
# once: log in with a personal access token (Lightdash, Settings, Personal access tokens)
npx -y @lightdash/cli@3.109.0 login https://<your-instance> --token <token>

# first time only: create the project without sending any warehouse credentials, then
# connect MotherDuck in the Lightdash UI (see above) with a read-only token
PATH="$PWD/.venv/bin:$PATH" npx -y @lightdash/cli@3.109.0 deploy \
  --project-dir dbt --profiles-dir dbt --target prod \
  --create "Noordkust" --no-warehouse-credentials --assume-yes

# every deploy: the marts only, with column types read from MotherDuck
export MOTHERDUCK_TOKEN=<token>             # stays local; the CLI reads it through the profile
PATH="$PWD/.venv/bin:$PATH" npx -y @lightdash/cli@3.109.0 deploy \
  --project-dir dbt --profiles-dir dbt --target lightdash \
  --select tag:bi --assume-yes --project <project uuid>
```

- `--create ... --no-warehouse-credentials` makes the project without uploading the
  token from your profile. It can't be combined with `--select`, so the first deploy also
  ships the staging models; the next deploy with `--select tag:bi` replaces them.
- `--target lightdash` is a dbt target in `dbt/profiles.yml` with the same database and
  schema as `prod`. The Lightdash CLI only finds a MotherDuck token in the profile's
  `settings.motherduck_token`, not in the environment the way dbt does. With `--target prod`
  the deploy stops at "MotherDuck duckdb targets require settings.motherduck_token".
- Don't deploy with `--skip-warehouse-catalog`. Without the catalog, CLI 3.109.0 replaces each
  column's YAML `data_type` with nothing, so every column becomes a string. Dates then get
  no month or quarter fields, and date filters fail with "No function has been implemented to
  render SQL for the filter operator". Only `meta.dimension.type` survives a skipped catalog.
- `--select tag:bi` exposes only the marts, the models `dbt_project.yml` tags `bi`. Staging
  and intermediate models never reach Lightdash.
- `--assume-yes` stops the CLI prompting (it hangs forever in CI otherwise), and `--project`
  stops it deploying to the CLI's current default project, which `--create` switches to the
  new one.
- The MetricFlow translation alone can be checked offline, with no account (skipping the
  catalog is fine here, because it only affects column types):

  ```bash
  NGA_DESTINATION=duckdb PATH="$PWD/.venv/bin:$PATH" npx -y @lightdash/cli@3.109.0 compile \
    --project-dir dbt --profiles-dir dbt --target prod --select tag:bi \
    --skip-warehouse-catalog --no-partial-compilation --verbose
  ```

  Expected: `Translated 29 MetricFlow metric(s)`, no skips, and `Compiled 7
  explores, SUCCESS=7 ERRORS=0`. This needs the local warehouse file only for `dbt ls`.
- To review a change before it reaches the shared project, use a preview project:
  `lightdash start-preview --name <branch> ...`, then `lightdash stop-preview`.
- Redeploy after every change to the metrics or marts YAML. For a Git-connected project,
  Lightdash does the compile when you refresh dbt, and the translation is the same.

## One definition per metric

- Change a metric in `_marts__metrics.yml` (or its measure in `_marts__semantic_models.yml`),
  nowhere else. `nga metrics validate-configs` and the dashboard SQL read it too.
- Redeploy; Lightdash shows the new definition. A chart built in Lightdash picks up the
  changed SQL because it only references the metric by name.
- A metric created in the Lightdash UI, or added to `meta.metrics`, is a second definition and
  is not allowed. If a metric cannot be translated (see above), express it in MetricFlow
  anyway, or slice an existing one by a dimension.
- Because a Lightdash metric is built from the same expression, the number matches the
  dashboard's compiled SQL. Verify after the first deploy by comparing, for example,
  `realised_revenue_eur` per quarter with `dashboard/queries/kpi_quarterly.sql`.

## The dashboard

`lightdash/` holds the Noordkust KPIs dashboard, its eight charts and its space, as written
by `lightdash download`. `lightdash/README.md` lists the charts and how to upload them to a
project. Each one queries MotherDuck live through the translated metrics. The screenshot in the
repository README is Lightdash's own dashboard export.
