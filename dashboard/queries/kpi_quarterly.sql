-- Headline KPIs by quarter: compiled by MetricFlow from `nga metrics query --metrics realised_revenue_eur,orders,average_order_value_eur,return_rate --group-by metric_time__quarter`.
-- Regenerate with `nga dashboard-sql`; do not edit by hand.
SELECT
  strftime(CAST(metric_time__quarter AS DATE), '%Y-%m-%d') AS metric_time__quarter
  , realised_revenue_eur
  , orders
  , average_order_value_eur
  , return_rate
FROM (
  WITH cm_8_cte AS (
    SELECT
      metric_time__quarter
      , SUM(__realised_revenue_eur) AS realised_revenue_eur
      , SUM(__orders) AS orders
    FROM (
      SELECT
        DATE_TRUNC('quarter', order_date) AS metric_time__quarter
        , case when is_cancelled then 0 else 1 end AS __orders
        , realised_net_amount_eur AS __realised_revenue_eur
      FROM "next_gen_analytics"."nga_marts"."fct_orders" orders_src_10000
    ) subq_3
    GROUP BY
      metric_time__quarter
  )

  SELECT
    COALESCE(subq_5.metric_time__quarter, subq_7.metric_time__quarter, subq_14.metric_time__quarter) AS metric_time__quarter
    , MAX(subq_5.realised_revenue_eur) AS realised_revenue_eur
    , MAX(subq_5.orders) AS orders
    , MAX(subq_7.average_order_value_eur) AS average_order_value_eur
    , MAX(subq_14.return_rate) AS return_rate
  FROM (
    SELECT
      metric_time__quarter
      , realised_revenue_eur
      , orders
    FROM cm_8_cte
  ) subq_5
  FULL OUTER JOIN (
    SELECT
      metric_time__quarter
      , CAST(realised_revenue_eur AS DOUBLE) / CAST(NULLIF(orders, 0) AS DOUBLE) AS average_order_value_eur
    FROM cm_8_cte
  ) subq_7
  ON
    subq_5.metric_time__quarter = subq_7.metric_time__quarter
  FULL OUTER JOIN (
    SELECT
      metric_time__quarter
      , CAST(units_returned AS DOUBLE) / CAST(NULLIF(units_sold, 0) AS DOUBLE) AS return_rate
    FROM (
      SELECT
        DATE_TRUNC('quarter', order_date) AS metric_time__quarter
        , SUM(returned_quantity) AS units_returned
        , SUM(sold_quantity) AS units_sold
      FROM "next_gen_analytics"."nga_marts"."fct_order_items" order_items_src_10000
      GROUP BY
        DATE_TRUNC('quarter', order_date)
    ) subq_13
  ) subq_14
  ON
    COALESCE(subq_5.metric_time__quarter, subq_7.metric_time__quarter) = subq_14.metric_time__quarter
  GROUP BY
    COALESCE(subq_5.metric_time__quarter, subq_7.metric_time__quarter, subq_14.metric_time__quarter)
  ORDER BY metric_time__quarter
) AS metricflow
ORDER BY metric_time__quarter
