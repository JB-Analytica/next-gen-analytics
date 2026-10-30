with days as (

    select date_day, is_weekend from {{ ref('dim_date') }}

),

countries as (

    select distinct country_code from {{ ref('dim_customers') }}

),

order_totals as (

    select
        shipping_country_code as country_code,
        order_date as date_day,
        count(*) as orders_placed,
        count(*) filter (where not is_cancelled) as orders,
        sum(units) filter (where not is_cancelled) as units,
        sum(net_amount_eur) as booked_net_revenue_eur,
        sum(realised_net_amount_eur) as realised_net_revenue_eur
    from {{ ref('fct_orders') }}
    group by shipping_country_code, order_date

),

rain_gear as (

    select
        items.shipping_country_code as country_code,
        items.order_date as date_day,
        sum(items.sold_quantity) as rain_gear_units,
        sum(items.realised_net_amount_eur) as rain_gear_realised_net_revenue_eur
    from {{ ref('fct_order_items') }} as items
    inner join {{ ref('dim_products') }} as products on items.product_id = products.product_id
    where products.category = 'rain_gear'
    group by items.shipping_country_code, items.order_date

),

weather as (

    select * from {{ ref('stg_openmeteo__daily_weather') }}

),

holidays as (

    select * from {{ ref('int_holidays__by_country_date') }} where is_national

),

final as (

    select
        countries.country_code || '-' || cast(days.date_day as varchar) as country_day_id,
        countries.country_code,
        days.date_day,
        days.is_weekend,
        coalesce(order_totals.orders_placed, 0) as orders_placed,
        coalesce(order_totals.orders, 0) as orders,
        cast(coalesce(order_totals.units, 0) as bigint) as units,
        coalesce(order_totals.booked_net_revenue_eur, 0) as booked_net_revenue_eur,
        coalesce(order_totals.realised_net_revenue_eur, 0) as realised_net_revenue_eur,
        cast(coalesce(rain_gear.rain_gear_units, 0) as bigint) as rain_gear_units,
        coalesce(rain_gear.rain_gear_realised_net_revenue_eur, 0)
            as rain_gear_realised_net_revenue_eur,
        weather.rain_mm,
        weather.precipitation_mm,
        weather.temperature_mean_c,
        weather.temperature_max_c,
        weather.sunshine_hours,
        coalesce(weather.rain_mm >= {{ var('rainy_day_threshold_mm') }}, false) as is_rainy_day,
        holidays.country_code is not null as is_holiday,
        holidays.holiday_name
    from days
    cross join countries
    left join order_totals
        on countries.country_code = order_totals.country_code
        and days.date_day = order_totals.date_day
    left join rain_gear
        on countries.country_code = rain_gear.country_code
        and days.date_day = rain_gear.date_day
    left join weather
        on countries.country_code = weather.country_code
        and days.date_day = weather.weather_date
    left join holidays
        on countries.country_code = holidays.country_code
        and days.date_day = holidays.holiday_date

)

select * from final
