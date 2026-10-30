# Lightdash content

Metrics and dimensions come from the dbt project (`dbt/models/marts/`), never from here. This
folder holds the Lightdash charts, dashboard and spaces as code, exactly as `lightdash download`
writes them. Setup, connection and deploy: [`docs/lightdash.md`](../docs/lightdash.md).

## The Noordkust KPIs dashboard

It mirrors the Claude KPI dashboard in `dashboard/`, using the same governed metrics, all of
them translated from MetricFlow:

| Chart | Explore | Dimensions | Metrics | Type |
|---|---|---|---|---|
| Realised revenue, Orders, Average order value | `fct_orders` | order date (quarter) | `realised_revenue_eur`, `orders`, `average_order_value_eur` | big number, compared with the quarter before |
| Return rate | `fct_order_items` | order date (quarter) | `return_rate` | big number, compared with the quarter before |
| Realised revenue by month and shipping country | `fct_orders` | order date (month), shipping country | `realised_revenue_eur` | stacked column |
| Revenue by category | `fct_order_items` | `product_category` | `line_revenue_eur` | horizontal bar |
| Rain gear share of revenue | `fct_order_items` | order date (quarter) | `rain_gear_share_of_revenue` | line |
| Does rain sell rain gear? | `fct_daily_country_sales` | country | `rain_gear_revenue_per_dry_day_eur`, `rain_gear_revenue_per_rainy_day_eur` | clustered column |

The charts that cover a period read the twelve months from October 2025 to September 2026.

## Keeping the content as code

```bash
export PATH="/path/to/node24/bin:$PATH"                     # download and upload need Node 24 or later
npx -y @lightdash/cli@3.109.0 lint --path lightdash          # offline schema check
npx -y @lightdash/cli@3.109.0 upload --project <uuid> --path lightdash --force
npx -y @lightdash/cli@3.109.0 download --project <uuid> --path lightdash
```

`download` overwrites local edits, and `upload` overwrites changes made in the UI, so treat one
side as the source. After changing a chart in the UI, download it and commit the result. Field
IDs are `<explore>_<column or metric>`, plus `_month` or `_quarter` for a date interval.
Interval fields only exist when Lightdash knows a column is a date; see the deploy notes in the
guide. `lightdash/.lightdash-metadata.json` is git-ignored bookkeeping, and `check-yaml` skips
this folder.
