with bounds as (

    select
        least(
            (select min(order_date) from {{ ref('fct_orders') }}),
            (select min(weather_date) from {{ ref('stg_openmeteo__daily_weather') }})
        ) as first_day,
        greatest(
            (select max(order_date) from {{ ref('fct_orders') }}),
            (select max(weather_date) from {{ ref('stg_openmeteo__daily_weather') }})
        ) as last_day

),

final as (

    select
        spine.date_day,
        extract(year from spine.date_day) as year_number,
        extract(quarter from spine.date_day) as quarter_number,
        extract(month from spine.date_day) as month_number,
        cast(date_trunc('month', spine.date_day) as date) as month_start_date,
        cast(date_trunc('week', spine.date_day) as date) as week_start_date,
        dayname(spine.date_day) as day_name,
        extract(isodow from spine.date_day) as iso_day_of_week,
        extract(isodow from spine.date_day) >= 6 as is_weekend
    from {{ ref('metricflow_time_spine') }} as spine
    cross join bounds
    where spine.date_day between bounds.first_day and bounds.last_day

)

select * from final
