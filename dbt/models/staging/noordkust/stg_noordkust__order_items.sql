with source as (

    select * from {{ source('noordkust', 'order_items') }}

),

renamed as (

    select
        id as order_item_id,
        order_id,
        product_id,
        quantity,
        unit_price_minor,
        discount_minor,
        created_at,
        _dlt_load_id as dlt_load_id
    from source

)

select * from renamed
