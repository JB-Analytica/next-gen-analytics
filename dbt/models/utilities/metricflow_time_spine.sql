{{ config(materialized='table') }}

{#- MetricFlow's daily time spine (dbt >= 1.9 convention: a model plus a `time_spine` block in its
    YAML). Wide enough to cover the synthetic history and a few years either side. -#}

with days as (

    select cast(unnest(generate_series(date '2024-01-01', date '2028-12-31', interval 1 day)) as date)
        as date_day

)

select * from days
