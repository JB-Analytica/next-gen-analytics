-- Revenue by category and quarter: compiled by MetricFlow from `nga metrics query --metrics line_revenue_eur --group-by metric_time__quarter,product__category`.
-- Regenerate with `nga dashboard-sql`; do not edit by hand.
SELECT
  strftime(CAST(metric_time__quarter AS DATE), '%Y-%m-%d') AS metric_time__quarter
  , product__category
  , line_revenue_eur
FROM (
  SELECT
    DATE_TRUNC('quarter', order_items_src_10000.order_date) AS metric_time__quarter
    , products_src_10000.category AS product__category
    , SUM(order_items_src_10000.realised_net_amount_eur) AS line_revenue_eur
  FROM "next_gen_analytics"."nga_marts"."fct_order_items" order_items_src_10000
  LEFT OUTER JOIN
    "next_gen_analytics"."nga_marts"."dim_products" products_src_10000
  ON
    order_items_src_10000.product_id = products_src_10000.product_id
  GROUP BY
    DATE_TRUNC('quarter', order_items_src_10000.order_date)
    , products_src_10000.category
  ORDER BY metric_time__quarter, product__category
) AS metricflow
ORDER BY metric_time__quarter, product__category
