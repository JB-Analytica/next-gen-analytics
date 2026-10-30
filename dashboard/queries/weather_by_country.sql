-- Rainy vs dry days by country: compiled by MetricFlow from `nga metrics query --metrics rainy_day_share,revenue_per_rainy_day_eur,revenue_per_dry_day_eur,rain_gear_revenue_per_rainy_day_eur,rain_gear_revenue_per_dry_day_eur --group-by country_day__country`.
-- Regenerate with `nga dashboard-sql`; do not edit by hand.
SELECT
  country_day__country
  , rainy_day_share
  , revenue_per_rainy_day_eur
  , revenue_per_dry_day_eur
  , rain_gear_revenue_per_rainy_day_eur
  , rain_gear_revenue_per_dry_day_eur
FROM (
  WITH sma_10002_cte AS (
    SELECT
      country_code AS country_day__country
      , is_rainy_day AS country_day__is_rainy_day
      , CASE WHEN country_day_id IS NOT NULL THEN 1 ELSE 0 END AS __country_days
      , case when is_rainy_day then 1 else 0 end AS __rainy_days
      , realised_net_revenue_eur AS __rainy_day_revenue_eur
      , realised_net_revenue_eur AS __dry_day_revenue_eur
      , CASE WHEN country_day_id IS NOT NULL THEN 1 ELSE 0 END AS __dry_days
      , rain_gear_realised_net_revenue_eur AS __rain_gear_revenue_on_rainy_days_eur
      , rain_gear_realised_net_revenue_eur AS __rain_gear_revenue_on_dry_days_eur
    FROM "next_gen_analytics"."nga_marts"."fct_daily_country_sales" daily_country_sales_src_10000
  )

  , cm_12_cte AS (
    SELECT
      country_day__country
      , SUM(__rainy_days) AS rainy_days
    FROM sma_10002_cte
    GROUP BY
      country_day__country
  )

  SELECT
    COALESCE(subq_5.country_day__country, subq_18.country_day__country, subq_25.country_day__country, subq_34.country_day__country) AS country_day__country
    , MAX(CAST(subq_5.rainy_days AS DOUBLE) / CAST(NULLIF(subq_5.country_days, 0) AS DOUBLE)) AS rainy_day_share
    , MAX(CAST(subq_18.rainy_day_revenue_eur AS DOUBLE) / CAST(NULLIF(subq_18.rainy_days, 0) AS DOUBLE)) AS revenue_per_rainy_day_eur
    , MAX(CAST(subq_25.dry_day_revenue_eur AS DOUBLE) / CAST(NULLIF(subq_25.dry_days, 0) AS DOUBLE)) AS revenue_per_dry_day_eur
    , MAX(CAST(subq_25.rain_gear_revenue_on_dry_days_eur AS DOUBLE) / CAST(NULLIF(subq_25.dry_days, 0) AS DOUBLE)) AS rain_gear_revenue_per_dry_day_eur
    , MAX(CAST(subq_34.rain_gear_revenue_on_rainy_days_eur AS DOUBLE) / CAST(NULLIF(subq_34.rainy_days, 0) AS DOUBLE)) AS rain_gear_revenue_per_rainy_day_eur
  FROM (
    SELECT
      country_day__country
      , SUM(__rainy_days) AS rainy_days
      , SUM(__country_days) AS country_days
    FROM sma_10002_cte
    GROUP BY
      country_day__country
  ) subq_5
  FULL OUTER JOIN (
    SELECT
      COALESCE(subq_12.country_day__country, cm_12_cte.country_day__country) AS country_day__country
      , MAX(subq_12.rainy_day_revenue_eur) AS rainy_day_revenue_eur
      , MAX(cm_12_cte.rainy_days) AS rainy_days
    FROM (
      SELECT
        country_day__country
        , SUM(rainy_day_revenue_eur) AS rainy_day_revenue_eur
      FROM (
        SELECT
          country_day__country
          , country_day__is_rainy_day
          , __rainy_day_revenue_eur AS rainy_day_revenue_eur
        FROM sma_10002_cte
      ) subq_8
      WHERE country_day__is_rainy_day
      GROUP BY
        country_day__country
    ) subq_12
    FULL OUTER JOIN
      cm_12_cte
    ON
      subq_12.country_day__country = cm_12_cte.country_day__country
    GROUP BY
      COALESCE(subq_12.country_day__country, cm_12_cte.country_day__country)
  ) subq_18
  ON
    subq_5.country_day__country = subq_18.country_day__country
  FULL OUTER JOIN (
    SELECT
      country_day__country
      , SUM(dry_day_revenue_eur) AS dry_day_revenue_eur
      , SUM(dry_days) AS dry_days
      , SUM(rain_gear_revenue_on_dry_days_eur) AS rain_gear_revenue_on_dry_days_eur
    FROM (
      SELECT
        country_day__country
        , country_day__is_rainy_day
        , __dry_day_revenue_eur AS dry_day_revenue_eur
        , __dry_days AS dry_days
        , __rain_gear_revenue_on_dry_days_eur AS rain_gear_revenue_on_dry_days_eur
      FROM sma_10002_cte
    ) subq_21
    WHERE not country_day__is_rainy_day
    GROUP BY
      country_day__country
  ) subq_25
  ON
    COALESCE(subq_5.country_day__country, subq_18.country_day__country) = subq_25.country_day__country
  FULL OUTER JOIN (
    SELECT
      COALESCE(subq_32.country_day__country, cm_12_cte.country_day__country) AS country_day__country
      , MAX(subq_32.rain_gear_revenue_on_rainy_days_eur) AS rain_gear_revenue_on_rainy_days_eur
      , MAX(cm_12_cte.rainy_days) AS rainy_days
    FROM (
      SELECT
        country_day__country
        , SUM(rain_gear_revenue_on_rainy_days_eur) AS rain_gear_revenue_on_rainy_days_eur
      FROM (
        SELECT
          country_day__country
          , country_day__is_rainy_day
          , __rain_gear_revenue_on_rainy_days_eur AS rain_gear_revenue_on_rainy_days_eur
        FROM sma_10002_cte
      ) subq_28
      WHERE country_day__is_rainy_day
      GROUP BY
        country_day__country
    ) subq_32
    FULL OUTER JOIN
      cm_12_cte
    ON
      subq_32.country_day__country = cm_12_cte.country_day__country
    GROUP BY
      COALESCE(subq_32.country_day__country, cm_12_cte.country_day__country)
  ) subq_34
  ON
    COALESCE(subq_5.country_day__country, subq_18.country_day__country, subq_25.country_day__country) = subq_34.country_day__country
  GROUP BY
    COALESCE(subq_5.country_day__country, subq_18.country_day__country, subq_25.country_day__country, subq_34.country_day__country)
  ORDER BY country_day__country
) AS metricflow
ORDER BY country_day__country
