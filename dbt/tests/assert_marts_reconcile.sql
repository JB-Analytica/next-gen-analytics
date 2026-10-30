{#- The marts must agree with each other on money.

    Each check compares two numbers computed independently by different models from the same
    underlying minor units, so a uniformly wrong column cannot pass by being self-consistent.

    Euros are rounded to two decimals once per row. An order converts its summed minor units
    while the lines convert one by one, so with a non-trivial exchange rate the two can differ
    by up to half a cent per line. The tolerance is therefore half a cent per line plus half a
    cent; for EUR orders (rate 1) the difference is exactly zero. The exact reconciliation,
    in minor units, is assert_order_totals_match_lines.sql. -#}

with items_per_order as (

    select
        order_id,
        count(*) as line_count,
        sum(net_amount_eur) as booked_eur,
        sum(realised_net_amount_eur) as realised_eur
    from {{ ref('fct_order_items') }}
    group by order_id

),

orders_vs_items as (

    select
        'fct_orders vs fct_order_items (booked)' as check_name,
        cast(o.order_id as varchar) as row_key,
        o.net_amount_eur as left_value,
        coalesce(i.booked_eur, 0) as right_value,
        0.005 * (coalesce(i.line_count, 0) + 1) as tolerance
    from {{ ref('fct_orders') }} as o
    left join items_per_order as i on o.order_id = i.order_id

    union all

    select
        'fct_orders vs fct_order_items (realised)',
        cast(o.order_id as varchar),
        o.realised_net_amount_eur,
        coalesce(i.realised_eur, 0),
        0.005 * (coalesce(i.line_count, 0) + 1)
    from {{ ref('fct_orders') }} as o
    left join items_per_order as i on o.order_id = i.order_id

),

-- Daily mart against the orders it summarises, over the whole window: no order lost or
-- double counted when rolled up to country x day.
daily_vs_orders as (

    select
        'fct_daily_country_sales vs fct_orders (realised)' as check_name,
        'all' as row_key,
        (select sum(realised_net_revenue_eur) from {{ ref('fct_daily_country_sales') }})
            as left_value,
        (select sum(realised_net_amount_eur) from {{ ref('fct_orders') }}) as right_value,
        0.005 as tolerance

    union all

    select
        'fct_daily_country_sales vs fct_orders (orders)',
        'all',
        (select sum(orders_placed) from {{ ref('fct_daily_country_sales') }}),
        (select count(*) from {{ ref('fct_orders') }}),
        0

    union all

    select
        'fct_daily_country_sales vs fct_order_items (rain gear)',
        'all',
        (select sum(rain_gear_realised_net_revenue_eur) from {{ ref('fct_daily_country_sales') }}),
        (
            select sum(i.realised_net_amount_eur)
            from {{ ref('fct_order_items') }} as i
            inner join {{ ref('dim_products') }} as p on i.product_id = p.product_id
            where p.category = 'rain_gear'
        ),
        0.005

),

customers_vs_orders as (

    select
        'dim_customers vs fct_orders (realised)' as check_name,
        'all' as row_key,
        (select sum(lifetime_realised_net_revenue_eur) from {{ ref('dim_customers') }})
            as left_value,
        (select sum(realised_net_amount_eur) from {{ ref('fct_orders') }}) as right_value,
        0.005 as tolerance

),

all_checks as (

    select * from orders_vs_items
    union all
    select * from daily_vs_orders
    union all
    select * from customers_vs_orders

)

select *
from all_checks
where abs(left_value - right_value) > tolerance
