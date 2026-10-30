with order_items as (

    select * from {{ ref('stg_noordkust__order_items') }}

),

orders as (

    select * from {{ ref('stg_noordkust__orders') }}

),

fx as (

    select * from {{ ref('int_orders__fx_rates') }}

),

returned as (

    select * from {{ ref('int_order_items__returned') }}

),

priced as (

    select
        order_items.order_item_id,
        order_items.order_id,
        order_items.product_id,
        orders.customer_id,
        orders.ordered_at,
        cast(orders.ordered_at as date) as order_date,
        orders.order_status,
        orders.currency,
        orders.shipping_country_code,
        fx.fx_rate,
        order_items.quantity,
        order_items.unit_price_minor,
        order_items.discount_minor,
        order_items.quantity * order_items.unit_price_minor as gross_minor,
        order_items.quantity * order_items.unit_price_minor - order_items.discount_minor
            as net_minor,
        orders.order_status = 'cancelled' as is_cancelled,
        returned.order_item_id is not null as is_returned,
        returned.first_returned_at
    from order_items
    inner join orders on order_items.order_id = orders.order_id
    inner join fx on order_items.order_id = fx.order_id
    left join returned on order_items.order_item_id = returned.order_item_id

),

final as (

    select
        *,
        -- Realised = not cancelled and not returned. Minor units, order currency.
        case when is_cancelled or is_returned then 0 else net_minor end as realised_net_minor,
        case when is_cancelled then 0 else quantity end as sold_quantity,
        case when is_returned and not is_cancelled then quantity else 0 end as returned_quantity
    from priced

)

select * from final
