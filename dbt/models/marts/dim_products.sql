with products as (

    select * from {{ ref('stg_noordkust__products') }}

),

final as (

    select
        product_id,
        sku,
        product_name,
        category,
        {{ cents_to_eur('list_price_cents') }} as list_price_eur,
        is_active,
        created_at
    from products

)

select * from final
