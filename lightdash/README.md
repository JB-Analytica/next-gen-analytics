# Lightdash content

Metrics and dimensions come from the dbt project (`dbt/models/marts/`), never from here. This
folder holds the dashboard blueprint and, once it exists, the charts and dashboards downloaded
from Lightdash. Setup, connection and deploy: [`docs/lightdash.md`](../docs/lightdash.md).

## Blueprint: the KPI dashboard

Mirrors the Claude KPI dashboard in `dashboard/` (same four charts, with the KPI table split in two because MetricFlow's fct_orders and fct_order_items metrics sit in different explores, same governed metrics).
Build it once in the Lightdash UI in a space called `Noordkust`, from these explores. Field
labels in the UI follow the metric `label` in `_marts__metrics.yml`.

| Chart | Explore | Dimensions | Metrics | Type |
|---|---|---|---|---|
| Headline KPIs by quarter (orders) | `fct_orders` | order date (quarter) | `realised_revenue_eur`, `orders`, `average_order_value_eur` | table |
| Return rate by quarter | `fct_order_items` | order date (quarter) | `return_rate` | line (add to the KPI table as a second tile) |
| Monthly revenue by country | `fct_orders` | order date (month), shipping country | `realised_revenue_eur` | stacked column |
| Revenue by category and quarter | `fct_order_items` | order date (quarter), `product_category` | `line_revenue_eur` | stacked column |
| Rainy vs dry days by country | `fct_daily_country_sales` | country | `rainy_day_share`, `revenue_per_rainy_day_eur`, `revenue_per_dry_day_eur`, `rain_gear_revenue_per_rainy_day_eur`, `rain_gear_revenue_per_dry_day_eur` | clustered column or table |

`rain_gear_revenue_eur` and `rain_gear_share_of_revenue` are available as translated metrics
in the `fct_order_items` explore as well.

## Keeping the content as code

```bash
# after building or changing a chart in the UI
npx -y @lightdash/cli@3.109.0 download --project <uuid>   # writes lightdash/charts, dashboards, spaces
npx -y @lightdash/cli@3.109.0 lint --path lightdash        # offline schema check
# to apply local edits to a project
npx -y @lightdash/cli@3.109.0 upload --project <uuid>
```

Download and upload need Node 24 or later. `download` overwrites local edits and `upload`
overwrites changes made in the UI, so treat one side as the source. Charts and dashboards are
edited in the UI and downloaded, not written by hand. `lightdash/.lightdash-metadata.json` is
git-ignored bookkeeping, and `check-yaml` skips this folder.
