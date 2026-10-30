-- Monthly revenue by country: compiled by MetricFlow from `nga metrics query --metrics realised_revenue_eur --group-by metric_time__month,order__shipping_country`.
-- Regenerate with `nga dashboard-sql`; do not edit by hand.
SELECT
  strftime(CAST(metric_time__month AS DATE), '%Y-%m-%d') AS metric_time__month
  , order__shipping_country
  , realised_revenue_eur
FROM (
  SELECT
    DATE_TRUNC('month', order_date) AS metric_time__month
    , shipping_country_code AS order__shipping_country
    , SUM(realised_net_amount_eur) AS realised_revenue_eur
  FROM "next_gen_analytics"."nga_marts"."fct_orders" orders_src_10000
  GROUP BY
    DATE_TRUNC('month', order_date)
    , shipping_country_code
  ORDER BY metric_time__month, order__shipping_country
) AS metricflow
ORDER BY metric_time__month, order__shipping_country
