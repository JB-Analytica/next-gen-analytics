with orders as (

    select * from {{ ref('stg_noordkust__orders') }}

),

order_money as (

    select * from {{ ref('int_orders__items_aggregated') }}

),

fx as (

    select * from {{ ref('int_orders__fx_rates') }}

),

final as (

    select
        orders.order_id,
        orders.customer_id,
        orders.ordered_at,
        cast(orders.ordered_at as date) as order_date,
        orders.order_status,
        orders.currency,
        fx.fx_rate,
        fx.fx_rate_date,
        orders.shipping_country_code,
        orders.shipped_at,
        orders.delivered_at,
        coalesce(order_money.line_item_count, 0) as line_item_count,
        cast(coalesce(order_money.units, 0) as bigint) as units,
        {{ cents_to_eur('coalesce(order_money.gross_minor, 0)', 'fx.fx_rate') }}
            as gross_amount_eur,
        {{ cents_to_eur('coalesce(order_money.discount_minor, 0)', 'fx.fx_rate') }}
            as discount_eur,
        {{ cents_to_eur('coalesce(order_money.net_minor, 0)', 'fx.fx_rate') }}
            as net_amount_eur,
        {{ cents_to_eur(
            "case when orders.order_status = 'cancelled' then 0
                  else coalesce(order_money.realised_net_minor, 0) end",
            'fx.fx_rate'
        ) }} as realised_net_amount_eur,
        {{ cents_to_eur('orders.shipping_minor', 'fx.fx_rate') }} as shipping_eur,
        {{ cents_to_eur('orders.subtotal_minor + orders.shipping_minor', 'fx.fx_rate') }}
            as total_amount_eur,
        orders.order_status = 'cancelled' as is_cancelled,
        orders.order_status = 'delivered' as is_delivered,
        coalesce(order_money.has_return, false) as has_return,
        case
            when orders.order_status in ('shipped', 'delivered') and orders.shipped_at is not null
                then date_diff('hour', orders.ordered_at, orders.shipped_at) / 24.0
        end as days_to_ship
    from orders
    inner join fx on orders.order_id = fx.order_id
    left join order_money on orders.order_id = order_money.order_id

)

select * from final
