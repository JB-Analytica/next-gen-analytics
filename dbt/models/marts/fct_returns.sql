with returns as (

    select * from {{ ref('stg_noordkust__returns') }}

),

items as (

    select * from {{ ref('int_order_items__priced') }}

),

final as (

    select
        returns.return_id,
        returns.order_item_id,
        items.order_id,
        items.customer_id,
        items.product_id,
        items.shipping_country_code,
        items.currency,
        returns.returned_at,
        cast(returns.returned_at as date) as return_date,
        returns.return_reason,
        items.quantity,
        {{ cents_to_eur('items.net_minor', 'items.fx_rate') }} as refund_amount_eur,
        date_diff('hour', items.ordered_at, returns.returned_at) / 24.0 as days_to_return
    from returns
    inner join items on returns.order_item_id = items.order_item_id

)

select * from final
