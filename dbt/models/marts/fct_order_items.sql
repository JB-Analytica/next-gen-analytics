with items as (

    select * from {{ ref('int_order_items__priced') }}

),

products as (

    select product_id, category from {{ ref('dim_products') }}

),

final as (

    select
        items.order_item_id,
        items.order_id,
        items.product_id,
        products.category as product_category,
        items.customer_id,
        items.ordered_at,
        items.order_date,
        items.order_status,
        items.currency,
        items.shipping_country_code,
        items.quantity,
        {{ cents_to_eur('items.unit_price_minor', 'items.fx_rate') }} as unit_price_eur,
        {{ cents_to_eur('items.gross_minor', 'items.fx_rate') }} as gross_amount_eur,
        {{ cents_to_eur('items.discount_minor', 'items.fx_rate') }} as discount_eur,
        {{ cents_to_eur('items.net_minor', 'items.fx_rate') }} as net_amount_eur,
        {{ cents_to_eur('items.realised_net_minor', 'items.fx_rate') }} as realised_net_amount_eur,
        items.is_cancelled,
        items.is_returned,
        items.sold_quantity,
        items.returned_quantity
    from items
    inner join products on items.product_id = products.product_id

)

select * from final
