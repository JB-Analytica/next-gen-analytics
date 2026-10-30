---
name: answering-with-metricflow
description: Use when asked a business or data question about Noordkust (revenue, orders, customers, returns, rain gear, weather, countries, trends), or when building or refreshing the Noordkust KPI dashboard. Answers come from the governed MetricFlow metrics in dbt, never from hand-written SQL, unless no metric fits.
---

# Answering data questions through MetricFlow

The 29 metrics in `dbt/models/marts/_marts__metrics.yml` are the definitions. An answer that
comes from them is the same number every time and everywhere; SQL written for the occasion is
not. So every figure in an answer goes through MetricFlow.

## How

1. **Find the metric.** `uv run nga metrics list metrics` lists them with descriptions. Map the
   question's words onto one: "revenue" is `realised_revenue_eur` (not cancelled, returned lines
   removed, shipping excluded, EUR), "sales" too unless the person says booked or gross.
2. **Find the cut.** `uv run nga metrics list dimensions --metrics <metric>` lists what it can be
   grouped or filtered by. Country means the shipping country (`order__shipping_country`,
   `order_item__shipping_country`, or `country_day__country` for the weather metrics); the
   customer's home country is `customer__country`, used only when asked for.
3. **Query.** For example:
   `uv run nga metrics query --metrics realised_revenue_eur --group-by metric_time__month,order__shipping_country`.
   Filter with `--where "{{ Dimension('product__category') }} = 'rain_gear'"`; add `--explain` to
   show the SQL MetricFlow ran. Ratios (AOV, return rate, shares) are metrics already: query them,
   never average a ratio yourself.
4. **Answer** with the numbers as MetricFlow returned them (rounded for reading), the metric names
   used, and the query, so the person can rerun it.

`nga metrics` targets dev by default; prefix `DBT_TARGET=prod` for the production marts on
MotherDuck (what Orchestra builds daily and the dashboard reads). Use prod for answers.

## When no metric fits

Say so, then answer with SQL against `nga_marts` only, and label the figure as ad hoc and not a
governed metric. If the same question is likely to come back, suggest adding the metric to dbt.

## The data

Synthetic Noordkust Outdoor shop data, pinned to an as-of date of 2026-10-01 (one year back),
plus real weather (one city per country), ECB rates and public holidays. Never present it as a
real business's performance. A weak or absent effect (rain vs rain gear) is the honest answer.

## The KPI dashboard

The Noordkust KPI dashboard (a private Claude Dashboard artifact; `dashboard/artifact/` holds it) queries MotherDuck
live through the MotherDuck connector. Each of its four sources runs the SQL MetricFlow compiled
for it, kept in `dashboard/queries/<id>.sql`; a loader on the page turns the connector's answer
into rows. So it refreshes itself whenever someone opens it, and still shows governed numbers.

When a metric the dashboard uses changes, run `DBT_TARGET=prod uv run nga dashboard-sql`: it
rewrites `dashboard/queries/*.sql` (commit the diff). Then set each changed file's text as its
dataset's `source.args.sql`, unchanged, and run it once on the MotherDuck connector. Never write
dashboard SQL by hand.

After any change to the dashboard, export its `dash`, `datasets` and `files` documents into
`dashboard/artifact/` in the layout `dashboard/README.md` describes, and commit with the change.
